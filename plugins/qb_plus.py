from logging import log
from loguru import logger

from flexget import plugin
from flexget.event import event
import qbittorrentapi
import time
import requests
from pyquery import PyQuery as pq
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36'

logger = logger.bind(name='qb_plus')

class FilterQbplus:
    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': {'type': 'string'},
            'task_type': {'type': 'string'},
            'task_del_less_than': {'type': 'integer'},
            'task_del_hr_list': {
                'type': 'array',
                'items': {'type': 'object'},
                'properties': {
                    'tags': {'type': 'string'},
                    'hr_hours': {'type': 'integer'},
                }
            },
            'task_add_category_max': {'type': 'integer'},
            'task_add_tags_max': {'type': 'integer'},
            'task_add_tags': {'type': 'string'},
            'task_add_remember': {'type': 'boolean', 'default': False},
        }
    }

    client = None

    def login(self, config):
        if self.client:
            return

        self.client = qbittorrentapi.Client(host=config.get('url'), username=config.get('username'), password=config.get('password'))
        try:
            self.client.auth_log_in()
        except qbittorrentapi.LoginFailed as e:
            logger.error(e)
        finally:
            logger.info("app version: {}".format(self.client.app_version()))
            
    def on_task_start(self, task, config):
        logger.debug("config:{}".format(config))
        #delete some torrent when free hdd size is less than some value
        if config.get('task_type') == "del":
            now = int(time.time())
            self.login(config)

            #delete stalled
            if config.get('stalled_hours'):
                torrents = self.client.torrents_info(status_filter='stalled_downloading', category=config.get('category'), reverse=False)
                for t in torrents:
                    if now - t['added_on'] > config.get('stalled_hours') * 3600:
                        logger.info('torrent {} will be deleted because it stall too long {:.02f}'.format(t['name'], (now - t['added_on'])/ 3600))
                        self.client.torrents_delete(True, t['hash'])
                    else:
                        logger.info('torrent {} stalled {:.02f} hours'.format(t['name'], (now - t['added_on'])/ 3600))

            #free space
            free_space_on_disk = self.client.sync_maindata()['server_state']['free_space_on_disk']
            if (free_space_on_disk < config.get('task_del_less_than')):
                logger.info("disk free {} less than task_del_less_than({}), will delete some torrents".format(free_space_on_disk, config.get('task_del_less_than')))
                torrents = self.client.torrents_info(status_filter='completed', category=config.get('category'), sort='completion_on', reverse=False)
                del_torrent = True
                for t in torrents:
                    del_torrent = True
                    if free_space_on_disk < config.get('task_del_less_than'):
                        for hr in config.get('task_del_hr_list'):
                            if hr['tags'] in t['tags']:
                                logger.info('seeding time {}'.format(t['seeding_time']))
                                if t['seeding_time'] < hr['hr_hours'] * 3600:
                                    logger.info('torrent {} keep for H&R, seed time {:.02f} < need seed time {}'.format(t['name'], (t['seeding_time']) / 3600, hr['hr_hours']))
                                    del_torrent = False
                                else:
                                    logger.info('torrent {} can be deleted, seed time {:.02f} >= need seed time {}'.format(t['name'], (t['seeding_time']) / 3600, hr['hr_hours']))

                        if del_torrent:
                            logger.info("delete torrent {} size {}.".format(t['name'], t['total_size']))
                            self.client.torrents_delete(True, t['hash'])
                            free_space_on_disk += int(t['total_size'])
                    else:
                        break
            



    def check_hddolby_hr(self, config, url):
        headers = {
            'User-Agent': UA,
            'referer': 'https://www.hddolby.com/torrents.php',
            'cookie': config.get('cookie')
        }

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            pqc = pq(response.text)
            if len(pqc.find('h1#top > .hitandrun')) == 1:
                return True

        return False

    def on_task_filter(self, task, config):
        if config.get('task_type') == "add":
            if not config.get('task_add_category_max') and not config.get('task_add_tags_max'):
                logger.error("need less one of task_add_category_max and task_add_tags_max")
                return
            
            self.login(config)
            torrents = self.client.torrents_info(status_filter='downloading', category=config.get('category'))
            add_count = len(task.entries)
            logger.info("start: find {} torrents".format(add_count))

            if config.get('task_add_category_max'):
                category_count = len(torrents)
                logger.info("category: get {} downloading torrents, max downloading is {}".format(category_count, config.get('task_add_category_max')))
                if add_count > config.get('task_add_category_max') - category_count:
                    add_count = config.get('task_add_category_max') - category_count
                logger.info("category: will add {} torrents".format(add_count))

            if config.get('task_add_tags_max'):
                tags_count = 0
                for t in torrents:
                    if config.get('tags') in t['tags']:
                        tags_count += 1
                logger.info("tags: get {} downloading torrents, max downloading is {}".format(tags_count, config.get('task_add_tags_max')))
                if add_count > config.get('task_add_tags_max') - tags_count:
                    add_count = config.get('task_add_tags_max') - tags_count
                logger.info("tags: will add {} torrents".format(add_count))

            add_count = 0 if add_count < 0 else add_count
            logger.info("will add {} torrents in {} torrents".format(add_count, len(task.entries)))
            count = 0
            for entry in task.entries:
                if count >= add_count:
                    entry.reject(reason='only add {} torrents'.format(add_count), remember=config.get('task_add_remember'))
                count += 1

    def on_task_output(self, task, config):
        if config.get('task_type') == "add":
            self.login(config)
            for entry in task.entries:
                tags = config.get('tags')
                if config.get('hr_test_string_in_url') and config.get('hr_tag') and \
                    config.get('cookie') and config.get('hr_check_url') and config.get('hr_sitename'):
                    if config.get('hr_test_string_in_url') in entry['url']:
                        id = entry['url'].split("?")[1].split('&')[0].split('=')[1]
                        info_url = config.get('hr_check_url').format(id)
                        try:
                            class_method = getattr(self, "check_{}_hr".format(config.get('hr_sitename')))
                        except:
                            class_method = None
                        if class_method and class_method(config, info_url):
                            tags = [config.get('tags'), config.get('hr_tag')]
                self.client.torrents_add(urls=entry['url'], category=config.get('category'), tags=tags)
                logger.debug('Added {} to qBittorrent, tags: {}', entry['title'], tags)

@event('plugin.register')
def register_plugin():
    plugin.register(FilterQbplus, 'qb_plus', api_ver=2)

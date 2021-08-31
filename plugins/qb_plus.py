from loguru import logger

from flexget import plugin
from flexget.event import event
import qbittorrentapi

logger = logger.bind(name='qb_plus')

class FilterQbplus:
    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'max_downloading': {'type': 'integer'},
            'category': {'type': 'string'},
            'tags': {'type': 'string'},
            'delete_less_than': {'type': 'integer'},
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
        self.login(config)
        free_space_on_disk = self.client.sync_maindata()['server_state']['free_space_on_disk']
        #delete some torrent when free hdd size is less than some value
        if (free_space_on_disk < config.get('delete_less_than')):
            logger.info("disk free {} less than delete_less_than({}), will delete some torrents".format(free_space_on_disk, config.get('delete_less_than')))
            torrents = self.client.torrents_info(status_filter='completed', category=config.get('category'), sort='completion_on', reverse=False)
            for t in torrents:
                if free_space_on_disk < config.get('delete_less_than'):
                    logger.info("delete torrent {} size {}".format(t['name'], t['total_size']))
                    self.client.torrents_delete(True, t['hash'])
                    free_space_on_disk += int(t['total_size'])
                else:
                    break

    def on_task_filter(self, task, config):
        torrents = self.client.torrents_info(status_filter='downloading', category=config.get('category'))
        logger.info("get {} downloading torrents, max downloading is {}".format(len(torrents), config.get('max_downloading')))
        total_count = len(task.entries) if config.get('max_downloading') - len(torrents) > len(task.entries) else config.get('max_downloading') - len(torrents)
        total_count = 0 if total_count < 0 else total_count
        logger.info("will add {} torrents in {} torrents".format(total_count, len(task.entries)))
        count = 0;
        for entry in task.entries:
            if count >= total_count:
                entry.reject(reason='only add {} torrents'.format(total_count))
            count += 1

    def on_task_output(self, task, config):
        if config:
            for entry in task.entries:
                self.client.torrents_add(urls=entry['url'], category=config.get('category'), tags=config.get('tags'))
                logger.debug('Added {} to qBittorrent', entry['title'])

@event('plugin.register')
def register_plugin():
    plugin.register(FilterQbplus, 'qb_plus', api_ver=2)

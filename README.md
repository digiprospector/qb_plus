# qb_plus
a docker for qb and qb_plus flexget plugin

## qb_plus
qb_plus是一个flexget用的qbittorrent plugin
功能有
1. 限定qbittorrent的同时下载个数
2. 下载时候，设定qbittorrent的catagory和tags
3. 当硬盘不足的时候，删除下载

## 使用方法
### 生成docker container
``` shell
docker run -d \
    --name=flexget \
    -p 5050:5050 \
    -v ~/docker/flexget/data:/data \
    -v ~/docker/flexget/config:/config \
    -e FG_WEBUI_PASSWD=flexget-password \
    -e FG_LOG_LEVEL=info \
    -e FG_LOG_FILE=flexget.log \
    -e PUID=1000 \
    -e PGID=1000 \
    -e TZ=Asia/Shanghai \
    --restart unless-stopped \
    wiserain/flexget
```
### 安装依赖的python包，qbittorrent-api
``` shell
docker exec flexget pip install qbittorrent-api -i https://pypi.tuna.tsinghua.edu.cn/simple
```
### 把plugin目录和config复制到~/docker/flexget/config
config文件需要修改RSS
``` shell
cp -r plugins ~/docker/flexget/config
cp config-sample.yml ~/docker/flexget/config/config.yml
```
### restart docker
``` shell
docker restart flexget
```

## config参数
参考config-sample.yml

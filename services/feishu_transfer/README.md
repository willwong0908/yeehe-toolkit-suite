# 飞书文件传输服务

服务运行在广州主机的 `~/apps/feishu-transfer`，Compose 服务名为 `gateway`，监听回环端口 18512。HTTPS 入口为 `/feishu-transfer/`。可用 `docker compose ps` 查看进程，或请求该入口下的 `health` 检查连通性。

服务器以 yeehe 用户运行 `bin/lark-cli`，使用名为 `file-transfer` 的专用 profile。本机验证 memoQ 后从服务领取临时用户和机器人令牌，直接访问飞书。服务器保存每群的文档 ID 与并发创建租约，文件内容不经过服务器。

首次配置时用 CLI 的 `--app-secret-stdin` 传入密钥。更换传输账号或用户授权需要续期时，在该目录运行：

```sh
bin/lark-cli --profile file-transfer auth login --domain all
bin/lark-cli --profile file-transfer auth status --verify
```

应用身份另需飞书的机器人发消息和上传资源权限。机器人和用户的应用必须与 `feishu-transfer.json` 中的 `bot_app_id` 一致。服务需要访问公司 memoQ 服务器及飞书开放平台。服务用 memoQ 令牌验证访问，只短时缓存令牌指纹。

部署时将本目录的 Dockerfile、.dockerignore、compose.yaml 、server.py 和 direct_auth.py 放入服务目录，提供对应平台的官方 CLI 到 `bin/lark-cli`，创建可由容器用户写入的 `data` 目录，运行 `docker compose up -d --build`。群与文档的对应关系保存在 data 中，请保留此目录。发送回执在客户端保存。首次安装现有 HTTPS 站点的路由，可由管理员检查并运行同目录的 `install_route.py`。

客户端构建需要在仓库根目录放置已被 Git 忽略的 `feishu-transfer.json` 和 `feishu-transfer-ca.pem`。JSON 只含 `bot_app_id` 和 `gateway_url`，PEM 为公司 HTTPS 服务的公开证书。构建脚本将两者打入程序。飞书应用密钥及用户授权数据由服务器上的 CLI 管理。

# Nginx 子路径部署

当前服务器入口是 `https://47.98.54.166/voicechat/`，使用现有的 Nginx 443 HTTPS 监听。后端由 `voicechatassistant.service` 管理，单进程监听 `127.0.0.1:8898`。8888 已用于其他服务，不应占用；5188 不再需要监听或开放。

在仓库根目录构建：

```sh
cd frontend
npm run build:cloud
```

将 `frontend/dist-cloud/` 的构建结果发布到 `/var/www/voicechat/`。`frontend/src/utils/apiUrl.js` 使用 Vite 的 `BASE_URL` 统一生成登录、HTTP、流式请求、附件和 WebSocket 的 API 路径，避免请求落到同域的其他应用。

Nginx 的 `/etc/nginx/conf.d/serverbox-monitor.conf` 在对应的 443 server 中引入 `/etc/nginx/snippets/voicechatassistant-path.conf`：

- `/voicechat/api/` 反向代理到 `http://127.0.0.1:8898/api/`，保持 Host、HTTPS 协议和 WebSocket 升级头，关闭代理缓冲。
- Cookie 的 Path 重写为 `/voicechat/`，登录与退出使用同一路径。
- `/voicechat/` 从 `/var/www` 提供前端文件并支持单页应用回退。

修改配置后先执行 `nginx -t`，通过后使用 `systemctl reload nginx` 平滑加载。仅修改前端及 Nginx 时不需要重启后端。

账号是 `chenbo` 和 `chenshuai`，初始密码与账号名相同。两个账号应分别验证登录、身份、会话接口及退出；未登录访问 API 应返回 401。模型密钥属于每个用户的独立配置，部署不会将一个用户的凭据复制给另一个用户。

本地使用 `npm run build`，输出到 `frontend/dist/`，由后端根路径提供页面（默认 `http://localhost:8888/`）。云端构建独立输出，避免 `/voicechat/assets/` 被本地根路径服务误用。运行 `./start.sh` 时也可使用启动日志中的 5188 开发页面地址（启用证书时为 HTTPS）。

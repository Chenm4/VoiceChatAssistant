# 局域网 HTTPS

窗口截图和麦克风属于浏览器的安全能力。通过局域网 IP 访问时，必须使用可信 HTTPS，普通 `http://局域网IP` 无法调用这些能力。

## 服务端配置（macOS）

```bash
brew install mkcert
./setup_lan_https.sh
./start.sh
```

脚本会为 `localhost`、当前主机名和当前局域网 IPv4 地址生成证书。`start.sh` 检测到 `.certs/lan-cert.pem` 后会自动启用 HTTPS。

## 其他设备信任证书

把服务端生成的 `.certs/rootCA.pem` 复制到需要访问项目的设备，并安装为“受信任的根证书”。不要复制或分享 mkcert CA 目录中的 `rootCA-key.pem`。

随后在其他设备访问脚本输出的地址，例如：

```text
https://10.19.244.12:5188
```

如果 Mac 的局域网 IP 发生变化，请重新运行 `./setup_lan_https.sh` 并使用新的地址。

## 自定义证书

也可以通过环境变量提供已有证书：

```bash
FRONTEND_HTTPS_CERT=/absolute/path/cert.pem \
FRONTEND_HTTPS_KEY=/absolute/path/key.pem \
./start.sh
```

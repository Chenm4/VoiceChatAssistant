#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="$PROJECT_DIR/.certs"

if command -v mkcert >/dev/null 2>&1; then
    MKCERT_BIN="$(command -v mkcert)"
elif [ -x "$PROJECT_DIR/.tools/mkcert" ]; then
    MKCERT_BIN="$PROJECT_DIR/.tools/mkcert"
else
    echo "❌ 未安装 mkcert"
    echo "macOS: brew install mkcert"
    echo "或安装到项目目录: GOBIN=$PROJECT_DIR/.tools go install filippo.io/mkcert@v1.4.4"
    echo "安装后重新运行: ./setup_lan_https.sh"
    exit 1
fi

LAN_IP="${LAN_IP:-$(ifconfig | awk '/^[a-z0-9]+:/{iface=$1} /inet / && $2 != "127.0.0.1" && $2 !~ /^198\.18\./ && iface !~ /^utun/ {print $2; exit}')}"
LOCAL_HOSTNAME="$(hostname)"

if [ -z "$LAN_IP" ]; then
    echo "❌ 未找到局域网 IPv4 地址，可手动指定："
    echo "LAN_IP=192.168.1.10 ./setup_lan_https.sh"
    exit 1
fi

mkdir -p "$CERT_DIR"

echo "🔐 安装/确认本机开发根证书..."
"$MKCERT_BIN" -install

echo "📜 为 localhost、$LOCAL_HOSTNAME 和 $LAN_IP 生成证书..."
"$MKCERT_BIN" \
    -cert-file "$CERT_DIR/lan-cert.pem" \
    -key-file "$CERT_DIR/lan-key.pem" \
    localhost 127.0.0.1 ::1 "$LOCAL_HOSTNAME" "$LAN_IP"

cp "$("$MKCERT_BIN" -CAROOT)/rootCA.pem" "$CERT_DIR/rootCA.pem"

echo ""
echo "✅ 局域网 HTTPS 已配置"
echo "📱 启动后访问: https://$LAN_IP:5188"
echo "📄 其他设备需安装并信任: $CERT_DIR/rootCA.pem"
echo "🔁 IP 变化后请重新运行本脚本"

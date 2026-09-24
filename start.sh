#!/bin/bash

FRONTEND_PORT=${FRONTEND_PORT:-5188}
PYTHON_BIN=${PYTHON_BIN:-python3}
BACKEND_PID=""
FRONTEND_PID=""

if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN="$(pwd)/.venv/bin/python"
fi

echo "🚀 启动 ChatGPT Web 应用"
echo "================================"
echo ""

# 检查是否在项目根目录
if [ ! -d "frontend" ] || [ ! -d "backend" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

if [ -f ".env" ]; then
    echo "🔐 加载本地环境变量: .env"
    set -a
    source .env
    set +a
fi

if [ -f ".env.local" ]; then
    echo "🔐 加载本地环境变量: .env.local"
    set -a
    source .env.local
    set +a
fi

# 默认重启：清理占用本应用端口的旧服务，避免误把旧后端当作新进程。
stop_port_listener() {
    local port="$1"
    local pids pid
    pids=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "🔄 端口 $port 已被占用，强制停止旧服务: $pids"
        for pid in $pids; do
            case "$pid" in
                *[!0-9]*|'') continue ;;
            esac
            kill -9 "$pid" 2>/dev/null || true
        done
    fi
    for attempt in 1 2 3 4 5; do
        if ! lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | grep -q .; then
            return
        fi
        sleep 0.2
    done
    echo "❌ 无法释放端口 $port"
    exit 1
}

cleanup() {
    [ -z "$BACKEND_PID" ] || kill "$BACKEND_PID" 2>/dev/null || true
    [ -z "$FRONTEND_PID" ] || kill "$FRONTEND_PID" 2>/dev/null || true
}

if ! command -v lsof >/dev/null 2>&1; then
    echo "❌ 缺少 lsof，无法检查并重启已有服务"
    exit 1
fi

stop_port_listener 8888
stop_port_listener "$FRONTEND_PORT"
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

CERT_DIR="$(pwd)/.certs"
if [ -z "$FRONTEND_HTTPS_CERT" ] && [ -z "$FRONTEND_HTTPS_KEY" ]; then
    if [ -f "$CERT_DIR/lan-cert.pem" ] && [ -f "$CERT_DIR/lan-key.pem" ]; then
        export FRONTEND_HTTPS_CERT="$CERT_DIR/lan-cert.pem"
        export FRONTEND_HTTPS_KEY="$CERT_DIR/lan-key.pem"
    fi
fi

FRONTEND_SCHEME="http"
if [ -n "$FRONTEND_HTTPS_CERT" ] && [ -n "$FRONTEND_HTTPS_KEY" ]; then
    FRONTEND_SCHEME="https"
    echo "🔒 已启用前端 HTTPS"
fi

# 启动后端
echo "📡 启动后端服务..."
$PYTHON_BIN -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 &
BACKEND_PID=$!

# 等待后端启动
echo "⏳ 等待后端启动..."
sleep 3

# 检查后端是否运行
if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! curl -sf http://localhost:8888/health > /dev/null; then
    echo "❌ 后端启动失败"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo "✅ 后端启动成功"
echo ""

# 启动前端
echo "🎨 启动前端服务..."
# 检查是否安装了依赖
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 安装前端依赖..."
    (cd frontend && npm install) || exit 1
fi

(
    cd frontend || exit 1
    FRONTEND_PORT="$FRONTEND_PORT" exec ./node_modules/.bin/vite --host 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if curl -skf "$FRONTEND_SCHEME://localhost:$FRONTEND_PORT/" > /dev/null; then
        break
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "❌ 前端启动失败"
        exit 1
    fi
    sleep 1
done

if ! curl -skf "$FRONTEND_SCHEME://localhost:$FRONTEND_PORT/" > /dev/null; then
    echo "❌ 前端启动超时"
    exit 1
fi

echo ""
echo "================================"
echo "✅ 应用启动成功！"
echo "================================"
echo ""
echo "📱 前端地址: $FRONTEND_SCHEME://localhost:$FRONTEND_PORT"
echo "📡 后端地址: http://localhost:8888"
echo "📚 API 文档: http://localhost:8888/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 等待 Ctrl+C
# 保持脚本运行
wait

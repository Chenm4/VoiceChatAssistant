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

# 默认停止占用端口的旧服务，避免新进程连接到旧实例。
stop_port_listener() {
    local port="$1"
    local pids pid
    pids=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "🔄 端口 $port 已被占用，停止旧服务: $pids"
        for pid in $pids; do
            case "$pid" in
                *[!0-9]*|'') continue ;;
            esac
            kill "$pid" 2>/dev/null || true
        done
    fi
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        if ! lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | grep -q .; then
            return
        fi
        sleep 0.2
    done
    # A process ignoring SIGTERM must be stopped before binding the same port.
    pids=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    for pid in $pids; do
        case "$pid" in
            *[!0-9]*|'') continue ;;
        esac
        kill -9 "$pid" 2>/dev/null || true
    done
    if ! lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | grep -q .; then
        return
    fi
    echo "❌ 无法释放端口 $port"
    exit 1
}

cleanup() {
    [ -z "$BACKEND_PID" ] || kill "$BACKEND_PID" 2>/dev/null || true
    [ -z "$FRONTEND_PID" ] || kill "$FRONTEND_PID" 2>/dev/null || true
}

# 启动耗时受依赖加载影响；本机探测不应经过系统代理或 IPv6 localhost。
wait_for_service() {
    local pid="$1" url="$2" label="$3" attempt
    for attempt in {1..30}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "❌ $label 进程已退出，请查看上方错误日志"
            return 1
        fi
        if curl --noproxy '*' --connect-timeout 1 --max-time 2 -skf "$url" > /dev/null; then
            return 0
        fi
        sleep 0.5
    done
    echo "❌ $label 启动超时，健康检查地址: $url"
    curl --noproxy '*' --connect-timeout 1 --max-time 2 -skfS "$url" > /dev/null
    return 1
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
wait_for_service "$BACKEND_PID" "http://127.0.0.1:8888/health" "后端" || exit 1

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

wait_for_service "$FRONTEND_PID" "$FRONTEND_SCHEME://127.0.0.1:$FRONTEND_PORT/" "前端" || exit 1

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

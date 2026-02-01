#!/bin/bash

echo "🚀 启动 ChatGPT Web 应用"
echo "================================"
echo ""

# 检查是否在项目根目录
if [ ! -d "frontend" ] || [ ! -d "backend" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 启动后端
echo "📡 启动后端服务..."
cd backend
python3 main.py &
BACKEND_PID=$!
cd ..

# 等待后端启动
echo "⏳ 等待后端启动..."
sleep 3

# 检查后端是否运行
if ! curl -s http://localhost:8888/health > /dev/null; then
    echo "❌ 后端启动失败"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo "✅ 后端启动成功"
echo ""

# 启动前端
echo "🎨 启动前端服务..."
cd frontend

# 检查是否安装了依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装前端依赖..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "================================"
echo "✅ 应用启动成功！"
echo "================================"
echo ""
echo "📱 前端地址: http://localhost:5173"
echo "📡 后端地址: http://localhost:8888"
echo "📚 API 文档: http://localhost:8888/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 等待 Ctrl+C
trap "echo ''; echo '正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

# 保持脚本运行
wait

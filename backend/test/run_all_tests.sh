#!/bin/bash

# 运行所有测试脚本

echo "=================================="
echo "  运行所有测试"
echo "=================================="

# 切换到项目根目录
cd "$(dirname "$0")/../.."

# 1. 测试配置
echo ""
echo "1/3 测试配置..."
python3 backend/test/test_config.py

# 等待用户确认
read -p "按 Enter 继续..."

# 2. 测试语音识别
echo ""
echo "2/3 测试语音识别..."
python3 backend/test/test_asr.py

# 等待用户确认
read -p "按 Enter 继续..."

# 3. 测试 API（需要先启动服务）
echo ""
echo "3/3 测试 API 接口..."
echo "注意：需要先启动后端服务（python3 backend/main.py）"
read -p "后端服务是否已启动？(y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]
then
    python3 backend/test/test_api.py
else
    echo "跳过 API 测试"
    echo "启动后端服务后，运行: python3 backend/test/test_api.py"
fi

echo ""
echo "=================================="
echo "  测试完成"
echo "=================================="

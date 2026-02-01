#!/bin/bash

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     🔍 流式输出诊断工具                                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 检查后端是否运行
echo "1️⃣ 检查后端服务..."
if curl -s http://localhost:8888/health > /dev/null; then
    echo "   ✅ 后端服务正常运行"
else
    echo "   ❌ 后端服务未运行！请先启动后端服务"
    echo "   命令: cd backend && uvicorn main:app --reload --port 8888"
    exit 1
fi
echo ""

# 测试流式输出
echo "2️⃣ 测试流式输出..."
echo "   发送测试消息：'请数数1到10'"
echo "   观察响应是否逐行输出..."
echo ""

curl -N -X POST http://localhost:8888/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "请数数1到10，每个数字单独一行"}' \
  2>/dev/null | while IFS= read -r line; do
    if [[ $line == data:* ]]; then
        # 提取 JSON 数据
        json_data="${line#data: }"
        
        # 解析 type 和 data
        type=$(echo "$json_data" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('type', ''))" 2>/dev/null)
        content=$(echo "$json_data" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('data', ''), end='')" 2>/dev/null)
        
        if [[ $type == "content" ]]; then
            # 实时输出内容（不换行）
            echo -n "$content"
        elif [[ $type == "done" ]]; then
            echo ""
            echo ""
            echo "✅ 流式输出完成！"
        elif [[ $type == "error" ]]; then
            echo ""
            echo "❌ 错误: $content"
        fi
    fi
done

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  📊 诊断说明                                               ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ 如果看到数字逐个出现 = 流式输出正常"
echo "❌ 如果等待后一次性显示 = 流式输出有问题"
echo ""
echo "💡 如果流式输出有问题，请："
echo "   1. 检查后端日志是否有 '📤 已发送 X 个chunks' 的输出"
echo "   2. 重启后端服务"
echo "   3. 清除浏览器缓存并刷新"
echo "   4. 查看浏览器控制台的详细日志"
echo ""

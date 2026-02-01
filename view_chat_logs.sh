#!/bin/bash

# 聊天消息日志查看工具
# 用于快速查看发送给模型的消息和接收到的响应

LOG_DIR="logs/chat_history"
TODAY=$(date +%Y%m%d)
LOG_FILE="${LOG_DIR}/chat_${TODAY}.log"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}        聊天消息日志查看工具${NC}"
echo -e "${BLUE}==================================================${NC}"
echo ""

# 检查日志目录是否存在
if [ ! -d "$LOG_DIR" ]; then
    echo -e "${RED}错误: 日志目录不存在: $LOG_DIR${NC}"
    echo "请先启动应用生成日志"
    exit 1
fi

# 选项菜单
echo "请选择查看选项:"
echo "1) 查看今天的日志"
echo "2) 实时监控日志（tail -f）"
echo "3) 查看最近的10次请求摘要"
echo "4) 查看最近的5次完整对话"
echo "5) 查看所有日志文件列表"
echo "6) 查看特定日期的日志"
echo ""
read -p "请输入选项 (1-6): " choice

case $choice in
    1)
        if [ -f "$LOG_FILE" ]; then
            echo -e "${GREEN}查看今天的日志: $LOG_FILE${NC}"
            echo ""
            cat "$LOG_FILE"
        else
            echo -e "${YELLOW}今天还没有日志文件: $LOG_FILE${NC}"
        fi
        ;;
    2)
        if [ -f "$LOG_FILE" ]; then
            echo -e "${GREEN}实时监控日志...（按 Ctrl+C 退出）${NC}"
            echo ""
            tail -f "$LOG_FILE"
        else
            echo -e "${YELLOW}今天还没有日志文件，创建并开始监控...${NC}"
            mkdir -p "$LOG_DIR"
            touch "$LOG_FILE"
            tail -f "$LOG_FILE"
        fi
        ;;
    3)
        if [ -f "$LOG_FILE" ]; then
            echo -e "${GREEN}最近的10次请求摘要:${NC}"
            echo ""
            grep -A 4 "📊 请求摘要" "$LOG_FILE" | tail -50
        else
            echo -e "${YELLOW}今天还没有日志文件${NC}"
        fi
        ;;
    4)
        if [ -f "$LOG_FILE" ]; then
            echo -e "${GREEN}最近的5次完整对话:${NC}"
            echo ""
            # 查找最后5个"发送请求到模型"块
            grep -B 2 -A 30 "📤 发送请求到模型" "$LOG_FILE" | tail -200
        else
            echo -e "${YELLOW}今天还没有日志文件${NC}"
        fi
        ;;
    5)
        echo -e "${GREEN}所有日志文件:${NC}"
        echo ""
        ls -lh "$LOG_DIR"
        ;;
    6)
        read -p "请输入日期 (格式: YYYYMMDD, 例如: 20260131): " date_input
        specific_log="${LOG_DIR}/chat_${date_input}.log"
        if [ -f "$specific_log" ]; then
            echo -e "${GREEN}查看日志: $specific_log${NC}"
            echo ""
            cat "$specific_log"
        else
            echo -e "${RED}日志文件不存在: $specific_log${NC}"
        fi
        ;;
    *)
        echo -e "${RED}无效选项${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}提示: 日志文件位于 $LOG_DIR${NC}"
echo -e "${BLUE}==================================================${NC}"

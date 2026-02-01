#!/bin/bash

# Backend 代码质量检查脚本
# 用于验证代码规范修复效果

echo "========================================="
echo "Backend 代码质量检查"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python3 已安装${NC}"
echo ""

# 1. 检查代码格式（使用 black）
echo "1. 检查代码格式..."
if command -v black &> /dev/null; then
    echo "   运行 black --check..."
    black --check backend/ 2>&1 | head -20
    if [ $? -eq 0 ]; then
        echo -e "   ${GREEN}✅ 代码格式符合 black 标准${NC}"
    else
        echo -e "   ${YELLOW}⚠️  代码格式需要调整，运行: black backend/${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  black 未安装，跳过检查${NC}"
    echo "   安装命令: pip install black"
fi
echo ""

# 2. 检查导入顺序（使用 isort）
echo "2. 检查导入顺序..."
if command -v isort &> /dev/null; then
    echo "   运行 isort --check-only..."
    isort --check-only backend/ 2>&1 | head -20
    if [ $? -eq 0 ]; then
        echo -e "   ${GREEN}✅ 导入顺序符合规范${NC}"
    else
        echo -e "   ${YELLOW}⚠️  导入顺序需要调整，运行: isort backend/${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  isort 未安装，跳过检查${NC}"
    echo "   安装命令: pip install isort"
fi
echo ""

# 3. 检查代码风格（使用 flake8）
echo "3. 检查代码风格..."
if command -v flake8 &> /dev/null; then
    echo "   运行 flake8..."
    flake8 backend/ --max-line-length=100 --extend-ignore=E203,W503 --count 2>&1 | tail -20
    if [ $? -eq 0 ]; then
        echo -e "   ${GREEN}✅ 代码风格符合 PEP 8${NC}"
    else
        echo -e "   ${YELLOW}⚠️  发现代码风格问题${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  flake8 未安装，跳过检查${NC}"
    echo "   安装命令: pip install flake8"
fi
echo ""

# 4. 检查类型注解（使用 mypy）
echo "4. 检查类型注解..."
if command -v mypy &> /dev/null; then
    echo "   运行 mypy..."
    mypy backend/services/ --ignore-missing-imports 2>&1 | head -20
    if [ $? -eq 0 ]; then
        echo -e "   ${GREEN}✅ 类型注解检查通过${NC}"
    else
        echo -e "   ${YELLOW}⚠️  发现类型注解问题${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  mypy 未安装，跳过检查${NC}"
    echo "   安装命令: pip install mypy"
fi
echo ""

# 5. 统计代码行数
echo "5. 代码统计..."
echo "   Python 文件数量:"
find backend/ -name "*.py" | wc -l | xargs echo "   "
echo "   总代码行数:"
find backend/ -name "*.py" -exec wc -l {} + | tail -1 | awk '{print "   " $1}'
echo "   文档字符串行数（估算）:"
grep -r '"""' backend/ --include="*.py" | wc -l | awk '{print "   " $1/2}'
echo ""

# 6. 检查是否使用 print()
echo "6. 检查是否使用 print()..."
print_count=$(grep -r "print(" backend/ --include="*.py" | grep -v "# print" | grep -v '"""' | wc -l)
if [ $print_count -eq 0 ]; then
    echo -e "   ${GREEN}✅ 未发现 print() 使用${NC}"
else
    echo -e "   ${RED}❌ 发现 $print_count 处使用 print()${NC}"
    echo "   详细位置:"
    grep -rn "print(" backend/ --include="*.py" | grep -v "# print" | grep -v '"""' | head -5
fi
echo ""

# 7. 检查全局变量
echo "7. 检查全局变量（模块级赋值）..."
echo "   主要问题文件:"
grep -rn "^[a-z_][a-z_0-9]* = " backend/ --include="*.py" | \
    grep -v "__" | \
    grep -v "def " | \
    grep -v "class " | \
    head -10
echo ""

# 总结
echo "========================================="
echo "检查完成！"
echo "========================================="
echo ""
echo "建议执行的命令:"
echo "  1. black backend/          # 格式化代码"
echo "  2. isort backend/          # 排序导入"
echo "  3. flake8 backend/         # 检查代码风格"
echo "  4. mypy backend/services/  # 检查类型注解"
echo ""
echo "安装所有工具:"
echo "  pip install black isort flake8 mypy"
echo ""

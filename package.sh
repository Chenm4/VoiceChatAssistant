#!/bin/bash

# 语音识别项目打包脚本
# 创建时间: 2026-02-01

set -e  # 遇到错误立即退出

echo "========================================="
echo "开始打包语音识别项目"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 获取当前日期时间
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PACKAGE_NAME="yuyinshibie_${TIMESTAMP}"
PACKAGE_DIR="dist/${PACKAGE_NAME}"

echo -e "${GREEN}📦 打包名称: ${PACKAGE_NAME}${NC}"
echo ""

# 1. 创建打包目录
echo "1. 创建打包目录..."
rm -rf dist
mkdir -p "${PACKAGE_DIR}"
echo -e "${GREEN}✅ 打包目录已创建: ${PACKAGE_DIR}${NC}"
echo ""

# 2. 复制后端文件
echo "2. 复制后端文件..."
cp -r backend "${PACKAGE_DIR}/"
cp config.py "${PACKAGE_DIR}/"
cp requirements.txt "${PACKAGE_DIR}/"
cp start.sh "${PACKAGE_DIR}/"
cp 启动.sh "${PACKAGE_DIR}/"
echo -e "${GREEN}✅ 后端文件已复制${NC}"
echo ""

# 3. 复制前端文件
echo "3. 复制前端文件..."
cp -r frontend "${PACKAGE_DIR}/"
echo -e "${GREEN}✅ 前端文件已复制${NC}"
echo ""

# 4. 复制文档
echo "4. 复制文档..."
mkdir -p "${PACKAGE_DIR}/docs"
cp -r docs/* "${PACKAGE_DIR}/docs/" 2>/dev/null || true
cp *.md "${PACKAGE_DIR}/" 2>/dev/null || true
echo -e "${GREEN}✅ 文档已复制${NC}"
echo ""

# 5. 复制配置和脚本
echo "5. 复制配置和脚本..."
cp check_code_quality.sh "${PACKAGE_DIR}/" 2>/dev/null || true
cp test_asr.py "${PACKAGE_DIR}/" 2>/dev/null || true
cp view_chat_logs.sh "${PACKAGE_DIR}/" 2>/dev/null || true
echo -e "${GREEN}✅ 配置和脚本已复制${NC}"
echo ""

# 6. 创建 README
echo "6. 创建 README..."
cat > "${PACKAGE_DIR}/README.md" << 'EOF'
# 语音识别对话系统

## 项目简介

这是一个基于 FastAPI + Vue 3 的语音识别对话系统，支持实时流式语音识别和多模型并行对话。

## 主要功能

- 🎤 实时流式语音识别（支持字节跳动 ASR）
- 💬 多模型并行对话
- 📝 对话历史管理
- ✏️ 消息编辑功能
- 🔄 打断和重新生成
- 📊 会话管理

## 快速开始

### 1. 安装依赖

#### 后端依赖
```bash
pip install -r requirements.txt
```

#### 前端依赖
```bash
cd frontend
npm install
```

### 2. 配置

编辑 `config.py` 文件，配置以下内容：

- OpenAI API 配置
- 字节跳动 ASR 配置
- 音频参数配置

### 3. 启动项目

#### 方式一：使用启动脚本（推荐）
```bash
./start.sh
```

或
```bash
./启动.sh
```

#### 方式二：手动启动

**启动后端**:
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端**:
```bash
cd frontend
npm run dev
```

### 4. 访问应用

打开浏览器访问: http://localhost:5173

## 项目结构

```
yuyinshibie/
├── backend/                 # 后端代码
│   ├── api/                # API 路由
│   ├── services/           # 服务层
│   └── utils/              # 工具类
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── components/    # Vue 组件
│   │   └── views/         # 页面视图
│   └── public/            # 静态资源
├── docs/                   # 文档
├── config.py              # 配置文件
├── requirements.txt       # Python 依赖
└── start.sh              # 启动脚本
```

## 技术栈

### 后端
- FastAPI
- Python 3.8+
- PyAudio
- WebSocket

### 前端
- Vue 3
- Vite
- Element Plus
- Markdown-it

## 常见问题

### 1. 麦克风权限问题

确保浏览器有麦克风访问权限。

### 2. 端口占用

如果端口被占用，可以修改：
- 后端端口：在 `start.sh` 中修改
- 前端端口：在 `frontend/vite.config.js` 中修改

### 3. 依赖安装失败

确保 Python 版本 >= 3.8，Node.js 版本 >= 16

## 更新日志

详见各个 `.md` 文档文件。

## 许可证

MIT License

## 联系方式

如有问题，请查看 docs/ 目录下的详细文档。
EOF

echo -e "${GREEN}✅ README 已创建${NC}"
echo ""

# 7. 创建 .gitignore
echo "7. 创建 .gitignore..."
cat > "${PACKAGE_DIR}/.gitignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
*.egg-info/
dist/
build/

# Node
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.pnpm-debug.log*

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Data
data/
recordings/

# Config (如果包含敏感信息)
# config.py
EOF

echo -e "${GREEN}✅ .gitignore 已创建${NC}"
echo ""

# 8. 清理不需要的文件
echo "8. 清理不需要的文件..."
find "${PACKAGE_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${PACKAGE_DIR}" -name "*.pyc" -delete 2>/dev/null || true
find "${PACKAGE_DIR}" -name ".DS_Store" -delete 2>/dev/null || true
find "${PACKAGE_DIR}" -name "node_modules" -type d -exec rm -rf {} + 2>/dev/null || true
rm -rf "${PACKAGE_DIR}/logs" 2>/dev/null || true
rm -rf "${PACKAGE_DIR}/data" 2>/dev/null || true
rm -rf "${PACKAGE_DIR}/.cursor" 2>/dev/null || true
rm -rf "${PACKAGE_DIR}/lobehub-main" 2>/dev/null || true
echo -e "${GREEN}✅ 清理完成${NC}"
echo ""

# 9. 创建压缩包
echo "9. 创建压缩包..."
cd dist
tar -czf "${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}"
ZIP_SIZE=$(du -h "${PACKAGE_NAME}.tar.gz" | cut -f1)
echo -e "${GREEN}✅ 压缩包已创建: ${PACKAGE_NAME}.tar.gz (${ZIP_SIZE})${NC}"
echo ""

# 10. 统计信息
echo "========================================="
echo "打包完成！"
echo "========================================="
echo ""
echo -e "${GREEN}📦 打包文件夹: dist/${PACKAGE_NAME}${NC}"
echo -e "${GREEN}📦 压缩包: dist/${PACKAGE_NAME}.tar.gz (${ZIP_SIZE})${NC}"
echo ""

# 统计文件数量
TOTAL_FILES=$(find "${PACKAGE_NAME}" -type f | wc -l | xargs)
PYTHON_FILES=$(find "${PACKAGE_NAME}" -name "*.py" | wc -l | xargs)
VUE_FILES=$(find "${PACKAGE_NAME}" -name "*.vue" | wc -l | xargs)

echo "📊 统计信息:"
echo "  - 总文件数: ${TOTAL_FILES}"
echo "  - Python 文件: ${PYTHON_FILES}"
echo "  - Vue 文件: ${VUE_FILES}"
echo ""

echo "📝 使用说明:"
echo "  1. 解压: tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "  2. 进入目录: cd ${PACKAGE_NAME}"
echo "  3. 查看 README.md 了解详细使用方法"
echo ""

echo -e "${GREEN}✨ 打包成功！${NC}"

# 多配置源系统 - 快速参考

## 🎯 配置文件结构

```python
# config.py
OPENAI_CONFIG = [
    {
        "name": "配置源名称",
        "api_key": "你的API Key",
        "models": ["模型1", "模型2", "模型3"],
        "base_url": "API地址"
    },
    # ... 更多配置源
]

DEFAULT_CONFIG_NAME = "默认配置源名称"
```

## 🖥️ Web 界面操作

### 查看当前配置
导航栏显示：
- 🔵 蓝色标签 = 当前配置源
- 🟢 绿色标签 = 当前模型

### 切换配置
1. 点击 **设置** 按钮
2. 选择 **配置源**
3. 选择 **模型**
4. 点击 **切换配置**

### 编辑配置源
1. 点击 **设置** → **管理配置源**
2. 找到目标配置源
3. 点击 **编辑**
4. 修改 API Key / Base URL / 模型列表
5. 点击 **保存修改**

## 🔌 API 接口

### 获取配置
```bash
curl http://localhost:8888/api/config
```

### 切换配置
```bash
curl -X POST "http://localhost:8888/api/config/switch?source_name=OpenRouter&model=google/gemini-2.5-flash"
```

### 更新配置源
```bash
curl -X POST http://localhost:8888/api/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OpenRouter",
    "api_key": "new-key",
    "models": ["model1", "model2"],
    "base_url": "https://..."
  }'
```

## 📦 预配置服务商

| 服务商 | Base URL | 特点 |
|--------|----------|------|
| **OpenRouter** | `https://openrouter.ai/api/v1` | 多模型聚合，有免费额度 |
| **OpenAI** | `https://api.openai.com/v1` | 官方 API |
| **DeepSeek** | `https://api.deepseek.com/v1` | 中文优化 |
| **本地模型** | `http://localhost:11434/v1` | Ollama 本地部署 |

## 🚀 常用命令

```bash
# 启动服务
./start.sh

# 验证配置
python3 -c "from config import OPENAI_CONFIG; print(f'配置源: {len(OPENAI_CONFIG)}')"

# 测试 API
./test_multi_config.sh

# 查看日志
tail -f backend/logs/app.log
```

## 💡 最佳实践

### ✅ 推荐做法
- 在 `config.py` 中配置所有 API Key
- 使用免费模型测试（如 `google/gemini-2.0-flash-exp:free`）
- 为不同任务使用不同模型：
  - 快速响应 → Gemini Flash
  - 高质量 → Claude Sonnet
  - 编程 → DeepSeek Coder
  - 本地 → Ollama 模型

### ❌ 避免做法
- 不要提交包含真实 API Key 的文件到 Git
- 不要频繁切换配置（会重新初始化客户端）
- 不要使用未验证的 API Key

## 🔍 故障排查

| 问题 | 解决方案 |
|------|----------|
| 配置切换无响应 | 检查浏览器控制台，刷新页面 |
| API Key 无效 | 在 Web 界面重新输入或修改 `config.py` |
| 模型不可用 | 检查模型名称拼写和服务商支持 |
| 后端启动失败 | 检查端口 8888 是否被占用 |

## 📖 文档索引

| 文档 | 用途 |
|------|------|
| `MULTI_CONFIG_GUIDE.md` | 详细使用指南 |
| `CHANGELOG_MULTI_CONFIG.md` | 更新日志 |
| `UPDATE_SUMMARY.md` | 更新总结 |
| `PROJECT_README.md` | 项目总览 |
| `QUICKSTART.md` | 快速开始 |

## 🎊 快速开始（3 步）

```bash
# 1. 编辑配置（填写 API Key）
nano config.py

# 2. 启动服务
./start.sh

# 3. 访问界面
open http://localhost:5173
```

搞定！🚀

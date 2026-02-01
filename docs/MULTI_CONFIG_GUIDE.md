# 多配置源使用指南

## 📋 概述

本系统支持配置多个 API 源，可以在不同的 AI 服务提供商之间快速切换，每个配置源支持多个模型。

## 🔧 配置文件结构

在 `config.py` 中，`OPENAI_CONFIG` 现在是一个列表，每个元素代表一个配置源：

```python
OPENAI_CONFIG = [
    {
        "name": "OpenRouter",           # 配置源名称
        "api_key": "sk-or-v1-xxx",      # API Key
        "models": [                      # 支持的模型列表
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-2.5-flash",
            "anthropic/claude-3.5-sonnet"
        ],
        "base_url": "https://openrouter.ai/api/v1"  # API 基础 URL
    },
    {
        "name": "OpenAI",
        "api_key": "",
        "models": ["gpt-4", "gpt-3.5-turbo"],
        "base_url": "https://api.openai.com/v1"
    }
]

# 默认使用的配置源
DEFAULT_CONFIG_NAME = "OpenRouter"
```

## 🎯 功能特点

### 1. **多配置源管理**
- 支持添加多个 API 服务提供商（OpenAI、OpenRouter、DeepSeek、本地模型等）
- 每个配置源独立管理 API Key、Base URL 和模型列表
- 可以在 Web 界面中查看和编辑所有配置源

### 2. **快速切换**
- 在 Web 界面中通过下拉菜单切换配置源和模型
- 切换后立即生效，无需重启服务
- 导航栏实时显示当前使用的配置源和模型

### 3. **模型列表**
- 每个配置源有独立的模型列表
- 切换配置源时自动显示对应的可用模型
- 支持在 Web 界面中编辑模型列表

## 📝 使用步骤

### 1️⃣ 配置 config.py

编辑 `/Users/hb952/code/yuyinshibie/config.py`，填写您的 API Keys：

```python
OPENAI_CONFIG = [
    {
        "name": "OpenRouter",
        "api_key": "sk-or-v1-YOUR-KEY-HERE",  # ← 填入您的 OpenRouter Key
        "models": [
            "google/gemini-2.0-flash-exp:free",
            "anthropic/claude-3.5-sonnet"
        ],
        "base_url": "https://openrouter.ai/api/v1"
    },
    {
        "name": "OpenAI",
        "api_key": "sk-YOUR-OPENAI-KEY",  # ← 填入您的 OpenAI Key
        "models": ["gpt-4", "gpt-3.5-turbo"],
        "base_url": "https://api.openai.com/v1"
    }
]
```

### 2️⃣ 启动服务

```bash
# 方式 1: 使用启动脚本（推荐）
./start.sh

# 方式 2: 手动启动
# 终端 1 - 启动后端
cd backend
uvicorn main:app --reload --port 8888

# 终端 2 - 启动前端
cd frontend
npm run dev
```

### 3️⃣ 在 Web 界面中使用

访问 `http://localhost:5173`

#### **查看当前配置**
导航栏会显示：
- 🔵 蓝色标签：当前配置源（如 "OpenRouter"）
- 🟢 绿色标签：当前模型（如 "google/gemini-2.5-flash"）

#### **切换配置**
1. 点击右上角 **"设置"** 按钮
2. 在 **"当前配置"** 区域：
   - 从 **"配置源"** 下拉菜单选择要使用的源
   - 从 **"模型"** 下拉菜单选择要使用的模型
   - 点击 **"切换配置"** 按钮
3. 切换成功后，新配置立即生效

#### **编辑配置源**
1. 在设置界面的 **"管理配置源"** 区域
2. 找到要编辑的配置源，点击 **"编辑"** 按钮
3. 修改以下内容：
   - **API Key**: 输入新的 API Key
   - **Base URL**: 修改 API 地址
   - **模型列表**: 每行一个模型名称
4. 点击 **"保存修改"** 按钮

## 🌐 支持的 API 提供商

### OpenRouter
```python
{
    "name": "OpenRouter",
    "api_key": "sk-or-v1-xxx",
    "models": [
        "google/gemini-2.0-flash-exp:free",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4-turbo"
    ],
    "base_url": "https://openrouter.ai/api/v1"
}
```

### OpenAI
```python
{
    "name": "OpenAI",
    "api_key": "sk-xxx",
    "models": [
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-3.5-turbo"
    ],
    "base_url": "https://api.openai.com/v1"
}
```

### DeepSeek
```python
{
    "name": "DeepSeek",
    "api_key": "sk-xxx",
    "models": [
        "deepseek-chat",
        "deepseek-coder"
    ],
    "base_url": "https://api.deepseek.com/v1"
}
```

### 本地模型 (Ollama)
```python
{
    "name": "本地模型",
    "api_key": "local",  # Ollama 不需要真实的 API Key
    "models": [
        "qwen2.5:latest",
        "llama3.2:latest"
    ],
    "base_url": "http://localhost:11434/v1"
}
```

## 🔄 API 接口说明

### 1. 获取配置列表
```http
GET /api/config
```

返回示例：
```json
{
  "sources": [
    {
      "name": "OpenRouter",
      "api_key": "sk-or-v1-xxx",
      "models": ["google/gemini-2.5-flash"],
      "base_url": "https://openrouter.ai/api/v1"
    }
  ],
  "current_source": "OpenRouter",
  "current_model": "google/gemini-2.5-flash"
}
```

### 2. 切换配置
```http
POST /api/config/switch?source_name=OpenRouter&model=google/gemini-2.5-flash
```

### 3. 更新配置源
```http
POST /api/config/update
Content-Type: application/json

{
  "name": "OpenRouter",
  "api_key": "new-key",
  "models": ["model1", "model2"],
  "base_url": "https://..."
}
```

## 💡 最佳实践

1. **安全性**
   - 不要将 `config.py` 提交到版本控制系统
   - 定期更换 API Keys
   - 为不同的项目使用不同的 API Keys

2. **性能优化**
   - 使用免费模型进行测试（如 `google/gemini-2.0-flash-exp:free`）
   - 生产环境使用性能更好的付费模型

3. **模型选择**
   - **快速响应**: `google/gemini-2.0-flash-exp:free`
   - **高质量**: `anthropic/claude-3.5-sonnet`
   - **编程任务**: `deepseek-coder`
   - **本地部署**: Ollama 模型

4. **成本控制**
   - OpenRouter 提供免费模型额度
   - 使用本地 Ollama 模型完全免费
   - 监控 API 使用量

## 🐛 故障排除

### 问题：切换配置后没有响应

**解决方案：**
1. 检查浏览器控制台是否有错误
2. 确认后端服务正常运行
3. 刷新页面重新加载配置

### 问题：API Key 无效

**解决方案：**
1. 在 Web 界面中重新输入 API Key
2. 或者修改 `config.py` 后重启服务
3. 验证 API Key 格式正确

### 问题：模型不可用

**解决方案：**
1. 检查模型名称拼写是否正确
2. 确认该配置源支持该模型
3. 查看服务商文档确认模型可用性

## 📚 相关文档

- [项目文档](PROJECT_README.md)
- [快速开始](QUICKSTART.md)
- [配置指南](CONFIG_GUIDE.md)

## 🎉 总结

通过多配置源系统，您可以：
- ✅ 灵活切换不同的 AI 服务提供商
- ✅ 快速测试不同模型的效果
- ✅ 根据任务需求选择最合适的模型
- ✅ 在 Web 界面中管理所有配置，无需重启服务

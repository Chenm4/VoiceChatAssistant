# 多配置源系统更新日志

## 🎉 新功能：多 API 配置源支持

### 📅 更新时间
2026-01-30

### 🎯 更新内容

#### 1. **配置文件重构** (`config.py`)

**之前：** 单一配置
```python
OPENAI_CONFIG = {
    "api_key": "xxx",
    "model": "gpt-3.5-turbo",
    "base_url": "https://api.openai.com/v1"
}
```

**现在：** 多配置源支持
```python
OPENAI_CONFIG = [
    {
        "name": "OpenRouter",
        "api_key": "sk-or-v1-xxx",
        "models": [
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-2.5-flash",
            "anthropic/claude-3.5-sonnet"
        ],
        "base_url": "https://openrouter.ai/api/v1"
    },
    {
        "name": "OpenAI",
        "api_key": "",
        "models": ["gpt-4", "gpt-3.5-turbo"],
        "base_url": "https://api.openai.com/v1"
    },
    # ... 更多配置源
]

DEFAULT_CONFIG_NAME = "OpenRouter"
```

#### 2. **后端 API 更新**

**新增数据模型** (`backend/api/models.py`):
- `ConfigSource`: 单个配置源模型
- `ConfigList`: 配置源列表模型

**新增 API 接口** (`backend/api/routes.py`):
- `GET /api/config`: 获取所有配置源和当前配置
- `POST /api/config/switch`: 切换配置源和模型
- `POST /api/config/update`: 更新某个配置源

**示例：**
```bash
# 获取配置
curl http://localhost:8888/api/config

# 切换配置
curl -X POST "http://localhost:8888/api/config/switch?source_name=OpenRouter&model=google/gemini-2.5-flash"

# 更新配置源
curl -X POST http://localhost:8888/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"name":"OpenRouter","api_key":"new-key","models":["model1"],"base_url":"https://..."}'
```

#### 3. **前端界面升级**

**导航栏** (`NavBar.vue`):
- ✨ 实时显示当前配置源（蓝色标签）
- ✨ 实时显示当前模型（绿色标签）

**设置界面** (`SettingsModal.vue`):
- ✨ 配置源下拉选择
- ✨ 模型下拉选择（根据配置源自动更新）
- ✨ 一键切换配置
- ✨ 管理所有配置源
- ✨ 在线编辑 API Key 和模型列表

**主视图** (`ChatView.vue`):
- ✨ 自动加载多配置源
- ✨ 配置刷新功能

### 🌟 功能亮点

#### ✅ 灵活切换
- 在 Web 界面中即时切换不同的 AI 服务
- 无需重启后端服务
- 配置立即生效

#### ✅ 多模型支持
- 每个配置源可配置多个模型
- 切换配置源时自动显示可用模型
- 支持自定义模型列表

#### ✅ 在线管理
- 在 Web 界面中编辑 API Key
- 在线添加/修改模型列表
- 实时查看配置状态

#### ✅ 预配置支持
- 内置 OpenRouter、OpenAI、DeepSeek、本地模型配置
- 开箱即用的配置模板
- 轻松添加新的服务商

### 📦 新增文件

```
/Users/hb952/code/yuyinshibie/
├── MULTI_CONFIG_GUIDE.md           # 多配置源使用指南
├── CHANGELOG_MULTI_CONFIG.md       # 更新日志（本文件）
├── config.py                       # 重构的配置文件
├── backend/
│   └── api/
│       ├── models.py               # 新增 ConfigSource, ConfigList 模型
│       └── routes.py               # 新增配置管理接口
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── NavBar.vue          # 更新：显示当前配置
    │   │   └── SettingsModal.vue   # 重构：多配置源管理
    │   └── views/
    │       └── ChatView.vue        # 更新：支持多配置源
```

### 🔄 迁移指南

如果您之前使用的是单配置版本，请按以下步骤迁移：

#### 1. 备份当前配置
```bash
cp config.py config.py.backup
```

#### 2. 更新 config.py 格式

将：
```python
OPENAI_CONFIG = {
    "api_key": "your-key",
    "model": "gpt-3.5-turbo",
    "base_url": "https://api.openai.com/v1"
}
```

改为：
```python
OPENAI_CONFIG = [
    {
        "name": "OpenAI",
        "api_key": "your-key",
        "models": ["gpt-3.5-turbo", "gpt-4"],
        "base_url": "https://api.openai.com/v1"
    }
]

DEFAULT_CONFIG_NAME = "OpenAI"
```

#### 3. 重启服务
```bash
./start.sh
```

#### 4. 验证配置
```bash
python3 -c "from config import OPENAI_CONFIG; print(f'配置源数量: {len(OPENAI_CONFIG)}')"
```

### 🐛 已知问题

无。

### 📝 待办事项

- [ ] 支持添加新配置源（不仅是编辑现有的）
- [ ] 支持删除配置源
- [ ] 配置导入/导出功能
- [ ] 配置源分组管理

### 💬 反馈

如有问题或建议，请查看：
- [多配置源使用指南](MULTI_CONFIG_GUIDE.md)
- [项目文档](PROJECT_README.md)

---

**测试验证：** ✅ 通过
- ✅ 配置文件读取
- ✅ 后端配置加载
- ✅ 当前配置: OpenRouter - google/gemini-2.0-flash-exp:free
- ✅ 4 个配置源可用

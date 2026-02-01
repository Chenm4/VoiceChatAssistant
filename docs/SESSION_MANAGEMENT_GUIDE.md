# 会话管理功能使用指南

## 📋 功能概述

会话管理功能允许您在一个应用中管理多个独立的对话，类似于浏览器的多标签页功能。每个会话都有独立的对话历史，互不干扰。

## 🎯 核心特性

### 1. **会话 ID 生成**
- 格式：`2026-01-30_23-01-32-038-ezc8`
- 组成：`日期_时间-毫秒-随机字符`
- 精度：毫秒级时间戳 + 4位随机字符
- 保证：全局唯一性

### 2. **会话数据结构**
```json
{
  "id": "2026-01-30_23-01-32-038-ezc8",
  "title": "FastAPI 和 Vue 架构",
  "created_at": 1706591532,
  "updated_at": 1706592001,
  "messages": [
    {
      "role": "user",
      "content": "你好"
    },
    {
      "role": "assistant",
      "content": "你好！有什么我可以帮助你的吗？"
    }
  ]
}
```

### 3. **会话排序**
- 按 `updated_at` 降序排列
- 最近更新的会话显示在最上方
- 每次发送消息自动更新时间戳

## 🖥️ 界面功能

### 左侧边栏

#### 顶部工具栏
- **新建对话** 按钮：创建新会话
- **折叠/展开** 按钮：折叠侧边栏以获得更大聊天空间

#### 会话列表
每个会话项显示：
- 📝 **会话标题**：自动从第一条消息生成，可手动编辑
- 💬 **消息数量**：该会话包含的消息数
- ⏰ **更新时间**：显示相对时间（刚刚、5分钟前、2小时前等）
- ✏️ **编辑按钮**：重命名会话标题
- 🗑️ **删除按钮**：删除会话

#### 会话状态
- **当前会话**：紫色渐变背景高亮显示
- **悬停效果**：鼠标悬停时显示操作按钮

## 📡 API 接口

### 1. 获取会话列表
```http
GET /api/sessions
```

**响应：**
```json
{
  "sessions": [
    {
      "id": "2026-01-30_23-01-32-038-ezc8",
      "title": "FastAPI 和 Vue 架构",
      "created_at": 1706591532,
      "updated_at": 1706592001,
      "messages": []
    }
  ],
  "current_session_id": "2026-01-30_23-01-32-038-ezc8"
}
```

### 2. 创建新会话
```http
POST /api/sessions?title=新对话
```

**响应：**
```json
{
  "success": true,
  "message": "会话创建成功",
  "session": {
    "id": "2026-01-30_23-02-15-123-abcd",
    "title": "新对话",
    "created_at": 1706591735,
    "updated_at": 1706591735,
    "messages": []
  }
}
```

### 3. 获取会话详情
```http
GET /api/sessions/{session_id}
```

**响应：**
```json
{
  "id": "2026-01-30_23-01-32-038-ezc8",
  "title": "FastAPI 和 Vue 架构",
  "created_at": 1706591532,
  "updated_at": 1706592001,
  "messages": [...]
}
```

### 4. 切换会话
```http
POST /api/sessions/{session_id}/switch
```

**响应：**
```json
{
  "success": true,
  "message": "会话切换成功",
  "session": {...}
}
```

### 5. 更新会话标题
```http
PUT /api/sessions/{session_id}/title?title=新标题
```

**响应：**
```json
{
  "success": true,
  "message": "标题更新成功",
  "session": {...}
}
```

### 6. 删除会话
```http
DELETE /api/sessions/{session_id}
```

**响应：**
```json
{
  "success": true,
  "message": "会话删除成功",
  "current_session_id": "2026-01-30_23-03-45-789-wxyz"
}
```

**注意：** 不允许删除最后一个会话

## 🎮 使用方法

### 创建新会话
1. 点击左侧边栏顶部的 **"新建对话"** 按钮
2. 系统自动创建新会话并切换到该会话
3. 新会话标题默认为 "新对话"
4. 发送第一条消息后，标题自动更新为消息前20个字符

### 切换会话
1. 在左侧边栏点击任意会话
2. 系统自动加载该会话的历史消息
3. 当前会话会高亮显示

### 重命名会话
1. 鼠标悬停在会话项上
2. 点击 **编辑图标** ✏️
3. 输入新标题，按 Enter 保存，按 Esc 取消

### 删除会话
1. 鼠标悬停在会话项上
2. 点击 **删除图标** 🗑️
3. 确认删除操作
4. 如果删除的是当前会话，自动切换到其他会话

### 折叠侧边栏
1. 点击右上角的 **折叠按钮** ◀
2. 侧边栏折叠为窄条，仅显示图标
3. 再次点击可展开

## 🔧 技术实现

### 后端实现

#### ID 生成器 (`backend/utils/id_generator.py`)
```python
def generate_session_id() -> str:
    """
    生成会话 ID
    格式: 2026-01-30_23-01-32-038-ezc8
    """
    now = datetime.now()
    datetime_part = now.strftime("%Y-%m-%d_%H-%M-%S")
    millisecond = now.strftime("%f")[:3]
    random_chars = ''.join(random.choices(
        string.ascii_lowercase + string.digits, k=4
    ))
    return f"{datetime_part}-{millisecond}-{random_chars}"
```

#### 数据模型 (`backend/api/models.py`)
```python
class Session(BaseModel):
    id: str
    title: str
    created_at: int
    updated_at: int
    messages: Optional[List[ChatMessage]] = []

class SessionList(BaseModel):
    sessions: List[Session]
    current_session_id: Optional[str] = None
```

#### 会话存储
- 使用内存存储（列表）
- 当前会话 ID 存储在全局变量
- 每个会话独立管理消息列表

### 前端实现

#### 组件结构
```
ChatView.vue
├── SessionSidebar.vue   (会话侧边栏)
├── NavBar.vue          (导航栏)
├── MessageList.vue     (消息列表)
├── InputArea.vue       (输入区域)
├── VoiceButton.vue     (语音按钮)
└── SettingsModal.vue   (设置对话框)
```

#### 状态管理
```javascript
const sessions = ref([])              // 会话列表
const currentSessionId = ref(null)    // 当前会话 ID
const messages = ref([])              // 当前会话的消息
```

#### 会话切换流程
1. 用户点击会话 → `handleSwitchSession(sessionId)`
2. 调用 API `/api/sessions/{sessionId}/switch`
3. 后端切换当前会话，返回会话详情
4. 前端加载会话消息 → `loadSessionMessages(sessionId)`
5. 更新界面显示

## 💡 最佳实践

### 1. 会话命名
- ✅ 使用描述性标题："Vue 组件开发问题"
- ✅ 包含关键词："FastAPI 路由配置"
- ❌ 避免模糊标题："问题"、"测试"

### 2. 会话管理
- 定期清理不需要的会话
- 重要会话重命名以便识别
- 利用时间排序快速找到最近的会话

### 3. 消息管理
- 每个会话专注于一个主题
- 相关讨论放在同一会话
- 需要新话题时创建新会话

## 🐛 故障排除

### 问题：会话列表不显示

**解决方案：**
```bash
# 检查后端是否正常运行
curl http://localhost:8888/api/sessions

# 检查浏览器控制台是否有错误
# 确认前端已正确加载 SessionSidebar 组件
```

### 问题：切换会话后消息没有更新

**解决方案：**
1. 检查 `watch(currentSessionId)` 是否正常触发
2. 查看浏览器控制台的网络请求
3. 确认后端返回了正确的消息列表

### 问题：无法删除会话

**可能原因：**
- 只剩最后一个会话（系统至少保留一个会话）
- 后端返回 400 错误

**解决方案：**
- 创建新会话后再删除旧会话
- 检查后端日志确认错误原因

## 📊 数据持久化

**当前实现：** 内存存储（重启后数据丢失）

**未来计划：**
- [ ] SQLite 数据库持久化
- [ ] 会话导出/导入功能
- [ ] 云端同步

## 🎉 总结

会话管理功能提供了强大的多对话支持，让您可以：
- ✅ 同时管理多个对话主题
- ✅ 快速切换不同会话
- ✅ 自动生成唯一会话 ID
- ✅ 按时间排序，快速找到最近对话
- ✅ 重命名和删除会话

**开始使用：** 启动应用后，左侧会自动显示会话列表，点击"新建对话"开始新的会话！

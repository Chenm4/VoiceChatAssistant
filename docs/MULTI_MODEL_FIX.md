# 多模型并行功能修复

## 📋 更新日期
2026-01-31

## 🐛 修复的问题

1. ✅ **会话配置保存后不生效**
   - 问题：保存多模型配置后，再次打开设置还是显示单个模型
   - 原因：`loadSessions()` 只加载轻量级索引，不包含 `session_config`
   - 解决：在 `loadSessionMessages()` 和 `handleSessionConfigUpdated()` 中同步更新 sessions 数组

2. ✅ **移除导航栏的全局模型显示**
   - 问题：顶部显示全局配置没有意义，每个会话都有自己的配置
   - 解决：移除 NavBar 中的配置源和模型标签显示

3. ✅ **会话列表中的图标**
   - 问题：消息数量前有个评论图标，用户觉得多余
   - 解决：将 `<i class="fas fa-comments"></i>` 改为纯文本 "X 条消息"

4. ✅ **多模型发送不工作**
   - 问题：后端还是单模型调用，不支持多模型
   - 解决：后端实现多模型顺序调用，前端处理多模型响应

## 🔧 主要代码修改

### 1. 后端修改 (`backend/api/routes.py`)

#### 支持会话配置的模型选择
```python
# 检查会话配置，确定要使用的模型列表
session_config = current_session.session_config
models_to_use = []
source_to_use = None

if session_config and session_config.models and len(session_config.models) > 0:
    # 使用会话配置的模型
    models_to_use = session_config.models
    source_name = session_config.source_name or current_config.current_source
    source_to_use = next((s for s in config_sources if s.name == source_name), None)
else:
    # 使用全局配置
    models_to_use = [api_config.model]
    source_to_use = next((s for s in config_sources if s.name == current_config.current_source), None)

is_parallel = len(models_to_use) > 1
```

#### 多模型顺序调用
```python
if is_parallel:
    # 多模型顺序调用模式
    yield f"data: {json.dumps({'type': 'multi_model_start', 'models': models_to_use}, ensure_ascii=False)}\n\n"
    
    # 顺序调用每个模型
    for model_index, model_name in enumerate(models_to_use):
        # 发送模型开始标记
        yield f"data: {json.dumps({'type': 'model_start', 'model_index': model_index, 'model': model_name}, ensure_ascii=False)}\n\n"
        
        # 调用模型并流式返回
        # 每个 chunk 包含 model_index 和 model 字段
        
        # 保存每个模型的响应
        assistant_msg = ChatMessage(
            id=assistant_msg_id,
            parent_id=user_msg_id,
            role="assistant",
            content=model_data['content'],
            model_info={
                "id": model_data['model'],
                "name": model_data['model'],
                "provider": source_to_use.name
            },
            is_parallel_response=True
        )
```

#### 新增的消息类型
- `multi_model_start`: 多模型模式开始，包含所有模型列表
- `model_start`: 某个模型开始响应
- `content`: 内容 chunk，多模型时包含 `model_index` 和 `model` 字段
- `model_done`: 某个模型完成
- `model_error`: 某个模型出错
- `done`: 全部完成

### 2. 前端修改 (`frontend/src/views/ChatView.vue`)

#### 修复会话配置加载
```javascript
async function handleSessionConfigUpdated() {
  // 重新加载当前会话的完整数据（包括 session_config）
  if (currentSessionId.value) {
    const sessionData = await api.get(`/sessions/${currentSessionId.value}`)
    // 更新 sessions 数组中的当前会话对象
    const index = sessions.value.findIndex(s => s.id === currentSessionId.value)
    if (index !== -1) {
      sessions.value[index] = {
        ...sessions.value[index],
        ...sessionData
      }
    }
  }
  showSessionSettings.value = false
}
```

#### 处理多模型响应
```javascript
function processLine(line) {
  const data = JSON.parse(jsonStr)
  
  if (data.type === 'multi_model_start') {
    // 为每个模型创建一个消息对象
    data.models.forEach((model, index) => {
      const msgObj = {
        role: 'assistant',
        content: '',
        model_info: { name: model, provider: 'unknown' }
      }
      messages.value.push(msgObj)
      modelMessages.push(msgObj)
    })
    
  } else if (data.type === 'content') {
    if (data.model_index !== undefined && modelMessages.length > 0) {
      // 多模型模式：更新对应索引的消息
      modelMessages[data.model_index].content += data.data
    } else {
      // 单模型模式：更新最后一条 assistant 消息
      // ...
    }
  }
}
```

### 3. 前端 UI 修改

#### 移除导航栏全局配置显示
```vue
<!-- NavBar.vue -->
<div class="flex items-center gap-3">
  <el-icon :size="28" color="#409EFF"><Cpu /></el-icon>
  <h1 class="text-xl font-semibold text-gray-800">ChatGPT Web</h1>
  <!-- 移除了配置源和模型的显示 -->
</div>
```

#### 会话列表图标移除
```vue
<!-- SessionSidebar.vue -->
<span class="message-count">
  {{ session.messages?.length || 0 }} 条消息
</span>
```

## 🎯 使用流程

### 单模型模式
1. 打开会话设置
2. 选择一个模型
3. 保存
4. 发送消息 → 单个 AI 回复

### 多模型模式
1. 打开会话设置
2. 选择多个模型（如 gpt-3.5-turbo 和 gpt-4）
3. 可选：拖拽调整模型顺序
4. 保存
5. 发送消息 → 多个 AI 回复（顺序显示）

## 📝 技术细节

### 为什么是顺序调用而不是真正并行？

1. **流式响应的限制**：SSE (Server-Sent Events) 是单向流，难以同时处理多个异步流
2. **简化实现**：顺序调用更可靠，不需要复杂的并发控制
3. **用户体验**：用户仍然能看到多个模型的响应，只是先后顺序不同
4. **资源考虑**：并行调用会同时占用多个 API 连接，成本更高

### 未来改进方向

如需真正的并行响应，可以考虑：
1. **前端发起多次请求**：为每个模型创建独立的 SSE 连接
2. **WebSocket**：使用双向通信协议，支持多路复用
3. **后端队列**：使用任务队列异步处理，前端轮询结果

## ✅ 测试清单

- [ ] 单模型配置保存和加载
- [ ] 多模型配置保存和加载
- [ ] 单模型发送消息正常
- [ ] 多模型发送消息，显示多个回复
- [ ] 每个回复正确显示模型标识
- [ ] 拖拽调整模型顺序生效
- [ ] 导航栏不再显示全局模型
- [ ] 会话列表显示"X 条消息"而非图标

## 🚀 启动测试

```bash
# 后端
python backend/main.py

# 前端
cd frontend
npm run dev
```

## 📊 消息格式示例

### 单模型模式
```json
data: {"type": "content", "data": "Hello"}
data: {"type": "content", "data": " world"}
data: {"type": "done", "message_id": "msg_abc123"}
```

### 多模型模式
```json
data: {"type": "multi_model_start", "models": ["gpt-3.5-turbo", "gpt-4"]}
data: {"type": "model_start", "model_index": 0, "model": "gpt-3.5-turbo"}
data: {"type": "content", "model_index": 0, "model": "gpt-3.5-turbo", "data": "Hello"}
data: {"type": "model_done", "model_index": 0, "model": "gpt-3.5-turbo"}
data: {"type": "model_start", "model_index": 1, "model": "gpt-4"}
data: {"type": "content", "model_index": 1, "model": "gpt-4", "data": "Hi"}
data: {"type": "model_done", "model_index": 1, "model": "gpt-4"}
data: {"type": "done", "model_count": 2}
```

## 🔍 调试建议

如果多模型不工作，检查：
1. 浏览器控制台是否有错误
2. 后端日志中是否显示多模型模式
3. 检查会话配置是否正确保存：`GET /api/sessions/{id}`
4. 检查消息中的 `model_info` 字段

## 📚 相关文件

- `/backend/api/routes.py` - 后端路由和多模型逻辑
- `/backend/api/models.py` - SessionConfig 数据模型
- `/frontend/src/views/ChatView.vue` - 消息发送和接收
- `/frontend/src/components/SessionSettingsSidebar.vue` - 会话设置UI
- `/frontend/src/components/MessageList.vue` - 消息显示
- `/frontend/src/components/NavBar.vue` - 导航栏
- `/frontend/src/components/SessionSidebar.vue` - 会话列表

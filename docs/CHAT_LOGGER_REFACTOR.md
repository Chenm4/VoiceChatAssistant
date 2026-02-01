# Chat Logger 重构说明

## 重构目标

彻底重构聊天日志记录器，使其更清晰地展示每个模型的交互过程。

## 主要改进

### 1. 按会话分文件存储
- **旧方式**: 所有会话的日志混在一起，按日期分文件（`chat_20260201.log`）
- **新方式**: 每个会话独立的日志文件（`session_{session_id}_{date}.log`）
- **优势**: 更容易追踪特定会话的完整对话历史

### 2. 以模型交互为单位
- **旧方式**: 先记录请求，后记录响应，分开两次记录
- **新方式**: 一次记录完整的"请求+响应"交互
- **优势**: 清晰展示每个模型收到什么、返回什么

### 3. 统一时间戳
- **旧方式**: 请求和响应各有时间戳
- **新方式**: 一个模型交互只有一个时间戳
- **优势**: 减少冗余信息，更简洁

### 4. 消息内容预览
- **旧方式**: 记录完整消息内容（最多500字符）
- **新方式**: 只显示前10个字符 + "..."
- **优势**: 日志更紧凑，一眼看清消息数量和角色

### 5. 并行模式清晰展示
- **问题**: 在并行模式下，每个模型接收的是**相同的消息列表**（不包含其他模型的回复）
- **解决**: 每个模型的日志独立记录，清楚显示发送给该模型的具体内容

## 新的日志格式示例

```
====================================================================================================
会话日志 - Session ID: 2026-02-01_14-04-50-933-oas5
创建时间: 2026-02-01 14:33:29
====================================================================================================

────────────────────────────────────────────────────────────────────────────────────────────────────
⏰ 时间: 2026-02-01 14:33:29
🤖 模型: qwen/qwen-2.5-7b-instruct
⏱️  耗时: 2.15秒
⚙️  配置: temperature=0.7, top_p=1.0

📤 发送消息 (共2条):
   1. [system] 你是一个有帮助的助手...
   2. [user] 你好，请介绍一下你自...

📥 模型响应:
   你好！我是一个AI助...
   (完整长度: 43 字符)

────────────────────────────────────────────────────────────────────────────────────────────────────
⏰ 时间: 2026-02-01 14:33:30
🤖 模型: google/gemini-2.5-flash
⏱️  耗时: 1.87秒
⚙️  配置: temperature=0.7, top_p=1.0

📤 发送消息 (共2条):
   1. [system] 你是一个有帮助的助手...
   2. [user] 你好，请介绍一下你自...

📥 模型响应:
   Hello! I'm...
   (完整长度: 98 字符)
```

## API 变化

### 旧 API（已废弃）
```python
log_request_to_model(session_id, models, messages, config)
log_response_from_model(session_id, model, response, elapsed_time)
log_summary(session_id, total_messages, user_message, models_count)
```

### 新 API
```python
# 记录模型交互（请求+响应）
log_model_interaction(
    session_id: str,
    model: str,
    messages: List[Dict[str, str]],
    response: str,
    elapsed_time: float,
    config: Dict[str, Any] = None
)

# 记录错误
log_error(
    session_id: str,
    model: str,
    messages: List[Dict[str, str]],
    error: Exception,
    stage: str = "unknown"
)
```

## 使用示例

### 单模型模式
```python
log_model_interaction(
    session_id="session_123",
    model="gpt-3.5-turbo",
    messages=[
        {"role": "user", "content": "你好"}
    ],
    response="你好！有什么可以帮你的吗？",
    elapsed_time=1.23,
    config={"temperature": 0.7, "top_p": 1.0}
)
```

### 并行模式
```python
# 两个模型接收相同的消息
messages = [{"role": "user", "content": "你好"}]

# 模型1
log_model_interaction(
    session_id="session_123",
    model="qwen/qwen-2.5-7b-instruct",
    messages=messages,  # 相同的消息
    response="你好！我是通义千问。",
    elapsed_time=2.15,
    config={"temperature": 0.7, "top_p": 1.0}
)

# 模型2
log_model_interaction(
    session_id="session_123",
    model="google/gemini-2.5-flash",
    messages=messages,  # 相同的消息
    response="Hello! I'm Gemini.",
    elapsed_time=1.87,
    config={"temperature": 0.7, "top_p": 1.0}
)
```

## 实现细节

### SessionChatLogger 类
- 为每个会话创建独立的日志记录器实例
- 使用全局缓存避免重复创建
- 自动创建日志文件和会话头部

### 消息截断
- 默认显示前10个字符
- 可通过 `_truncate_text()` 方法调整
- 始终显示完整长度信息

### 时间线顺序
- 按照实际调用顺序记录
- 并行模式下，哪个模型先完成就先记录
- 每条记录都有独立的时间戳

## 文件位置

- 日志文件: `logs/chat_history/session_{session_id}_{date}.log`
- 源代码: `backend/utils/chat_logger.py`
- 调用位置: `backend/api/routes.py`

## 注意事项

1. **并行模式**: 每个模型接收的消息列表是相同的，不包含其他模型的回复
2. **错误处理**: 错误也会记录发送的消息内容
3. **旧日志文件**: 旧格式的日志文件（`chat_*.log`）仍然存在，但不再生成新的
4. **Legacy API**: `routes_legacy.py` 仍使用旧 API，未更新

## 测试

运行测试脚本验证功能：
```bash
python3 test_chat_logger.py
```

查看生成的日志文件：
```bash
cat logs/chat_history/session_test_session_123_*.log
```

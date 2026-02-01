# 模型上下文修复说明

## 问题描述

在并行模式下，不同模型接收到的消息历史中，assistant 回复的内容为空或不正确。

### 问题原因

之前的实现中，所有模型共享相同的消息历史，没有根据模型来筛选对应的 assistant 回复。当用户从单模型切换到并行模式时，会出现以下问题：

1. **第一次请求**：只使用 qwen 模型
   - qwen 的回复被保存

2. **第二次请求**：切换到并行模式（qwen + gemini）
   - 两个模型都收到了包含 qwen 回复的历史
   - 但 gemini 从未回复过，不应该看到 qwen 的回复
   - 导致 gemini 的上下文不正确

### 日志中的表现

```
📤 发送消息 (共5条):
   1. [user] 我叫什么你知道吗
   2. [assistant] 你好！根据你的描述，...  <- qwen 的回复
   3. [user] 你是谁？
   4. [assistant]                           <- 空的！
   5. [user] 你知道今天几号吗
```

## 解决方案

### 核心思路

**每个模型只使用自己历史回复的上下文**

- 如果当前模型是 gemini，只添加 gemini 历史回复的 assistant 消息
- 如果当前模型是 qwen，只添加 qwen 历史回复的 assistant 消息
- 如果某个模型之前没有回复过（新加入并行），则该模型的 assistant 消息为空
- **用户消息和 system 消息始终包含**

### 实现细节

#### 1. 创建 `build_messages_for_model` 函数

```python
def build_messages_for_model(target_model: str) -> List[Dict[str, str]]:
    """为特定模型构建消息历史"""
    api_messages = []
    
    # 1. 添加 system prompt
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    
    # 2. 遍历历史消息
    for msg in current_session.messages[:-1]:
        if msg.role == 'user':
            # 用户消息：所有模型都需要
            api_messages.append({"role": "user", "content": msg.content})
        elif msg.role == 'assistant':
            # assistant 消息：只添加当前模型的回复
            assistant_content = None
            
            if msg.is_parallel_response and msg.parallel_models:
                # 并行响应：从 parallel_models 中找当前模型
                for model_data in msg.parallel_models:
                    if model_data.get('model') == target_model:
                        assistant_content = model_data.get('content', '')
                        break
            else:
                # 单模型响应：检查是否是当前模型
                if msg.model_info and msg.model_info.get('name') == target_model:
                    assistant_content = msg.content
            
            # 只有找到对应模型的回复才添加
            if assistant_content is not None:
                api_messages.append({"role": "assistant", "content": assistant_content})
    
    # 3. 添加当前用户消息
    api_messages.append({"role": "user", "content": user_message.content})
    
    return api_messages
```

#### 2. 并行模式下为每个模型构建专属消息

```python
async def stream_model(model_index: int, model_name: str):
    # 为当前模型构建专属的消息历史
    model_messages = build_messages_for_model(model_name)
    
    # 使用专属消息调用 API
    stream = await client.chat.completions.create(
        model=model_name,
        messages=model_messages,  # 每个模型不同
        ...
    )
```

#### 3. 单模型模式同样使用

```python
# 单模型模式
model_to_use = models_to_use[0]
model_messages = build_messages_for_model(model_to_use)

stream = openai_client.chat.completions.create(
    model=model_to_use,
    messages=model_messages,
    ...
)
```

#### 4. 日志记录也使用专属消息

```python
# 记录每个模型的交互
for model_data in parallel_models_data:
    model_name = model_data['model_info']['name']
    model_messages = build_messages_for_model(model_name)  # 获取该模型的专属消息
    log_model_interaction(
        session_id=current_session_id,
        model=model_name,
        messages=model_messages,  # 记录该模型实际收到的消息
        response=model_data['content'],
        ...
    )
```

## 修复后的效果

### 场景1：从单模型切换到并行

**第一次请求**（只用 qwen）：
```
📤 qwen 发送消息 (共1条):
   1. [user] 你是谁？

📥 qwen 响应:
   我是Qwen...
```

**第二次请求**（qwen + gemini 并行）：
```
📤 qwen 发送消息 (共3条):
   1. [user] 你是谁？
   2. [assistant] 我是Qwen...     <- qwen 自己的历史回复
   3. [user] 你知道今天几号吗

📤 gemini 发送消息 (共2条):
   1. [user] 你是谁？
   2. [user] 你知道今天几号吗    <- gemini 没有历史回复，所以跳过
```

### 场景2：持续并行

**第三次请求**（qwen + gemini 并行）：
```
📤 qwen 发送消息 (共5条):
   1. [user] 你是谁？
   2. [assistant] 我是Qwen...     <- qwen 的第一次回复
   3. [user] 你知道今天几号吗
   4. [assistant] 今天是...        <- qwen 的第二次回复
   5. [user] 天气怎么样？

📤 gemini 发送消息 (共5条):
   1. [user] 你是谁？
   2. [assistant] 我是Gemini...   <- gemini 的第一次回复
   3. [user] 你知道今天几号吗
   4. [assistant] 今天是...        <- gemini 的第二次回复
   5. [user] 天气怎么样？
```

## 修改的文件

1. **backend/api/routes.py**
   - 添加 `build_messages_for_model()` 函数（聊天接口）
   - 添加 `build_messages_for_model_regenerate()` 函数（重新生成接口）
   - 修改并行模式的 `stream_model()` 函数
   - 修改单模型模式的消息构建
   - 修改日志记录调用

2. **backend/utils/chat_logger.py**
   - 已经在之前的重构中更新

## 测试建议

1. **测试场景1**：单模型 → 并行模式
   - 先用 qwen 问几个问题
   - 切换到 qwen + gemini 并行
   - 检查日志，确认 gemini 没有收到 qwen 的历史回复

2. **测试场景2**：并行模式持续使用
   - 一直使用 qwen + gemini 并行
   - 检查日志，确认每个模型只看到自己的历史回复

3. **测试场景3**：并行 → 单模型 → 并行
   - 先并行使用
   - 切换到单个模型
   - 再切换回并行
   - 检查上下文是否正确

## 注意事项

1. **旧数据兼容性**：如果消息没有 `model_info`，会被当作所有模型共享的回复
2. **System 消息**：始终包含在所有模型的上下文中
3. **用户消息**：始终包含在所有模型的上下文中
4. **Assistant 消息**：只包含当前模型的历史回复

## 相关文档

- `CHAT_LOGGER_REFACTOR.md` - 聊天日志重构说明
- `backend/api/models.py` - 数据模型定义

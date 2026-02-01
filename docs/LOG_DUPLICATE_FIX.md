# 日志重复消息修复说明

## 问题描述

在日志文件中，用户消息出现了重复：

```
📤 发送消息 (共15条):
...
14. [user] 今天天气真不错
15. [user] 今天天气真不错   <- 重复了！
```

## 问题原因

### 时间线分析

1. **第686行**：用户消息被添加到 `current_session.messages`
   ```python
   current_session.messages.append(user_message)
   ```

2. **第801行**：调用 `build_messages_for_model()` 构建消息历史（用于 API 调用）
   - 此时遍历 `current_session.messages[:-1]`（排除最后一条）
   - 然后添加 `user_message.content`（当前用户消息）
   - **结果正确**：不包含重复

3. **第925行**：Assistant 消息被添加到 `current_session.messages`
   ```python
   current_session.messages.append(assistant_msg)
   ```

4. **第933行**：再次调用 `build_messages_for_model()` 用于日志记录
   - 此时遍历 `current_session.messages[:-1]`
   - **问题**：现在最后一条是 assistant 消息，所以 `[:-1]` 包含了用户消息
   - 然后又添加 `user_message.content`
   - **结果错误**：用户消息出现了两次！

### 根本原因

在记录日志时重新调用 `build_messages_for_model()`，而此时会话状态已经改变（assistant 消息已添加），导致构建的消息历史与实际发送给 API 的消息历史不一致。

## 解决方案

### 核心思路

**在调用 API 时保存构建的消息历史，日志记录时使用保存的消息历史。**

### 实现步骤

#### 1. 创建消息历史缓存

```python
model_messages_map = {}  # 存储每个模型的消息历史（用于日志记录）
```

#### 2. 在调用 API 时保存消息历史

```python
async def stream_model(model_index: int, model_name: str):
    # 为当前模型构建专属的消息历史
    model_messages = build_messages_for_model(model_name)
    
    # 保存消息历史用于日志记录
    model_messages_map[model_name] = model_messages
    
    # 使用 model_messages 调用 API
    stream = await client.chat.completions.create(
        model=model_name,
        messages=model_messages,  # 使用构建的消息
        ...
    )
```

#### 3. 日志记录时使用保存的消息历史

```python
# 记录每个模型的交互
for model_data in parallel_models_data:
    model_name = model_data['model_info']['name']
    # 使用保存的消息历史（调用 API 时的消息）
    model_messages = model_messages_map.get(model_name, [])
    log_model_interaction(
        session_id=current_session_id,
        model=model_name,
        messages=model_messages,  # 使用保存的消息
        response=model_data['content'],
        ...
    )
```

## 修改的位置

### 1. 聊天接口 - 并行模式

**文件**: `backend/api/routes.py`

- **第784行**：添加 `model_messages_map = {}`
- **第805行**：保存消息历史 `model_messages_map[model_name] = model_messages`
- **第935行**：使用保存的消息历史 `model_messages = model_messages_map.get(model_name, [])`

### 2. 聊天接口 - 单模型模式

单模型模式不需要修改，因为：
- 第959行：构建消息历史
- 第1002行：直接使用同一个 `model_messages` 变量
- 没有重新调用 `build_messages_for_model()`

### 3. 重新生成接口 - 并行模式

**文件**: `backend/api/routes.py`

- **第1896行**：添加 `model_messages_map = {}`
- **第1911行**：保存消息历史 `model_messages_map[model_name] = model_messages`
- **第2044行**：使用保存的消息历史 `model_messages = model_messages_map.get(model_name, [])`

### 4. 重新生成接口 - 单模型模式

单模型模式不需要修改（原因同上）。

## 修复后的效果

### 修复前

```
📤 发送消息 (共15条):
   1. [system] 你是一个参与过讯飞实...
   2. [user] 我叫什么你知道吗
   3. [assistant] 你好！根据你的描述，...
   ...
   14. [user] 今天天气真不错
   15. [user] 今天天气真不错   <- 重复！
```

### 修复后

```
📤 发送消息 (共14条):
   1. [system] 你是一个参与过讯飞实...
   2. [user] 我叫什么你知道吗
   3. [assistant] 你好！根据你的描述，...
   ...
   14. [user] 今天天气真不错   <- 不再重复
```

## 测试建议

1. **测试并行模式**
   - 发送多条消息
   - 检查日志文件，确认没有重复的用户消息

2. **测试单模型模式**
   - 发送多条消息
   - 检查日志文件，确认没有重复的用户消息

3. **测试重新生成**
   - 重新生成某条消息
   - 检查日志文件，确认没有重复的用户消息

## 相关文档

- `CHAT_LOGGER_REFACTOR.md` - 聊天日志重构说明
- `MODEL_CONTEXT_FIX.md` - 模型上下文修复说明

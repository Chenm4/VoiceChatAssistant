# 数据结构重构文档

## 概述

本次重构将对话数据从**线性结构**升级为**树形结构**，支持多分支对话、并行响应和动态 System Prompt。

## 重构日期

2026-01-31

## 主要变更

### 1. 消息结构变更

#### 旧格式（线性）
```json
{
  "role": "user",
  "content": "我是谁？",
  "timestamp": 1769826840
}
```

#### 新格式（树形）
```json
{
  "id": "msg_uuid_001",
  "parent_id": null,
  "role": "user",
  "content": "我是谁？",
  "type": "text",
  "created_at": 1769826840,
  "children_ids": ["msg_uuid_002", "msg_uuid_003"]
}
```

### 2. Assistant 消息增强

新增字段：

- `model_info`: 模型信息（ID、名称、提供商）
- `usage`: Token 使用统计
- `status`: 消息状态（success/error/pending）
- `latency_ms`: 响应延迟（毫秒）
- `is_parallel_response`: 是否为并行响应

示例：
```json
{
  "id": "msg_uuid_002",
  "parent_id": "msg_uuid_001",
  "role": "assistant",
  "content": "您是使用我进行交流的用户...",
  "type": "text",
  "created_at": 1769826843,
  "children_ids": [],
  "model_info": {
    "id": "qwen-turbo",
    "name": "Qwen Turbo",
    "provider": "aliyun"
  },
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  },
  "status": "success",
  "latency_ms": 1200
}
```

### 3. 会话结构变更

#### 新增字段

- `system_prompt`: 全局系统提示词
- 消息中可插入 `role: "system"` 实现动态 System Prompt

#### 会话索引增强

```json
{
  "id": "2026-01-31_10-33-00-454-gg3t",
  "title": "我是谁？",
  "created_at": 1769826780,
  "updated_at": 1769827339,
  "storage_path": "2026/01/...",
  "message_count": 7,
  "used_models": ["qwen-turbo", "gpt-4"]  // 新增：使用的模型列表
}
```

## 新功能

### 1. 树形对话结构

支持从任意消息分支出新的对话路径：

```
用户: 我是谁？
├─ 助手A: 您是用户...
│  └─ 用户: 可以的
│     └─ 助手A: 好的...
└─ 助手B: 从哲学角度...（并行响应）
```

### 2. 并行响应

可以同时使用多个模型回答同一个问题，生成多个并行的回复分支。

### 3. 动态 System Prompt

在对话中途可以插入 `role: "system"` 的消息，改变后续对话的行为：

```json
{
  "id": "msg_uuid_006",
  "parent_id": "msg_uuid_005",
  "role": "system",
  "content": "现在请用英语回答",
  "type": "text",
  "created_at": 1769827500,
  "children_ids": []
}
```

## API 变更

### 新增 API

#### 1. 插入动态 System Prompt
```http
POST /sessions/{session_id}/system-prompt
Content-Type: application/json

{
  "parent_id": "msg_xxx",  // 在哪条消息后插入
  "content": "现在请用更专业的语气回答"
}
```

### 修改的 API

#### 1. 发送消息（支持从指定消息分支）
```http
POST /chat
Content-Type: application/json

{
  "message": "你好",
  "parent_id": "msg_xxx"  // 可选：从哪条消息继续对话
}
```

#### 2. 消息管理（使用 ID 而非索引）
```http
# 更新消息
PUT /sessions/{session_id}/messages/{message_id}

# 删除消息（自动处理子消息）
POST /sessions/{session_id}/messages/delete
{
  "message_ids": ["msg_xxx", "msg_yyy"]
}
```

## 数据迁移

### 自动迁移脚本

运行以下命令迁移现有数据：

```bash
python3 migrate_data_to_tree_structure.py
```

迁移特性：
- ✅ 自动备份原文件（`.backup.json`）
- ✅ 生成唯一消息 ID
- ✅ 建立父子关系（parent_id 和 children_ids）
- ✅ 为 assistant 消息添加 model_info
- ✅ 更新索引文件

### 回滚方法

如需回滚到旧版本：

```bash
# 1. 删除新格式文件
rm backend/data/storage/*/*.json
rm backend/data/sessions_index.json

# 2. 恢复备份
find backend/data -name "*.backup.json" -exec bash -c 'mv "$1" "${1%.backup.json}"' _ {} \;
```

## 存储架构

### 目录结构

```
backend/data/
├── sessions_index.json          # 轻量级索引（快速列表）
└── storage/
    └── YYYY/                     # 按年分组
        └── MM/                   # 按月分组
            └── session_id.json   # 会话文件（完整内容）
```

### 优势

- 📁 按月分组，方便归档和管理
- 🚀 索引与内容分离，列表加载速度快
- 💾 单会话读取，按需加载，节省内存
- 🔍 便于搜索和备份特定时间段的会话

## 兼容性

### 后端

- ✅ 完全重写会话存储服务
- ✅ 所有 API 已适配新格式
- ✅ 保持向后兼容（通过迁移脚本）

### 前端

前端需要适配以下变化：

1. **消息列表渲染**
   - 使用 `msg.id` 代替索引
   - 支持渲染树形结构（可选）
   - 显示模型信息和使用统计

2. **消息操作**
   - 更新/删除使用 `message_id` 而非索引
   - 发送消息时可指定 `parent_id` 实现分支

3. **会话列表**
   - 显示 `used_models` 标签
   - 显示消息数量 `message_count`

## 测试验证

运行测试脚本验证数据结构：

```bash
python3 test_new_structure.py
```

测试覆盖：
- ✅ 加载会话索引
- ✅ 加载会话详情（树形结构）
- ✅ 创建新会话
- ✅ 插入动态 System Prompt
- ✅ 消息父子关系
- ✅ 模型信息记录

## 性能对比

| 操作 | 旧结构 | 新结构 | 提升 |
|------|--------|--------|------|
| 加载会话列表 | 加载所有消息 | 仅加载索引 | ~10x |
| 打开会话 | 即时 | 按需加载 | 相同 |
| 保存消息 | 全量保存 | 增量更新索引 | ~2x |
| 存储空间 | 单文件 | 按月分组 | 便于管理 |

## 注意事项

1. **消息 ID 唯一性**：使用 UUID 确保全局唯一
2. **父子关系维护**：删除消息时自动处理子消息
3. **索引同步**：每次保存会话自动更新索引
4. **备份策略**：重要操作前建议先备份

## 未来扩展

基于新的树形结构，可以实现：

- 🌳 多分支对话可视化
- 🔄 对话路径回溯和切换
- 🤖 多模型并行对比
- 📊 对话数据分析（使用的模型、Token 统计等）
- 🎯 智能推荐最佳回复分支

## 相关文件

- `backend/api/models.py` - 数据模型定义
- `backend/services/session_storage.py` - 存储服务
- `backend/api/routes.py` - API 路由
- `migrate_data_to_tree_structure.py` - 数据迁移脚本
- `test_new_structure.py` - 测试脚本

## 问题反馈

如遇到问题，请检查：
1. 迁移脚本是否成功执行
2. 备份文件是否存在
3. 运行测试脚本查看详细错误

---

**重构完成日期**: 2026-01-31  
**状态**: ✅ 已完成并测试通过

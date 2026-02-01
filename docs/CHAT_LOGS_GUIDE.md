# 聊天消息日志使用指南

## 🎯 快速开始

### 查看实时日志
```bash
# 方法1: 使用提供的脚本（推荐）
./view_chat_logs.sh

# 方法2: 直接查看今天的日志
tail -f logs/chat_history/chat_$(date +%Y%m%d).log

# 方法3: 查看所有今天的日志
cat logs/chat_history/chat_$(date +%Y%m%d).log
```

## 📂 日志文件说明

### 日志位置
```
logs/chat_history/
├── chat_20260131.log  # 2026年1月31日的日志
├── chat_20260201.log  # 2026年2月1日的日志
└── ...
```

### 日志按天分文件
- 每天自动创建新的日志文件
- 文件名格式：`chat_YYYYMMDD.log`
- 自动创建目录（如果不存在）

## 📊 日志内容说明

每次聊天请求会记录以下信息：

### 1. 请求摘要
```
================================================================================
📊 请求摘要
会话ID: session_abc123
历史消息数: 4          ← 包含多少条历史消息
并行模型数: 1          ← 使用多少个模型
用户消息: 如何学习Python？
================================================================================
```

### 2. 发送的完整消息
```
================================================================================
📤 发送请求到模型
会话ID: session_abc123
模型: gpt-4, gpt-3.5-turbo
配置: {"temperature": 0.7, "top_p": 1.0, "parallel": true}

发送的消息历史（共 5 条）:    ← 这里显示发送了几条消息
--------------------------------------------------------------------------------

消息 1 [SYSTEM]:             ← 系统提示词（如果有）
你是一个友好、专业的AI助手

消息 2 [USER]:               ← 用户的历史消息
什么是Python？

消息 3 [ASSISTANT]:          ← AI的历史回复
Python是一种高级编程语言...

消息 4 [USER]:               ← 用户的历史消息
它有什么优点？

消息 5 [ASSISTANT]:          ← AI的历史回复
Python的主要优点包括...

消息 6 [USER]:               ← 用户的最新消息
如何学习Python？

--------------------------------------------------------------------------------
```

### 3. 接收的响应
```
================================================================================
📥 接收到模型响应
会话ID: session_abc123
模型: gpt-4
模型索引: 0
耗时: 3.45 秒
--------------------------------------------------------------------------------

响应内容:
学习Python可以按照以下步骤...（完整的AI回复）

--------------------------------------------------------------------------------
完整响应长度: 523 字符
================================================================================
```

## 🔍 日志查看技巧

### 查看特定会话的所有记录
```bash
grep "session_abc123" logs/chat_history/chat_20260131.log
```

### 查看所有发送的消息摘要
```bash
grep -A 4 "📊 请求摘要" logs/chat_history/chat_20260131.log
```

### 查看所有接收的响应摘要
```bash
grep -A 5 "📥 接收到模型响应" logs/chat_history/chat_20260131.log
```

### 查看错误信息
```bash
grep "❌" logs/chat_history/chat_20260131.log
```

### 统计今天处理了多少次请求
```bash
grep -c "📤 发送请求到模型" logs/chat_history/chat_$(date +%Y%m%d).log
```

### 查看最近5次对话
```bash
grep -B 2 -A 30 "📤 发送请求到模型" logs/chat_history/chat_$(date +%Y%m%d).log | tail -200
```

## 💡 实用示例

### 示例1: 检查是否发送了历史消息

1. 启动应用并发送几条消息
2. 查看日志：
```bash
./view_chat_logs.sh
# 选择选项 4: 查看最近的5次完整对话
```

3. 在日志中你会看到类似：
```
发送的消息历史（共 7 条）:    ← 这里显示共发送了7条消息
```

### 示例2: 调试对话问题

如果AI回复不符合预期：

1. 查看日志确认发送的消息：
```bash
./view_chat_logs.sh
# 选择选项 1: 查看今天的日志
```

2. 检查：
   - ✅ 系统提示词是否正确？
   - ✅ 历史消息是否完整？
   - ✅ 温度参数是否合适？
   - ✅ 使用的模型是否正确？

### 示例3: 监控实时消息流

```bash
./view_chat_logs.sh
# 选择选项 2: 实时监控日志

# 然后在另一个终端或浏览器中使用应用
# 你会实时看到所有发送和接收的消息
```

## 📈 日志分析

### 分析历史消息数量分布
```bash
grep "历史消息数:" logs/chat_history/chat_$(date +%Y%m%d).log | \
  awk '{print $3}' | \
  sort -n | \
  uniq -c
```

输出示例：
```
  10 2      # 10次请求发送了2条历史消息
  15 4      # 15次请求发送了4条历史消息
   5 8      # 5次请求发送了8条历史消息
```

### 分析响应时间
```bash
grep "耗时:" logs/chat_history/chat_$(date +%Y%m%d).log | \
  awk '{print $2}' | \
  awk '{sum+=$1; count++} END {print "平均耗时:", sum/count, "秒"}'
```

### 查找长对话
```bash
grep "历史消息数:" logs/chat_history/chat_$(date +%Y%m%d).log | \
  awk '$3 > 10 {print}'
```

## ⚙️ 配置选项

### 修改日志级别

编辑 `backend/utils/chat_logger.py`:
```python
chat_logger.setLevel(logging.DEBUG)  # 更详细的日志
chat_logger.setLevel(logging.WARNING)  # 只记录警告和错误
```

### 修改日志格式

编辑 `backend/utils/chat_logger.py`:
```python
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S.%f'
)
```

### 日志文件大小管理

如果日志文件太大，可以添加日志轮转：
```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
```

## 🔒 隐私和安全

### 注意事项

⚠️ 日志文件包含：
- 用户的所有消息内容
- AI的所有回复内容
- 系统提示词

### 建议

1. **不要提交日志到版本控制**
   ```bash
   # .gitignore 已包含
   logs/chat_history/
   ```

2. **定期清理旧日志**
   ```bash
   # 删除30天前的日志
   find logs/chat_history/ -name "chat_*.log" -mtime +30 -delete
   ```

3. **限制日志访问权限**
   ```bash
   chmod 600 logs/chat_history/chat_*.log
   ```

## 📚 相关文档

- [CHAT_HISTORY_MECHANISM.md](./CHAT_HISTORY_MECHANISM.md) - 详细的消息历史机制说明
- [系统提示词功能说明](./docs/系统提示词功能说明.md) - 系统提示词配置

## 🐛 故障排除

### 问题1: 日志文件不存在

**原因**: 应用还没有处理过任何聊天请求

**解决**: 
- 启动应用
- 发送一条消息
- 日志会自动创建

### 问题2: 日志权限错误

**解决**:
```bash
chmod 755 logs/chat_history/
chmod 644 logs/chat_history/chat_*.log
```

### 问题3: 日志内容被截断

**原因**: 单条消息或响应太长，被自动截断（限制500/1000字符）

**解决**: 编辑 `backend/utils/chat_logger.py`，修改截断长度：
```python
display_content = content if len(content) <= 2000 else content[:2000] + "..."
```

## 📞 获取帮助

查看日志时遇到问题？

1. 检查日志目录权限
2. 确认应用正在运行
3. 查看应用主日志: `logs/app.log`
4. 联系技术支持

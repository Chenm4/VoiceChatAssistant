# Logger 未定义问题修复

**问题时间**: 2026-02-01  
**错误信息**: `name 'logger' is not defined`  
**问题文件**: `backend/services/streaming_asr.py`

---

## 🐛 问题描述

### 错误现象

用户尝试开始录音时，前端显示错误：

```
启动录音失败: 启动任务失败: name 'logger' is not defined
```

### 错误追踪

错误发生在 `backend/api/routes.py` 的 `start_recording()` 函数中：

```python
# 检查任务是否立即失败
if task.done() and task.exception():
    error = task.exception()
    logger.error(f"❌ [启动失败] 任务失败: {error}")
    raise Exception(f"启动任务失败: {error}")  # ← 这里抛出的异常
```

异常信息显示：`name 'logger' is not defined`

这说明在 `streaming_asr.py` 的某个地方使用了未定义的 `logger` 变量。

---

## 🔍 问题分析

### 代码检查

在 `backend/services/streaming_asr.py` 文件中：

```python
class StreamingASR:
    def __init__(self, preload: bool = False) -> None:
        self.logger = get_asr_logger()  # ✅ 正确定义
        # ...
    
    async def start_streaming(self):
        # ❌ 错误：使用全局 logger 而不是 self.logger
        logger.info("🚀 [实时识别] 开始启动...")
        logger.info("=" * 80)
        
        try:
            logger.info(f"📌 [事件循环] 保存事件循环引用: {self.loop}")
            logger.info("🎤 [立即启动录音] 开始录音线程...")
            # ... 更多使用 logger 的地方
        except Exception as e:
            logger.error(f"❌ [启动失败] {e}")
```

**问题根源**：

1. 在 `__init__()` 中正确定义了 `self.logger`
2. 但在类的方法中，有些地方使用了 `logger` 而不是 `self.logger`
3. Python 在方法内部找不到名为 `logger` 的变量，抛出 `NameError`

### 受影响的代码位置

通过 grep 搜索发现，有 **55 处**使用了错误的 `logger.` 而不是 `self.logger.`：

```python
# ❌ 错误的用法（55处）
logger.info("...")
logger.error("...")
logger.warning("...")
logger.debug("...")

# ✅ 正确的用法
self.logger.info("...")
self.logger.error("...")
self.logger.warning("...")
self.logger.debug("...")
```

---

## ✅ 修复方案

### 修复方法

使用 Python 脚本批量替换所有的 `logger.` 为 `self.logger.`：

```python
import re

with open('backend/services/streaming_asr.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换所有缩进后的 logger.，但不替换已经是 self.logger. 的
content = re.sub(r'(\s+)(?<!self\.)logger\.', r'\1self.logger.', content)

with open('backend/services/streaming_asr.py', 'w', encoding='utf-8') as f:
    f.write(content)
```

### 修复前后对比

#### 修复前

```python
class StreamingASR:
    def __init__(self, preload: bool = False) -> None:
        self.logger = get_asr_logger()  # ✅ 定义
    
    async def start_streaming(self):
        logger.info("=" * 80)  # ❌ 使用全局 logger
        if self.preloaded:
            logger.info("🚀 [实时识别] 开始启动...")  # ❌
        else:
            logger.info("🚀 [实时识别] 开始启动...")  # ❌
        logger.info("=" * 80)  # ❌
        
        try:
            logger.info(f"📌 [事件循环] ...")  # ❌
            # ... 更多错误使用
        except Exception as e:
            logger.error(f"❌ [启动失败] {e}")  # ❌
```

#### 修复后

```python
class StreamingASR:
    def __init__(self, preload: bool = False) -> None:
        self.logger = get_asr_logger()  # ✅ 定义
    
    async def start_streaming(self):
        self.logger.info("=" * 80)  # ✅ 使用实例 logger
        if self.preloaded:
            self.logger.info("🚀 [实时识别] 开始启动...")  # ✅
        else:
            self.logger.info("🚀 [实时识别] 开始启动...")  # ✅
        self.logger.info("=" * 80)  # ✅
        
        try:
            self.logger.info(f"📌 [事件循环] ...")  # ✅
            # ... 全部修复
        except Exception as e:
            self.logger.error(f"❌ [启动失败] {e}")  # ✅
```

---

## 📊 修复统计

| 项目 | 数量 |
|------|------|
| 修复的文件 | 1 个 |
| 修复的位置 | 55 处 |
| 修复的方法 | `start_streaming()`, `_start_audio_capture()`, `_send_audio_loop()`, `_receive_results_loop()`, `_save_audio()`, `stop_streaming()` |

---

## 🎯 相关问题预防

### 1. 类中使用 Logger 的正确方式

**原则**：在类中，logger 应该作为实例变量，而不是全局变量。

```python
# ✅ 正确的做法
class MyClass:
    def __init__(self):
        self.logger = get_logger()  # 实例变量
    
    def method(self):
        self.logger.info("message")  # 使用 self.logger

# ❌ 错误的做法
logger = get_logger()  # 全局变量

class MyClass:
    def method(self):
        logger.info("message")  # 使用全局 logger（不推荐）
```

### 2. 为什么要使用实例变量

**优点**：

1. **封装性**：logger 属于类的一部分，不污染全局命名空间
2. **灵活性**：不同实例可以有不同的 logger 配置
3. **可测试性**：更容易 mock 和测试
4. **避免错误**：不会出现 `NameError`

**示例**：

```python
# ✅ 好处：每个实例可以有不同的 logger
class ServiceA:
    def __init__(self):
        self.logger = get_logger("service_a")

class ServiceB:
    def __init__(self):
        self.logger = get_logger("service_b")
```

### 3. 代码检查工具

使用以下命令检查是否有未定义的 logger：

```bash
# 检查是否有使用全局 logger 的地方
grep -n "^\s\+logger\." backend/services/*.py

# 应该返回空结果（No matches found）
```

---

## 🧪 测试建议

### 测试场景

1. **正常录音流程**
   - 开始录音 → 录音成功 → 停止录音 → 识别成功
   - ✅ 验证不会出现 `NameError`

2. **启动失败场景**
   - 模拟麦克风不可用
   - ✅ 验证错误信息正确，不是 `logger not defined`

3. **日志输出**
   - 检查日志文件
   - ✅ 验证所有日志都正常输出

### 测试命令

```bash
# 重启后端服务
cd /Users/hb952/code/yuyinshibie
./start.sh

# 测试录音功能
# 在前端点击录音按钮

# 查看日志
tail -f logs/asr.log
```

---

## 📝 代码规范建议

### 1. Logger 命名规范

```python
# ✅ 推荐：使用 self.logger
class MyClass:
    def __init__(self):
        self.logger = get_logger()

# ❌ 不推荐：使用全局 logger
logger = get_logger()
```

### 2. 导入规范

```python
# ✅ 正确的导入
from backend.utils.logger import get_asr_logger

class StreamingASR:
    def __init__(self):
        self.logger = get_asr_logger()  # 在 __init__ 中初始化
```

### 3. 类型注解

```python
import logging
from typing import Optional

class StreamingASR:
    def __init__(self) -> None:
        self.logger: logging.Logger = get_asr_logger()  # 添加类型注解
```

---

## 🔗 相关文件

- `backend/services/streaming_asr.py` - 修复的主要文件
- `backend/utils/logger.py` - Logger 工具类
- `backend/services/audio_recorder.py` - 同样使用 self.logger 的示例
- `backend/services/voice_recognizer.py` - 同样使用 self.logger 的示例

---

## 📌 总结

### 问题本质

**变量作用域错误** - 在类方法中使用了未定义的全局变量 `logger`，而应该使用实例变量 `self.logger`。

### 修复核心

**批量替换** - 将所有的 `logger.` 替换为 `self.logger.`，确保使用实例变量。

### 经验教训

1. **在类中使用 logger 时，应该作为实例变量**
2. **使用 self.logger 而不是全局 logger**
3. **代码审查时注意变量作用域**
4. **使用工具检查潜在的 NameError**

---

**修复完成！所有 logger 使用现在都正确了！** 🎉

**文档版本**: v1.0  
**最后更新**: 2026-02-01  
**修复人员**: AI Assistant  
**修复方法**: 批量替换（55处）

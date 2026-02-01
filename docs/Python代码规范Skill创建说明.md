# Python 代码规范 Skill 创建说明

## 创建完成

我已经成功创建了一个 Python 代码规范和注释的 skill，存储在你的个人 skill 目录中。

## Skill 信息

- **名称**：`python-code-style`
- **位置**：`~/.cursor/skills/python-code-style/`
- **作用域**：个人技能（在你所有的项目中可用）

## 文件结构

```
~/.cursor/skills/python-code-style/
├── SKILL.md          # 主要规范说明（548 行）
├── examples.md       # 详细示例代码
└── README.md         # 使用说明文档
```

## 核心功能

### 1. 强制函数封装
- 确保所有代码都在函数体内
- 避免全局作用域的裸代码
- 提供 `main()` 函数作为入口

### 2. Logger 工具类使用
- 强制使用项目的 `backend.utils.logger`
- 禁止使用 `print()` 输出
- 支持以下 logger 函数：
  - `get_app_logger()` - 应用主日志
  - `get_asr_logger()` - 语音识别日志
  - `get_api_logger()` - API 日志
  - `log_info()`, `log_error()`, `log_warning()`, `log_debug()` - 便捷函数

### 3. 完整的文档字符串
- 模块级文档字符串
- 类级文档字符串
- 函数文档字符串（包含 Args、Returns、Raises、Example）
- 遵循 Google Style Guide 格式

### 4. 类型注解
- 函数参数类型注解
- 返回值类型注解
- 类属性类型注解
- 使用 `typing` 模块的类型

### 5. PEP 8 格式规范
- 命名规范（类、函数、变量、常量）
- 导入规范（标准库、第三方库、本地模块）
- 空行规范（模块、类、函数之间）
- 行长度限制（79 字符）
- 缩进规范（4 个空格）

### 6. 行内注释
- 为复杂逻辑添加解释性注释
- 使用 TODO、FIXME、NOTE 等标记
- 注释清晰、简洁

## 自动触发条件

当你的消息包含以下关键词时，这个 skill 会自动激活：

- "添加注释"
- "规范代码"
- "格式化 Python 代码"
- "文档字符串"
- "docstring"
- "代码规范"
- "PEP 8"
- "logging"
- "logger"

## 使用示例

### 示例 1：规范单个文件

```
请帮我规范 backend/services/user_service.py 文件的代码
```

AI 会：
1. 读取文件内容
2. 检查是否符合规范
3. 添加缺失的注释和文档字符串
4. 修复格式问题
5. 将 print() 替换为 logger
6. 确保所有代码在函数体内

### 示例 2：规范代码片段

```
请帮我规范这段代码：

def process(data):
    print("processing")
    for item in data:
        if item > 0:
            print(item)
```

AI 会提供规范后的代码：

```python
def process_positive_numbers(data: List[int]) -> None:
    """
    处理并输出正数
    
    Args:
        data: 数字列表
    """
    logger = get_app_logger()
    logger.info("开始处理数据")
    
    # 筛选并输出正数
    for item in data:
        if item > 0:
            logger.info(f"正数: {item}")
```

### 示例 3：批量规范目录

```
请规范 backend/services/ 目录下所有 Python 文件
```

AI 会：
1. 扫描目录下的所有 .py 文件
2. 逐个文件进行规范检查
3. 提供修改建议
4. 可以选择一次性应用或逐个确认

## 规范检查清单

使用这个 skill 后，你的代码应该满足：

- [x] 所有代码都在函数体内
- [x] 使用 logger 工具类，没有 print()
- [x] 每个函数都有完整的文档字符串
- [x] 文档字符串包含 Args、Returns、Raises
- [x] 使用类型注解
- [x] 遵循 PEP 8 命名规范
- [x] 每行不超过 79 个字符
- [x] 导入语句正确分组
- [x] 复杂逻辑有行内注释
- [x] 异常处理完整
- [x] 资源正确释放

## Logger 工具类 API

你的项目使用自定义的 logger 工具类（`backend/utils/logger.py`）：

### 获取 Logger 实例

```python
from backend.utils.logger import get_app_logger, get_asr_logger, get_api_logger

# 应用主日志
logger = get_app_logger()

# 语音识别日志
asr_logger = get_asr_logger()

# API 日志
api_logger = get_api_logger()
```

### 使用便捷函数

```python
from backend.utils.logger import log_info, log_error, log_warning, log_debug

log_info("信息日志")
log_error("错误日志", exc_info=True)
log_warning("警告日志")
log_debug("调试日志")
```

### Logger 方法

```python
logger.info("信息日志")
logger.error("错误日志", exc_info=True)
logger.warning("警告日志")
logger.debug("调试日志")
```

## 文档字符串模板

### 函数模板

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    简短的一句话描述
    
    详细描述（可选），说明函数的具体行为和注意事项。
    
    Args:
        param1: 参数1的说明
        param2: 参数2的说明
        
    Returns:
        ReturnType: 返回值的说明
        
    Raises:
        ExceptionType: 异常说明
        
    Example:
        >>> result = function_name(arg1, arg2)
        >>> print(result)
        expected_output
    """
    pass
```

### 类模板

```python
class ClassName:
    """
    简短的一句话描述
    
    详细描述（可选）。
    
    Attributes:
        attr1: 属性1的说明
        attr2: 属性2的说明
        
    Example:
        >>> obj = ClassName()
        >>> obj.method()
    """
    
    def __init__(self, param: Type) -> None:
        """
        初始化类实例
        
        Args:
            param: 参数说明
        """
        pass
```

### 模块模板

```python
"""
模块名称

模块的详细描述，说明模块的主要功能和用途。

Author: 作者名
Date: 创建日期
"""
```

## 常见规范问题

### 问题 1：使用 print() 输出

❌ **错误**：
```python
print("开始处理")
print(f"结果: {result}")
```

✅ **正确**：
```python
logger = get_app_logger()
logger.info("开始处理")
logger.info(f"结果: {result}")
```

### 问题 2：全局作用域的代码

❌ **错误**：
```python
import json
data = load_data()
result = process(data)
```

✅ **正确**：
```python
import json
from backend.utils.logger import get_app_logger

def main() -> None:
    """主函数"""
    data = load_data()
    result = process(data)

if __name__ == "__main__":
    main()
```

### 问题 3：缺少文档字符串

❌ **错误**：
```python
def calculate(a, b):
    return a + b
```

✅ **正确**：
```python
def calculate(a: float, b: float) -> float:
    """
    计算两个数的和
    
    Args:
        a: 第一个数
        b: 第二个数
        
    Returns:
        float: 两数之和
    """
    return a + b
```

### 问题 4：缺少类型注解

❌ **错误**：
```python
def process_data(data, config=None):
    pass
```

✅ **正确**：
```python
def process_data(data: List[Dict], config: Optional[Dict] = None) -> bool:
    """处理数据"""
    pass
```

### 问题 5：异常处理不完整

❌ **错误**：
```python
def read_file(path):
    f = open(path)
    data = f.read()
    return data
```

✅ **正确**：
```python
def read_file(path: str) -> str:
    """
    读取文件内容
    
    Args:
        path: 文件路径
        
    Returns:
        str: 文件内容
        
    Raises:
        FileNotFoundError: 文件不存在
        IOError: 读取失败
    """
    logger = get_app_logger()
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
        logger.info(f"成功读取文件: {path}")
        return data
    except FileNotFoundError:
        logger.error(f"文件不存在: {path}")
        raise
    except IOError as e:
        logger.error(f"读取文件失败: {e}", exc_info=True)
        raise
```

## 配合工具使用

### Black（代码格式化）

```bash
# 格式化单个文件
black your_file.py

# 格式化整个目录
black backend/

# 检查但不修改
black --check your_file.py
```

### Flake8（代码检查）

```bash
# 检查单个文件
flake8 your_file.py

# 检查整个目录
flake8 backend/

# 忽略特定错误
flake8 --ignore=E501,W503 your_file.py
```

### MyPy（类型检查）

```bash
# 类型检查
mypy your_file.py

# 严格模式
mypy --strict your_file.py
```

### isort（导入排序）

```bash
# 排序导入
isort your_file.py

# 检查但不修改
isort --check-only your_file.py
```

## 技巧和建议

### 技巧 1：先写文档字符串

在实现函数前先写文档字符串，明确函数的输入输出和行为。

### 技巧 2：使用类型注解

类型注解不仅帮助 IDE 提供更好的补全，也让代码更易读。

### 技巧 3：合理使用日志级别

- `debug`: 详细的调试信息
- `info`: 一般的信息日志
- `warning`: 警告信息，不影响运行
- `error`: 错误信息，需要关注

### 技巧 4：异常处理要具体

捕获具体的异常类型，而不是笼统的 `Exception`。

### 技巧 5：使用上下文管理器

对于文件、数据库连接等资源，使用 `with` 语句自动管理。

## 下一步

1. 尝试使用这个 skill 规范你的代码
2. 查看 [examples.md](~/.cursor/skills/python-code-style/examples.md) 获取更多示例
3. 根据项目需求调整规范
4. 向团队分享这个 skill

## 反馈

如果你发现规范不合理或有改进建议，可以直接编辑 `~/.cursor/skills/python-code-style/SKILL.md` 文件。

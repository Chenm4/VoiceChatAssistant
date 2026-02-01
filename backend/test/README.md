# 测试文档

这个文件夹包含了各种测试脚本，用于验证系统的各个组件是否正常工作。

## 测试脚本

### 1. test_config.py - 配置测试

测试所有配置文件是否正确设置。

```bash
python backend/test/test_config.py
```

**测试内容：**
- 火山引擎配置（appid, token, cluster）
- OpenAI 配置（API key, 模型列表, base URL）
- 音频配置（采样率、声道数等）
- 快捷键配置

### 2. test_asr.py - 语音识别测试

测试火山引擎语音识别功能。

```bash
python backend/test/test_asr.py
```

**测试内容：**
- 火山引擎配置验证
- 音频文件识别
- 可以使用现有音频或创建测试音频

**使用方法：**
1. 直接运行脚本
2. 选择测试方式：
   - 使用现有音频文件
   - 创建测试音频文件（需要 numpy）
   - 跳过音频测试

### 3. test_api.py - API 接口测试

测试后端 API 接口是否正常。

**前置条件：** 需要先启动后端服务

```bash
# 启动后端服务
python backend/main.py

# 在另一个终端运行测试
python backend/test/test_api.py
```

**测试内容：**
- 服务健康检查
- 配置接口
- 会话管理接口
- 聊天接口（流式）
- 录音接口

## 快速测试流程

### 完整测试流程

```bash
# 1. 测试配置
python backend/test/test_config.py

# 2. 启动后端服务（在新终端）
python backend/main.py

# 3. 测试 API 接口（在另一个终端）
python backend/test/test_api.py

# 4. 测试语音识别（可选）
python backend/test/test_asr.py
```

### 快速诊断问题

如果遇到问题，按以下顺序诊断：

1. **配置问题**
   ```bash
   python backend/test/test_config.py
   ```
   检查所有配置是否正确设置

2. **语音识别问题**
   ```bash
   python backend/test/test_asr.py
   ```
   测试火山引擎是否可以正常连接和识别

3. **API 接口问题**
   ```bash
   python backend/test/test_api.py
   ```
   测试后端接口是否正常响应

## 常见问题

### 1. 语音识别失败

**错误信息：** `识别失败，请确保说话清晰`

**可能原因：**
- 火山引擎配置错误（appid、token、cluster）
- 网络连接问题
- websockets 库版本不兼容
- 音频格式不正确

**解决方法：**
```bash
# 1. 检查配置
python backend/test/test_config.py

# 2. 测试语音识别
python backend/test/test_asr.py
```

### 2. API 接口无法连接

**错误信息：** `无法连接到服务`

**可能原因：**
- 后端服务未启动
- 端口被占用
- 防火墙阻止

**解决方法：**
```bash
# 检查服务是否运行
ps aux | grep "python.*main.py"

# 重新启动服务
python backend/main.py
```

### 3. 配置文件缺失字段

**错误信息：** `缺少必要字段`

**解决方法：**
检查 `config.py` 文件，确保所有必要字段都已设置：
- `VOLCENGINE_CONFIG`: appid, token, cluster
- `OPENAI_CONFIG`: api_key, models, base_url

## 依赖说明

测试脚本需要以下依赖：

```bash
# 基础依赖
pip install requests

# 语音识别测试（可选）
pip install numpy
```

## 测试结果说明

- ✅ 表示测试通过
- ❌ 表示测试失败
- ⚠️ 表示警告（功能可能受影响）

## 日志文件

测试过程中的详细日志存储在：
- `backend/logs/asr_*.log` - 语音识别日志
- `backend/logs/api_*.log` - API 接口日志

查看最近的日志：
```bash
tail -100 backend/logs/asr_$(date +%Y-%m-%d).log
tail -100 backend/logs/api_$(date +%Y-%m-%d).log
```

## 贡献测试

如果你想添加新的测试脚本：

1. 在 `backend/test/` 目录下创建新文件
2. 命名格式：`test_*.py`
3. 包含清晰的测试说明和结果输出
4. 更新本 README 文件

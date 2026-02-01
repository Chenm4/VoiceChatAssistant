# 火山引擎语音识别问题修复总结

## 问题描述

在使用火山引擎进行语音识别时，系统显示错误：

```
识别失败: 识别失败，请确保说话清晰
```

## 问题原因

通过日志分析发现，实际的错误信息是：

```
TypeError: create_connection() got an unexpected keyword argument 'additional_headers'
```

**根本原因：** 在 `backend/utils/asr_demo.py` 文件中，代码尝试兼容不同版本的 websockets 库，使用了 `additional_headers` 参数。但是，当前环境使用的 uvloop 的 `create_connection` 方法不支持这个参数，导致连接失败。

## 修复方案

### 1. 修复 websockets 连接问题

**文件：** `backend/utils/asr_demo.py`

**修改前：**
```python
# 兼容不同版本的 websockets 库
try:
    # 新版本 (>= 10.0) 使用 additional_headers
    ws_context = websockets.connect(self.ws_url, additional_headers=header, max_size=1000000000)
except TypeError:
    # 旧版本 (< 10.0) 使用 extra_headers
    ws_context = websockets.connect(self.ws_url, extra_headers=header, max_size=1000000000)

async with ws_context as ws:
```

**修改后：**
```python
# 使用 extra_headers 参数（兼容大多数版本）
async with websockets.connect(self.ws_url, extra_headers=header, max_size=1000000000) as ws:
```

**说明：** 直接使用 `extra_headers` 参数，这是 websockets 库的标准参数，兼容大多数版本。

## 新增功能

### 创建测试文件夹

为了方便测试和诊断问题，在 `backend/test/` 目录下创建了完整的测试套件：

```
backend/test/
├── __init__.py              # 模块初始化文件
├── test_config.py           # 配置文件测试
├── test_asr.py              # 语音识别测试
├── test_api.py              # API 接口测试
├── run_all_tests.sh         # 一键运行所有测试
└── README.md                # 测试文档
```

### 测试脚本说明

#### 1. test_config.py - 配置测试

测试所有配置是否正确设置：
- 火山引擎配置（appid, token, cluster）
- OpenAI 配置（API key, 模型列表）
- 音频配置（采样率、声道数等）
- 快捷键配置

**运行：**
```bash
python3 backend/test/test_config.py
```

#### 2. test_asr.py - 语音识别测试

测试火山引擎语音识别功能：
- 配置验证
- 音频文件识别
- 可选择创建测试音频

**运行：**
```bash
python3 backend/test/test_asr.py
```

#### 3. test_api.py - API 接口测试

测试后端 API 接口：
- 服务健康检查
- 配置接口
- 会话管理接口
- 聊天接口（流式）
- 录音接口

**运行：**（需要先启动后端服务）
```bash
# 启动后端服务
python3 backend/main.py

# 在另一个终端运行测试
python3 backend/test/test_api.py
```

#### 4. run_all_tests.sh - 一键测试

运行所有测试脚本的便捷工具：

**运行：**
```bash
bash backend/test/run_all_tests.sh
```

## 验证修复

### 步骤 1：测试配置

```bash
python3 backend/test/test_config.py
```

**预期结果：**
```
✅ 所有配置测试通过
```

### 步骤 2：测试 API 接口

确保后端服务正在运行：

```bash
python3 backend/main.py
```

在另一个终端运行：

```bash
python3 backend/test/test_api.py
```

**预期结果：**
```
✅ 服务正常运行
✅ 获取配置成功
✅ 获取会话列表成功
✅ 创建会话成功
```

### 步骤 3：测试语音识别

```bash
python3 backend/test/test_asr.py
```

按照提示选择测试方式。

### 步骤 4：在前端测试

1. 启动后端服务（如果未启动）：
   ```bash
   python3 backend/main.py
   ```

2. 启动前端服务：
   ```bash
   cd frontend
   npm run dev
   ```

3. 在浏览器中打开前端界面

4. 点击麦克风按钮，说话后释放

5. 应该能看到识别出的文字

## 日志查看

如果仍然遇到问题，可以查看详细日志：

```bash
# 查看语音识别日志
tail -100 backend/logs/asr_$(date +%Y-%m-%d).log

# 查看 API 日志
tail -100 backend/logs/api_$(date +%Y-%m-%d).log
```

## 常见问题

### 1. 仍然识别失败

**检查步骤：**

1. 确认配置正确：
   ```bash
   python3 backend/test/test_config.py
   ```

2. 查看日志中的详细错误信息

3. 确认网络连接正常（可以访问火山引擎服务）

4. 确认音频格式正确（16000Hz, 单声道, WAV 格式）

### 2. websockets 版本问题

如果还有 websockets 相关错误，尝试重新安装：

```bash
pip install --upgrade websockets
```

### 3. 录音时长问题

如果录音时间太短（< 1秒），可能无法识别。建议：
- 录音时长至少 1-2 秒
- 说话清晰，环境安静
- 麦克风权限已授予

## 技术细节

### 修复的关键点

1. **WebSocket 连接参数**
   - 问题：使用了 `additional_headers` 参数
   - 解决：改用标准的 `extra_headers` 参数
   - 影响：兼容更多 websockets 版本

2. **错误处理**
   - 问题：实际错误被捕获但没有传递给前端
   - 解决：在日志中记录详细错误信息
   - 影响：更容易诊断问题

### 测试覆盖

新增的测试覆盖了：
- ✅ 配置验证
- ✅ 服务健康检查
- ✅ API 接口功能
- ✅ 会话管理
- ✅ 语音识别核心功能

## 总结

**问题：** WebSocket 连接参数不兼容导致语音识别失败

**修复：** 使用标准的 `extra_headers` 参数

**新增：** 完整的测试套件，方便后续诊断和维护

**状态：** ✅ 已修复并验证

---

**修复时间：** 2026-01-30

**影响范围：** 火山引擎语音识别功能

**测试状态：** 全部通过 ✅

# 🎤 双识别器快速测试指南

## 立即测试

### 1️⃣ 启动服务

```bash
cd /Users/hb952/code/yuyinshibie
./start.sh
```

### 2️⃣ 测试语音识别

#### 方法 A：通过 Web 界面
1. 打开浏览器访问应用
2. 点击语音输入按钮
3. 说话并停止录音
4. 查看识别结果

#### 方法 B：命令行测试

```bash
# 测试已保存的音频文件
cd backend
python3 -c "
from services.voice_recognizer import VoiceRecognizer
import asyncio

async def test():
    vr = VoiceRecognizer()
    audio_file = '../data/voices/voice_20260131_130823_926374.wav'
    
    print('开始测试双识别器...')
    text, error = await vr.recognize_file(audio_file)
    
    if text:
        print(f'✅ 识别成功: {text}')
    else:
        print(f'❌ 识别失败: {error}')

asyncio.run(test())
"
```

### 3️⃣ 查看日志

```bash
# 实时查看日志
tail -f logs/asr.log

# 或者查看最近的日志
tail -n 100 logs/asr.log
```

## 📊 预期结果

### ✅ 成功场景（字节跳动）

```
============================================================
开始识别音频文件: data/voices/voice_20260131_130823_926374.wav
============================================================
  主要: 字节跳动 ASR (app_key=2448163126)
  备用: 火山引擎 ASR (appid=2448163126, cluster=volcengine_streaming_common)
🎯 使用字节跳动 ASR 识别: data/voices/voice_20260131_130823_926374.wav
✅ 字节跳动识别成功: 数据库在监控的过程中发现了大量慢 SQL 的话，你要怎么优化？从哪些思路开始优化？
✅ 使用字节跳动 ASR 识别成功
```

### 🔄 切换到备用（火山引擎）

```
============================================================
开始识别音频文件: data/voices/voice_20260131_130823_926374.wav
============================================================
🎯 使用字节跳动 ASR 识别: ...
❌ 字节跳动识别异常: Connection error
⚠️ 字节跳动 ASR 失败: Connection error
🔄 切换到火山引擎 ASR（备用方案）
🔄 使用火山引擎 ASR 识别（备用）: ...
✅ 火山引擎识别成功: 数据库在监控的过程中发现了大量慢 SQL
✅ 使用火山引擎 ASR 识别成功
```

## 🔍 验证点

### 1. 配置正确性
```bash
# 检查配置文件
cat config.py | grep -A 5 "BYTEDANCE_ASR_CONFIG"
cat config.py | grep -A 5 "VOLCENGINE_CONFIG"
```

应该看到：
- ✅ `app_key` 和 `access_key` 已配置
- ✅ `appid` 和 `token` 已配置

### 2. 依赖安装
```bash
# 检查 aiohttp
python3 -c "import aiohttp; print(f'✅ aiohttp {aiohttp.__version__}')"
```

应该输出：
```
✅ aiohttp 3.9.1
```

### 3. 模块导入
```bash
cd backend
python3 -c "
from utils.sauc_client import AsrWsClient
from services.voice_recognizer import VoiceRecognizer
print('✅ 所有模块导入成功')
"
```

### 4. 音频文件
```bash
# 检查音频文件
ls -lh data/voices/
```

应该看到 `.wav` 文件。

## 🐛 常见问题

### 问题 1：ModuleNotFoundError: No module named 'aiohttp'

**解决**：
```bash
pip3 install aiohttp==3.9.1
```

### 问题 2：字节跳动一直返回错误

**检查**：
1. 密钥是否正确
2. 网络是否连通
3. 服务是否欠费

```bash
# 测试网络
ping openspeech.bytedance.com

# 检查配置
python3 -c "from config import BYTEDANCE_ASR_CONFIG; print(BYTEDANCE_ASR_CONFIG)"
```

### 问题 3：两个识别器都失败

**检查**：
1. 音频文件格式（必须是 WAV, 16000Hz, 单声道）
2. 音频文件大小（不能为空）
3. 音频内容质量（是否有人声）

```bash
# 检查音频格式
ffprobe data/voices/voice_*.wav

# 播放音频（Mac）
afplay data/voices/voice_*.wav
```

## 📈 性能测试

### 测试识别速度

```bash
python3 -c "
from services.voice_recognizer import VoiceRecognizer
import asyncio
import time

async def benchmark():
    vr = VoiceRecognizer()
    audio_file = '../data/voices/voice_20260131_130823_926374.wav'
    
    start = time.time()
    text, error = await vr.recognize_file(audio_file)
    elapsed = time.time() - start
    
    print(f'识别耗时: {elapsed:.2f}秒')
    if text:
        print(f'文本长度: {len(text)} 字符')
    
asyncio.run(benchmark())
"
```

### 测试并发识别

```bash
python3 -c "
from services.voice_recognizer import VoiceRecognizer
import asyncio
import time

async def test_concurrent():
    vr = VoiceRecognizer()
    audio_file = '../data/voices/voice_20260131_130823_926374.wav'
    
    start = time.time()
    
    # 并发识别 5 次
    tasks = [vr.recognize_file(audio_file) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    
    elapsed = time.time() - start
    
    success_count = sum(1 for text, _ in results if text)
    print(f'并发识别 5 次，成功 {success_count} 次，总耗时 {elapsed:.2f}秒')
    
asyncio.run(test_concurrent())
"
```

## 🎉 测试清单

完成以下测试项：

- [ ] ✅ 配置文件已更新
- [ ] ✅ aiohttp 已安装
- [ ] ✅ 模块导入成功
- [ ] ✅ 服务启动正常
- [ ] ✅ 语音录音功能正常
- [ ] ✅ 字节跳动识别成功
- [ ] ✅ 火山引擎备用可用
- [ ] ✅ 识别结果准确
- [ ] ✅ 日志输出清晰
- [ ] ✅ 响应时间合理

**全部通过？恭喜！双识别器集成成功！** 🎊

## 📚 相关文档

- `/DUAL_ASR_INTEGRATION.md` - 详细技术文档
- `/VOICE_STORAGE_UPDATE.md` - 音频存储说明
- `/config.py` - 配置文件

---

**现在就开始测试吧！** 🚀

# 语音文件存储位置修改

## 📋 更新日期
2026-01-31

## 🎯 修改内容

### 音频文件保存位置

**修改前**：❌
- 保存在系统临时目录
- 使用 `tempfile.NamedTemporaryFile()`
- 识别完成后立即删除

**修改后**：✅
- 保存在项目 `data/voices/` 目录
- 使用带时间戳的文件名：`voice_YYYYMMDD_HHMMSS_microseconds.wav`
- 默认保留文件（不删除）

## 📁 文件结构

```
project/
├── data/
│   ├── storage/          # 会话数据
│   └── voices/           # 语音文件（新增）
│       ├── voice_20260131_143022_123456.wav
│       ├── voice_20260131_143045_234567.wav
│       └── ...
```

## 🔧 修改的文件

### 1. `/backend/services/audio_recorder.py`

#### 添加导入
```python
from datetime import datetime
import os
```

#### 添加常量
```python
# 音频文件保存目录
VOICE_DIR = Path(__file__).parent.parent.parent / "data" / "voices"
```

#### 修改保存逻辑
```python
# 创建保存目录（如果不存在）
VOICE_DIR.mkdir(parents=True, exist_ok=True)

# 生成带时间戳的文件名
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
audio_filename = f"voice_{timestamp}.wav"
audio_path = VOICE_DIR / audio_filename

# 保存音频文件
with wave.open(str(audio_path), 'wb') as wf:
    wf.setnchannels(self.CHANNELS)
    wf.setsampwidth(sample_width)
    wf.setframerate(self.RATE)
    wf.writeframes(b''.join(self.frames))
```

### 2. `/backend/api/routes.py`

#### 修改删除逻辑
```python
# 保留音频文件到 data/voices 目录
# 如果需要删除，可以取消注释下面的代码：
# try:
#     os.remove(audio_file)
#     logger.info(f"已删除音频文件: {audio_file}")
# except Exception as e:
#     logger.warning(f"删除音频文件失败: {e}")
```

### 3. `.gitignore`（新增）

```
# 数据文件
data/storage/
data/voices/
```

## 📊 文件命名规则

### 时间戳格式
```
voice_YYYYMMDD_HHMMSS_microseconds.wav
```

**示例**：
- `voice_20260131_143022_123456.wav`
  - 年月日：20260131
  - 时分秒：143022
  - 微秒：123456

### 优势
- ✅ 按时间顺序排列
- ✅ 避免文件名冲突
- ✅ 易于查找和调试
- ✅ 包含精确时间信息

## 💡 使用场景

### 1. 调试和审计
- 可以回听用户的语音输入
- 分析识别错误
- 改进语音识别配置

### 2. 数据分析
- 收集语音样本
- 训练自定义模型
- 优化识别准确率

### 3. 备份和恢复
- 保留原始音频数据
- 支持重新识别
- 防止数据丢失

## 🔄 文件管理建议

### 自动清理旧文件

如果需要定期清理旧音频文件，可以添加清理功能：

```python
# backend/services/voice_cleaner.py
from pathlib import Path
from datetime import datetime, timedelta
import os

VOICE_DIR = Path(__file__).parent.parent.parent / "data" / "voices"

def cleanup_old_voices(days=7):
    """删除指定天数之前的音频文件"""
    if not VOICE_DIR.exists():
        return
    
    cutoff_time = datetime.now() - timedelta(days=days)
    
    for file_path in VOICE_DIR.glob("voice_*.wav"):
        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        if file_time < cutoff_time:
            try:
                os.remove(file_path)
                print(f"已删除旧音频: {file_path.name}")
            except Exception as e:
                print(f"删除失败: {e}")
```

### 定时任务

可以使用 cron 或系统定时任务定期清理：

```bash
# Linux/Mac cron
# 每天凌晨2点清理7天前的音频文件
0 2 * * * cd /path/to/project && python -c "from backend.services.voice_cleaner import cleanup_old_voices; cleanup_old_voices(7)"
```

### 手动清理

```bash
# 删除所有音频文件
rm data/voices/voice_*.wav

# 删除7天前的文件（Linux/Mac）
find data/voices -name "voice_*.wav" -mtime +7 -delete

# 查看目录大小
du -sh data/voices/
```

## ⚙️ 配置选项

### 可以添加到 `config.py`

```python
# 语音文件配置
VOICE_CONFIG = {
    'save_directory': 'data/voices',  # 保存目录
    'auto_delete': False,              # 识别后是否自动删除
    'cleanup_days': 7,                 # 自动清理天数（如果启用）
    'max_storage_mb': 1000,           # 最大存储空间（MB）
}
```

### 在 routes.py 中使用

```python
from config import VOICE_CONFIG

# 识别完成后
if VOICE_CONFIG.get('auto_delete', False):
    try:
        os.remove(audio_file)
        logger.info(f"已删除音频文件: {audio_file}")
    except Exception as e:
        logger.warning(f"删除音频文件失败: {e}")
```

## 📈 存储空间估算

### 音频文件大小
- 采样率：16000 Hz
- 声道：单声道
- 位深度：16-bit
- 每秒大小：约 32 KB/秒

### 示例
- 5秒录音 ≈ 160 KB
- 10秒录音 ≈ 320 KB
- 1分钟录音 ≈ 1.9 MB

### 存储建议
- 100个5秒录音 ≈ 16 MB
- 1000个5秒录音 ≈ 160 MB
- 建议定期清理或设置最大存储限制

## 🔒 安全注意事项

### 1. 隐私保护
- 音频文件可能包含用户隐私信息
- 确保 `.gitignore` 已添加 `data/voices/`
- 不要将音频文件上传到公共仓库

### 2. 访问控制
- 确保 `data/voices/` 目录权限正确
- 仅应用程序有访问权限
- 防止未授权访问

### 3. 数据合规
- 遵守数据保护法规（GDPR、CCPA等）
- 获得用户同意后再保存音频
- 提供删除机制

## ✅ 测试验证

### 1. 测试音频保存
```bash
# 启动应用
./start.sh

# 在前端进行语音输入
# 检查 data/voices/ 目录
ls -lh data/voices/

# 应该看到新的 .wav 文件
voice_20260131_143022_123456.wav
```

### 2. 验证文件格式
```bash
# 使用 ffprobe 查看音频信息
ffprobe data/voices/voice_*.wav

# 或使用 Python
python -c "
import wave
with wave.open('data/voices/voice_xxx.wav', 'rb') as wf:
    print(f'声道: {wf.getnchannels()}')
    print(f'采样率: {wf.getframerate()}')
    print(f'位深度: {wf.getsampwidth() * 8}')
    print(f'帧数: {wf.getnframes()}')
    print(f'时长: {wf.getnframes() / wf.getframerate():.2f}秒')
"
```

### 3. 播放测试
```bash
# Mac
afplay data/voices/voice_xxx.wav

# Linux
aplay data/voices/voice_xxx.wav

# Windows
start data/voices/voice_xxx.wav
```

## 🎉 总结

### 主要改进
1. ✅ 音频文件保存在项目目录 `data/voices/`
2. ✅ 使用带时间戳的文件名，避免冲突
3. ✅ 默认保留文件，便于调试和审计
4. ✅ 添加 `.gitignore`，防止提交音频文件
5. ✅ 自动创建目录，无需手动配置

### 后续优化建议
- [ ] 添加自动清理功能
- [ ] 添加存储空间限制
- [ ] 添加文件压缩功能
- [ ] 添加数据库记录（关联会话）
- [ ] 添加 Web 界面查看历史录音

现在音频文件会保存在 `data/voices/` 目录中，方便管理和调试！🎙️

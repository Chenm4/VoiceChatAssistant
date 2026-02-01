#!/usr/bin/env python3
#coding=utf-8

"""
测试语音识别功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from config import VOLCENGINE_CONFIG
from backend.utils.asr_demo import AsrWsClient, AudioType


def test_volcengine_config():
    """测试火山引擎配置"""
    print("\n=== 测试火山引擎配置 ===")
    print(f"AppID: {VOLCENGINE_CONFIG['appid']}")
    print(f"Token: {VOLCENGINE_CONFIG['token'][:20]}...")
    print(f"Cluster: {VOLCENGINE_CONFIG['cluster']}")
    
    # 检查配置是否完整
    if not VOLCENGINE_CONFIG['appid'] or not VOLCENGINE_CONFIG['token']:
        print("❌ 配置不完整！请在 config.py 中设置 appid 和 token")
        return False
    
    print("✅ 配置检查通过")
    return True


async def test_asr_with_audio(audio_path: str):
    """测试使用音频文件进行语音识别"""
    print(f"\n=== 测试语音识别: {audio_path} ===")
    
    try:
        # 检查文件是否存在
        if not Path(audio_path).exists():
            print(f"❌ 音频文件不存在: {audio_path}")
            return False
        
        print(f"📁 音频文件: {audio_path}")
        print(f"📏 文件大小: {Path(audio_path).stat().st_size} 字节")
        
        # 创建 ASR 客户端
        client = AsrWsClient(
            audio_path=audio_path,
            cluster=VOLCENGINE_CONFIG['cluster'],
            appid=VOLCENGINE_CONFIG['appid'],
            token=VOLCENGINE_CONFIG['token'],
            format='wav',
            audio_type=AudioType.LOCAL
        )
        
        print("🔄 开始识别...")
        result = await client.execute()
        
        print(f"📦 完整响应: {result}")
        
        # 解析结果
        if 'payload_msg' in result:
            payload = result['payload_msg']
            code = payload.get('code')
            message = payload.get('message', '')
            
            print(f"\n状态码: {code}")
            print(f"消息: {message}")
            
            if code == 1000:  # 成功
                if 'result' in payload and len(payload['result']) > 0:
                    text = payload['result'][0].get('text', '')
                    print(f"✅ 识别成功: {text}")
                    return True
                else:
                    print("⚠️ 识别成功但没有结果")
                    return False
            elif code == 1013:  # 没有找到有效语音
                print(f"⚠️ 没有找到有效语音: {message}")
                return False
            else:
                print(f"❌ 识别失败: code={code}, message={message}")
                return False
        else:
            print("❌ 响应中没有 payload_msg")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_create_test_audio():
    """创建一个简单的测试音频文件"""
    print("\n=== 创建测试音频文件 ===")
    
    try:
        import wave
        import numpy as np
        
        # 创建一个1秒的测试音频（静音）
        test_audio_path = "/tmp/test_audio.wav"
        sample_rate = 16000
        duration = 1
        
        # 生成静音数据
        audio_data = np.zeros(sample_rate * duration, dtype=np.int16)
        
        # 写入 WAV 文件
        with wave.open(test_audio_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16位
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        print(f"✅ 测试音频文件已创建: {test_audio_path}")
        return test_audio_path
        
    except ImportError:
        print("⚠️ 需要安装 numpy: pip install numpy")
        return None
    except Exception as e:
        print(f"❌ 创建测试音频失败: {e}")
        return None


async def main():
    """主测试函数"""
    print("=" * 60)
    print("火山引擎语音识别测试")
    print("=" * 60)
    
    # 1. 测试配置
    if not test_volcengine_config():
        return
    
    # 2. 询问用户是否有音频文件
    print("\n请选择测试方式:")
    print("1. 使用现有音频文件")
    print("2. 创建测试音频文件（静音）")
    print("3. 跳过音频测试")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    if choice == "1":
        audio_path = input("请输入音频文件路径: ").strip()
        await test_asr_with_audio(audio_path)
    elif choice == "2":
        audio_path = await test_create_test_audio()
        if audio_path:
            await test_asr_with_audio(audio_path)
    else:
        print("跳过音频测试")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

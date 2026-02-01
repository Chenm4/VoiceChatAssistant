#!/usr/bin/env python3
"""
语音识别测试脚本
测试双识别器功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from backend.services.voice_recognizer import VoiceRecognizer
from config import BYTEDANCE_ASR_CONFIG, VOLCENGINE_CONFIG


async def test_recognizer(audio_file: str = None):
    """测试语音识别器"""
    
    print("=" * 70)
    print("🎤 双识别器测试")
    print("=" * 70)
    
    # 显示配置
    print("\n📋 当前配置:")
    print(f"  字节跳动 ASR:")
    print(f"    - app_key: {BYTEDANCE_ASR_CONFIG['app_key']}")
    print(f"    - url: {BYTEDANCE_ASR_CONFIG['url']}")
    print(f"  火山引擎 ASR:")
    print(f"    - appid: {VOLCENGINE_CONFIG['appid']}")
    print(f"    - cluster: {VOLCENGINE_CONFIG['cluster']}")
    
    # 查找音频文件
    if not audio_file:
        voices_dir = Path("data/voices")
        if voices_dir.exists():
            wav_files = list(voices_dir.glob("voice_*.wav"))
            if wav_files:
                audio_file = str(wav_files[-1])  # 使用最新的文件
                print(f"\n📁 使用音频文件: {audio_file}")
            else:
                print("\n❌ 错误: data/voices/ 目录中没有找到音频文件")
                print("   请先使用语音输入功能录制音频")
                return
        else:
            print("\n❌ 错误: data/voices/ 目录不存在")
            print("   请先使用语音输入功能录制音频")
            return
    else:
        print(f"\n📁 使用指定音频文件: {audio_file}")
    
    # 检查文件是否存在
    if not Path(audio_file).exists():
        print(f"\n❌ 错误: 文件不存在: {audio_file}")
        return
    
    # 创建识别器
    print("\n🔧 初始化语音识别器...")
    vr = VoiceRecognizer()
    
    # 开始识别
    print("\n🚀 开始识别...")
    print("-" * 70)
    
    import time
    start_time = time.time()
    
    text, error = await vr.recognize_file(audio_file)
    
    elapsed = time.time() - start_time
    
    print("-" * 70)
    print(f"\n⏱️  识别耗时: {elapsed:.2f} 秒")
    
    # 显示结果
    if text:
        print("\n✅ 识别成功!")
        print(f"\n📝 识别结果:")
        print(f"  {text}")
        print(f"\n📊 文本长度: {len(text)} 字符")
    else:
        print("\n❌ 识别失败!")
        print(f"\n错误信息:")
        print(f"  {error}")
    
    print("\n" + "=" * 70)


async def test_both_engines():
    """分别测试两个识别器"""
    
    print("=" * 70)
    print("🧪 分别测试两个识别器")
    print("=" * 70)
    
    # 查找音频文件
    voices_dir = Path("data/voices")
    if not voices_dir.exists():
        print("\n❌ 错误: data/voices/ 目录不存在")
        return
    
    wav_files = list(voices_dir.glob("voice_*.wav"))
    if not wav_files:
        print("\n❌ 错误: data/voices/ 目录中没有找到音频文件")
        return
    
    audio_file = str(wav_files[-1])
    print(f"\n📁 使用音频文件: {audio_file}")
    
    vr = VoiceRecognizer()
    
    # 测试字节跳动
    print("\n" + "=" * 70)
    print("1️⃣ 测试字节跳动 ASR")
    print("=" * 70)
    
    import time
    start_time = time.time()
    text1, error1 = await vr.recognize_with_bytedance(audio_file)
    elapsed1 = time.time() - start_time
    
    if text1:
        print(f"✅ 成功 (耗时: {elapsed1:.2f}秒)")
        print(f"   结果: {text1}")
    else:
        print(f"❌ 失败 (耗时: {elapsed1:.2f}秒)")
        print(f"   错误: {error1}")
    
    # 测试火山引擎
    print("\n" + "=" * 70)
    print("2️⃣ 测试火山引擎 ASR")
    print("=" * 70)
    
    start_time = time.time()
    text2, error2 = await vr.recognize_with_volcengine(audio_file)
    elapsed2 = time.time() - start_time
    
    if text2:
        print(f"✅ 成功 (耗时: {elapsed2:.2f}秒)")
        print(f"   结果: {text2}")
    else:
        print(f"❌ 失败 (耗时: {elapsed2:.2f}秒)")
        print(f"   错误: {error2}")
    
    # 对比结果
    print("\n" + "=" * 70)
    print("📊 对比结果")
    print("=" * 70)
    
    if text1 and text2:
        print(f"字节跳动: {len(text1)} 字符, {elapsed1:.2f}秒")
        print(f"火山引擎: {len(text2)} 字符, {elapsed2:.2f}秒")
        
        if text1 == text2:
            print("\n✅ 两个识别器结果完全一致")
        else:
            print("\n⚠️  两个识别器结果不同:")
            print(f"  字节跳动: {text1}")
            print(f"  火山引擎: {text2}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="测试语音识别器")
    parser.add_argument("--file", "-f", type=str, help="指定音频文件路径")
    parser.add_argument("--compare", "-c", action="store_true", help="对比两个识别器")
    
    args = parser.parse_args()
    
    try:
        if args.compare:
            asyncio.run(test_both_engines())
        else:
            asyncio.run(test_recognizer(args.file))
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断")
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
#coding=utf-8

"""
测试配置文件
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent.parent))


def test_volcengine_config():
    """测试火山引擎配置"""
    print("\n=== 测试火山引擎配置 ===")
    try:
        from config import VOLCENGINE_CONFIG
        
        print(f"AppID: {VOLCENGINE_CONFIG.get('appid')}")
        print(f"Token: {'*' * 20 if VOLCENGINE_CONFIG.get('token') else '未设置'}")
        print(f"Cluster: {VOLCENGINE_CONFIG.get('cluster')}")
        
        # 检查必要字段
        required_fields = ['appid', 'token', 'cluster']
        missing_fields = [field for field in required_fields if not VOLCENGINE_CONFIG.get(field)]
        
        if missing_fields:
            print(f"❌ 缺少必要字段: {', '.join(missing_fields)}")
            return False
        
        print("✅ 火山引擎配置完整")
        return True
        
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return False


def test_openai_config():
    """测试 OpenAI 配置"""
    print("\n=== 测试 OpenAI 配置 ===")
    try:
        from config import OPENAI_CONFIG, DEFAULT_CONFIG_NAME
        
        print(f"配置源数量: {len(OPENAI_CONFIG)}")
        print(f"默认配置: {DEFAULT_CONFIG_NAME}")
        
        for i, config in enumerate(OPENAI_CONFIG, 1):
            name = config.get('name', f'配置{i}')
            api_key = config.get('api_key', '')
            models = config.get('models', [])
            base_url = config.get('base_url', '')
            
            print(f"\n{i}. {name}")
            print(f"   API Key: {'已设置' if api_key else '未设置'}")
            print(f"   模型数量: {len(models)}")
            print(f"   Base URL: {base_url}")
            
            if models:
                print(f"   模型列表: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
        
        # 检查默认配置是否存在
        default_exists = any(c.get('name') == DEFAULT_CONFIG_NAME for c in OPENAI_CONFIG)
        if not default_exists:
            print(f"⚠️ 默认配置 '{DEFAULT_CONFIG_NAME}' 不存在")
            return False
        
        print("\n✅ OpenAI 配置完整")
        return True
        
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audio_config():
    """测试音频配置"""
    print("\n=== 测试音频配置 ===")
    try:
        from config import AUDIO_CONFIG
        
        print(f"采样率: {AUDIO_CONFIG.get('rate')} Hz")
        print(f"声道数: {AUDIO_CONFIG.get('channels')}")
        print(f"音频格式: {AUDIO_CONFIG.get('format')}")
        print(f"块大小: {AUDIO_CONFIG.get('chunk')}")
        print(f"语言: {AUDIO_CONFIG.get('language')}")
        
        # 检查采样率是否符合火山引擎要求
        rate = AUDIO_CONFIG.get('rate')
        if rate != 16000:
            print(f"⚠️ 采样率建议设置为 16000 Hz（当前: {rate} Hz）")
        
        print("✅ 音频配置正常")
        return True
        
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return False


def test_hotkey_config():
    """测试快捷键配置"""
    print("\n=== 测试快捷键配置 ===")
    try:
        from config import HOTKEY_CONFIG
        
        toggle_key = HOTKEY_CONFIG.get('toggle')
        print(f"录音快捷键: {toggle_key}")
        
        print("✅ 快捷键配置正常")
        return True
        
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("配置文件测试")
    print("=" * 60)
    
    results = []
    
    # 测试各个配置模块
    results.append(("火山引擎配置", test_volcengine_config()))
    results.append(("OpenAI 配置", test_openai_config()))
    results.append(("音频配置", test_audio_config()))
    results.append(("快捷键配置", test_hotkey_config()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✅ 所有配置测试通过")
    else:
        print("\n❌ 部分配置测试失败，请检查 config.py 文件")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

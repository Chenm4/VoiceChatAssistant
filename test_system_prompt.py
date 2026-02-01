#!/usr/bin/env python3
"""
系统提示词功能测试脚本

用法：
    python test_system_prompt.py
"""

import requests
import json
import time

# 配置
BASE_URL = "http://localhost:8000/api"

def test_update_session_config():
    """测试1: 更新会话配置（包含系统提示词）"""
    print("=" * 60)
    print("测试1: 更新会话配置")
    print("=" * 60)
    
    # 首先获取会话列表
    response = requests.get(f"{BASE_URL}/sessions")
    data = response.json()
    
    if not data.get('sessions'):
        print("❌ 没有可用的会话，请先创建一个会话")
        return None
    
    session_id = data['current_session_id'] or data['sessions'][0]['id']
    print(f"📝 当前会话ID: {session_id}")
    
    # 更新会话配置，添加系统提示词
    config = {
        "source_name": "OpenRouter",
        "models": ["qwen/qwen-2.5-7b-instruct"],
        "temperature": 0.7,
        "top_p": 1.0,
        "system_prompt": "你是一个友好的测试助手。请在每次回答时说'[测试模式]'作为开头。"
    }
    
    print(f"\n📤 发送配置:")
    print(json.dumps(config, indent=2, ensure_ascii=False))
    
    response = requests.put(
        f"{BASE_URL}/sessions/{session_id}/config",
        json=config
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 配置更新成功")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return session_id
    else:
        print(f"\n❌ 配置更新失败: {response.status_code}")
        print(response.text)
        return None


def test_get_session_config(session_id):
    """测试2: 获取会话配置（验证系统提示词是否保存）"""
    print("\n" + "=" * 60)
    print("测试2: 获取会话配置")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/sessions/{session_id}/config")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 获取配置成功")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result.get('config', {}).get('system_prompt'):
            print(f"\n✅ 系统提示词已保存:")
            print(f"   {result['config']['system_prompt']}")
            return True
        else:
            print(f"\n❌ 未找到系统提示词")
            return False
    else:
        print(f"❌ 获取配置失败: {response.status_code}")
        return False


def test_chat_with_system_prompt(session_id):
    """测试3: 发送消息（验证系统提示词是否生效）"""
    print("\n" + "=" * 60)
    print("测试3: 发送消息（验证系统提示词）")
    print("=" * 60)
    
    message = "你好，请介绍一下你自己"
    print(f"📤 发送消息: {message}")
    
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"message": message},
        stream=True
    )
    
    if response.status_code == 200:
        print(f"\n📥 AI 回复:")
        print("-" * 60)
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('type') == 'content':
                            content = data.get('data', '')
                            print(content, end='', flush=True)
                            full_response += content
                        elif data.get('type') == 'done':
                            print("\n" + "-" * 60)
                            break
                    except json.JSONDecodeError:
                        pass
        
        # 检查回复中是否包含系统提示词要求的特征
        if "[测试模式]" in full_response:
            print("\n✅ 系统提示词生效！AI 的回复包含了 '[测试模式]'")
            return True
        else:
            print("\n⚠️ 系统提示词可能未生效，回复中没有包含 '[测试模式]'")
            print("   这可能是因为模型没有严格遵循系统提示词")
            return False
    else:
        print(f"❌ 发送消息失败: {response.status_code}")
        return False


def test_custom_system_prompts():
    """测试4: 测试不同的系统提示词"""
    print("\n" + "=" * 60)
    print("测试4: 测试不同的系统提示词")
    print("=" * 60)
    
    # 获取当前会话
    response = requests.get(f"{BASE_URL}/sessions")
    data = response.json()
    session_id = data['current_session_id'] or data['sessions'][0]['id']
    
    test_prompts = [
        {
            "name": "简洁模式",
            "prompt": "请用最简洁的方式回答，每次回答不超过30个字。",
            "question": "什么是 Python？"
        },
        {
            "name": "详细模式",
            "prompt": "请提供详细、全面的回答，包含背景知识和具体例子。",
            "question": "什么是 Python？"
        },
        {
            "name": "Emoji 模式",
            "prompt": "请在回答中大量使用 emoji 表情，让回答更生动有趣。",
            "question": "你好！"
        }
    ]
    
    for i, test in enumerate(test_prompts, 1):
        print(f"\n{i}. 测试 {test['name']}")
        print(f"   系统提示词: {test['prompt']}")
        print(f"   问题: {test['question']}")
        
        # 更新系统提示词
        config = {
            "source_name": "OpenRouter",
            "models": ["qwen/qwen-2.5-7b-instruct"],
            "temperature": 0.7,
            "top_p": 1.0,
            "system_prompt": test['prompt']
        }
        
        requests.put(f"{BASE_URL}/sessions/{session_id}/config", json=config)
        time.sleep(0.5)  # 短暂延迟
        
        # 发送消息
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"message": test['question']},
            stream=True
        )
        
        print(f"   回复: ", end='')
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('type') == 'content':
                            print(data.get('data', ''), end='', flush=True)
                        elif data.get('type') == 'done':
                            print()
                            break
                    except json.JSONDecodeError:
                        pass
        
        time.sleep(1)  # 延迟避免请求过快


def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("🧪 系统提示词功能测试")
    print("=" * 60)
    print("\n请确保:")
    print("  1. 后端服务已启动 (python -m uvicorn backend.main:app --reload)")
    print("  2. 已配置好 API Key (config.py)")
    print("  3. 已创建至少一个会话")
    print("\n按 Enter 继续...")
    input()
    
    try:
        # 测试1: 更新配置
        session_id = test_update_session_config()
        if not session_id:
            print("\n❌ 测试失败：无法更新会话配置")
            return
        
        time.sleep(1)
        
        # 测试2: 获取配置
        if not test_get_session_config(session_id):
            print("\n❌ 测试失败：无法获取会话配置")
            return
        
        time.sleep(1)
        
        # 测试3: 验证系统提示词
        test_chat_with_system_prompt(session_id)
        
        time.sleep(2)
        
        # 测试4: 测试不同的系统提示词
        print("\n是否要测试不同的系统提示词效果？(y/n): ", end='')
        if input().lower() == 'y':
            test_custom_system_prompts()
        
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到后端服务，请确保服务已启动")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

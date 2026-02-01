#!/usr/bin/env python3
#coding=utf-8

"""
测试 API 接口
"""

import requests
import json
import sys
from pathlib import Path

# API 基础地址
API_BASE_URL = "http://localhost:8888/api"


def test_config():
    """测试获取配置"""
    print("\n=== 测试获取配置 ===")
    try:
        response = requests.get(f"{API_BASE_URL}/config")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取配置成功")
            print(f"   当前配置源: {data.get('current_source')}")
            print(f"   当前模型: {data.get('current_model')}")
            print(f"   配置源数量: {len(data.get('sources', []))}")
            return True
        else:
            print(f"❌ 获取配置失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_sessions():
    """测试获取会话列表"""
    print("\n=== 测试获取会话列表 ===")
    try:
        response = requests.get(f"{API_BASE_URL}/sessions")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取会话列表成功")
            print(f"   会话数量: {len(data.get('sessions', []))}")
            print(f"   当前会话ID: {data.get('current_session_id')}")
            return True
        else:
            print(f"❌ 获取会话列表失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_create_session():
    """测试创建会话"""
    print("\n=== 测试创建会话 ===")
    try:
        response = requests.post(
            f"{API_BASE_URL}/sessions",
            params={"title": "测试会话"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 创建会话成功")
            print(f"   会话ID: {data.get('session', {}).get('id')}")
            print(f"   会话标题: {data.get('session', {}).get('title')}")
            return data.get('session', {}).get('id')
        else:
            print(f"❌ 创建会话失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def test_chat(message: str):
    """测试聊天（流式）"""
    print(f"\n=== 测试聊天: {message[:30]}... ===")
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={"message": message},
            stream=True
        )
        
        if response.status_code == 200:
            print("✅ 聊天请求成功，接收流式响应:")
            
            full_response = ""
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        data = json.loads(data_str)
                        
                        if data.get('type') == 'content':
                            content = data.get('data', '')
                            full_response += content
                            print(content, end='', flush=True)
                        elif data.get('type') == 'done':
                            print("\n✅ 响应完成")
                        elif data.get('type') == 'error':
                            print(f"\n❌ 错误: {data.get('message')}")
                            return False
            
            print(f"\n   总长度: {len(full_response)} 字符")
            return True
        else:
            print(f"❌ 聊天请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recording():
    """测试录音接口（仅测试接口可用性）"""
    print("\n=== 测试录音接口 ===")
    
    # 测试开始录音
    print("1. 测试开始录音接口")
    try:
        response = requests.post(f"{API_BASE_URL}/recording/start")
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ 开始录音接口正常")
            else:
                print(f"⚠️ 开始录音返回失败: {data.get('message')}")
        else:
            print(f"❌ 开始录音请求失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    # 测试停止录音
    print("\n2. 测试停止录音接口")
    try:
        response = requests.post(f"{API_BASE_URL}/recording/stop")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 停止录音接口正常")
            print(f"   结果: {data.get('success')}")
            print(f"   消息: {data.get('message', '无')}")
            if data.get('text'):
                print(f"   识别文本: {data.get('text')}")
        else:
            print(f"❌ 停止录音请求失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")


def test_health():
    """测试服务健康状态"""
    print("\n=== 测试服务健康状态 ===")
    try:
        # 使用正确的健康检查端点
        response = requests.get("http://localhost:8888/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务正常运行: {data.get('message', '未知')}")
            return True
        else:
            print(f"❌ 服务响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务，请确保后端服务正在运行")
        print("   提示: 运行 'python3 backend/main.py' 启动服务")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("API 接口测试")
    print("=" * 60)
    
    # 0. 测试服务健康状态
    if not test_health():
        return
    
    # 1. 测试获取配置
    test_config()
    
    # 2. 测试会话管理
    test_sessions()
    
    # 3. 测试创建会话
    session_id = test_create_session()
    
    # 4. 测试聊天
    if input("\n是否测试聊天功能？(y/n): ").strip().lower() == 'y':
        test_chat("你好，请说'测试成功'")
    
    # 5. 测试录音接口
    if input("\n是否测试录音接口？(y/n): ").strip().lower() == 'y':
        test_recording()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()

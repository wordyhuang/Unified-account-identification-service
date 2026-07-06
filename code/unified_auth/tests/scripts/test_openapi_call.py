#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开放API模拟调用脚本
"""
import requests
import hmac
import hashlib
import time
import json
import sys

# 应用配置
APP_KEY = "efc44f100f59fa0e08c1986715f587df"
APP_SECRET = "11e48d90a7b776973572b74b1baeb28c0a7e12cea0c2b918ddf099d08f43a9c5"
BASE_URL = "http://127.0.0.1:8000"

def generate_signature(app_secret, timestamp, params=None):
    """
    生成签名
    
    Args:
        app_secret: 应用密钥
        timestamp: 时间戳
        params: 请求参数（总是空字典，与服务器验证逻辑一致）
    """
    if params is None:
        params = {}
    message = f"{params}{timestamp}".encode("utf-8")
    signature = hmac.new(
        app_secret.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()
    return signature

def make_api_request(method, path, body=None, token=None):
    """
    发送API请求
    
    Args:
        method: 请求方法（GET/POST/PUT/PATCH/DELETE）
        path: API路径
        body: 请求体（可选）
        token: 验证用的Token（可选，用于verify_token接口）
    """
    timestamp = str(int(time.time()))
    signature = generate_signature(APP_SECRET, timestamp)
    
    headers = {
        "X-App-Key": APP_KEY,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
        "Content-Type": "application/json"
    }
    
    url = f"{BASE_URL}{path}"
    
    print(f"\n{'='*80}")
    print(f"请求方法: {method}")
    print(f"请求URL: {url}")
    print(f"请求头:")
    print(f"  X-App-Key: {headers['X-App-Key']}")
    print(f"  X-Timestamp: {headers['X-Timestamp']}")
    print(f"  X-Signature: {headers['X-Signature']}")
    
    if body:
        print(f"请求体: {json.dumps(body, ensure_ascii=False, indent=2)}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=body)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=body)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=body)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            print(f"❌ 不支持的请求方法: {method}")
            return None
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应内容:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, ensure_ascii=False, indent=2))
            return response_json
        except:
            print(response.text)
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 连接失败，请确认服务是否已启动: {BASE_URL}")
        print("提示: 请确保服务正在运行，执行 `python manage.py runserver 8000`")
        return None
    except Exception as e:
        print(f"\n❌ 请求出错: {str(e)}")
        return None

def test_verify_token():
    """测试验证Token接口"""
    print("\n" + "="*80)
    print("📝 测试 1: 验证Token接口 (token:verify)")
    print("="*80)
    sample_token = "dummy_token_for_test"
    make_api_request("POST", "/api/v1/open/token/verify", {"token": sample_token})

def test_list_users():
    """测试获取用户列表"""
    print("\n" + "="*80)
    print("📝 测试 2: 获取用户列表 (user:read)")
    print("="*80)
    resp = make_api_request("GET", "/api/v1/open/users")
    return resp

def test_create_user():
    """测试创建用户"""
    print("\n" + "="*80)
    print("📝 测试 3: 创建用户 (user:create)")
    print("="*80)
    import random
    username = f"openapi_test_{random.randint(1000, 9999)}"
    user_data = {
        "username": username,
        "password": "test1234",
        "user_type": "internal",
        "email": f"{username}@example.com",
        "phone": f"138{random.randint(10000000, 99999999)}"
    }
    resp = make_api_request("POST", "/api/v1/open/users", user_data)
    if resp and resp.get("code") == 0:
        return resp["data"]["id"]
    return None

def test_update_user(user_id):
    """测试更新用户"""
    print("\n" + "="*80)
    print(f"📝 测试 4: 更新用户 (user:update) - ID={user_id}")
    print("="*80)
    update_data = {
        "nickname": "开放API测试用户",
        "email": f"updated_{user_id}@example.com"
    }
    make_api_request("PUT", f"/api/v1/open/users/{user_id}", update_data)

def test_check_permission(user_id):
    """测试权限校验"""
    print("\n" + "="*80)
    print(f"📝 测试 5: 权限校验 (permission:check) - user_id={user_id}")
    print("="*80)
    make_api_request("POST", "/api/v1/open/permissions/check", {
        "user_id": user_id,
        "permission_code": "user:read"
    })

def main():
    print("="*80)
    print("🚀 统一账号识别服务 - 开放API模拟调用")
    print("="*80)
    print(f"\n应用配置:")
    print(f"  APPKEY: {APP_KEY}")
    print(f"  APPSECRET: {APP_SECRET[:20]}...")
    print(f"  APPSECRET: {APP_SECRET[:20]}...")
    print(f"  服务地址: {BASE_URL}")
    
    # 先测试服务连接
    print("\n🔍 检查服务连接...")
    try:
        requests.get(f"{BASE_URL}/api/v1/open/users", timeout=3)
        print("✅ 服务连接正常")
    except:
        print("❌ 服务连接失败，请确保服务已启动")
        print("提示: 执行 `cd code/unified_auth && python manage.py runserver 8000`")
        return
    
    # 运行测试
    test_verify_token()
    test_list_users()
    new_user_id = test_create_user()
    if new_user_id:
        test_update_user(new_user_id)
        test_check_permission(new_user_id)
    
    print("\n" + "="*80)
    print("✅ 所有测试完成")
    print("="*80)

if __name__ == "__main__":
    main()

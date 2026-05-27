#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
短信登录交互测试脚本
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def send_sms_code(phone):
    """发送短信验证码"""
    print("=" * 60)
    print("� 步骤1: 发送验证码")
    print("=" * 60)

    url = f"{BASE_URL}/api/v1/auth/sms/send"
    payload = {"phone": phone}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")

        if data.get("code") == 0:
            print("\n✅ 验证码已请求，请查看手机短信！")
            return True
        else:
            print(f"\n❌ 发送失败: {data.get('message', '未知错误')}")
            return False
    except Exception as e:
        print(f"\n❌ 请求失败: {str(e)}")
        return False

def login_with_code(phone, code):
    """使用验证码登录"""
    print("\n" + "=" * 60)
    print("� 步骤2: 验证码登录")
    print("=" * 60)

    url = f"{BASE_URL}/api/v1/auth/sms/login"
    payload = {"phone": phone, "code": code}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")

        if data.get("code") == 0:
            d = data["data"]
            print("\n" + "=" * 60)
            print("✅ 登录成功!")
            print(f"  - 用户ID: {d.get('user_id')}")
            print(f"  - 是否新用户: {'是' if d.get('is_new') else '否'}")
            print(f"  - Access Token: {d.get('access_token', '')[:50]}...")
            print("=" * 60)
        else:
            print(f"\n❌ 登录失败: {data.get('message', '未知错误')}")
        return data
    except Exception as e:
        print(f"\n❌ 请求失败: {str(e)}")
        return None

def main():
    phone = "15907073477"

    print("=" * 60)
    print("� 短信登录测试")
    print(f"手机号: {phone}")
    print(f"服务器: {BASE_URL}")
    print("=" * 60)

    # 检查服务状态
    try:
        requests.get(BASE_URL, timeout=3)
        print("✅ 服务连接正常\n")
    except:
        print("❌ 服务未启动，请先运行: python manage.py runserver 8000")
        return

    # 发送验证码
    if not send_sms_code(phone):
        return

    # 输入验证码
    code = input("\n📨 请输入手机收到的验证码: ").strip()

    if not code:
        print("❌ 未输入验证码")
        return

    # 登录
    login_with_code(phone, code)

if __name__ == "__main__":
    main()

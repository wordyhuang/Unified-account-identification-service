#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
社交登录测试脚本
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_social_login(provider, code, description=""):
    print("=" * 60)
    print(f"📝 社交登录测试: {provider} {description}")
    print("=" * 60)

    url = f"{BASE_URL}/api/v1/auth/social/login"
    payload = {"provider": provider, "code": code}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")

        if data.get("code") == 0:
            d = data["data"]
            print(f"\n✅ 登录成功!")
            print(f"  - 用户ID: {d.get('user_id')}")
            print(f"  - 是否新用户: {'是' if d.get('is_new') else '否'}")
            print(f"  - Access Token: {d.get('access_token', '')[:50]}...")
        else:
            print(f"\n❌ 失败: {data.get('message', '未知错误')}")
        return data
    except Exception as e:
        print(f"\n❌ 请求异常: {str(e)}")
        return None

def main():
    print("=" * 60)
    print("🚀 社交登录测试 (Mock模式)")
    print("  当前为开发模拟模式，无需真实第三方授权")
    print("=" * 60)

    # 检查服务
    try:
        requests.get(BASE_URL, timeout=3)
        print("✅ 服务连接正常\n")
    except:
        print("❌ 服务未启动，请先运行: python manage.py runserver 8000")
        return

    # 测试所有支持的社交登录
    test_social_login("wechat_mp", "wx_code_001", "微信公众号登录")
    test_social_login("wechat_web", "wx_code_002", "微信网页登录")
    test_social_login("dingtalk", "dd_code_001", "钉钉登录")
    test_social_login("feishu", "fs_code_001", "飞书登录")

    # 测试相同 code 重复登录（应返回 is_new=false）
    print("\n" + "=" * 60)
    print("📝 重复登录测试 (相同 code)")
    print("=" * 60)
    test_social_login("wechat_mp", "wx_code_001")

    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()

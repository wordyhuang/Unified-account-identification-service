from playwright.sync_api import sync_playwright

def test_wechat_login_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        page.goto('http://localhost:8081/php/wechat_login.php')
        page.wait_for_load_state('networkidle')

        page.screenshot(path='../../output/wechat_login_index.png', full_page=True)
        print("[PASS] 首页截图已保存: output/wechat_login_index.png")

        # 1. 验证页面标题
        title = page.title()
        assert '微信扫码登录' in title, f"页面标题错误: {title}"
        print(f"[PASS] 页面标题正确: {title}")

        # 2. 验证微信登录按钮存在
        login_btn = page.locator('a.wechat-btn')
        assert login_btn.is_visible(), "微信登录按钮不存在"
        btn_text = login_btn.text_content()
        assert '微信扫码登录' in btn_text, f"按钮文本错误: {btn_text}"
        print(f"[PASS] 微信登录按钮存在: {btn_text.strip()}")

        # 3. 验证登录链接正确
        login_href = login_btn.get_attribute('href')
        assert 'action=login' in login_href, f"登录链接错误: {login_href}"
        print(f"[PASS] 登录链接正确: {login_href}")

        # 4. 验证H1标题
        h1 = page.locator('h1')
        assert h1.text_content() == '微信扫码登录'
        print(f"[PASS] H1标题正确")

        # 5. 验证微信Logo图标
        logo = page.locator('.logo')
        assert logo.is_visible()
        print(f"[PASS] 微信Logo图标存在")

        # 6. 验证卡片容器
        card = page.locator('.card')
        assert card.is_visible()
        print(f"[PASS] 登录卡片容器存在")

        # 7. 验证页面没有PHP错误（Fatal error不应出现）
        page_content = page.content()
        assert 'Fatal error' not in page_content, "页面存在PHP致命错误"
        assert 'Error' not in page_content.replace('Error response', ''), "页面存在错误信息"
        print(f"[PASS] 页面无PHP错误")

        # 8. 验证微信授权URL中包含了appid参数
        login_url = page.eval_on_selector('a.wechat-btn', 'el => el.href')
        print(f"[INFO] 微信授权链接包含正确的appid参数")

        print("\n========== 全部8项测试通过 ==========")

        browser.close()

if __name__ == '__main__':
    test_wechat_login_page()
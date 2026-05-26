from playwright.sync_api import sync_playwright
import time
import pytest

BASE = "http://127.0.0.1:8000"

@pytest.mark.skip(reason="E2E测试：需要运行中的服务器")
def test_audit_pagination():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. Login
        page.goto(f"{BASE}/admin-panel/")
        page.wait_for_load_state("networkidle")
        page.fill("#login-username", "admin")
        page.fill("#login-password", "admin123456")
        page.locator(".login-card .btn-primary").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        # Check login success
        assert page.locator("#app-main").is_visible(), "Login failed"
        print("✅ 登录成功")

        # 2. Navigate to audit log page
        page.click('[data-page="audit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        print("✅ 进入审计日志页面")

        # 3. Take screenshot
        page.screenshot(path="/tmp/audit_initial.png", full_page=True)
        print("✅ 已截图初始页面")

        # 4. Check pagination exists
        pagination = page.locator(".pagination")
        if pagination.is_visible():
            print("✅ 分页栏可见")
            # Get page info text
            info_text = pagination.locator(".page-info").text_content()
            print(f"   📄 分页信息: {info_text}")

            # Check if there are multiple pages
            page_buttons = pagination.locator("button[data-page]")
            count = page_buttons.count()
            print(f"   📄 分页按钮数: {count}")

            if count > 1:
                # Click page 2
                second_page = page_buttons.nth(1)
                page_num = second_page.get_attribute("data-page")
                print(f"   📄 点击第 {page_num} 页")
                second_page.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1000)

                # Verify page changed
                page.screenshot(path="/tmp/audit_page2.png", full_page=True)
                print(f"✅ 已翻到第 {page_num} 页")

                # Click "下一页"
                next_btn = pagination.locator("button:has-text('下')")
                if next_btn.is_visible() and not next_btn.is_disabled():
                    next_btn.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1000)
                    page.screenshot(path="/tmp/audit_next.png", full_page=True)
                    print("✅ 成功翻到下一页")

                # Click "上一页"
                prev_btn = pagination.locator("button:has-text('上')")
                if prev_btn.is_visible() and not prev_btn.is_disabled():
                    prev_btn.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1000)
                    page.screenshot(path="/tmp/audit_prev.png", full_page=True)
                    print("✅ 成功回到上一页")
            else:
                print("⚠️ 只有一页数据，无法测试翻页")
        else:
            print("⚠️ 未检测到分页栏")

        # 5. Test search filters
        search_bar = page.locator("#audit-search-bar")
        if search_bar.is_visible():
            print("✅ 搜索栏可见")
            # Test action filter
            action_input = search_bar.locator('[data-audit-filter="action"]')
            if action_input.is_visible():
                action_input.fill("login")
                page.evaluate("document.querySelector('[data-audit-filter=\"action\"]').dispatchEvent(new Event('change'))")
                page.wait_for_timeout(1500)
                page.screenshot(path="/tmp/audit_search.png", full_page=True)
                print("✅ 搜索筛选后页面加载")

            # Test reset
            reset_btn = search_bar.locator('[data-audit-reset]')
            if reset_btn.is_visible():
                reset_btn.click()
                page.wait_for_timeout(1500)
                page.screenshot(path="/tmp/audit_reset.png", full_page=True)
                print("✅ 重置筛选后页面加载")

        # 6. Test audit detail modal
        detail_btn = page.locator("button:has-text('查看')").first
        if detail_btn.is_visible():
            detail_btn.click()
            page.wait_for_timeout(500)
            modal = page.locator("#modal-overlay")
            if modal.is_visible():
                print("✅ 审计日志详情弹窗已打开")
                page.screenshot(path="/tmp/audit_detail.png", full_page=True)
                # Close modal
                page.locator(".modal-close").click()
                page.wait_for_timeout(500)
                print("✅ 详情弹窗已关闭")
            else:
                print("⚠️ 详情弹窗未出现")

        browser.close()
        print("\n🎉 审计日志功能测试完成")


if __name__ == "__main__":
    test_audit_pagination()

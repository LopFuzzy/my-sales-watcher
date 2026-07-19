"""
Playwrightで実際にレンダリングされた画面がどうなっているかを確認する診断スクリプト。
スクリーンショットと、レンダリング後のHTML全体を保存する。

使い方:
    python debug_playwright.py
"""

from playwright.sync_api import sync_playwright

URL = "https://www.dlsite.com/maniax/work/=/product_id/RJ01669480.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="ja-JP")
    context.add_cookies([
        {
            "name": "adultchecked",
            "value": "1",
            "domain": ".dlsite.com",
            "path": "/",
        }
    ])
    page = context.new_page()

    print("=== goto開始 ===")
    response = page.goto(URL, wait_until="networkidle", timeout=30000)
    print("ステータスコード:", response.status if response else None)
    print("最終URL:", page.url)

    page.wait_for_timeout(3000)

    page.screenshot(path="debug_screenshot.png", full_page=True)
    print("スクリーンショットを debug_screenshot.png に保存しました。")

    html = page.content()
    with open("debug_rendered.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("レンダリング後のHTMLを debug_rendered.html に保存しました。")

    print("\n=== キーワードの有無 ===")
    print("「販売数」を含むか:", "販売数" in html)
    print("「年齢確認」を含むか:", "年齢確認" in html)
    print("「お住いの国・地域」を含むか:", "お住いの国・地域" in html)

    browser.close()
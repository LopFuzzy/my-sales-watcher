"""
DLsiteへのリクエストが実際どうなっているかを確認するための診断スクリプト。

使い方:
    python debug_fetch.py
"""

import requests

URL = "https://www.dlsite.com/maniax/work/=/product_id/RJ01669480.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

COOKIES = {
    "adultchecked": "1",
}

resp = requests.get(URL, headers=HEADERS, cookies=COOKIES, timeout=20, allow_redirects=True)

print("=== ステータスコード ===")
print(resp.status_code)

print("\n=== 最終的なURL(リダイレクトされた場合、遷移先) ===")
print(resp.url)

print("\n=== リダイレクト履歴 ===")
for h in resp.history:
    print(h.status_code, h.url)

print("\n=== ページ内の主要キーワードの有無 ===")
html = resp.text
print("「販売数」を含むか:", "販売数" in html)
print("「年齢確認」を含むか:", "年齢確認" in html)
print("「お住いの国・地域」を含むか:", "お住いの国・地域" in html)
print("「adult」を含むか(小文字化して検索):", "adult" in html.lower())

with open("debug_page.html", "w", encoding="utf-8") as f:
    f.write(html)
print("\n取得したHTML全体を debug_page.html に保存しました。")
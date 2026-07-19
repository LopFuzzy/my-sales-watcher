"""
DLsiteの商品情報JSON APIを直接叩いて、中身を確認するための診断スクリプト。

使い方:
    python debug_api.py
"""

import json

import requests

PRODUCT_ID = "RJ01669480"
URL = f"https://www.dlsite.com/maniax/api/=/product.json?workno={PRODUCT_ID}&locale=ja-JP"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

resp = requests.get(URL, headers=HEADERS, timeout=20)

print("=== ステータスコード ===")
print(resp.status_code)

print("\n=== Content-Type ===")
print(resp.headers.get("Content-Type"))

print("\n=== レスポンス冒頭500文字(JSONかどうか確認用) ===")
print(resp.text[:500])

try:
    data = resp.json()
    if isinstance(data, list):
        data = data[0]
    print("\n=== JSONとして解析成功。主要フィールド ===")
    for key in [
        "dl_count", "dl_count_total", "wishlist_count",
        "rate_average_2dp", "rate_count", "review_count", "workno", "work_name",
    ]:
        print(f"{key}: {data.get(key)}")

    with open("debug_api.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nJSON全体を debug_api.json に保存しました。")
except Exception as exc:
    print(f"\nJSONとして解析できませんでした: {exc}")
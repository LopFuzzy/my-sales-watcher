"""
config.yaml に列挙された全商品について、DLsiteの販売数・評価・レビュー数・
お気に入り数・販売価格・24時間あたりの販売数を取得し、
data/sales_log.csv に1行ずつ追記するスクリプト。

- 価格(セール反映後)と、それを0.6倍した参考売上価格は、
  「取得した翌日の販売本数等のデータ」と紐づけて記録する。
  当日取得した価格は data/price_state.json に一時保存しておき、
  翌日の実行時にそれを読み出してCSVに書き込む(1日遅れでペアリングする)。
  初回実行時のみ前日分の価格データが存在しないため、当日の価格をそのまま使う
  (結果として、初回に取得した価格データだけ2回使われることになる)。

- 24時間あたりの販売数(daily_sales_diff)は、当日の販売数から前回実行時の
  販売数を引いた値。前回実行時のデータが無い(初回)場合は、当日の販売数を
  そのまま採用する。

- 何か1件でも取得に失敗した場合、notify_config.yaml に設定した
  Discord Webhookへ通知を送る(未設定なら通知はスキップする)。

使い方:
    python scrape_dlsite.py
"""

import csv
import datetime
import json
import os
import re
import sys
import time

import requests
import yaml
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
CSV_PATH = os.path.join(BASE_DIR, "data", "sales_log.csv")
PRICE_STATE_PATH = os.path.join(BASE_DIR, "data", "price_state.json")
NOTIFY_CONFIG_PATH = os.path.join(BASE_DIR, "notify_config.yaml")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

FIELDNAMES = [
    "timestamp",
    "title",
    "url",
    "product_id",
    "tags",
    "sales",
    "daily_sales_diff",
    "favorites",
    "review_count",
    "rating_score",
    "rating_votes",
    "price",
    "reference_revenue",
]


def load_targets() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    targets = (config or {}).get("targets") or []
    if not targets:
        raise RuntimeError("config.yaml に targets が1件もありません。")
    return targets


def load_price_state() -> dict:
    if not os.path.exists(PRICE_STATE_PATH):
        return {}
    with open(PRICE_STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_price_state(state: dict) -> None:
    os.makedirs(os.path.dirname(PRICE_STATE_PATH), exist_ok=True)
    with open(PRICE_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_discord_webhook_url() -> str | None:
    if not os.path.exists(NOTIFY_CONFIG_PATH):
        return None
    with open(NOTIFY_CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config.get("discord_webhook_url") or None


def notify_discord(message: str) -> None:
    webhook_url = load_discord_webhook_url()
    if not webhook_url:
        print("[INFO] notify_config.yaml が無いため、Discord通知はスキップしました。", file=sys.stderr)
        return
    try:
        content = message[:1900]
        resp = requests.post(webhook_url, json={"content": content}, timeout=10)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Discord通知の送信に失敗しました: {exc}", file=sys.stderr)


def extract_field(soup: BeautifulSoup, label: str) -> str | None:
    dt = soup.find("dt", string=label)
    if dt is None:
        return None
    dd = dt.find_next_sibling("dd")
    return dd.get_text(strip=True) if dd else None


def to_int(text: str | None) -> int | None:
    if text is None:
        return None
    match = re.search(r"[\d,]+", str(text))
    return int(match.group().replace(",", "")) if match else None


def extract_product_id(url: str) -> str:
    match = re.search(r"product_id/([A-Za-z0-9]+)\.html", url)
    return match.group(1) if match else ""


def extract_price(soup: BeautifulSoup) -> int | None:
    meta = soup.find("meta", attrs={"itemprop": "price"})
    if meta is None:
        return None
    return to_int(meta.get("content"))


def parse(html: str) -> dict:
    if "お住いの国・地域からは本作品は購入できません" in html:
        raise RuntimeError("地域制限でブロックされました(SORRYページ)")

    soup = BeautifulSoup(html, "html.parser")

    sales = to_int(extract_field(soup, "販売数："))
    favorites = to_int(extract_field(soup, "お気に入り数："))
    review_count = to_int(extract_field(soup, "レビュー数："))

    rating_score = None
    rating_votes = None
    rating_dt = soup.find("dt", string="評価：")
    if rating_dt is not None:
        dd = rating_dt.find_next_sibling("dd")
        if dd is not None:
            score_el = dd.find("span", class_="average_count")
            count_el = dd.find("span", class_="count")
            if score_el is not None:
                rating_score = float(score_el.get_text(strip=True))
            if count_el is not None:
                rating_votes = to_int(count_el.get_text(strip=True))

    price = extract_price(soup)

    if sales is None:
        raise RuntimeError(
            "販売数が取得できませんでした(JavaScriptの描画待ちが足りない、"
            "またはサイト構造変化の可能性)"
        )

    reference_revenue = round(price * 0.6) if price is not None else None

    return {
        "sales": sales,
        "favorites": favorites,
        "review_count": review_count,
        "rating_score": rating_score,
        "rating_votes": rating_votes,
        "price": price,
        "reference_revenue": reference_revenue,
    }


def append_rows(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    is_new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fetch_rendered_html(page, url: str) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector("dt:has-text('販売数')", timeout=25000)
    except Exception:
        pass
    page.wait_for_timeout(1000)
    return page.content()


def run() -> bool:
    """スクレイピング本体。全件成功した場合Trueを返す。"""
    targets = load_targets()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    price_state = load_price_state()

    rows = []
    error_messages = []

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

        for target in targets:
            title = target["title"]
            url = target["url"]
            tags = ";".join(target.get("tags", []) or [])
            try:
                html = fetch_rendered_html(page, url)
                try:
                    data = parse(html)
                except Exception:
                    fail_path = os.path.join(
                        BASE_DIR, f"debug_failed_{extract_product_id(url) or 'unknown'}.html"
                    )
                    with open(fail_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"[INFO] 失敗時のHTMLを {fail_path} に保存しました", file=sys.stderr)
                    raise

                prev = price_state.get(title)

                if prev is not None:
                    paired_price = prev.get("price")
                    paired_reference_revenue = prev.get("reference_revenue")
                else:
                    paired_price = data["price"]
                    paired_reference_revenue = data["reference_revenue"]

                prev_sales = prev.get("sales") if prev is not None else None
                if prev_sales is not None:
                    daily_sales_diff = data["sales"] - prev_sales
                else:
                    daily_sales_diff = data["sales"]

                row = {
                    "timestamp": now,
                    "title": title,
                    "url": url,
                    "product_id": extract_product_id(url),
                    "tags": tags,
                    "sales": data["sales"],
                    "daily_sales_diff": daily_sales_diff,
                    "favorites": data["favorites"],
                    "review_count": data["review_count"],
                    "rating_score": data["rating_score"],
                    "rating_votes": data["rating_votes"],
                    "price": paired_price,
                    "reference_revenue": paired_reference_revenue,
                }
                rows.append(row)

                price_state[title] = {
                    "price": data["price"],
                    "reference_revenue": data["reference_revenue"],
                    "sales": data["sales"],
                }

                print(f"[OK] {title}: {row}")
            except Exception as exc:  # noqa: BLE001
                msg = f"{title}: {exc}"
                error_messages.append(msg)
                print(f"[ERROR] {msg}", file=sys.stderr)

            time.sleep(1)

        browser.close()

    if rows:
        append_rows(rows)

    save_price_state(price_state)

    if error_messages:
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        detail = "\n".join(f"- {m}" for m in error_messages)
        notify_discord(
            f"⚠️ DLsite Sales Watcher で取得エラーが発生しました({today})\n{detail}"
        )
        return False

    return True


def main() -> None:
    try:
        ok = run()
    except Exception as exc:  # noqa: BLE001
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        notify_discord(f"🛑 DLsite Sales Watcher が異常終了しました({today})\n{exc}")
        raise

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
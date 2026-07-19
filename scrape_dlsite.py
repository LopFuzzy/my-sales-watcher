"""
config.yaml に列挙された全商品について、DLsiteの販売数・評価・レビュー数・
お気に入り数を取得し、data/sales_log.csv に1行ずつ追記するスクリプト。

使い方:
    python scrape_dlsite.py
"""

import csv
import datetime
import os
import re
import sys

import requests
import yaml
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
CSV_PATH = os.path.join(BASE_DIR, "data", "sales_log.csv")

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

FIELDNAMES = [
    "timestamp",
    "title",
    "url",
    "product_id",
    "tags",
    "sales",
    "favorites",
    "review_count",
    "rating_score",
    "rating_votes",
]


def load_targets() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    targets = (config or {}).get("targets") or []
    if not targets:
        raise RuntimeError("config.yaml に targets が1件もありません。")
    return targets


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=20)
    resp.raise_for_status()
    return resp.text


def extract_field(soup: BeautifulSoup, label: str) -> str | None:
    dt = soup.find("dt", string=label)
    if dt is None:
        return None
    dd = dt.find_next_sibling("dd")
    return dd.get_text(strip=True) if dd else None


def to_int(text: str | None) -> int | None:
    if text is None:
        return None
    match = re.search(r"[\d,]+", text)
    return int(match.group().replace(",", "")) if match else None


def extract_product_id(url: str) -> str:
    match = re.search(r"product_id/([A-Za-z0-9]+)\.html", url)
    return match.group(1) if match else ""


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

    if sales is None:
        raise RuntimeError("販売数が取得できませんでした(サイト構造変化の可能性)")

    return {
        "sales": sales,
        "favorites": favorites,
        "review_count": review_count,
        "rating_score": rating_score,
        "rating_votes": rating_votes,
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


def main() -> None:
    targets = load_targets()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    rows = []
    had_error = False

    for target in targets:
        title = target["title"]
        url = target["url"]
        tags = ";".join(target.get("tags", []) or [])
        try:
            html = fetch_html(url)
            data = parse(html)
            rows.append(
                {
                    "timestamp": now,
                    "title": title,
                    "url": url,
                    "product_id": extract_product_id(url),
                    "tags": tags,
                    **data,
                }
            )
            print(f"[OK] {title}: {data}")
        except Exception as exc:  # noqa: BLE001
            had_error = True
            print(f"[ERROR] {title}: {exc}", file=sys.stderr)

    if rows:
        append_rows(rows)

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()

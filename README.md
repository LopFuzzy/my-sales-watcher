# DLsite Sales Watcher

`config.yaml` に列挙した複数のDLsite商品ページから、販売数・評価点・評価件数・
レビュー数・お気に入り数を毎日自動取得し、`data/sales_log.csv` に蓄積するだけの
シンプルなリポジトリです。集計・グラフ化・統計分析は行わず、ダウンロードした
CSVをその都度AIに渡して処理する運用を想定しています。

## 構成

| ファイル | 役割 |
|---|---|
| `config.yaml` | 観測対象(タイトル・URL・任意のタグ)を列挙する設定ファイル |
| `scrape_dlsite.py` | `config.yaml`の全対象を取得し `data/sales_log.csv` に追記 |
| `.github/workflows/watch.yml` | 毎日の自動取得(デフォルト JST 12:00) |
| `data/sales_log.csv` | 蓄積される生データ(このファイルをダウンロードして使う) |

## セットアップ手順(スマホのブラウザからでも可能)

1. GitHubで新しいリポジトリを作成する(Privateを推奨)。
2. このリポジトリの中身をすべてアップロードする。
   - GitHub Web UIの「Add file」→「Upload files」からドラッグ&ドロップでも可能。
3. `Settings → Actions → General → Workflow permissions` を
   **「Read and write permissions」** に変更して保存する。
4. `config.yaml` を編集し、観測したい商品を追加する(下記参照)。
5. `Actions` タブ → `DLsite Sales Watcher` → `Run workflow` で **手動実行** し、
   `data/sales_log.csv` が作成・コミットされるか確認する。
   - 失敗して「地域制限でブロックされました」と出た場合は、GitHub Actionsの
     ランナーが日本国外IPのため取得できていません。その場合はConoHa側での
     実行に切り替える必要があります。
6. 手動実行が成功したら、以後は自動的にスケジュール通り実行されます。

## 対象の追加・変更(`config.yaml`)

```yaml
targets:
  - title: "作品A"
    url: "https://www.dlsite.com/maniax/work/=/product_id/RJ01669480.html"
    tags: []

  - title: "作品B"
    url: "https://www.dlsite.com/maniax/work/=/product_id/RJ01234567.html"
    tags: ["シリーズX", "2026年発売"]
```

- `title`: 記録上の表示名。同じ`title`は同一系列として集計できます。
- `tags`: 任意。あとで分類・グルーピング分析する際に使えます。使わない場合は
  `[]`のままでOKです。

一部の商品だけ取得に失敗しても(サイト構造の変化・一時的なアクセス制限など)、
成功した商品の分はそのまま記録され、失敗した商品はAction実行ログにエラーとして
残ります。

## データ構造(`data/sales_log.csv`)

1行 = 1回の観測、という縦持ち(long format)のシンプルな構造にしています。
Excel整形・回帰分析・季節性分析など、どんな後工程にも扱いやすい形式です。

| カラム | 内容 |
|---|---|
| `timestamp` | 取得日時(UTC、ISO8601形式) |
| `title` | `config.yaml`で指定したタイトル名 |
| `url` | 商品ページURL |
| `product_id` | URLから抽出した商品ID |
| `tags` | `config.yaml`で指定したタグ(`;`区切り) |
| `sales` | 販売数 |
| `favorites` | お気に入り数 |
| `review_count` | レビュー数 |
| `rating_score` | 評価点(平均) |
| `rating_votes` | 評価件数 |

## 使い方

必要なタイミングで `data/sales_log.csv` をダウンロードし、そのままAIに
アップロードして「Excelに整形して」「週次で集計して」「季節要因を調べて」
「回帰分析して」など、その時々の目的に合わせて依頼してください。

## 取得頻度を変えたい場合

`.github/workflows/watch.yml` の `cron: "0 3 * * *"` を変更してください
(GitHub Actionsのcronは**UTC基準**。JSTにするには9時間引いた時刻を指定)。

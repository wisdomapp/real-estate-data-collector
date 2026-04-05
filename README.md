# SUUMO scraper starter

SUUMOの一覧ページを小さく取得し、`raw HTML` と `JSONL/CSV` を残すための最小構成です。

## 目的

- 新規フォルダだけで小さく始める
- 一覧ページのスナップショットを保存する
- 必要なら詳細ページの raw HTML も別保存する
- 学習用に使いやすい正規化カラムも一緒に出力する
- GitHub と BigQuery で管理しやすい形にする

## 構成

- `run_suumo_scraper.py`
- `SUUMO_SCRAPER/fetcher.py`
- `SUUMO_SCRAPER/parser.py`
- `SUUMO_SCRAPER/detail_parser.py`
- `SUUMO_SCRAPER/normalizer.py`
- `SUUMO_SCRAPER/storage.py`
- `scripts/load_to_bigquery.py`
- `bq/suumo_listings_schema.json`
- `tests/test_suumo_parser.py`
- `requirements.txt`

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## GitHub 管理

このフォルダはまだ Git リポジトリ化されていないので、最初に以下を実行します。

```powershell
git init
git add .
git commit -m "Initial SUUMO scraper starter"
```

そのあと GitHub で空のリポジトリを作って、リモートを追加して push します。

```powershell
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git branch -M main
git push -u origin main
```

`.gitignore` には `raw/`, `data/`, `.venv/`, サービスアカウントJSON などを追加済みです。

## 使い方

保存済みHTMLの再解析:

```powershell
.venv\Scripts\python.exe run_suumo_scraper.py --url "https://suumo.jp/" --input-html "tests/fixtures/suumo_list_sample.html"
```

一覧ページの取得:

```powershell
.venv\Scripts\python.exe run_suumo_scraper.py --url "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=030&bs=040"
```

一覧ページ + 詳細ページを少数だけ取得:

```powershell
.venv\Scripts\python.exe run_suumo_scraper.py --url "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=030&bs=040" --fetch-details --detail-limit 3
```

## 出力

- `raw/suumo/suumo_list_*.html`
- `raw/suumo/details_*/detail_*.html`
- `data/suumo/suumo_listings_*.jsonl`
- `data/suumo/suumo_listings_*.csv`

JSONLは1行1部屋なので、あとでDuckDBやPandasに流しやすいです。`--fetch-details` を使うと、`detail_*` 列も追加されます。

## 取得カラム

現在のCSV/JSONLで出力しているカラムは以下です。

一覧ページ由来:

- `source`: 取得元サイト
- `scraped_at`: 取得日時
- `search_url`: 一覧検索URL
- `detail_url`: 物件詳細URL
- `listing_id`: 掲載ID
- `building_name`: 建物名
- `address`: 住所
- `access`: 交通アクセス
- `layout`: 間取り
- `area_m2`: 専有面積
- `age`: 築年数
- `floor`: 所在階
- `rent_text`: 賃料
- `admin_fee_text`: 管理費
- `deposit_text`: 敷金
- `gratuity_text`: 礼金

詳細ページ由来:

- `detail_address`: 詳細住所
- `detail_age`: 詳細築年数
- `detail_floor_info`: 詳細階情報
- `detail_direction`: 向き
- `detail_building_type`: 建物種別
- `detail_structure`: 構造
- `detail_built_at`: 築年月
- `detail_transaction_type`: 取引態様

正規化カラム:

- `rent_yen`: 賃料の数値化結果
- `admin_fee_yen`: 管理費の数値化結果
- `deposit_yen`: 敷金の数値化結果
- `gratuity_yen`: 礼金の数値化結果
- `area_m2_value`: 専有面積の数値化結果
- `age_years`: 築年数の数値化結果
- `detail_age_years`: 詳細築年数の数値化結果
- `detail_built_month`: 築年月の正規化結果
- `station_name`: 最寄り駅名
- `station_walk_minutes`: 徒歩分数

補足:

- `detail_*` 列は `--fetch-details` を付けたときだけ埋まります
- `*_yen`, `*_value`, `*_years` は学習向けの正規化列です
- `detail_built_month` は `YYYY-MM` 形式です
- 同じ建物でも部屋ごとに1行出力されます

## BigQuery 管理

まず GCP 認証情報を環境変数へ設定します。

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account.json"
```

そのうえで JSONL を BigQuery にロードします。

```powershell
.venv\Scripts\python.exe scripts\load_to_bigquery.py ^
  --project-id <YOUR_GCP_PROJECT_ID> ^
  --dataset suumo ^
  --table listings ^
  --input data\suumo\suumo_listings_20260405_132533.jsonl
```

スキーマは `bq/suumo_listings_schema.json` にあります。

おすすめの最初のテーブル設計:

- dataset: `suumo`
- table: `listings_raw`
- パーティション列: `scraped_at`
- クラスタ列候補: `listing_id`, `station_name`

## テスト

```powershell
.venv\Scripts\python.exe -m unittest tests.test_suumo_parser
```

## 注意

- SUUMOの利用条件、robots.txt、アクセス制御に従う
- 高頻度アクセスを避ける
- このスターターは一覧ページのクラス名に依存するため、HTML変更には弱い

## 次の一手

- 同一物件の `canonical_property_id` を作る
- 日次実行して `days_on_market` と価格改定回数を作る
- 数値化できていないアクセス情報をさらに分解する
- BigQuery に定期ロードするバッチを作る

# SUUMO scraper starter

東京都の `分譲物件` を対象に、`raw HTML` と `JSONL/CSV` を残すための最小構成です。

現在の標準対象:

- 中古マンション
- 新築一戸建て
- 中古一戸建て

賃貸ではなく、売買物件を前提にしています。

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 使い方

東京都の売買物件を小さく取得:

```powershell
.venv\Scripts\python.exe run_suumo_scraper.py --profile tokyo_sale_all --city-limit 10
```

東京都の売買物件 + 詳細ページを少数だけ取得:

```powershell
.venv\Scripts\python.exe run_suumo_scraper.py --profile tokyo_sale_all --city-limit 10 --fetch-details --detail-limit 3
```

任意のURLを直接取得:

```powershell
.venv\Scripts\python.exe run_suumo_scraper.py --profile custom_urls --url "https://suumo.jp/ms/chuko/tokyo/sc_setagaya/"
```

補足:

- `tokyo_sale_all` は東京都の市区町村ページを自動発見して巡回します
- `--city-limit` は巡回する市区町村ページ数です
- `--city-limit 0` で制限なしです

## 出力

- `raw/suumo/suumo_list_*.html`
- `raw/suumo/details_*/detail_*.html`
- `data/suumo/suumo_listings_*.jsonl`
- `data/suumo/suumo_listings_*.csv`

## 主なカラム

売買向けに特に重要な列:

- `listing_kind`: `used_mansion` / `new_house` / `used_house`
- `price_text`: 販売価格
- `price_yen`: 販売価格の数値化結果
- `building_name`: 物件名
- `address`: 所在地
- `access`: 沿線・駅
- `layout`: 間取り
- `area_m2`: 専有面積
- `land_area_m2`: 土地面積
- `building_area_m2`: 建物面積
- `age`: 築年月などの生値
- `station_name`: 最寄り駅名
- `station_walk_minutes`: 徒歩分数

詳細ページを取ると追加される列:

- `detail_address`
- `detail_age`
- `detail_floor_info`
- `detail_direction`
- `detail_building_type`
- `detail_structure`
- `detail_built_at`
- `detail_transaction_type`

## BigQuery

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account.json"
.venv\Scripts\python.exe scripts\create_bigquery_resources.py --project-id real-estate-data-492405 --dataset suumo --table listings_raw
.venv\Scripts\python.exe scripts\load_to_bigquery.py --project-id real-estate-data-492405 --dataset suumo --table listings_raw --input data\suumo\suumo_listings_20260405_132533.jsonl
```

## テスト

```powershell
.venv\Scripts\python.exe -m unittest tests.test_suumo_parser
```

## 注意

- SUUMOの利用条件、robots.txt、アクセス制御に従う
- 高頻度アクセスを避ける
- まずは小さく取得して、問題ないことを確認してから範囲を広げる

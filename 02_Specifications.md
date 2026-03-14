# ニュースダイジェスト自動生成システム 機能仕様書

## 1. システム概要

テック系ニュースを1日2回（朝6:00・夕18:00）自動収集・要約し、GitHub Pages で公開する個人用Webシステム。
毎週土曜日の朝には、週間ニュースをタイトル＋1行で振り返る総集編ページを追加生成する。

---

## 2. ファイル構成

```
news-digest/
├── 01_Requests.md
├── 02_Specifications.md        # 本ファイル
├── generate.py                 # メインスクリプト
├── config.yaml                 # 設定ファイル
├── seen_urls.json              # 取得済みURLキャッシュ（gitignore対象）
├── templates/
│   ├── digest.html.j2          # 日別ダイジェストテンプレート
│   └── weekly.html.j2          # 週次総集編テンプレート
├── index.html                  # ナビゲーションページ（自動更新）
├── pages/
│   └── 2026/
│       └── 03/
│           ├── 20260314_morning.html
│           ├── 20260314_morning.json   # 記事データ（weekly生成用）
│           ├── 20260314_evening.html
│           ├── 20260314_evening.json   # 記事データ（weekly生成用）
│           ├── 20260315_weekly.html    # 土曜日の週次総集編
│           └── ...
└── README.md
```

> `seen_urls.json` はローカルのみで管理し、`.gitignore` に追加する。

---

## 3. 設定ファイル仕様（config.yaml）

```yaml
model:
  primary: "gemini-3-flash-preview"        # メインモデル
  fallback: "gemini-3.1-flash-lite-preview"  # レート制限時のフォールバック

sources:
  tier1:
    limit: 5                            # 1ソースあたりの最大取得件数
    items:
      - name: "Anthropic Blog"
        url: "https://www.anthropic.com/blog"
        type: rss
      - name: "OpenAI Blog"
        url: "https://openai.com/blog"
        type: rss
      - name: "Google DeepMind Blog"
        url: "https://deepmind.google/blog"
        type: rss
      - name: "Hugging Face Blog"
        url: "https://huggingface.co/blog"
        type: rss
      - name: "Hacker News"
        url: "https://hacker-news.firebaseio.com/v0/"
        type: hn_api

  tier2:
    limit: 3
    items:
      - name: "Zenn トレンド"
        url: "https://zenn.dev/feed"
        type: rss
      - name: "Qiita トレンド"
        url: "https://qiita.com/popular-items/feed"
        type: rss
      - name: "VentureBeat AI"
        url: "https://venturebeat.com/ai/feed/"
        type: rss
      - name: "TechCrunch"
        url: "https://techcrunch.com/feed/"
        type: rss

  tier3:
    enabled: false                      # false でスキップ
    limit: 3
    items:
      - name: "arXiv cs.AI"
        url: "https://rss.arxiv.org/rss/cs.AI"
        type: rss
      - name: "Ars Technica"
        url: "https://feeds.arstechnica.com/arstechnica/index"
        type: rss
      - name: "The Verge"
        url: "https://www.theverge.com/rss/index.xml"
        type: rss
      - name: "ITmedia AI+"
        url: "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"
        type: rss

  tier4:
    limit: 3
    items:
      - name: "IEEE Spectrum Quantum"
        url: "https://spectrum.ieee.org/feeds/topic/quantum-computing.rss"
        type: rss
      - name: "Quantum Computing Report"
        url: "https://quantumcomputingreport.com/feed/"
        type: rss
      - name: "IBM Research Blog"
        url: "https://research.ibm.com/blog/rss"
        type: rss

  tier5:
    limit: 3
    items:
      - name: "Reuters World News"
        url: "https://feeds.reuters.com/reuters/worldNews"
        type: rss
      - name: "BBC World News"
        url: "https://feeds.bbci.co.uk/news/world/rss.xml"
        type: rss
      - name: "NHK国際放送"
        url: "https://www3.nhk.or.jp/rss/news/cat6.xml"
        type: rss

seen_urls:
  retention_days: 7                     # キャッシュ保持期間（日）
```

---

## 4. モジュール仕様

### 4.1 エントリポイント（generate.py）

**起動コマンド:**
```bash
uv run python generate.py morning   # 朝実行
uv run python generate.py evening   # 夕実行
uv run python generate.py weekly    # 週次総集編（土曜朝のみ）
```

**処理フロー（morning / evening）:**
1. コマンドライン引数 (`morning` / `evening`) を受け取る
2. `config.yaml` を読み込む
3. RSS収集モジュールを呼び出し記事リストを取得
4. `seen_urls.json` と照合し、未取得記事のみ残す
5. Gemini API で一括要約・翻訳
6. HTML生成モジュールで出力ファイルを生成（`YYYYMMDD_morning/evening.html`）
7. 記事データをJSONで保存（`YYYYMMDD_morning/evening.json`）
8. `index.html` を更新
9. `seen_urls.json` を更新
10. git commit & push

**処理フロー（weekly）:**
1. `pages/` から当週月曜〜金曜の `.json` ファイルを収集
2. 全記事の既存要約を Gemini API で150字以内に再要約（1回のAPIリクエスト）
3. 週次総集編HTMLを生成（`YYYYMMDD_weekly.html`）
4. `index.html` を更新
5. git commit & push

---

### 4.2 RSS収集モジュール

**対応フィード種別:**

| type    | 処理方法 |
|---------|---------|
| `rss`   | `feedparser` でフィードを取得し、`limit` 件まで収集 |
| `hn_api`| Hacker News Firebase API でスコア順Top500のIDを取得し、上位 `limit` 件のタイトル・URL・スコアを収集 |

**取得する記事メタ情報:**
- `title`: 記事タイトル
- `url`: 記事URL
- `published`: 公開日時（取得できない場合は収集日時）
- `source_name`: ソース名（config.yaml の `name`）
- `tier`: ティア番号（1 / 2 / 3）

**エラー処理:**
- タイムアウト: 10秒で打ち切り、そのソースはスキップ
- フィード取得失敗: 警告ログを出力してスキップ（他ソースへの影響なし）

---

### 4.3 seen_urls.json 管理モジュール

**スキーマ:**
```json
{
  "https://example.com/article1": "2026-03-14T06:00:00",
  "https://example.com/article2": "2026-03-13T18:00:00"
}
```

**処理:**
- 読み込み時: `retention_days` を超えたエントリを自動削除
- 書き込み時: 今回処理した記事URLを追加（ISO8601形式のタイムスタンプ付き）
- ファイルが存在しない場合: 空の辞書として初期化

---

### 4.4 要約・翻訳モジュール（Gemini API）

**APIキー:** 環境変数 `GEMINI_API_KEY` から取得

**ライブラリ:** `google-genai`

**一括処理仕様:**
- 未取得記事を全件まとめて1回のAPIリクエストで送信（コスト最小化）
- 記事が0件の場合はAPIを呼び出さずスキップ

**プロンプト仕様:**
```
以下のニュース記事リストを要約してください。

ルール:
- 英語記事は日本語に翻訳して要約する
- 日本語記事はそのまま要約する
- 各記事の要約は300字以内にまとめる
- 出力はJSON配列形式で返す: [{"id": 0, "summary": "..."}, ...]

記事リスト:
[各記事のID・タイトル・URLをリスト形式で渡す]
```

**フォールバック処理:**
- `primary` モデルがレート制限エラー（429）を返した場合、`fallback` モデルで再試行
- `fallback` も失敗した場合: 要約を `"取得できませんでした"` として処理を継続

---

### 4.5 記事データ保存モジュール（JSON）

HTML生成と同タイミングで、記事データをJSONファイルとして保存する。
週次総集編の生成時にこのデータを再利用することで、RSS再取得・API再呼び出しを不要にする。

**出力ファイル:** `pages/YYYY/MM/YYYYMMDD_morning.json` / `pages/YYYY/MM/YYYYMMDD_evening.json`

**スキーマ:**
```json
{
  "generated_at": "2026-03-14T06:12:34",
  "slot": "morning",
  "articles": [
    {
      "title": "記事タイトル",
      "url": "https://example.com/article",
      "source_name": "Anthropic Blog",
      "tier": 1,
      "published": "2026-03-14T05:00:00",
      "summary": "300字以内の要約テキスト"
    }
  ]
}
```

---

### 4.6 HTML生成モジュール（Jinja2）

**出力ファイル:**
- 朝実行: `pages/YYYY/MM/YYYYMMDD_morning.html`
- 夕実行: `pages/YYYY/MM/YYYYMMDD_evening.html`
- ディレクトリが存在しない場合は `os.makedirs(..., exist_ok=True)` で自動作成

**テンプレート（`templates/digest.html.j2`）の要素:**

| 要素 | 内容 |
|------|------|
| ページタイトル | `YYYY年MM月DD日 朝刊 / 夕刊 ニュースダイジェスト` |
| セクション | Tier 1: AI一次情報 / Tier 2: テック全般 / Tier 3: その他 / Tier 4: 量子コンピュータ / Tier 5: 世界情勢（有効なTierのみ表示） |
| 各記事カード | タイトル（元記事リンク付き）・ソース名・取得日時・日本語要約 |
| ヘッダー | ページタイトル・生成日時 |
| フッター | `index.html` へ戻るリンク |

**スタイル要件:**
- レスポンシブデザイン（モバイルファースト、ブレークポイント: 768px）
- ダークモード対応（`prefers-color-scheme: dark` メディアクエリ）
- 外部CSS/JSライブラリ不使用（単一HTMLファイルで完結）

---

### 4.7 週次総集編生成モジュール

**トリガー:** `generate.py weekly`（毎週土曜日6:00 実行）

**対象データの収集:**
- 実行日（土曜）の前週月曜〜金曜（5日分）の `.json` ファイルを `pages/YYYY/MM/` から読み込む
- 月をまたぐ週は複数の `YYYY/MM/` ディレクトリを参照する
- ファイルが存在しない日・スロットはスキップ（記事0件でも生成は実行する）

**再要約処理:**
- 各記事の既存 `summary` を Gemini API で **150字以内** に再要約
- 全記事まとめて1回のAPIリクエストで処理
- API失敗時: 既存 `summary` の先頭150字を切り詰めてフォールバック

**プロンプト仕様（weekly用）:**
```
以下のニュース記事リストをさらに短く要約してください。

ルール:
- 各要約を150字以内にまとめる
- 日本語で出力する
- 出力はJSON配列形式: [{"id": 0, "one_liner": "..."}, ...]

記事リスト:
[各記事のID・タイトル・既存summary をリスト形式で渡す]
```

**出力ファイル:** `pages/YYYY/MM/YYYYMMDD_weekly.html`（土曜日の日付）

**テンプレート（`templates/weekly.html.j2`）の要素:**

| 要素 | 内容 |
|------|------|
| ページタイトル | `YYYY年MM月第N週 週刊ニュースダイジェスト` |
| 期間表示 | `MM/DD（月）〜 MM/DD（金）` |
| セクション | 日付ごとにグループ化（月〜金の順） |
| 各記事行 | タイトル（リンク付き）・ソース名・1行要約 |
| ヘッダー | ページタイトル・生成日時 |
| フッター | `index.html` へ戻るリンク |

---

### 4.8 index.html 更新モジュール

**動作:**
- `pages/` を再帰スキャン（`glob("pages/**/*.html", recursive=True)`）し、`YYYYMMDD_morning.html` / `YYYYMMDD_evening.html` / `YYYYMMDD_weekly.html` を日付降順で取得
- ファイル名から日付・種別を判定し、リンクリストを生成・`index.html` を上書き
- `.json` ファイルはリンク一覧に含めない

**index.html の構成:**
- タイトル: `ニュースダイジェスト`
- 日付ごとにグループ化したリンク一覧（最新順）
- 各エントリ: 日付・朝刊/夕刊/週刊の表示と該当HTMLへのリンク
- 週次総集編は `[週刊]` バッジを付与して視覚的に区別

---

### 4.9 git 自動push モジュール

**実行コマンド（順次）:**
```bash
# morning / evening
git add pages/ index.html
git commit -m "digest: YYYYMMDD morning/evening"
git push origin main

# weekly
git add pages/ index.html
git commit -m "digest: YYYYMMDD weekly"
git push origin main
```

**エラー処理:**
- コミット対象ファイルが存在しない場合はスキップ
- push 失敗時: エラーログを出力して終了（HTMLファイルはローカルに保存済み）

---

## 5. タイムゾーン・日時取得ルール

### 基本方針
- システム全体で **JST（Asia/Tokyo, UTC+9）** を前提とする
- 日付・曜日・時刻はすべて実行時にシステムから取得し、ハードコードしない

### 実装ルール

**現在日時の取得（必須パターン）:**
```python
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
now = datetime.now(JST)  # 必ずこの形式を使う
```

**禁止パターン:**
```python
datetime.now()           # NG: タイムゾーン未指定
datetime.utcnow()        # NG: UTC基準
date.today()             # NG: システムロケール依存
```

**適用箇所と用途:**

| 用途 | 取得方法 |
|------|---------|
| 出力ファイル名の日付（`YYYYMMDD`） | `now.strftime("%Y%m%d")` |
| ディレクトリパス（`YYYY/MM`） | `now.strftime("%Y/%m")` |
| seen_urls.json のタイムスタンプ | `now.isoformat()` |
| JSON データの `generated_at` | `now.isoformat()` |
| HTML表示の生成日時 | `now.strftime("%Y年%m月%d日 %H:%M JST")` |
| weekly 対象期間の計算（月〜金） | `now.weekday()` で曜日を判定（0=月, 5=土） |
| weekly 対象JSONのパス解決 | 対象日ごとに `date.strftime("%Y/%m")` を算出 |

### 依存ライブラリ
- `zoneinfo` は Python 3.9 標準ライブラリ（追加インストール不要）
- Windows 環境で `ZoneInfo("Asia/Tokyo")` が失敗する場合のフォールバック:
  ```python
  try:
      from zoneinfo import ZoneInfo
  except ImportError:
      from backports.zoneinfo import ZoneInfo
  ```
  → `pyproject.toml` に `backports.zoneinfo` を依存追加することで対応

---

## 6. 環境変数・依存ライブラリ

### 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `GEMINI_API_KEY` | 必須 | Google Gemini API キー |

### 依存ライブラリ（pyproject.toml）

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "feedparser",
    "google-genai",
    "pyyaml",
    "jinja2",
    "backports.zoneinfo; python_version < '3.9'",  # 通常不要だが念のため
]
```

---

## 7. 自動実行設定（Windows タスクスケジューラ）

| 項目 | 朝（日次） | 夕（日次） | 週次総集編 |
|------|-----------|-----------|-----------|
| トリガー | 毎日 06:00 | 毎日 18:00 | 毎週土曜 06:00 |
| 実行コマンド | `uv run python generate.py morning` | `uv run python generate.py evening` | `uv run python generate.py weekly` |
| 作業ディレクトリ | プロジェクトルート | プロジェクトルート | プロジェクトルート |
| 実行ユーザー | ログオン中のユーザー | ログオン中のユーザー | ログオン中のユーザー |

> 土曜日は `morning`（通常の朝刊）と `weekly`（総集編）の両方が実行される。
> タスクスケジューラの実行順を `morning` → `weekly` とするか、`weekly` の開始時刻を 06:15 等にずらすこと。

---

## 8. .gitignore 対象

```
seen_urls.json
.env
__pycache__/
*.pyc
```

---

## 9. エラー・ログ方針

- 標準出力にログを出力（ファイル出力なし）
- 各ステップの開始・完了・スキップをログ出力
- エラー時も処理を継続し、最終的に取得できた記事のみでHTML生成
- 記事が1件も取得できなかった場合: HTML生成・git pushをスキップして終了

---

## 10. 未決事項・今後の検討

- [ ] ページデザインの詳細（カラースキーム・フォント等）
- [ ] Tier3ソースを週次で有効にするスケジュール管理の仕組み（土曜 morning 実行時のみ有効化する等）
- [ ] 記事本文をスクレイピングして要約精度を向上させる拡張（現状はタイトルのみ）

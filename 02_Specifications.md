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
│           ├── 20260314_morning.mp3    # ポッドキャスト音声（保持期間経過で自動削除）
│           ├── 20260314_morning_script.json # 生成した対話台本（デバッグ・再合成用）
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

podcast:
  enabled: true                         # false で音声生成をスキップ
  tts_model: "gemini-3.1-flash-tts-preview"  # マルチスピーカーTTSモデル
  retention_days: 30                    # 音声ファイル(mp3)の保持期間（日）
  speakers:                             # 話者は2名まで（Gemini TTS のマルチスピーカー上限）
    - name: "あかり"                     # 台本・TTSで使う話者名
      voice: "Kore"                     # Gemini TTS の voice プリセット（ホスト役）
    - name: "たくみ"
      voice: "Puck"                     # 相方役
```

> `podcast.enabled: false` の場合、`morning` / `evening` 実行では音声生成を丸ごとスキップする。
> `speakers` は必ず2名分を指定する（Gemini TTS のマルチスピーカーは最大2話者）。
> 台本生成には `model.primary` / `model.fallback`（要約と同じモデル）を流用し、追加のモデル設定は不要。

---

## 4. モジュール仕様

### 4.1 エントリポイント（generate.py）

**起動コマンド:**
```bash
uv run python generate.py morning   # 朝実行
uv run python generate.py evening   # 夕実行
uv run python generate.py weekly    # 週次総集編（土曜朝のみ）
uv run python generate.py podcast morning  # 当日 morning の音声のみ再生成（任意・手動）
```

> `podcast` サブコマンドは対象スロット（`morning` / `evening`）を第2引数で受け、既存の日別JSONから
> 音声のみを単独生成する。通常運用では daily 実行に統合された自動生成で足りるため、手動再生成用の補助コマンド。

**処理フロー（morning / evening）:**
1. コマンドライン引数 (`morning` / `evening`) を受け取る
2. `config.yaml` を読み込む
3. RSS収集モジュールを呼び出し記事リストを取得
4. `seen_urls.json` と照合し、未取得記事のみ残す
5. Gemini API で一括要約・翻訳
6. 記事データをJSONで保存（`YYYYMMDD_morning/evening.json`）
7. `podcast.enabled: true` の場合、ポッドキャスト音声を生成（`YYYYMMDD_{slot}.mp3`）し、保持期間切れの古い音声を削除
8. HTML生成モジュールで出力ファイルを生成（`YYYYMMDD_morning/evening.html`、音声があれば `<audio>` を埋め込み）
9. `index.html` を更新
10. `seen_urls.json` を更新
11. git commit & push

> 音声生成（手順7）は失敗しても致命的とせず、警告ログを出して後続処理を継続する
> （音声なしでもダイジェスト本体は公開する）。HTML生成（手順8）は音声生成の後に行い、
> 生成された mp3 の有無に応じてプレイヤー埋め込みを切り替える。

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

### 4.10 ポッドキャスト音声生成モジュール

日別ダイジェストの内容を、2人のポッドキャスターが掛け合いで解説する音声（mp3）に変換する。
NotebookLM 風の対話を **台本生成（LLM）→ 音声合成（TTS）→ mp3変換** の3段で実現する。

**入力:** 要約済みの記事リスト（`Article` のリスト）。daily フローから直接受け取るか、`podcast` サブコマンド時は日別JSONから復元する。

**処理の流れ:**

1. **台本生成（LLM）**
   - `model.primary` / `model.fallback`（要約と同じモデル）で、要約テキストから2人の対話台本を生成
   - 出力は話者ラベル付きの発話リスト（JSON配列）: `[{"speaker": "あかり", "text": "..."}, ...]`
   - 台本は `pages/YYYY/MM/YYYYMMDD_{slot}_script.json` に保存（デバッグ・再合成用）
   - プロンプトで相槌・軽い驚き・話題の受け渡し・専門用語のかみ砕きを指示し、楽しい雰囲気を演出
2. **音声合成（Gemini TTS）**
   - `podcast.tts_model`（`gemini-3.1-flash-tts-preview`）のマルチスピーカーで、台本全体を1回のAPI呼び出しで合成
   - `speakers` の `name` を話者ラベル、`voice` を各話者の声プリセットに割り当てる
   - 出力は PCM/WAV（24kHz・16bit・mono）
3. **mp3変換**
   - PCM を `wave` で WAV ファイルに書き出し、`subprocess` で `ffmpeg` を直接呼び出して mp3 に変換
   - 変換後、中間生成物の WAV ファイルは削除する
   - 出力先: `pages/YYYY/MM/YYYYMMDD_{slot}.mp3`
4. **古い音声の自動削除**
   - `pages/` 配下を走査し、`podcast.retention_days` を超えた `*.mp3` および `*_script.json` を削除
   - HTML・記事JSONは削除対象外（音声関連ファイルのみ）

**プロンプト仕様（台本生成）:**
```
以下のニュース要約を、2人のポッドキャスター（{speaker_a} と {speaker_b}）が
リスナーに楽しく解説するラジオ番組の台本にしてください。

ルール:
- 冒頭に軽い挨拶、最後に締めの一言を入れる
- 相槌・言い換え・軽い驚き・質問と回答のやり取りを自然に含める
- 専門用語はかみ砕いて説明する
- 全体で3〜5分程度の長さ（合計 6000 字以内）に収める
- 出力はJSON配列のみ: [{"speaker": "{speaker_a}", "text": "..."}, ...]
- speaker には {speaker_a} または {speaker_b} のみを使う

ニュース要約:
[各記事のタイトルと要約をリスト形式で渡す]
```

**TTS入力の組み立て:**
- 台本JSONを `"{speaker}: {text}"` の行に連結したテキストを TTS のプロンプトとして渡す
- 入力上限は 32k トークン。台本は 6000 字以内に収めるため通常は問題ないが、超過時は記事数を削って再構成

**エラー処理:**
- 台本生成失敗（API・パース）: 音声生成を中止し警告ログ、daily フローは継続（音声なしで公開）
- TTS 失敗: 同上（mp3 を生成せず継続）
- `ffmpeg` 不在で mp3 変換失敗: WAV を残さず警告ログ、継続

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

> mp3変換は追加ライブラリを使わず、`subprocess` で `ffmpeg` を直接呼び出す（`pydub` は
> Python 3.13+ で `audioop` モジュール依存が壊れているため不採用）。Windows/Ubuntu の
> 両環境に `ffmpeg` をインストールし、PATH を通しておくこと（`podcast.enabled: false` の場合は不要）。

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

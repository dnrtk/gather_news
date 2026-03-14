# ニュースダイジェスト自動生成システム ソフトウェア設計書

## 1. モジュール構成

```
generate.py               # エントリポイント（引数ルーティングのみ）
modules/
├── collector.py          # RSS/HN API からの記事収集
├── summarizer.py         # Gemini API による要約・翻訳
├── store.py              # seen_urls.json / digest JSON の読み書き
├── renderer.py           # Jinja2 による HTML 生成
├── index_builder.py      # index.html の再構築
└── publisher.py          # git commit & push
```

各モジュールは単一責務とし、`generate.py` がオーケストレーターとして呼び出す。
モジュール間の直接依存はなく、すべてのデータは `generate.py` 経由で受け渡す。

---

## 2. データ型定義

```python
# modules/collector.py
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Article:
    title: str
    url: str
    source_name: str
    tier: int                        # 1 / 2 / 3
    published: datetime              # JST aware datetime
    summary: str = ""                # summarizer が埋める
    one_liner: str = ""              # weekly summarizer が埋める
```

```python
# weekly 再要約の入力単位（store.py が JSON から復元）
@dataclass
class WeeklyArticle:
    title: str
    url: str
    source_name: str
    tier: int
    published: datetime
    summary: str                     # 日別 JSON の summary をそのまま使用
    date: date                       # 元の収集日（月〜金の分類用）
    slot: str                        # "morning" / "evening"
    one_liner: str = ""              # weekly summarizer が埋める
```

---

## 3. 関数シグネチャ

### generate.py

```python
def main() -> None
    """引数を解析し run_daily / run_weekly へ分岐する。"""

def run_daily(slot: str, config: dict) -> None
    """morning / evening の通常フローを実行する。"""

def run_weekly(config: dict) -> None
    """weekly 総集編の生成フローを実行する。"""
```

### modules/collector.py

```python
def collect_all(config: dict, now: datetime) -> list[Article]
    """config の全 tier・全ソースから記事を収集して返す。
    now は JST aware datetime（ファイル名・published フォールバックに使用）。"""

def _fetch_rss(source: dict, limit: int, now: datetime) -> list[Article]
    """feedparser でフィードを取得し Article リストを返す。
    タイムアウト 10 秒。失敗時は空リストを返す（例外を外に出さない）。"""

def _fetch_hn(source: dict, limit: int, now: datetime) -> list[Article]
    """HN Firebase API でスコア順 Top500 を取得し上位 limit 件を返す。
    失敗時は空リストを返す。"""
```

### modules/store.py

```python
def load_seen_urls(path: Path, retention_days: int, now: datetime) -> dict[str, str]
    """seen_urls.json を読み込み、retention_days を超えたエントリを除去して返す。
    ファイルが存在しない場合は空辞書を返す。"""

def save_seen_urls(path: Path, seen: dict[str, str], new_articles: list[Article], now: datetime) -> None
    """seen に new_articles の URL を追加して seen_urls.json に書き込む。"""

def filter_new(articles: list[Article], seen: dict[str, str]) -> list[Article]
    """seen に含まれない記事だけを返す。"""

def save_digest_json(articles: list[Article], slot: str, now: datetime, pages_dir: Path) -> Path
    """記事データを pages/YYYY/MM/YYYYMMDD_{slot}.json に保存し、そのパスを返す。"""

def load_weekly_articles(pages_dir: Path, target_dates: list[date]) -> list[WeeklyArticle]
    """target_dates の各日の morning/evening JSON を読み込み WeeklyArticle リストを返す。
    ファイルが存在しない日・スロットはスキップする。"""
```

### modules/summarizer.py

```python
def summarize(articles: list[Article], api_key: str, primary: str, fallback: str) -> list[Article]
    """全記事をまとめて Gemini API に投げ、summary を埋めた Article リストを返す。
    articles が空の場合は即返却（API 呼び出しなし）。
    primary が 429 の場合は fallback で再試行。
    fallback も失敗した場合は summary = "取得できませんでした" として継続。"""

def summarize_weekly(articles: list[WeeklyArticle], api_key: str, primary: str, fallback: str) -> list[WeeklyArticle]
    """全記事の summary を 50 字以内の one_liner に再要約して返す。
    API 失敗時は summary の先頭 50 字をフォールバックとして使用。"""

def _call_api(prompt: str, api_key: str, model: str) -> str
    """Gemini API を呼び出しレスポンステキストを返す。429 時は RateLimitError を raise する。"""

def _parse_summaries(response: str, articles: list) -> list
    """API レスポンス（JSON 文字列）をパースして articles に結果をマージする。
    パース失敗時は元の articles をそのまま返す（フォールバック済みとして扱う）。"""
```

### modules/renderer.py

```python
def render_digest(articles: list[Article], slot: str, now: datetime, pages_dir: Path) -> Path
    """digest.html.j2 を使って日別ダイジェスト HTML を生成し、そのパスを返す。
    出力先: pages/YYYY/MM/YYYYMMDD_{slot}.html（ディレクトリは自動作成）。"""

def render_weekly(articles: list[WeeklyArticle], week_dates: list[date], now: datetime, pages_dir: Path) -> Path
    """weekly.html.j2 を使って週次総集編 HTML を生成し、そのパスを返す。
    出力先: pages/YYYY/MM/YYYYMMDD_weekly.html（土曜日付）。"""

def _get_output_path(pages_dir: Path, now: datetime, suffix: str) -> Path
    """pages/YYYY/MM/YYYYMMDD_{suffix}.html のパスを返す。ディレクトリを作成する。"""
```

### modules/index_builder.py

```python
def update_index(pages_dir: Path, index_path: Path) -> None
    """pages/ を再帰スキャンして *.html を収集し、日付降順でソートして index.html を上書きする。
    weekly ページは [週刊] バッジを付与する。"""

def _parse_page_entry(html_path: Path) -> dict | None
    """ファイル名から {"date": date, "slot": str, "path": Path} を返す。
    パターンに合わない場合は None を返す。"""
```

### modules/publisher.py

```python
def git_push(commit_message: str) -> None
    """git add pages/ index.html → commit → push を順次実行する。
    コミット対象の変更がない場合はスキップする。
    push 失敗時は例外をキャッチしてエラーログを出力し、処理を終了する。"""
```

---

## 4. データフロー

### 4.1 daily（morning / evening）

```
main()
  └─ run_daily(slot, config)
       │
       ├─ collect_all(config, now)
       │    ├─ _fetch_rss() × N ソース
       │    └─ _fetch_hn()
       │    → list[Article]  ★ summary=""
       │
       ├─ load_seen_urls(path, retention_days, now)
       │    → dict[url, timestamp]
       │
       ├─ filter_new(articles, seen)
       │    → list[Article]  ★ 未取得のみ
       │
       ├─ summarize(articles, ...)          ← 0件なら skip
       │    → list[Article]  ★ summary 埋まり
       │
       ├─ render_digest(articles, slot, now, pages_dir)
       │    → pages/YYYY/MM/YYYYMMDD_{slot}.html
       │
       ├─ save_digest_json(articles, slot, now, pages_dir)
       │    → pages/YYYY/MM/YYYYMMDD_{slot}.json
       │
       ├─ update_index(pages_dir, index_path)
       │    → index.html 上書き
       │
       ├─ save_seen_urls(path, seen, articles, now)
       │    → seen_urls.json 上書き
       │
       └─ git_push("digest: YYYYMMDD {slot}")
```

### 4.2 weekly

```
main()
  └─ run_weekly(config)
       │
       ├─ _calc_week_dates(now)             ← JST の now から月〜金を算出
       │    → list[date]  5件
       │
       ├─ load_weekly_articles(pages_dir, week_dates)
       │    → list[WeeklyArticle]  ★ one_liner=""
       │
       ├─ summarize_weekly(articles, ...)   ← 0件なら skip
       │    → list[WeeklyArticle]  ★ one_liner 埋まり
       │
       ├─ render_weekly(articles, week_dates, now, pages_dir)
       │    → pages/YYYY/MM/YYYYMMDD_weekly.html
       │
       ├─ update_index(pages_dir, index_path)
       │    → index.html 上書き
       │
       └─ git_push("digest: YYYYMMDD weekly")
```

---

## 5. 主要アルゴリズム

### 5.1 weekly 対象期間の計算

```python
def _calc_week_dates(now: datetime) -> list[date]:
    """実行日（土曜）から当週の月〜金の date リストを返す。"""
    today = now.date()
    # weekday(): 月=0, 火=1, ..., 土=5
    # 土曜から 5 日前が月曜
    monday = today - timedelta(days=today.weekday())  # 当週月曜
    return [monday + timedelta(days=i) for i in range(5)]  # 月〜金
```

### 5.2 seen_urls TTL 管理

```python
def load_seen_urls(path: Path, retention_days: int, now: datetime) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    cutoff = now - timedelta(days=retention_days)
    return {
        url: ts
        for url, ts in data.items()
        if datetime.fromisoformat(ts).replace(tzinfo=JST) > cutoff
    }
```

### 5.3 Gemini API プロンプト構築（daily）

```python
def _build_prompt(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles):
        lines.append(f"id={i}, title={a.title}, url={a.url}")
    body = "\n".join(lines)
    return f"""\
以下のニュース記事リストを要約してください。

ルール:
- 英語記事は日本語に翻訳して要約する
- 日本語記事はそのまま要約する
- 各記事の要約は300字以内にまとめる
- 出力はJSON配列形式で返す: [{{"id": 0, "summary": "..."}}]

記事リスト:
{body}
"""
```

### 5.4 API レスポンスのパース

Gemini API のレスポンスにはコードフェンス（` ```json ... ``` `）が含まれる場合があるため、
正規表現で JSON 部分を抽出してからパースする。

```python
import re, json

def _parse_summaries(response: str, articles: list[Article]) -> list[Article]:
    # コードフェンスを除去
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if not match:
        return articles  # パース失敗 → フォールバック済み articles を返す
    data = json.loads(match.group())
    id_to_summary = {item["id"]: item["summary"] for item in data}
    for i, a in enumerate(articles):
        a.summary = id_to_summary.get(i, "取得できませんでした")
    return articles
```

---

## 6. JST 定数の共有

タイムゾーンオブジェクトはモジュールをまたいで共通利用するため、
`generate.py` のトップレベルで定義し、各関数の引数として `now: datetime` を渡す。
モジュール内での `datetime.now()` 呼び出しは禁止。

```python
# generate.py
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

def main():
    now = datetime.now(JST)   # ← 唯一の now 生成箇所
    ...
    run_daily(slot, config, now)
```

---

## 7. エラー処理方針

| 発生箇所 | 対処 | 継続可否 |
|---------|------|---------|
| RSS/HN 取得失敗（タイムアウト・接続エラー） | 警告ログ出力、そのソースをスキップ | 継続 |
| Gemini API 429（primary） | fallback モデルで再試行 | 継続 |
| Gemini API 失敗（fallback も失敗） | summary = "取得できませんでした" | 継続 |
| API レスポンスの JSON パース失敗 | articles をそのまま使用（summary 空のまま） | 継続 |
| weekly JSON ファイル不存在 | その日・スロットをスキップ | 継続 |
| 記事が 0 件（daily） | HTML 生成・git push をスキップして正常終了 | 終了 |
| git push 失敗 | エラーログ出力して異常終了（HTML はローカル保存済み） | 終了 |

---

## 8. ログ出力フォーマット

標準出力に以下の形式で出力する（ファイル保存なし）。

```
[INFO]  collect: Anthropic Blog → 5 件取得
[INFO]  collect: Hacker News → 5 件取得
[WARN]  collect: Zenn トレンド → 失敗（タイムアウト）、スキップ
[INFO]  filter: 12 件中 9 件が未取得
[INFO]  summarize: primary モデルで要約開始
[INFO]  summarize: 完了
[INFO]  render: pages/2026/03/20260314_morning.html 生成
[INFO]  store: pages/2026/03/20260314_morning.json 保存
[INFO]  index: index.html 更新
[INFO]  seen_urls: 9 件追加、合計 47 件
[INFO]  git: コミット・プッシュ完了
```

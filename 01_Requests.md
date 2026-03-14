# ニュースダイジェスト自動生成システム 要件定義

## 概要

テック系を中心とした主要ニュースを1日2回（朝・夕）自動収集・要約し、個人用Webページとして公開するシステム。
Claude Codeで自動実行し、GitHub Pagesでホスティングする。

---

## システム構成

```
Windowsタスクスケジューラ（6:00 / 18:00）
  └─ generate.py 実行（引数で morning / evening を指定）
       ├─ RSS取得 (feedparser) ← 各ニュースソースから最新記事収集
       ├─ seen_urls.json 照合 → 未取得記事のみ対象
       ├─ Anthropic API呼び出し ← まとめて要約・翻訳（1回）
       ├─ morning.html または evening.html 生成
       ├─ index.html 更新（最新版へのリンクナビゲーション）
       └─ git commit & push → GitHub Pages 自動反映
```

---

## ニュースソース

### Tier 1 - 毎日必須（AI一次情報）

| ソース | URL | 備考 |
|--------|-----|------|
| Anthropic Blog | https://www.anthropic.com/blog | RSS あり |
| OpenAI Blog | https://openai.com/blog | RSS あり |
| Google DeepMind Blog | https://deepmind.google/blog | RSS あり |
| Hugging Face Blog | https://huggingface.co/blog | RSS あり |
| Hacker News | https://news.ycombinator.com | 公式JSON API / RSS あり |

### Tier 2 - 毎日（テック全般・日本語）

| ソース | URL | 備考 |
|--------|------|------|
| Zenn トレンド | https://zenn.dev | RSS あり |
| Qiita トレンド | https://qiita.com | RSS あり |
| VentureBeat AI | https://venturebeat.com/ai | RSS あり |
| TechCrunch | https://techcrunch.com | RSS あり |

### Tier 3 - 任意（週次でも可）

| ソース | URL | 備考 |
|--------|------|------|
| arXiv (cs.AI / cs.LG) | https://arxiv.org | RSS あり |
| Ars Technica | https://arstechnica.com | RSS あり |
| The Verge | https://www.theverge.com | RSS あり |
| ITmedia AI+ | https://www.itmedia.co.jp/aiplus/ | RSS あり |

### Tier 4 - 量子コンピュータ

| ソース | URL | 備考 |
|--------|------|------|
| IEEE Spectrum Quantum | https://spectrum.ieee.org/feeds/topic/quantum-computing.rss | RSS あり |
| Quantum Computing Report | https://quantumcomputingreport.com/feed/ | RSS あり |
| IBM Research Blog | https://research.ibm.com/blog/rss | RSS あり |

### Tier 5 - 世界情勢

| ソース | URL | 備考 |
|--------|------|------|
| Reuters World News | https://feeds.reuters.com/reuters/worldNews | RSS あり |
| BBC World News | https://feeds.bbci.co.uk/news/world/rss.xml | RSS あり |
| NHK国際放送 | https://www3.nhk.or.jp/rss/news/cat6.xml | RSS あり |

---

## 機能要件

### ニュース収集
- feedparser を使ってRSSフィードから最新記事を取得
- Hacker Newsは公式JSON API（`https://hacker-news.firebaseio.com/v0/`）でスコア順Top10取得
- 取得件数：Tier1は5件、Tier2は3件（config.yaml で変更可能）
- seen_urls.json で取得済みURLを管理し、重複記事をスキップ
- seen_urls.json の保持期間：**7日間**（古いエントリは自動削除）

### 要約・翻訳
- 収集した記事をまとめてAnthropicAPIに1回で渡す（コスト最小化）
- 英語記事は日本語に翻訳して要約
- 日本語記事はそのまま要約
- 要約は300字以内（日別ダイジェスト）
- 使用モデル: `gemini-3-flash-preview`（無料枠、config.yaml で変更可能）
- フォールバック: `gemini-3.1-flash-lite-preview`（レート制限時に自動切り替え）
- APIキー: 環境変数 `GEMINI_API_KEY` から取得

### HTML生成
- 実行タイミングに応じて別ファイルを生成
  - 朝6:00実行 → `YYYYMMDD_morning.html`
  - 夕18:00実行 → `YYYYMMDD_evening.html`
- `index.html` は過去ページへのリンク一覧として機能（ナビゲーション用）
- カテゴリ別にセクション分け（AI一次情報 / テック全般 / 日本語）
- 各記事に：タイトル・要約・元記事リンク・ソース名・取得日時を表示
- レスポンシブデザイン（スマホでも読みやすい）
- ダークモード対応

### 自動公開
- 生成後に `git add . && git commit && git push` を自動実行
- GitHub Pages（mainブランチの /root）に即時反映

### 自動実行（Windows）
- Windowsタスクスケジューラで1日2回起動
  - 朝：`06:00` → `uv run python generate.py morning`
  - 夕：`18:00` → `uv run python generate.py evening`
- 毎週土曜日の朝6:00に週次総集編を追加生成
  - `uv run python generate.py weekly`

### 週次総集編
- 毎週土曜日の朝、当週月曜〜金曜のニュースをまとめた総集編ページを生成
- 各記事をタイトル＋要約（150字以内）で一覧表示
- 日別ダイジェストの要約データを再利用し、APIコールを最小化
- 出力ファイル: `pages/YYYYMMDD_weekly.html`（土曜日の日付）

---

## 非機能要件

- **APIコスト最小化**: RSSで記事メタ情報を取得し、Claude APIは要約のみに使う
- **実行時間**: 5分以内に完了
- **エラー時**: 失敗したソースはスキップし、取得できた分だけでHTML生成
- **設定の外部化**: ソース一覧・件数・モデル名などは設定ファイル（config.yaml等）で管理
- **タイムゾーン**: システム全体でJST（Asia/Tokyo, UTC+9）を前提とする
- **日付・曜日の取得**: ハードコードせず、実行時に必ずシステムから取得する（`datetime.now(ZoneInfo("Asia/Tokyo"))`）

---

## ディレクトリ構成（案）

```
news-digest/
├── 00_Requests.md            # 本ファイル
├── generate.py               # メインスクリプト
├── config.yaml               # ソース設定・件数・モデルなど
├── seen_urls.json            # 取得済みURLキャッシュ（7日保持）
├── index.html                # ナビゲーション（過去ページへのリンク一覧）
├── pages/
│   ├── 20260314_morning.html
│   ├── 20260314_evening.html
│   └── ...                   # 日付_morning/evening.html が蓄積
└── README.md
```

---

## 開発環境

- OS: Windows (動作環境はWindowsとUbuntu両対応が必要)
- パッケージマネージャ: uv
- エディタ: VS Code + Claude Code拡張
- Python: 3.11以上
- 主要ライブラリ: `feedparser`, `google-genai`, `pyyaml`, `jinja2`（HTML生成用）

---

## 実装ステップ

1. GitHubリポジトリ作成 → GitHub Pages有効化
2. `config.yaml` 作成（ソース一覧定義）
3. RSS取得モジュール実装（feedparser + HN API）
4. Anthropic API呼び出し・要約モジュール実装
5. HTML生成モジュール実装（Jinja2テンプレート）
6. git自動push処理実装
7. ローカルで動作確認
8. Windowsタスクスケジューラ設定

---

## 未決事項

- [ ] ページデザインの詳細
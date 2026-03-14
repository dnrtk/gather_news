# gather_news

テック系ニュースを1日2回（朝・夕）自動収集・要約し、GitHub Pages で公開する個人用システム。
毎週土曜日には週間総集編ページを生成します。

**公開先:** https://dnrtk.github.io/gather_news/

---

## 機能

- RSS / Hacker News API からニュースを自動収集
- Gemini API で日本語要約（英語記事は翻訳）
- GitHub Pages へ自動 push・公開
- サイドバーで日付ナビゲーション、ダークモード対応
- 毎週土曜日に週間総集編を生成

## 収集ソース

| Tier | ソース |
|------|--------|
| 1（AI一次情報） | Anthropic Blog / OpenAI Blog / Google DeepMind / Hugging Face / Hacker News |
| 2（テック全般） | Zenn / Qiita / VentureBeat AI / TechCrunch |
| 3（任意・無効） | arXiv / Ars Technica / The Verge / ITmedia AI+ |

---

## セットアップ

### 必要なもの

- Python 3.11 以上
- [uv](https://docs.astral.sh/uv/)
- Gemini API キー（[Google AI Studio](https://aistudio.google.com/) で無料取得）
- GitHub アカウント（Pages 用）

### 手順

```bash
# 1. リポジトリをクローン
git clone git@github.com:dnrtk/gather_news.git
cd gather_news

# 2. 依存ライブラリをインストール
uv sync

# 3. 環境変数ファイルを作成
echo "export GEMINI_API_KEY=your_api_key_here" > .env
chmod 600 .env

# 4. 動作確認
uv run python generate.py morning
```

### GitHub Pages の有効化

リポジトリの **Settings → Pages → Source** を `main` ブランチ / `/ (root)` に設定して Save。

---

## 使い方

```bash
uv run python generate.py morning   # 朝刊を生成・push
uv run python generate.py evening   # 夕刊を生成・push
uv run python generate.py weekly    # 週間総集編を生成・push（土曜推奨）
```

### テンプレート変更後の全ページ再レンダリング

```bash
uv run python rerender.py
```

---

## 自動実行の設定

### Windows（タスクスケジューラ）

タスクスケジューラで以下の2タスクを作成します。

| タスク | トリガー | 操作 |
|--------|---------|------|
| 朝刊 | 毎日 06:00 | `uv run python generate.py morning` |
| 夕刊 | 毎日 18:00 | `uv run python generate.py evening` |
| 週刊 | 毎週土曜 06:15 | `uv run python generate.py weekly` |

作業ディレクトリはプロジェクトルートを指定してください。
環境変数 `GEMINI_API_KEY` はシステムの環境変数として登録するか、タスクの「環境変数」設定に追加します。

---

### Ubuntu（cron）

#### 1. タイムゾーンを JST に設定

```bash
sudo timedatectl set-timezone Asia/Tokyo
timedatectl  # Asia/Tokyo になっていることを確認
```

#### 2. 環境変数ファイルを作成

```bash
echo "export GEMINI_API_KEY=your_api_key_here" > /path/to/gather_news/.env
chmod 600 /path/to/gather_news/.env
```

> `.env` は `.gitignore` 対象なので誤って push されません。

#### 3. git の SSH 設定

cron からの自動 push には SSH 認証が必要です。

```bash
# SSH キーを生成（既にある場合はスキップ）
ssh-keygen -t ed25519 -C "your@email.com"

# 公開鍵を GitHub に登録
cat ~/.ssh/id_ed25519.pub
# → GitHub Settings → SSH keys に追加

# リモートURLを SSH に変更
cd /path/to/gather_news
git remote set-url origin git@github.com:dnrtk/gather_news.git

# 接続確認
ssh -T git@github.com
```

#### 4. uv のパスを確認

```bash
which uv
# → 例: /home/yourname/.local/bin/uv
```

#### 5. crontab に登録

```bash
crontab -e
```

以下を追記します（パスは環境に合わせて変更）。

```cron
0 6  * * 1-6 . /path/to/gather_news/.env && cd /path/to/gather_news && /home/yourname/.local/bin/uv run python generate.py morning >> /path/to/gather_news/cron.log 2>&1
0 18 * * 1-6 . /path/to/gather_news/.env && cd /path/to/gather_news && /home/yourname/.local/bin/uv run python generate.py evening >> /path/to/gather_news/cron.log 2>&1
15 6 * * 6   . /path/to/gather_news/.env && cd /path/to/gather_news && /home/yourname/.local/bin/uv run python generate.py weekly  >> /path/to/gather_news/cron.log 2>&1
```

| 式 | 意味 |
|----|------|
| `0 6 * * 1-6` | 月〜土 6:00 |
| `0 18 * * 1-6` | 月〜土 18:00 |
| `15 6 * * 6` | 土曜 6:15（morning の後に実行） |

#### 6. 動作確認

```bash
# 手動実行でエラーがないか確認
. /path/to/gather_news/.env && cd /path/to/gather_news && uv run python generate.py morning

# ログ確認
tail -f /path/to/gather_news/cron.log
```

---

## 設定変更

`config.yaml` で以下を変更できます。

| 項目 | デフォルト |
|------|-----------|
| 使用モデル | `gemini-3-flash-preview` |
| フォールバックモデル | `gemini-3.1-flash-lite-preview` |
| Tier1 取得件数 | 5件 |
| Tier2 取得件数 | 3件 |
| Tier3 有効/無効 | 無効 |
| seen_urls 保持期間 | 7日 |

---

## ディレクトリ構成

```
gather_news/
├── generate.py          # メインスクリプト
├── rerender.py          # テンプレート変更後の再レンダリング
├── config.yaml          # 設定ファイル
├── modules/             # 各処理モジュール
├── templates/           # Jinja2 HTMLテンプレート
├── pages/               # 生成されたHTMLページ
│   └── YYYY/MM/
│       ├── YYYYMMDD_morning.html
│       ├── YYYYMMDD_evening.html
│       └── YYYYMMDD_weekly.html
├── index.html           # ナビゲーション（自動生成）
├── nav.json             # サイドバー用データ（自動生成）
└── seen_urls.json       # 取得済みURLキャッシュ（gitignore）
```

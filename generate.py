import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from modules.collector import collect_all
from modules.index_builder import update_index
from modules.publisher import git_push
from modules.renderer import render_digest, render_weekly
from modules.store import (
    filter_new,
    load_seen_urls,
    load_weekly_articles,
    save_digest_json,
    save_seen_urls,
)
from modules.summarizer import summarize, summarize_weekly

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
PROJECT_ROOT = Path(__file__).parent
PAGES_DIR = PROJECT_ROOT / "pages"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
SEEN_URLS_PATH = PROJECT_ROOT / "seen_urls.json"
INDEX_PATH = PROJECT_ROOT / "index.html"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="ニュースダイジェスト生成")
    parser.add_argument("slot", choices=["morning", "evening", "weekly"])
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY が設定されていません")
        sys.exit(1)

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    now = datetime.now(JST)

    if args.slot in ("morning", "evening"):
        run_daily(args.slot, config, now, api_key)
    else:
        run_weekly(config, now, api_key)


def run_daily(slot: str, config: dict, now: datetime, api_key: str) -> None:
    model_cfg = config["model"]

    # 1. 収集
    articles = collect_all(config, now)

    # 2. 重複フィルタ
    retention = config.get("seen_urls", {}).get("retention_days", 7)
    seen = load_seen_urls(SEEN_URLS_PATH, retention, now)
    articles = filter_new(articles, seen)

    if not articles:
        logger.info("新着記事なし。スキップします。")
        return

    # 3. 要約
    articles = summarize(articles, api_key, model_cfg["primary"], model_cfg["fallback"])

    # 4. HTML生成
    render_digest(articles, slot, now, PAGES_DIR, TEMPLATES_DIR)

    # 5. JSONデータ保存
    save_digest_json(articles, slot, now, PAGES_DIR)

    # 6. index.html 更新
    update_index(PAGES_DIR, INDEX_PATH, PROJECT_ROOT)

    # 7. seen_urls 更新
    save_seen_urls(SEEN_URLS_PATH, seen, articles, now)

    # 8. git push
    git_push(f"digest: {now.strftime('%Y%m%d')} {slot}")


def run_weekly(config: dict, now: datetime, api_key: str) -> None:
    model_cfg = config["model"]

    # 1. 当週月〜金の date リスト（JST 基準）
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    week_dates = [monday + timedelta(days=i) for i in range(5)]

    # 2. JSON から記事読み込み
    articles = load_weekly_articles(PAGES_DIR, week_dates)

    if not articles:
        logger.info("週次記事データなし。スキップします。")
        return

    # 3. 再要約
    articles = summarize_weekly(
        articles, api_key, model_cfg["primary"], model_cfg["fallback"]
    )

    # 4. HTML生成
    render_weekly(articles, week_dates, now, PAGES_DIR, TEMPLATES_DIR)

    # 5. index.html 更新
    update_index(PAGES_DIR, INDEX_PATH, PROJECT_ROOT)

    # 6. git push
    git_push(f"digest: {now.strftime('%Y%m%d')} weekly")


if __name__ == "__main__":
    main()

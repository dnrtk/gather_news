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
from modules.podcast import generate_podcast
from modules.publisher import git_push
from modules.renderer import render_digest, render_weekly
from modules.store import (
    filter_new,
    load_digest_articles,
    load_seen_urls,
    load_weekly_articles,
    save_digest_json,
    save_seen_urls,
)
from modules.summarizer import summarize, summarize_weekly

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
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
    parser.add_argument("mode", choices=["morning", "evening", "weekly", "podcast"])
    parser.add_argument(
        "podcast_slot",
        nargs="?",
        choices=["morning", "evening"],
        help="mode=podcast の場合に対象スロットを指定",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY が設定されていません")
        sys.exit(1)

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    now = datetime.now(JST)

    if args.mode in ("morning", "evening"):
        run_daily(args.mode, config, now, api_key)
    elif args.mode == "weekly":
        run_weekly(config, now, api_key)
    else:
        if not args.podcast_slot:
            logger.error("podcast モードには slot (morning/evening) の指定が必要です")
            sys.exit(1)
        run_podcast(args.podcast_slot, config, now, api_key)


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

    # 4. JSONデータ保存
    save_digest_json(articles, slot, now, PAGES_DIR)

    # 5. ポッドキャスト音声生成（失敗しても継続）
    podcast_cfg = config.get("podcast", {})
    if podcast_cfg.get("enabled", False):
        generate_podcast(articles, slot, now, PAGES_DIR, api_key, podcast_cfg, model_cfg)

    # 6. HTML生成
    render_digest(articles, slot, now, PAGES_DIR, TEMPLATES_DIR)

    # 7. index.html 更新
    update_index(PAGES_DIR, INDEX_PATH, PROJECT_ROOT)

    # 8. seen_urls 更新
    save_seen_urls(SEEN_URLS_PATH, seen, articles, now)

    # 9. git push
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


def run_podcast(slot: str, config: dict, now: datetime, api_key: str) -> None:
    model_cfg = config["model"]
    podcast_cfg = config.get("podcast", {})
    if not podcast_cfg.get("enabled", False):
        logger.error("podcast.enabled が false のため実行できません")
        sys.exit(1)

    # 1. 既存の日別JSONから記事読み込み
    articles = load_digest_articles(PAGES_DIR, slot, now)
    if not articles:
        logger.info(f"{slot} の記事データなし。スキップします。")
        return

    # 2. ポッドキャスト音声を再生成
    result = generate_podcast(articles, slot, now, PAGES_DIR, api_key, podcast_cfg, model_cfg)
    if result is None:
        logger.error("podcast: 音声生成に失敗しました")
        sys.exit(1)

    # 3. HTMLを再生成（<audio> 埋め込みを反映）
    render_digest(articles, slot, now, PAGES_DIR, TEMPLATES_DIR)

    # 4. git push
    git_push(f"podcast: {now.strftime('%Y%m%d')} {slot} 再生成")


if __name__ == "__main__":
    main()

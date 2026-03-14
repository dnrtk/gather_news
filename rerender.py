"""
既存の JSON データから全ページを再レンダリングするユーティリティ。
テンプレートを変更した後などに使用する。

使い方:
    uv run python rerender.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from modules.index_builder import update_index
from modules.models import Article, WeeklyArticle
from modules.renderer import render_digest, render_weekly

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]  %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
PROJECT_ROOT = Path(__file__).parent
PAGES_DIR = PROJECT_ROOT / "pages"
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def main() -> None:
    json_files = sorted(PAGES_DIR.glob("**/*.json"))
    if not json_files:
        logger.info("JSONファイルが見つかりません。")
        return

    count = 0
    for json_path in json_files:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        slot = data["slot"]
        now = datetime.fromisoformat(data["generated_at"]).astimezone(JST)

        if slot in ("morning", "evening"):
            articles = [
                Article(
                    title=a["title"],
                    url=a["url"],
                    source_name=a["source_name"],
                    tier=a["tier"],
                    published=datetime.fromisoformat(a["published"]).astimezone(JST),
                    summary=a["summary"],
                )
                for a in data["articles"]
            ]
            render_digest(articles, slot, now, PAGES_DIR, TEMPLATES_DIR)
            count += 1

    update_index(PAGES_DIR, PROJECT_ROOT / "index.html", PROJECT_ROOT)
    logger.info(f"完了: {count} ページ再レンダリング、index.html / nav.json 更新")


if __name__ == "__main__":
    main()

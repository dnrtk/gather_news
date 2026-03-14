import json
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

from modules.models import Article, WeeklyArticle

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")


def load_seen_urls(path: Path, retention_days: int, now: datetime) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    cutoff = now - timedelta(days=retention_days)
    return {
        url: ts
        for url, ts in data.items()
        if datetime.fromisoformat(ts).astimezone(JST) > cutoff
    }


def save_seen_urls(
    path: Path, seen: dict[str, str], new_articles: list[Article], now: datetime
) -> None:
    for a in new_articles:
        seen[a.url] = now.isoformat()
    path.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"seen_urls: {len(new_articles)} 件追加、合計 {len(seen)} 件")


def filter_new(articles: list[Article], seen: dict[str, str]) -> list[Article]:
    new = [a for a in articles if a.url not in seen]
    logger.info(f"filter: {len(articles)} 件中 {len(new)} 件が未取得")
    return new


def save_digest_json(
    articles: list[Article], slot: str, now: datetime, pages_dir: Path
) -> Path:
    dir_path = pages_dir / now.strftime("%Y") / now.strftime("%m")
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{now.strftime('%Y%m%d')}_{slot}.json"

    data = {
        "generated_at": now.isoformat(),
        "slot": slot,
        "articles": [
            {
                "title": a.title,
                "url": a.url,
                "source_name": a.source_name,
                "tier": a.tier,
                "published": a.published.isoformat(),
                "summary": a.summary,
            }
            for a in articles
        ],
    }
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"store: {file_path} 保存")
    return file_path


def load_weekly_articles(pages_dir: Path, target_dates: list[date]) -> list[WeeklyArticle]:
    articles = []
    for d in target_dates:
        dir_path = pages_dir / d.strftime("%Y") / d.strftime("%m")
        for slot in ["morning", "evening"]:
            json_path = dir_path / f"{d.strftime('%Y%m%d')}_{slot}.json"
            if not json_path.exists():
                continue
            data = json.loads(json_path.read_text(encoding="utf-8"))
            for item in data.get("articles", []):
                articles.append(
                    WeeklyArticle(
                        title=item["title"],
                        url=item["url"],
                        source_name=item["source_name"],
                        tier=item["tier"],
                        published=datetime.fromisoformat(item["published"]).astimezone(JST),
                        summary=item["summary"],
                        date=d,
                        slot=slot,
                    )
                )
    logger.info(f"store: weekly 記事 {len(articles)} 件読み込み")
    return articles

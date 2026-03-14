import json
import logging
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser

from modules.models import Article

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")
TIMEOUT = 10


def collect_all(config: dict, now: datetime) -> list[Article]:
    articles = []
    sources = config.get("sources", {})

    for tier_key, tier_cfg in sources.items():
        if not tier_cfg.get("enabled", True):
            logger.info(f"collect: {tier_key} は無効、スキップ")
            continue
        tier_num = int(tier_key.replace("tier", ""))
        limit = tier_cfg.get("limit", 5)
        for source in tier_cfg.get("items", []):
            src_type = source.get("type", "rss")
            if src_type == "rss":
                fetched = _fetch_rss(source, limit, now, tier_num)
            elif src_type == "hn_api":
                fetched = _fetch_hn(source, limit, now, tier_num)
            else:
                logger.warning(f"collect: 未知のタイプ {src_type}、スキップ")
                continue
            articles.extend(fetched)

    return articles


def _fetch_rss(source: dict, limit: int, now: datetime, tier: int) -> list[Article]:
    name = source["name"]
    url = source["url"]
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "gather-news/1.0"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content = resp.read()
        feed = feedparser.parse(content)

        articles = []
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue
            published = now
            if getattr(entry, "published_parsed", None):
                published = datetime.fromtimestamp(
                    time.mktime(entry.published_parsed), tz=JST
                )
            articles.append(
                Article(
                    title=title,
                    url=link,
                    source_name=name,
                    tier=tier,
                    published=published,
                )
            )
        logger.info(f"collect: {name} → {len(articles)} 件取得")
        return articles
    except Exception as e:
        logger.warning(f"collect: {name} → 失敗 ({e})、スキップ")
        return []


def _fetch_hn(source: dict, limit: int, now: datetime, tier: int) -> list[Article]:
    name = source["name"]
    base_url = source["url"].rstrip("/")
    try:
        with urllib.request.urlopen(
            f"{base_url}/topstories.json", timeout=TIMEOUT
        ) as resp:
            story_ids = json.loads(resp.read())

        articles = []
        for story_id in story_ids[: limit * 3]:
            if len(articles) >= limit:
                break
            try:
                with urllib.request.urlopen(
                    f"{base_url}/item/{story_id}.json", timeout=TIMEOUT
                ) as resp:
                    item = json.loads(resp.read())
            except Exception:
                continue

            if item.get("type") != "story" or not item.get("url"):
                continue

            published = (
                datetime.fromtimestamp(item["time"], tz=JST)
                if "time" in item
                else now
            )
            articles.append(
                Article(
                    title=item.get("title", "").strip(),
                    url=item["url"],
                    source_name=name,
                    tier=tier,
                    published=published,
                )
            )

        logger.info(f"collect: {name} → {len(articles)} 件取得")
        return articles
    except Exception as e:
        logger.warning(f"collect: {name} → 失敗 ({e})、スキップ")
        return []

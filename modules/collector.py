import html
import json
import logging
import re
import time
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import feedparser

from modules.models import Article

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")
TIMEOUT = 10
USER_AGENT = "gather-news/1.0"
# 要約プロンプトのトークン数（Gemini Free プランの TPM 上限）を抑えるため概要を切り詰める
DESCRIPTION_MAX_CHARS = 300
# meta description は <head> 内にあるため先頭だけ読めば足りる
META_FETCH_MAX_BYTES = 256 * 1024


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
            url, headers={"User-Agent": USER_AGENT}
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
            description = _clean_text(
                entry.get("summary", "") or entry.get("description", "")
            )
            if not description:
                description = _fetch_meta_description(link)
            articles.append(
                Article(
                    title=title,
                    url=link,
                    source_name=name,
                    tier=tier,
                    published=published,
                    description=description,
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
                    description=_fetch_meta_description(item["url"]),
                )
            )

        logger.info(f"collect: {name} → {len(articles)} 件取得")
        return articles
    except Exception as e:
        logger.warning(f"collect: {name} → 失敗 ({e})、スキップ")
        return []


def _clean_text(raw: str) -> str:
    """HTML タグ・実体参照・余分な空白を除去し、DESCRIPTION_MAX_CHARS で切り詰める。"""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > DESCRIPTION_MAX_CHARS:
        text = text[:DESCRIPTION_MAX_CHARS].rstrip() + "…"
    return text


class _MetaDescriptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.description = ""
        self.og_description = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr = {k.lower(): (v or "") for k, v in attrs}
        key = (attr.get("name") or attr.get("property") or "").lower()
        if key == "description" and not self.description:
            self.description = attr.get("content", "")
        elif key in ("og:description", "twitter:description") and not self.og_description:
            self.og_description = attr.get("content", "")


def _fetch_meta_description(url: str) -> str:
    """記事ページの meta description を取得する。失敗時は空文字（要約はタイトルのみで行う）。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type:
                return ""
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read(META_FETCH_MAX_BYTES).decode(charset, errors="replace")
    except Exception as e:
        logger.info(f"collect: meta description 取得失敗 {url} ({e})")
        return ""

    parser = _MetaDescriptionParser()
    try:
        parser.feed(body)
    except Exception as e:
        logger.info(f"collect: meta description 解析失敗 {url} ({e})")
        return ""
    return _clean_text(parser.og_description or parser.description)

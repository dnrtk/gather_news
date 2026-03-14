import logging
from datetime import datetime, date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from modules.models import Article, WeeklyArticle

logger = logging.getLogger(__name__)


def render_digest(
    articles: list[Article],
    slot: str,
    now: datetime,
    pages_dir: Path,
    templates_dir: Path,
) -> Path:
    output_path = _get_output_path(pages_dir, now, slot)
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    tmpl = env.get_template("digest.html.j2")

    slot_label = "朝刊" if slot == "morning" else "夕刊"
    tier_groups: dict[int, list[Article]] = {}
    for a in articles:
        tier_groups.setdefault(a.tier, []).append(a)

    html = tmpl.render(
        title=f"{now.strftime('%Y年%m月%d日')} {slot_label} ニュースダイジェスト",
        generated_at=now.strftime("%Y年%m月%d日 %H:%M JST"),
        slot_label=slot_label,
        tier_groups=tier_groups,
        nav_root="../../../",
    )
    output_path.write_text(html, encoding="utf-8")
    logger.info(f"render: {output_path} 生成")
    return output_path


def render_weekly(
    articles: list[WeeklyArticle],
    week_dates: list[date],
    now: datetime,
    pages_dir: Path,
    templates_dir: Path,
) -> Path:
    output_path = _get_output_path(pages_dir, now, "weekly")
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    tmpl = env.get_template("weekly.html.j2")

    date_groups: dict[date, list[WeeklyArticle]] = {d: [] for d in week_dates}
    for a in articles:
        if a.date in date_groups:
            date_groups[a.date].append(a)

    week_num = (now.date().day - 1) // 7 + 1
    period = f"{week_dates[0].strftime('%m/%d')}（月）〜{week_dates[-1].strftime('%m/%d')}（金）"

    html = tmpl.render(
        title=f"{now.strftime('%Y年%m月')}第{week_num}週 週刊ニュースダイジェスト",
        period=period,
        generated_at=now.strftime("%Y年%m月%d日 %H:%M JST"),
        date_groups=date_groups,
        week_dates=week_dates,
        nav_root="../../../",
    )
    output_path.write_text(html, encoding="utf-8")
    logger.info(f"render: {output_path} 生成")
    return output_path


def _get_output_path(pages_dir: Path, now: datetime, suffix: str) -> Path:
    dir_path = pages_dir / now.strftime("%Y") / now.strftime("%m")
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path / f"{now.strftime('%Y%m%d')}_{suffix}.html"

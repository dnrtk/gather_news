from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class Article:
    title: str
    url: str
    source_name: str
    tier: int
    published: datetime
    summary: str = ""
    one_liner: str = ""


@dataclass
class WeeklyArticle:
    title: str
    url: str
    source_name: str
    tier: int
    published: datetime
    summary: str
    date: date
    slot: str
    one_liner: str = ""

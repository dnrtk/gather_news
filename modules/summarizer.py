import json
import logging
import re

from google import genai

from modules.models import Article, WeeklyArticle

logger = logging.getLogger(__name__)


def summarize(
    articles: list[Article], api_key: str, primary: str, fallback: str
) -> list[Article]:
    if not articles:
        return articles

    prompt = _build_daily_prompt(articles)
    response = _call_with_fallback(prompt, api_key, primary, fallback)

    if response:
        articles = _parse_into(response, articles, "summary")
    else:
        for a in articles:
            a.summary = "取得できませんでした"
    return articles


def summarize_weekly(
    articles: list[WeeklyArticle], api_key: str, primary: str, fallback: str
) -> list[WeeklyArticle]:
    if not articles:
        return articles

    prompt = _build_weekly_prompt(articles)
    response = _call_with_fallback(prompt, api_key, primary, fallback)

    if response:
        articles = _parse_into(response, articles, "one_liner")
    else:
        for a in articles:
            a.one_liner = a.summary[:150]
    return articles


def _build_daily_prompt(articles: list[Article]) -> str:
    lines = "\n".join(
        f"id={i}, title={a.title}, url={a.url}" for i, a in enumerate(articles)
    )
    return f"""\
以下のニュース記事リストを要約してください。

ルール:
- 英語記事は日本語に翻訳して要約する
- 日本語記事はそのまま要約する
- 各記事の要約は300字以内にまとめる
- 出力はJSON配列形式のみで返す: [{{"id": 0, "summary": "..."}}]
- JSON以外のテキストは含めないこと

記事リスト:
{lines}"""


def _build_weekly_prompt(articles: list[WeeklyArticle]) -> str:
    lines = "\n".join(
        f"id={i}, title={a.title}, summary={a.summary}"
        for i, a in enumerate(articles)
    )
    return f"""\
以下のニュース記事リストをさらに短く要約してください。

ルール:
- 各要約を150字以内にまとめる
- 日本語で出力する
- 出力はJSON配列形式のみで返す: [{{"id": 0, "one_liner": "..."}}]
- JSON以外のテキストは含めないこと

記事リスト:
{lines}"""


def _call_with_fallback(
    prompt: str, api_key: str, primary: str, fallback: str
) -> str | None:
    for model in [primary, fallback]:
        try:
            logger.info(f"summarize: {model} で要約開始")
            result = _call_api(prompt, api_key, model)
            logger.info("summarize: 完了")
            return result
        except Exception as e:
            logger.warning(f"summarize: {model} 失敗 ({e})")
    return None


def _call_api(prompt: str, api_key: str, model: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text


def _parse_into(response: str, articles: list, key: str) -> list:
    start = response.find("[")
    end = response.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.warning("summarize: JSONパース失敗（配列が見つからない）")
        return articles
    try:
        data = json.loads(response[start : end + 1])
        id_to_value = {item["id"]: item[key] for item in data}
        for i, a in enumerate(articles):
            setattr(a, key, id_to_value.get(i, ""))
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"summarize: パースエラー ({e})")
    return articles

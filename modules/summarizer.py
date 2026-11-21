import json
import logging

from google import genai

from modules.models import Article, WeeklyArticle

logger = logging.getLogger(__name__)


class InvalidResponseError(Exception):
    """モデルの応答が期待する JSON 配列として解釈できない（拒否文など）。"""


def summarize(
    articles: list[Article], api_key: str, primary: str, fallback: str
) -> list[Article]:
    if not articles:
        return articles

    prompt = _build_daily_prompt(articles)
    data = _call_with_fallback(prompt, api_key, primary, fallback, "summary")

    if data is not None:
        _apply(data, articles, "summary")
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
    data = _call_with_fallback(prompt, api_key, primary, fallback, "one_liner")

    if data is not None:
        _apply(data, articles, "one_liner")
    else:
        for a in articles:
            a.one_liner = a.summary[:150]
    return articles


def _build_daily_prompt(articles: list[Article]) -> str:
    lines = "\n".join(
        f"id={i}, title={a.title}, url={a.url}, description={a.description or '(なし)'}"
        for i, a in enumerate(articles)
    )
    return f"""\
以下のニュース記事リストを要約してください。
各記事のタイトル(title)と概要(description)を提供しています。URL へのアクセスは不要です。

ルール:
- 提供した title と description の情報だけを使って要約する（記載のない事実を補わない）
- description が「(なし)」の記事は、タイトルから読み取れる範囲で簡潔にまとめる
- 情報が少なくても要約を断らず、必ず全記事分を出力する
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
    prompt: str, api_key: str, primary: str, fallback: str, key: str
) -> list[dict] | None:
    """primary → fallback の順に呼び出す。API 例外に加え、応答が JSON 配列として
    解釈できない場合（拒否文など）も失敗とみなして fallback へ切り替える。
    API 呼び出しは最大 2 回（primary 成功時は 1 回）。"""
    for model in [primary, fallback]:
        try:
            logger.info(f"summarize: {model} で要約開始")
            response = _call_api(prompt, api_key, model)
            data = _parse_response(response, key)
            logger.info("summarize: 完了")
            return data
        except Exception as e:
            logger.warning(f"summarize: {model} 失敗 ({e})")
    return None


def _call_api(prompt: str, api_key: str, model: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text or ""


def _parse_response(response: str, key: str) -> list[dict]:
    start = response.find("[")
    end = response.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise InvalidResponseError(
            f"JSON配列が見つからない: {response[:100]!r}"
        )
    try:
        data = json.loads(response[start : end + 1])
    except json.JSONDecodeError as e:
        raise InvalidResponseError(f"JSONデコード失敗 ({e})") from e
    if not isinstance(data, list) or not all(
        isinstance(item, dict) and "id" in item and key in item for item in data
    ):
        raise InvalidResponseError(f"想定外のJSON構造（id / {key} が欠落）")
    return data


def _apply(data: list[dict], articles: list, key: str) -> None:
    id_to_value = {item["id"]: item[key] for item in data}
    for i, a in enumerate(articles):
        setattr(a, key, id_to_value.get(i, ""))

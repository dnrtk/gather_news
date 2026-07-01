import json
import logging
import re
import subprocess
import wave
from datetime import datetime, timedelta
from pathlib import Path

from google import genai
from google.genai import types

from modules.models import Article

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"(\d{8})_")


def generate_podcast(
    articles: list[Article],
    slot: str,
    now: datetime,
    pages_dir: Path,
    api_key: str,
    podcast_cfg: dict,
    model_cfg: dict,
) -> Path | None:
    speakers = podcast_cfg["speakers"]
    tts_model = podcast_cfg["tts_model"]

    script = _build_script(
        articles, speakers, api_key, model_cfg["primary"], model_cfg["fallback"]
    )
    if script is None:
        logger.warning("podcast: 台本生成に失敗、音声生成を中止")
        return None
    _save_script(script, slot, now, pages_dir)

    pcm = _synthesize(script, speakers, api_key, tts_model)
    if pcm is None:
        logger.warning("podcast: TTS合成に失敗、音声生成を中止")
        return None

    out_path = _get_audio_path(pages_dir, now, slot)
    try:
        _pcm_to_mp3(pcm, out_path)
    except Exception as e:
        logger.warning(f"podcast: mp3変換に失敗 ({e})、音声生成を中止")
        return None

    logger.info(f"podcast: {out_path} 生成")

    retention_days = podcast_cfg.get("retention_days", 30)
    removed = cleanup_old_audio(pages_dir, retention_days, now)
    if removed:
        logger.info(f"podcast: 保持期間超過の音声/台本を {removed} 件削除")

    return out_path


def _build_script(
    articles: list[Article],
    speakers: list[dict],
    api_key: str,
    primary: str,
    fallback: str,
) -> list[dict] | None:
    if not articles:
        return None

    speaker_a, speaker_b = speakers[0]["name"], speakers[1]["name"]
    prompt = _build_script_prompt(articles, speaker_a, speaker_b)

    for model in [primary, fallback]:
        try:
            logger.info(f"podcast: {model} で台本生成開始")
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model=model, contents=prompt)
            script = _parse_script(response.text, speaker_a, speaker_b)
            if script:
                logger.info("podcast: 台本生成完了")
                return script
            logger.warning(f"podcast: {model} の台本パースに失敗")
        except Exception as e:
            logger.warning(f"podcast: {model} 失敗 ({e})")
    return None


def _build_script_prompt(articles: list[Article], speaker_a: str, speaker_b: str) -> str:
    lines = "\n".join(f"- {a.title}: {a.summary}" for a in articles)
    return f"""\
以下のニュース要約を、2人のポッドキャスター（{speaker_a} と {speaker_b}）が
リスナーに楽しく解説するラジオ番組の台本にしてください。

ルール:
- 冒頭に軽い挨拶、最後に締めの一言を入れる
- 相槌・言い換え・軽い驚き・質問と回答のやり取りを自然に含める
- 専門用語はかみ砕いて説明する
- 全体で3〜5分程度の長さ（合計6000字以内）に収める
- 出力はJSON配列のみで返す: [{{"speaker": "{speaker_a}", "text": "..."}}]
- speaker には {speaker_a} または {speaker_b} のみを使う
- JSON以外のテキストは含めないこと

ニュース要約:
{lines}"""


def _parse_script(
    response: str, speaker_a: str, speaker_b: str
) -> list[dict] | None:
    start = response.find("[")
    end = response.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(response[start : end + 1])
    except json.JSONDecodeError:
        return None

    valid_speakers = {speaker_a, speaker_b}
    script = [
        {"speaker": item["speaker"], "text": item["text"]}
        for item in data
        if item.get("speaker") in valid_speakers and item.get("text")
    ]
    return script or None


def _script_to_prompt(script: list[dict]) -> str:
    lines = [f'{turn["speaker"]}: {turn["text"]}' for turn in script]
    return "TTS the following podcast conversation:\n" + "\n".join(lines)


def _synthesize(
    script: list[dict], speakers: list[dict], api_key: str, tts_model: str
) -> bytes | None:
    try:
        client = genai.Client(api_key=api_key)
        prompt = _script_to_prompt(script)
        speaker_cfgs = [
            types.SpeakerVoiceConfig(
                speaker=s["name"],
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=s["voice"]
                    )
                ),
            )
            for s in speakers[:2]
        ]
        logger.info(f"podcast: {tts_model} で音声合成開始")
        response = client.models.generate_content(
            model=tts_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=speaker_cfgs
                    )
                ),
            ),
        )
        logger.info("podcast: 音声合成完了")
        return response.candidates[0].content.parts[0].inline_data.data
    except Exception as e:
        logger.warning(f"podcast: TTS呼び出し失敗 ({e})")
        return None


def _pcm_to_mp3(pcm: bytes, out_path: Path) -> None:
    wav_path = out_path.with_suffix(".wav")
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "96k", str(out_path)],
            check=True,
            capture_output=True,
        )
    finally:
        wav_path.unlink(missing_ok=True)


def _save_script(script: list[dict], slot: str, now: datetime, pages_dir: Path) -> Path:
    dir_path = pages_dir / now.strftime("%Y") / now.strftime("%m")
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"{now.strftime('%Y%m%d')}_{slot}_script.json"
    path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _get_audio_path(pages_dir: Path, now: datetime, slot: str) -> Path:
    dir_path = pages_dir / now.strftime("%Y") / now.strftime("%m")
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path / f"{now.strftime('%Y%m%d')}_{slot}.mp3"


def cleanup_old_audio(pages_dir: Path, retention_days: int, now: datetime) -> int:
    cutoff = (now - timedelta(days=retention_days)).date()
    removed = 0
    for pattern in ("*.mp3", "*_script.json"):
        for f in pages_dir.rglob(pattern):
            m = _DATE_RE.search(f.name)
            if not m:
                continue
            file_date = datetime.strptime(m.group(1), "%Y%m%d").date()
            if file_date < cutoff:
                f.unlink()
                removed += 1
    return removed

import logging
import subprocess

logger = logging.getLogger(__name__)


def git_push(commit_message: str) -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "pages/", "index.html", "nav.json"],
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        logger.info("git: 変更なし、スキップ")
        return

    try:
        subprocess.run(["git", "add", "pages/", "index.html", "nav.json"], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)
        logger.info("git: コミット・プッシュ完了")
    except subprocess.CalledProcessError as e:
        logger.error(f"git: 失敗 ({e})")
        raise

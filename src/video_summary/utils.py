from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path


YOUTUBE_HOST_RE = re.compile(r"(^|\.)youtube\.com$|(^|\.)youtu\.be$")
BILIBILI_HOST_RE = re.compile(r"(^|\.)bilibili\.com$|(^|\.)b23\.tv$")


def is_youtube_url(value: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(YOUTUBE_HOST_RE.search(parsed.hostname or ""))


def is_bilibili_url(value: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(BILIBILI_HOST_RE.search(parsed.hostname or ""))


def is_supported_video_url(value: str) -> bool:
    return is_youtube_url(value) or is_bilibili_url(value)


def format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "00:00"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def slugify(value: str, fallback: str = "video") -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", " ", value)
    value = re.sub(r"\s+", "-", value.strip().lower())
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff._-]+", "", value)
    return value[:80].strip(".-_") or fallback


def unique_dir(base: Path, stem: str) -> Path:
    candidate = base / stem
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = base / f"{stem}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def yt_dlp_command() -> list[str] | None:
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    executable = shutil.which("yt-dlp")
    if executable is not None:
        return [executable]
    return None

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import SubtitleFetchError
from .models import Segment, VideoMetadata


LANGUAGE_PREFERENCES = ("zh-Hans", "zh-CN", "zh", "en", "en-US", "en-GB")


def fetch_youtube_subtitles(url: str, language_preferences: tuple[str, ...] = LANGUAGE_PREFERENCES) -> tuple[VideoMetadata, list[Segment]]:
    if shutil.which("yt-dlp") is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")

    metadata = probe_youtube_metadata(url)
    segments = fetch_subtitles_for_metadata(metadata, language_preferences)
    metadata.extra.pop("raw_info", None)
    return metadata, segments


def probe_youtube_metadata(url: str) -> VideoMetadata:
    if shutil.which("yt-dlp") is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")
    return _probe_metadata(url)


def fetch_subtitles_for_metadata(
    metadata: VideoMetadata,
    language_preferences: tuple[str, ...] = LANGUAGE_PREFERENCES,
) -> list[Segment]:
    with tempfile.TemporaryDirectory(prefix="video-summary-") as tmp:
        temp_dir = Path(tmp)
        info = metadata.extra.get("raw_info", {})
        language = _pick_subtitle_language(info, language_preferences)
        if language is None:
            raise SubtitleFetchError("这个 YouTube 视频没有发现可用字幕。第 1 阶段暂不做音频转写。")

        output_template = str(temp_dir / "subtitle.%(ext)s")
        command = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            language,
            "--sub-format",
            "vtt",
            "-o",
            output_template,
            metadata.webpage_url or metadata.source_url,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode != 0:
            raise SubtitleFetchError(f"字幕下载失败：{completed.stderr.strip() or completed.stdout.strip()}")

        vtt_files = sorted(temp_dir.glob("subtitle*.vtt"))
        if not vtt_files:
            raise SubtitleFetchError("yt-dlp 没有生成字幕文件。")

        segments = parse_vtt(vtt_files[0].read_text(encoding="utf-8", errors="replace"), language)
        if not segments:
            raise SubtitleFetchError("字幕文件为空，无法继续总结。")

        metadata.subtitle_language = language
        metadata.subtitle_source = "yt-dlp"
        metadata.transcript_source = "subtitle"
        return segments


def _probe_metadata(url: str) -> VideoMetadata:
    command = ["yt-dlp", "--dump-single-json", "--skip-download", url]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise SubtitleFetchError(f"无法读取 YouTube 元数据：{completed.stderr.strip() or completed.stdout.strip()}")
    try:
        info = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SubtitleFetchError("yt-dlp 返回的元数据不是有效 JSON。") from exc

    return VideoMetadata(
        source_url=url,
        source_type="youtube",
        title=info.get("title") or "Untitled YouTube Video",
        duration=info.get("duration"),
        webpage_url=info.get("webpage_url") or url,
        extractor=info.get("extractor_key") or info.get("extractor"),
        extra={"id": info.get("id"), "channel": info.get("channel"), "raw_info": info},
    )


def _pick_subtitle_language(info: dict[str, object], preferences: tuple[str, ...]) -> str | None:
    manual = info.get("subtitles") if isinstance(info.get("subtitles"), dict) else {}
    automatic = info.get("automatic_captions") if isinstance(info.get("automatic_captions"), dict) else {}
    available = {**automatic, **manual}
    if not available:
        return None
    for language in preferences:
        if language in available:
            return language
    for language in available:
        if language.startswith("zh"):
            return language
    for language in available:
        if language.startswith("en"):
            return language
    return next(iter(available), None)


TIMING_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def parse_vtt(content: str, language: str) -> list[Segment]:
    segments: list[Segment] = []
    lines = content.replace("\ufeff", "").splitlines()
    index = 0
    while index < len(lines):
        match = TIMING_RE.search(lines[index])
        if not match:
            index += 1
            continue

        start = _parse_time(match.group("start"))
        end = _parse_time(match.group("end"))
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            line = lines[index].strip()
            if not line.startswith(("NOTE", "STYLE")):
                text_lines.append(TAG_RE.sub("", line))
            index += 1
        text = _normalize_caption_text(" ".join(text_lines))
        if text and not text.startswith("align:"):
            if segments and segments[-1].start == start and segments[-1].text == text:
                segments[-1].end = max(segments[-1].end, end)
            else:
                segments.append(Segment(start=start, end=end, text=text, language=language))
        index += 1
    return segments


def _parse_time(value: str) -> float:
    parts = value.split(":")
    if len(parts) == 2:
        minutes, rest = parts
        seconds, millis = rest.split(".")
        return int(minutes) * 60 + int(seconds) + int(millis) / 1000
    hours, minutes, rest = parts
    seconds, millis = rest.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def _normalize_caption_text(value: str) -> str:
    value = value.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    value = value.replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\s+", " ", value).strip()

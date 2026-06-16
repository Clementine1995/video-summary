from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from .errors import SubtitleFetchError
from .models import Segment, VideoMetadata
from .utils import yt_dlp_command


LANGUAGE_PREFERENCES = ("zh-Hans", "zh-CN", "zh", "en", "en-US", "en-GB")


def fetch_youtube_subtitles(
    url: str,
    language_preferences: tuple[str, ...] = LANGUAGE_PREFERENCES,
) -> tuple[VideoMetadata, list[Segment]]:
    if yt_dlp_command() is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")

    metadata = probe_youtube_metadata(url)
    segments = fetch_subtitles_for_metadata(metadata, language_preferences)
    metadata.extra.pop("raw_info", None)
    return metadata, segments


def probe_youtube_metadata(url: str) -> VideoMetadata:
    command_prefix = yt_dlp_command()
    if command_prefix is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")
    return _probe_metadata(command_prefix, url)


def fetch_subtitles_for_metadata(
    metadata: VideoMetadata,
    language_preferences: tuple[str, ...] = LANGUAGE_PREFERENCES,
) -> list[Segment]:
    info = metadata.extra.get("raw_info", {})
    languages = _subtitle_language_candidates(info, language_preferences)
    if not languages:
        raise SubtitleFetchError("这个 YouTube 视频没有发现可用字幕。")

    command_prefix = yt_dlp_command()
    errors: list[str] = []
    for language in languages:
        try:
            segments = _fetch_one_subtitle_language(command_prefix, metadata, language)
        except SubtitleFetchError as exc:
            errors.append(f"{language}: {exc}")
            continue
        if segments:
            metadata.subtitle_language = language
            metadata.subtitle_source = "yt-dlp"
            metadata.transcript_source = "subtitle"
            return segments
        errors.append(f"{language}: 字幕文件为空")

    detail = "；".join(errors[:5])
    if len(errors) > 5:
        detail += f"；另有 {len(errors) - 5} 个语言也失败"
    raise SubtitleFetchError(f"字幕下载失败，已尝试 {len(languages)} 个语言。{detail}")


def _fetch_one_subtitle_language(
    command_prefix: list[str] | None,
    metadata: VideoMetadata,
    language: str,
) -> list[Segment]:
    if command_prefix is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")

    with tempfile.TemporaryDirectory(prefix="video-summary-") as tmp:
        temp_dir = Path(tmp)
        output_template = str(temp_dir / "subtitle.%(ext)s")
        command = [
            *command_prefix,
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
            raise SubtitleFetchError(completed.stderr.strip() or completed.stdout.strip())

        vtt_files = sorted(temp_dir.glob("subtitle*.vtt"))
        if not vtt_files:
            raise SubtitleFetchError("yt-dlp 没有生成字幕文件")

        for vtt_file in vtt_files:
            segments = parse_vtt(vtt_file.read_text(encoding="utf-8", errors="replace"), language)
            if segments:
                return segments
    return []


def _probe_metadata(command_prefix: list[str], url: str) -> VideoMetadata:
    command = [*command_prefix, "--dump-single-json", "--skip-download", url]
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


def _subtitle_language_candidates(info: dict[str, object], preferences: tuple[str, ...]) -> list[str]:
    manual = info.get("subtitles") if isinstance(info.get("subtitles"), dict) else {}
    automatic = info.get("automatic_captions") if isinstance(info.get("automatic_captions"), dict) else {}
    available = {**automatic, **manual}
    if not available:
        return []

    candidates: list[str] = []
    for language in preferences:
        if language in available:
            candidates.append(language)
    for language in available:
        if language.startswith("zh") and language not in candidates:
            candidates.append(language)
    for language in available:
        if language.startswith("en") and language not in candidates:
            candidates.append(language)
    for language in available:
        if language not in candidates:
            candidates.append(language)
    return candidates


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

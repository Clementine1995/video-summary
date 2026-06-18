from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from .errors import SubtitleFetchError
from .models import Segment, VideoMetadata
from .utils import yt_dlp_command


LANGUAGE_PREFERENCES = ("zh-Hans", "zh-CN", "zh", "zh-Hant", "en", "en-US", "en-GB")


def fetch_youtube_subtitles(
    url: str,
    language_preferences: tuple[str, ...] = LANGUAGE_PREFERENCES,
    yt_dlp_extra_args: list[str] | None = None,
) -> tuple[VideoMetadata, list[Segment]]:
    if yt_dlp_command() is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")

    metadata = probe_youtube_metadata(url, yt_dlp_extra_args)
    segments = fetch_subtitles_for_metadata(metadata, language_preferences, yt_dlp_extra_args)
    metadata.extra.pop("raw_info", None)
    return metadata, segments


def probe_youtube_metadata(url: str, yt_dlp_extra_args: list[str] | None = None) -> VideoMetadata:
    return probe_video_metadata(url, yt_dlp_extra_args)


def probe_video_metadata(url: str, yt_dlp_extra_args: list[str] | None = None) -> VideoMetadata:
    command_prefix = yt_dlp_command()
    if command_prefix is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")
    return _probe_metadata(command_prefix, url, yt_dlp_extra_args or [])


def fetch_subtitles_for_metadata(
    metadata: VideoMetadata,
    language_preferences: tuple[str, ...] = LANGUAGE_PREFERENCES,
    yt_dlp_extra_args: list[str] | None = None,
) -> list[Segment]:
    info = metadata.extra.get("raw_info", {})
    languages = _subtitle_language_candidates(info, language_preferences)
    if not languages:
        raise SubtitleFetchError("这个 YouTube 视频没有发现可用字幕。")

    command_prefix = yt_dlp_command()
    errors: list[str] = []
    for language in languages:
        try:
            segments = _fetch_one_subtitle_language(command_prefix, metadata, language, yt_dlp_extra_args)
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
    yt_dlp_extra_args: list[str] | None = None,
) -> list[Segment]:
    if command_prefix is None:
        raise SubtitleFetchError("未找到 yt-dlp。请先运行 `pip install yt-dlp`，或确保 yt-dlp 在 PATH 中。")

    with tempfile.TemporaryDirectory(prefix="video-summary-") as tmp:
        temp_dir = Path(tmp)
        output_template = str(temp_dir / "subtitle.%(ext)s")
        command = [
            *command_prefix,
            *(yt_dlp_extra_args or []),
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            language,
            "--sub-format",
            "vtt/srt/json/best",
            "-o",
            output_template,
            metadata.webpage_url or metadata.source_url,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode != 0:
            raise SubtitleFetchError(completed.stderr.strip() or completed.stdout.strip())

        subtitle_files = sorted(path for path in temp_dir.glob("subtitle*.*") if path.is_file())
        if not subtitle_files:
            raise SubtitleFetchError("yt-dlp 没有生成字幕文件")

        for subtitle_file in subtitle_files:
            segments = parse_subtitle(
                subtitle_file.read_text(encoding="utf-8", errors="replace"),
                language,
                subtitle_file.suffix.lower(),
            )
            if segments:
                return segments
    return []


def _probe_metadata(command_prefix: list[str], url: str, yt_dlp_extra_args: list[str]) -> VideoMetadata:
    command = [*command_prefix, *yt_dlp_extra_args, "--dump-single-json", "--skip-download", url]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        if "HTTP Error 412" in detail and "bilibili.com" in url:
            detail += "。B站可能要求登录 cookie；请手动导出 cookies.txt 后使用 `--cookies path\\to\\cookies.txt`。"
        raise SubtitleFetchError(f"无法读取视频元数据：{detail}")
    try:
        info = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SubtitleFetchError("yt-dlp 返回的元数据不是有效 JSON。") from exc

    extractor = info.get("extractor_key") or info.get("extractor")
    source_type = _source_type_from_extractor(str(extractor or ""))

    return VideoMetadata(
        source_url=url,
        source_type=source_type,
        title=info.get("title") or "Untitled Video",
        duration=info.get("duration"),
        webpage_url=info.get("webpage_url") or url,
        extractor=extractor,
        extra={
            "id": info.get("id"),
            "channel": info.get("channel") or info.get("uploader"),
            "raw_info": info,
        },
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


def _source_type_from_extractor(extractor: str) -> str:
    value = extractor.lower()
    if "bilibili" in value:
        return "bilibili"
    if "youtube" in value:
        return "youtube"
    return "video"


TIMING_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def parse_subtitle(content: str, language: str, suffix: str = "") -> list[Segment]:
    if suffix in {".json", ".json3"}:
        return parse_json_subtitle(content, language)
    if suffix == ".srt":
        return parse_srt(content, language)
    if suffix == ".vtt" or "-->" in content:
        return parse_vtt(content, language)
    try:
        return parse_json_subtitle(content, language)
    except SubtitleFetchError:
        return []


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


def parse_srt(content: str, language: str) -> list[Segment]:
    segments: list[Segment] = []
    blocks = re.split(r"\n\s*\n", content.replace("\ufeff", "").strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        start_text, end_text = lines[timing_index].split("-->", 1)
        text = _normalize_caption_text(" ".join(TAG_RE.sub("", line) for line in lines[timing_index + 1 :]))
        if text:
            segments.append(
                Segment(
                    start=_parse_time(start_text.strip().replace(",", ".")),
                    end=_parse_time(end_text.strip().split()[0].replace(",", ".")),
                    text=text,
                    language=language,
                )
            )
    return segments


def parse_json_subtitle(content: str, language: str) -> list[Segment]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SubtitleFetchError("字幕 JSON 格式异常。") from exc

    body = payload.get("body") if isinstance(payload, dict) else None
    if not isinstance(body, list):
        return []

    segments: list[Segment] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        start = item.get("from", item.get("start"))
        end = item.get("to", item.get("end"))
        text = item.get("content") or item.get("text")
        if isinstance(start, int | float) and isinstance(end, int | float) and isinstance(text, str):
            cleaned_text = _normalize_caption_text(text)
            if cleaned_text:
                segments.append(Segment(float(start), float(end), cleaned_text, language))
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

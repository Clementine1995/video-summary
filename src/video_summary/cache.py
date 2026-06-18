from __future__ import annotations

import json
import re
from dataclasses import fields
from pathlib import Path

from .models import ChunkSummary, Segment, VideoMetadata
from .utils import slugify


TRANSCRIPT_LINE_RE = re.compile(r"^\[(?P<start>[0-9:]+) - (?P<end>[0-9:]+)\] (?P<text>.*)$")
CHUNK_HEADING_RE = re.compile(r"^## Chunk (?P<index>\d+): (?P<start>[0-9:]+) - (?P<end>[0-9:]+)\s*$")


def find_resume_dir(output_root: Path, title: str) -> Path | None:
    stem = slugify(title)
    candidates = [path for path in output_root.glob(f"{stem}*") if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_cached_pipeline_inputs(output_dir: Path) -> tuple[VideoMetadata, list[Segment], list[Segment]] | None:
    metadata_path = output_dir / "metadata.json"
    raw_path = output_dir / "transcript.raw.md"
    cleaned_path = output_dir / "transcript.cleaned.md"
    if not (metadata_path.exists() and raw_path.exists() and cleaned_path.exists()):
        return None

    metadata = load_cached_metadata(metadata_path)
    raw_segments = parse_transcript(raw_path)
    cleaned_segments = parse_transcript(cleaned_path)
    if not raw_segments or not cleaned_segments:
        return None
    return metadata, raw_segments, cleaned_segments


def load_cached_metadata(path: Path) -> VideoMetadata:
    payload = json.loads(path.read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(VideoMetadata)}
    values = {key: value for key, value in payload.items() if key in allowed}
    return VideoMetadata(**values)


def parse_transcript(path: Path) -> list[Segment]:
    language = "unknown"
    segments: list[Segment] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- Language: "):
            language = line.removeprefix("- Language: ").strip() or "unknown"
            continue
        match = TRANSCRIPT_LINE_RE.match(line)
        if match:
            segments.append(
                Segment(
                    start=parse_timestamp(match.group("start")),
                    end=parse_timestamp(match.group("end")),
                    text=match.group("text").strip(),
                    language=language,
                )
            )
    return segments


def load_cached_chunk_summaries(path: Path) -> list[ChunkSummary]:
    if not path.exists():
        return []

    summaries: list[ChunkSummary] = []
    current_index: int | None = None
    current_start = 0.0
    current_end = 0.0
    current_lines: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        match = CHUNK_HEADING_RE.match(line)
        if match:
            if current_index is not None:
                summaries.append(ChunkSummary(current_index, current_start, current_end, "\n".join(current_lines).strip()))
            current_index = int(match.group("index"))
            current_start = parse_timestamp(match.group("start"))
            current_end = parse_timestamp(match.group("end"))
            current_lines = []
            continue
        if current_index is not None:
            current_lines.append(line)

    if current_index is not None:
        summaries.append(ChunkSummary(current_index, current_start, current_end, "\n".join(current_lines).strip()))
    return [summary for summary in summaries if summary.markdown]


def load_cached_summary(path: Path) -> str | None:
    if not path.exists():
        return None
    summary = path.read_text(encoding="utf-8").strip()
    return summary or None


def parse_timestamp(value: str) -> float:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    return 0.0

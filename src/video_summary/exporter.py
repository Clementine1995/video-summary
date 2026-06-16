from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import PipelineResult, Segment, VideoMetadata
from .utils import format_timestamp, slugify, unique_dir


def export_result(result: PipelineResult, output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    output_dir = unique_dir(output_root, slugify(result.metadata.title))
    output_dir.mkdir(parents=True)

    (output_dir / "summary.md").write_text(result.summary_markdown, encoding="utf-8")
    (output_dir / "transcript.raw.md").write_text(render_transcript(result.metadata, result.raw_segments), encoding="utf-8")
    (output_dir / "transcript.cleaned.md").write_text(render_transcript(result.metadata, result.cleaned_segments), encoding="utf-8")
    (output_dir / "metadata.json").write_text(render_metadata(result.metadata, result.raw_segments, result.cleaned_segments), encoding="utf-8")
    return output_dir


def render_transcript(metadata: VideoMetadata, segments: list[Segment]) -> str:
    lines = [
        f"# {metadata.title}",
        "",
        f"- Source: {metadata.webpage_url or metadata.source_url}",
        f"- Transcript source: {metadata.transcript_source or metadata.subtitle_source or 'unknown'}",
        f"- Language: {metadata.subtitle_language or 'unknown'}",
        "",
    ]
    for segment in segments:
        lines.append(f"[{format_timestamp(segment.start)} - {format_timestamp(segment.end)}] {segment.text}")
    lines.append("")
    return "\n".join(lines)


def render_metadata(metadata: VideoMetadata, raw_segments: list[Segment], cleaned_segments: list[Segment]) -> str:
    payload = asdict(metadata)
    payload["processed_at"] = datetime.now(timezone.utc).isoformat()
    payload["status"] = "completed"
    payload["raw_segment_count"] = len(raw_segments)
    payload["cleaned_segment_count"] = len(cleaned_segments)
    return json.dumps(payload, ensure_ascii=False, indent=2)

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Segment:
    start: float
    end: float
    text: str
    language: str = "unknown"


@dataclass(slots=True)
class VideoMetadata:
    source_url: str
    source_type: str
    title: str
    duration: float | None = None
    webpage_url: str | None = None
    subtitle_language: str | None = None
    subtitle_source: str | None = None
    transcript_source: str | None = None
    audio_path: str | None = None
    asr_model: str | None = None
    extractor: str | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineResult:
    metadata: VideoMetadata
    raw_segments: list[Segment]
    cleaned_segments: list[Segment]
    summary_markdown: str

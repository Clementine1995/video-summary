from __future__ import annotations

from .models import Segment, TranscriptChunk


def split_segments_into_chunks(
    segments: list[Segment],
    target_minutes: float = 12,
    max_chars: int = 30000,
) -> list[TranscriptChunk]:
    if not segments:
        return []

    target_seconds = max(60.0, target_minutes * 60)
    chunks: list[TranscriptChunk] = []
    current: list[Segment] = []
    current_chars = 0
    chunk_start = segments[0].start

    for segment in segments:
        segment_text_len = len(segment.text)
        would_exceed_time = current and segment.end - chunk_start > target_seconds
        would_exceed_chars = current and current_chars + segment_text_len > max_chars
        if would_exceed_time or would_exceed_chars:
            chunks.append(_make_chunk(len(chunks) + 1, current))
            current = []
            current_chars = 0
            chunk_start = segment.start

        current.append(segment)
        current_chars += segment_text_len

    if current:
        chunks.append(_make_chunk(len(chunks) + 1, current))

    return chunks


def _make_chunk(index: int, segments: list[Segment]) -> TranscriptChunk:
    return TranscriptChunk(
        index=index,
        start=segments[0].start,
        end=segments[-1].end,
        segments=segments,
    )

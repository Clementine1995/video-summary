from __future__ import annotations

import re

from .models import Segment


FILLER_PATTERNS = [
    r"\b(um|uh|erm|ah|like you know)\b",
    r"\b(嗯+|呃+|啊+|这个这个|那个那个)\b",
]


def clean_segments(
    segments: list[Segment],
    min_gap_to_merge: float = 1.2,
    min_chars: int = 24,
    max_merged_chars: int = 240,
    max_merged_duration: float = 45,
) -> list[Segment]:
    cleaned: list[Segment] = []
    previous_text = ""

    for segment in segments:
        text = _clean_text(segment.text)
        if not text:
            continue
        if _is_near_duplicate(previous_text, text):
            continue

        can_merge_short_segment = (
            cleaned
            and len(text) < min_chars
            and segment.start - cleaned[-1].end <= min_gap_to_merge
            and len(cleaned[-1].text) + len(text) <= max_merged_chars
            and segment.end - cleaned[-1].start <= max_merged_duration
        )
        if can_merge_short_segment:
            cleaned[-1].end = max(cleaned[-1].end, segment.end)
            cleaned[-1].text = _join_text(cleaned[-1].text, text)
        else:
            cleaned.append(Segment(segment.start, segment.end, text, segment.language))
        previous_text = text
    return cleaned


def _clean_text(text: str) -> str:
    text = re.sub(r"\[[^\]]+\]", "", text)
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -，,。.")


def _is_near_duplicate(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    return previous == current or previous in current and len(previous) / max(len(current), 1) > 0.85


def _join_text(left: str, right: str) -> str:
    if not left:
        return right
    if left.endswith((".", "。", "?", "？", "!", "！")):
        return f"{left} {right}"
    return f"{left}，{right}"

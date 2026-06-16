from __future__ import annotations

from .cleaner import clean_segments
from .errors import UnsupportedInputError
from .llm import summarize_with_openai_compatible
from .models import PipelineResult
from .utils import is_youtube_url
from .youtube import fetch_youtube_subtitles


def run_phase1(url: str) -> PipelineResult:
    if not is_youtube_url(url):
        raise UnsupportedInputError("第 1 阶段只支持 YouTube 链接。B站、本地文件和 ASR 会在后续阶段加入。")

    metadata, raw_segments = fetch_youtube_subtitles(url)
    cleaned_segments = clean_segments(raw_segments)
    summary = summarize_with_openai_compatible(metadata, cleaned_segments)
    return PipelineResult(
        metadata=metadata,
        raw_segments=raw_segments,
        cleaned_segments=cleaned_segments,
        summary_markdown=summary,
    )

from __future__ import annotations

import json
from urllib import error, request

from .chunker import split_segments_into_chunks
from .config import ChunkingConfig, LLMConfig, load_llm_config
from .errors import LLMError
from .models import ChunkSummary, Segment, TranscriptChunk, VideoMetadata
from .utils import format_timestamp


SUMMARY_TEMPLATE = """# {title}

## 一句话总结

## 3 分钟速读

## 详细大纲

## 核心观点

## 章节时间线

## 重要概念

## 可执行建议

## 值得回看的时间点

## 材料质量说明
"""


def summarize_with_openai_compatible(
    metadata: VideoMetadata,
    segments: list[Segment],
    config: LLMConfig | None = None,
) -> str:
    llm_config = config or load_llm_config()
    transcript = _render_prompt_transcript(segments)
    system_prompt = (
        "你是一个擅长整理讲座、访谈和课程内容的学习笔记助手。"
        "请基于用户提供的带时间戳字幕生成结构化 Markdown 总结。"
        "不要编造字幕里没有的信息，关键观点尽量带时间戳。"
    )
    user_prompt = f"""视频标题：{metadata.title}
视频链接：{metadata.webpage_url or metadata.source_url}
视频时长：{format_timestamp(metadata.duration)}

请严格按下面结构输出 Markdown；没有识别到内容的章节写“未识别到相关内容”。

{SUMMARY_TEMPLATE.format(title=metadata.title)}

字幕：
{transcript}
"""
    return _chat_completion(llm_config, system_prompt, user_prompt)


def summarize_with_chunking(
    metadata: VideoMetadata,
    segments: list[Segment],
    llm_config: LLMConfig,
    chunking_config: ChunkingConfig,
) -> tuple[str, list[ChunkSummary]]:
    chunks = split_segments_into_chunks(
        segments,
        target_minutes=chunking_config.target_minutes,
        max_chars=chunking_config.max_chars,
    )
    if len(chunks) <= 1:
        return summarize_with_openai_compatible(metadata, segments, llm_config), []

    chunk_summaries = [
        summarize_chunk_with_openai_compatible(metadata, chunk, len(chunks), llm_config)
        for chunk in chunks
    ]
    summary = summarize_chunk_summaries_with_openai_compatible(metadata, chunk_summaries, llm_config)
    return summary, chunk_summaries


def summarize_chunk_with_openai_compatible(
    metadata: VideoMetadata,
    chunk: TranscriptChunk,
    total_chunks: int,
    config: LLMConfig,
) -> ChunkSummary:
    transcript = _render_prompt_transcript(chunk.segments, max_chars=50000)
    system_prompt = (
        "你是一个擅长整理讲座、访谈和课程内容的学习笔记助手。"
        "请先为长视频的一个片段生成局部结构化摘要，保留关键时间戳。"
    )
    user_prompt = f"""视频标题：{metadata.title}
片段：{chunk.index}/{total_chunks}
片段时间：{format_timestamp(chunk.start)} - {format_timestamp(chunk.end)}

请输出 Markdown，包含：

## 本段主题
## 关键观点
## 重要例子
## 提到的人名、书名、工具或概念
## 可引用时间戳

字幕：
{transcript}
"""
    return ChunkSummary(
        index=chunk.index,
        start=chunk.start,
        end=chunk.end,
        markdown=_chat_completion(config, system_prompt, user_prompt),
    )


def summarize_chunk_summaries_with_openai_compatible(
    metadata: VideoMetadata,
    chunk_summaries: list[ChunkSummary],
    config: LLMConfig,
) -> str:
    rendered = "\n\n".join(
        f"<!-- chunk {summary.index}: {format_timestamp(summary.start)} - {format_timestamp(summary.end)} -->\n"
        f"{summary.markdown}"
        for summary in chunk_summaries
    )
    system_prompt = (
        "你是一个擅长把长视频分段摘要整合为学习笔记的助手。"
        "请去重、归纳并保持时间线顺序，不要只拼接分段摘要。"
    )
    user_prompt = f"""视频标题：{metadata.title}
视频链接：{metadata.webpage_url or metadata.source_url}
视频时长：{format_timestamp(metadata.duration)}

请严格按下面结构输出 Markdown；没有识别到内容的章节写“未识别到相关内容”。

{SUMMARY_TEMPLATE.format(title=metadata.title)}

分段摘要：
{rendered}
"""
    return _chat_completion(config, system_prompt, user_prompt)


def _chat_completion(config: LLMConfig, system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    return _post_chat_completion(config, payload)


def _render_prompt_transcript(segments: list[Segment], max_chars: int = 50000) -> str:
    lines = [f"[{format_timestamp(s.start)} - {format_timestamp(s.end)}] {s.text}" for s in segments]
    transcript = "\n".join(lines)
    if len(transcript) <= max_chars:
        return transcript
    return transcript[:max_chars] + "\n\n[字幕过长，当前片段已按字符上限截断。]"


def _post_chat_completion(config: LLMConfig, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{config.base_url}/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=config.timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"LLM 调用失败：HTTP {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise LLMError(f"LLM 调用失败：{exc.reason}") from exc

    try:
        result = json.loads(body)
        content = result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMError("LLM 返回格式异常，无法提取 summary 内容。") from exc
    if not content:
        raise LLMError("LLM 返回了空 summary。")
    return content

from __future__ import annotations

import json
from urllib import error, request

from .config import LLMConfig, load_llm_config
from .errors import LLMError
from .models import Segment, VideoMetadata
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
    payload = {
        "model": llm_config.model,
        "temperature": llm_config.temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{llm_config.base_url}/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {llm_config.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=llm_config.timeout) as response:
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


def _render_prompt_transcript(segments: list[Segment], max_chars: int = 50000) -> str:
    lines = [f"[{format_timestamp(s.start)} - {format_timestamp(s.end)}] {s.text}" for s in segments]
    transcript = "\n".join(lines)
    if len(transcript) <= max_chars:
        return transcript
    return transcript[:max_chars] + "\n\n[字幕过长，第一阶段已截断。后续阶段会加入分块总结。]"

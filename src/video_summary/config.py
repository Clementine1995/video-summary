from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import LLMError


@dataclass(slots=True)
class LLMConfig:
    provider: str
    base_url: str
    model: str
    api_key: str
    temperature: float = 0.2
    timeout: float = 120


@dataclass(slots=True)
class ASRConfig:
    model: str
    language: str | None
    device: str
    compute_type: str


@dataclass(slots=True)
class ChunkingConfig:
    target_minutes: float
    max_chars: int


PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    "openai_compatible": {
        "base_url": "",
        "model": "",
        "api_key_env": "VIDEO_SUMMARY_LLM_API_KEY",
    },
}


def load_llm_config(
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMConfig:
    provider_name = (provider or os.getenv("VIDEO_SUMMARY_LLM_PROVIDER") or "deepseek").strip().lower()
    defaults = PROVIDER_DEFAULTS.get(provider_name)
    if defaults is None:
        supported = ", ".join(sorted(PROVIDER_DEFAULTS))
        raise LLMError(f"不支持的 LLM provider：{provider_name}。当前支持：{supported}。")

    api_key_env = defaults["api_key_env"]
    resolved_api_key = api_key or os.getenv(api_key_env) or os.getenv("VIDEO_SUMMARY_LLM_API_KEY")
    if not resolved_api_key:
        raise LLMError(f"未设置 LLM API key。请设置 {api_key_env}，或通用变量 VIDEO_SUMMARY_LLM_API_KEY。")

    resolved_base_url = (
        base_url
        or os.getenv("VIDEO_SUMMARY_LLM_BASE_URL")
        or defaults["base_url"]
    ).rstrip("/")
    resolved_model = model or os.getenv("VIDEO_SUMMARY_LLM_MODEL") or defaults["model"]
    if not resolved_base_url:
        raise LLMError("未设置 LLM base_url。请设置 VIDEO_SUMMARY_LLM_BASE_URL 或使用内置 provider。")
    if not resolved_model:
        raise LLMError("未设置 LLM model。请设置 VIDEO_SUMMARY_LLM_MODEL 或使用内置 provider。")

    return LLMConfig(
        provider=provider_name,
        base_url=resolved_base_url,
        model=resolved_model,
        api_key=resolved_api_key,
        temperature=float(os.getenv("VIDEO_SUMMARY_LLM_TEMPERATURE", "0.2")),
        timeout=float(os.getenv("VIDEO_SUMMARY_LLM_TIMEOUT", "120")),
    )


def load_asr_config(
    model: str | None = None,
    language: str | None = None,
    device: str | None = None,
    compute_type: str | None = None,
) -> ASRConfig:
    resolved_language = language or os.getenv("VIDEO_SUMMARY_ASR_LANGUAGE") or None
    if resolved_language == "auto":
        resolved_language = None
    return ASRConfig(
        model=model or os.getenv("VIDEO_SUMMARY_ASR_MODEL", "medium"),
        language=resolved_language,
        device=device or os.getenv("VIDEO_SUMMARY_ASR_DEVICE", "auto"),
        compute_type=compute_type or os.getenv("VIDEO_SUMMARY_ASR_COMPUTE_TYPE", "default"),
    )


def load_chunking_config(
    target_minutes: float | None = None,
    max_chars: int | None = None,
) -> ChunkingConfig:
    return ChunkingConfig(
        target_minutes=target_minutes or float(os.getenv("VIDEO_SUMMARY_CHUNK_TARGET_MINUTES", "12")),
        max_chars=max_chars or int(os.getenv("VIDEO_SUMMARY_CHUNK_MAX_CHARS", "30000")),
    )

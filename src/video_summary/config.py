from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    import tomli as tomllib

from .errors import ConfigurationError, LLMError


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
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
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


def load_file_config() -> dict[str, object]:
    config_path = os.getenv("VIDEO_SUMMARY_CONFIG")
    path = Path(config_path) if config_path else Path.cwd() / "config.local.toml"
    if not path.exists():
        return {}
    try:
        with path.open("rb") as file:
            payload = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"配置文件格式错误：{path}。{exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError(f"配置文件格式错误：{path}。")
    return payload


def load_llm_config(
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMConfig:
    file_config = load_file_config()
    llm_file_config = _section(file_config, "llm")
    provider_name = (
        provider
        or os.getenv("VIDEO_SUMMARY_LLM_PROVIDER")
        or _string_value(llm_file_config, "provider")
        or "deepseek"
    ).strip().lower()
    defaults = PROVIDER_DEFAULTS.get(provider_name)
    if defaults is None:
        supported = ", ".join(sorted(PROVIDER_DEFAULTS))
        raise LLMError(f"不支持的 LLM provider：{provider_name}。当前支持：{supported}。")

    api_key_env = defaults["api_key_env"]
    resolved_api_key = (
        api_key
        or os.getenv(api_key_env)
        or os.getenv("VIDEO_SUMMARY_LLM_API_KEY")
        or _string_value(llm_file_config, "api_key")
    )
    if not resolved_api_key:
        raise LLMError(f"未设置 LLM API key。请设置 {api_key_env}，或通用变量 VIDEO_SUMMARY_LLM_API_KEY。")

    resolved_base_url = (
        base_url
        or os.getenv("VIDEO_SUMMARY_LLM_BASE_URL")
        or _string_value(llm_file_config, "base_url")
        or defaults["base_url"]
    ).rstrip("/")
    resolved_model = model or os.getenv("VIDEO_SUMMARY_LLM_MODEL") or _string_value(llm_file_config, "model") or defaults["model"]
    if not resolved_base_url:
        raise LLMError("未设置 LLM base_url。请设置 VIDEO_SUMMARY_LLM_BASE_URL 或使用内置 provider。")
    if not resolved_model:
        raise LLMError("未设置 LLM model。请设置 VIDEO_SUMMARY_LLM_MODEL 或使用内置 provider。")

    return LLMConfig(
        provider=provider_name,
        base_url=resolved_base_url,
        model=resolved_model,
        api_key=resolved_api_key,
        temperature=_read_float_config(
            "VIDEO_SUMMARY_LLM_TEMPERATURE",
            llm_file_config,
            "temperature",
            0.2,
            minimum=0.0,
            maximum=2.0,
        ),
        timeout=_read_float_config("VIDEO_SUMMARY_LLM_TIMEOUT", llm_file_config, "timeout", 120, minimum=1.0),
    )


def load_asr_config(
    model: str | None = None,
    language: str | None = None,
    device: str | None = None,
    compute_type: str | None = None,
) -> ASRConfig:
    file_config = load_file_config()
    asr_file_config = _section(file_config, "asr")
    resolved_language = language or os.getenv("VIDEO_SUMMARY_ASR_LANGUAGE") or _string_value(asr_file_config, "language") or None
    if resolved_language == "auto":
        resolved_language = None
    return ASRConfig(
        model=model or os.getenv("VIDEO_SUMMARY_ASR_MODEL") or _string_value(asr_file_config, "model") or "medium",
        language=resolved_language,
        device=device or os.getenv("VIDEO_SUMMARY_ASR_DEVICE") or _string_value(asr_file_config, "device") or "auto",
        compute_type=compute_type
        or os.getenv("VIDEO_SUMMARY_ASR_COMPUTE_TYPE")
        or _string_value(asr_file_config, "compute_type")
        or "default",
    )


def load_chunking_config(
    target_minutes: float | None = None,
    max_chars: int | None = None,
) -> ChunkingConfig:
    file_config = load_file_config()
    chunking_file_config = _section(file_config, "chunking")
    resolved_target_minutes = (
        target_minutes
        if target_minutes is not None
        else _read_float_config(
            "VIDEO_SUMMARY_CHUNK_TARGET_MINUTES",
            chunking_file_config,
            "target_minutes",
            12,
            minimum=1.0,
        )
    )
    resolved_max_chars = (
        max_chars
        if max_chars is not None
        else _read_int_config("VIDEO_SUMMARY_CHUNK_MAX_CHARS", chunking_file_config, "max_chars", 30000, minimum=1000)
    )
    if resolved_target_minutes < 1:
        raise ConfigurationError("chunk-target-minutes 必须大于或等于 1。")
    if resolved_max_chars < 1000:
        raise ConfigurationError("chunk-max-chars 必须大于或等于 1000。")
    return ChunkingConfig(
        target_minutes=resolved_target_minutes,
        max_chars=resolved_max_chars,
    )


def _section(config: dict[str, object], name: str) -> dict[str, object]:
    value = config.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"配置文件中的 [{name}] 必须是表。")
    return value


def _string_value(config: dict[str, object], name: str) -> str | None:
    value = config.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigurationError(f"配置项 {name} 必须是字符串。")
    return value.strip() or None


def _read_float_config(
    env_name: str,
    file_config: dict[str, object],
    file_name: str,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw_env_value = os.getenv(env_name)
    if raw_env_value is not None and raw_env_value.strip() != "":
        return _parse_float(raw_env_value, env_name, minimum, maximum)
    file_value = file_config.get(file_name)
    if file_value is None:
        return _validate_float(default, env_name, minimum, maximum)
    if not isinstance(file_value, int | float):
        raise ConfigurationError(f"配置项 {file_name} 必须是数字，当前值：{file_value!r}。")
    return _validate_float(float(file_value), file_name, minimum, maximum)


def _read_int_config(
    env_name: str,
    file_config: dict[str, object],
    file_name: str,
    default: int,
    minimum: int | None = None,
) -> int:
    raw_env_value = os.getenv(env_name)
    if raw_env_value is not None and raw_env_value.strip() != "":
        return _parse_int(raw_env_value, env_name, minimum)
    file_value = file_config.get(file_name)
    if file_value is None:
        return _validate_int(default, env_name, minimum)
    if not isinstance(file_value, int):
        raise ConfigurationError(f"配置项 {file_name} 必须是整数，当前值：{file_value!r}。")
    return _validate_int(file_value, file_name, minimum)


def _read_float_env(
    name: str,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        value = default
    else:
        return _parse_float(raw_value, name, minimum, maximum)
    return _validate_float(value, name, minimum, maximum)


def _read_int_env(name: str, default: int, minimum: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        value = default
    else:
        return _parse_int(raw_value, name, minimum)
    return _validate_int(value, name, minimum)


def _parse_float(raw_value: str, name: str, minimum: float | None, maximum: float | None) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} 必须是数字，当前值：{raw_value!r}。") from exc
    return _validate_float(value, name, minimum, maximum)


def _validate_float(value: float, name: str, minimum: float | None, maximum: float | None) -> float:
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} 必须大于或等于 {minimum:g}，当前值：{value:g}。")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} 必须小于或等于 {maximum:g}，当前值：{value:g}。")
    return value


def _parse_int(raw_value: str, name: str, minimum: int | None) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} 必须是整数，当前值：{raw_value!r}。") from exc
    return _validate_int(value, name, minimum)


def _validate_int(value: int, name: str, minimum: int | None) -> int:
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} 必须大于或等于 {minimum}，当前值：{value}。")
    return value

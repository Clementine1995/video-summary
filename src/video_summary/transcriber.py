from __future__ import annotations

from pathlib import Path

from .config import ASRConfig
from .errors import ASRError
from .models import Segment


def transcribe_audio(audio_path: Path, config: ASRConfig) -> tuple[list[Segment], str | None]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ASRError("未安装 faster-whisper。请运行 `python -m pip install -e \".[asr]\"` 后重试。") from exc

    try:
        kwargs = {"device": config.device}
        if config.compute_type != "default":
            kwargs["compute_type"] = config.compute_type
        model = WhisperModel(config.model, **kwargs)
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=config.language,
            vad_filter=True,
        )
        detected_language = getattr(info, "language", None)
        segments = [
            Segment(
                start=float(segment.start),
                end=float(segment.end),
                text=segment.text.strip(),
                language=detected_language or config.language or "unknown",
            )
            for segment in segments_iter
            if segment.text.strip()
        ]
    except Exception as exc:
        raise ASRError(f"faster-whisper 转写失败。音频已保留在：{audio_path}") from exc

    if not segments:
        raise ASRError(f"faster-whisper 没有识别出文本。音频已保留在：{audio_path}")
    return segments, detected_language

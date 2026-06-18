from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ChunkingConfig, LLMConfig
from .models import TranscriptChunk, VideoMetadata
from .utils import format_timestamp


class RunState:
    def __init__(self, output_dir: Path, url: str, resume: bool) -> None:
        self.output_dir = output_dir
        self.path = output_dir / "run_state.json"
        self.payload: dict[str, Any] = {
            "status": "running",
            "started_at": _now(),
            "finished_at": None,
            "source_url": url,
            "resume": resume,
            "stage": "started",
            "metadata": {},
            "llm": {},
            "chunking": {},
            "steps": {},
            "chunks": [],
            "error": None,
        }
        self.write()

    def set_metadata(self, metadata: VideoMetadata) -> None:
        self.payload["metadata"] = {
            "title": metadata.title,
            "duration": metadata.duration,
            "webpage_url": metadata.webpage_url or metadata.source_url,
            "transcript_source": metadata.transcript_source or metadata.subtitle_source,
            "subtitle_language": metadata.subtitle_language,
            "asr_model": metadata.asr_model,
        }
        self.write()

    def set_configs(self, llm_config: LLMConfig, chunking_config: ChunkingConfig) -> None:
        self.payload["llm"] = {
            "provider": llm_config.provider,
            "base_url": llm_config.base_url,
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "timeout": llm_config.timeout,
        }
        self.payload["chunking"] = {
            "target_minutes": chunking_config.target_minutes,
            "max_chars": chunking_config.max_chars,
        }
        self.write()

    def stage(self, name: str, status: str = "running", **details: object) -> None:
        self.payload["stage"] = name
        steps = self.payload["steps"]
        steps[name] = {
            "status": status,
            "updated_at": _now(),
            **details,
        }
        self.write()

    def chunk_started(self, chunk: TranscriptChunk, total_chunks: int, cached: bool) -> None:
        self._upsert_chunk(
            chunk,
            total_chunks,
            {
                "status": "cached" if cached else "running",
                "cached": cached,
                "started_at": _now(),
                "finished_at": _now() if cached else None,
                "error": None,
            },
        )

    def chunk_completed(self, chunk: TranscriptChunk, total_chunks: int, cached: bool = False) -> None:
        self._upsert_chunk(
            chunk,
            total_chunks,
            {
                "status": "cached" if cached else "completed",
                "cached": cached,
                "finished_at": _now(),
                "error": None,
            },
        )

    def chunk_failed(self, chunk: TranscriptChunk, total_chunks: int, error: Exception) -> None:
        self._upsert_chunk(
            chunk,
            total_chunks,
            {
                "status": "failed",
                "cached": False,
                "finished_at": _now(),
                "error": str(error),
            },
        )

    def complete(self) -> None:
        self.payload["status"] = "completed"
        self.payload["stage"] = "completed"
        self.payload["finished_at"] = _now()
        self.write()

    def fail(self, stage: str, error: Exception) -> None:
        self.payload["status"] = "failed"
        self.payload["stage"] = stage
        self.payload["finished_at"] = _now()
        self.payload["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
        self.write()

    def write(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _upsert_chunk(self, chunk: TranscriptChunk, total_chunks: int, values: dict[str, object]) -> None:
        chunks = self.payload["chunks"]
        item = next((candidate for candidate in chunks if candidate["index"] == chunk.index), None)
        if item is None:
            item = {
                "index": chunk.index,
                "total": total_chunks,
                "start": format_timestamp(chunk.start),
                "end": format_timestamp(chunk.end),
                "status": "pending",
                "cached": False,
                "started_at": None,
                "finished_at": None,
                "error": None,
            }
            chunks.append(item)
        item.update(values)
        self.write()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

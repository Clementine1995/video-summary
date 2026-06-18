from __future__ import annotations

from pathlib import Path

from .audio import probe_media_duration
from .models import VideoMetadata


def probe_local_file_metadata(path: Path) -> VideoMetadata:
    resolved = path.resolve()
    return VideoMetadata(
        source_url=str(resolved),
        source_type="local_file",
        title=resolved.stem,
        duration=probe_media_duration(resolved),
        webpage_url=str(resolved),
        extractor="local",
        extra={"path": str(resolved)},
    )

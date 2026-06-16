from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import AudioExtractionError
from .models import VideoMetadata
from .utils import slugify, unique_dir


def download_youtube_audio(metadata: VideoMetadata, work_root: Path, sample_rate: int = 16000) -> Path:
    if shutil.which("yt-dlp") is None:
        raise AudioExtractionError("未找到 yt-dlp，无法下载音频。请先安装 yt-dlp。")
    if shutil.which("ffmpeg") is None:
        raise AudioExtractionError("未找到 ffmpeg，无法转换音频。请先安装 ffmpeg 并确保它在 PATH 中。")

    work_root.mkdir(parents=True, exist_ok=True)
    job_dir = unique_dir(work_root, slugify(metadata.title))
    job_dir.mkdir(parents=True)
    output_template = str(job_dir / "audio.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        "wav",
        "--postprocessor-args",
        f"ffmpeg:-ar {sample_rate} -ac 1",
        "-o",
        output_template,
        metadata.webpage_url or metadata.source_url,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise AudioExtractionError(f"音频下载或转换失败：{completed.stderr.strip() or completed.stdout.strip()}")

    audio_files = sorted(job_dir.glob("audio*.wav"))
    if not audio_files:
        raise AudioExtractionError("yt-dlp 没有生成可用的 wav 音频文件。")
    metadata.audio_path = str(audio_files[0])
    return audio_files[0]

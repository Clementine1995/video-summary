from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import AudioExtractionError
from .models import VideoMetadata
from .utils import slugify, unique_dir, yt_dlp_command


def download_video_audio(
    metadata: VideoMetadata,
    work_root: Path,
    sample_rate: int = 16000,
    yt_dlp_extra_args: list[str] | None = None,
) -> Path:
    command_prefix = yt_dlp_command()
    if command_prefix is None:
        raise AudioExtractionError("未找到 yt-dlp，无法下载音频。请先安装 yt-dlp。")
    ffmpeg_location = _find_ffmpeg()
    if ffmpeg_location is None:
        raise AudioExtractionError("未找到 ffmpeg，无法转换音频。请先安装 ffmpeg，或运行 `python -m pip install -e \".[asr]\"`。")

    work_root.mkdir(parents=True, exist_ok=True)
    job_dir = unique_dir(work_root, slugify(metadata.title))
    job_dir.mkdir(parents=True)
    output_template = str(job_dir / "audio.%(ext)s")
    command = [
        *command_prefix,
        *(yt_dlp_extra_args or []),
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        "wav",
        "--ffmpeg-location",
        ffmpeg_location,
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


def download_youtube_audio(metadata: VideoMetadata, work_root: Path, sample_rate: int = 16000) -> Path:
    return download_video_audio(metadata, work_root, sample_rate)


def extract_local_audio(
    metadata: VideoMetadata,
    input_path: Path,
    work_root: Path,
    sample_rate: int = 16000,
) -> Path:
    ffmpeg_location = _find_ffmpeg()
    if ffmpeg_location is None:
        raise AudioExtractionError("未找到 ffmpeg，无法转换本地音频。请先安装 ffmpeg，或运行 `python -m pip install -e \".[asr]\"`。")

    work_root.mkdir(parents=True, exist_ok=True)
    job_dir = unique_dir(work_root, slugify(metadata.title))
    job_dir.mkdir(parents=True)
    audio_path = job_dir / "audio.wav"
    command = [
        ffmpeg_location,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        str(audio_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise AudioExtractionError(f"本地音频转换失败：{completed.stderr.strip() or completed.stdout.strip()}")
    metadata.audio_path = str(audio_path)
    return audio_path


def probe_media_duration(input_path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        return None
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return None


def _find_ffmpeg() -> str | None:
    executable = shutil.which("ffmpeg")
    if executable is not None:
        return executable
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    return imageio_ffmpeg.get_ffmpeg_exe()

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from .audio import download_youtube_audio
from .cleaner import clean_segments
from .config import load_asr_config, load_chunking_config, load_llm_config
from .errors import SubtitleFetchError, UnsupportedInputError, VideoSummaryError
from .exporter import export_result
from .llm import summarize_with_chunking
from .models import PipelineResult
from .transcriber import transcribe_audio
from .utils import is_youtube_url
from .youtube import fetch_subtitles_for_metadata, probe_youtube_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a YouTube video into Markdown.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--output", "-o", default="outputs", help="Output root directory. Default: outputs")
    parser.add_argument(
        "--llm-provider",
        choices=["deepseek", "openai", "openai_compatible"],
        help="LLM provider. Default: VIDEO_SUMMARY_LLM_PROVIDER or deepseek.",
    )
    parser.add_argument("--llm-base-url", help="Override LLM base URL, for OpenAI-compatible services.")
    parser.add_argument("--llm-model", help="Override LLM model name.")
    parser.add_argument("--llm-api-key", help="Override LLM API key. Prefer environment variables for daily use.")
    parser.add_argument("--asr-model", help="faster-whisper model name or local model path. Default: medium.")
    parser.add_argument("--asr-language", help="ASR language code, such as zh/en. Default: auto.")
    parser.add_argument("--asr-device", help="ASR device, such as auto/cpu/cuda. Default: auto.")
    parser.add_argument("--asr-compute-type", help="faster-whisper compute type. Default: default.")
    parser.add_argument("--chunk-target-minutes", type=float, help="Target minutes per chunk for long videos. Default: 12.")
    parser.add_argument("--chunk-max-chars", type=int, help="Maximum transcript characters per chunk. Default: 30000.")
    parser.add_argument("--debug", action="store_true", help="Print technical traceback when a step fails.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if not is_youtube_url(args.url):
            raise UnsupportedInputError("第 2 阶段仍只支持 YouTube 链接。B站和本地文件会在后续阶段加入。")

        print("1/5 读取 YouTube 元数据...")
        metadata = probe_youtube_metadata(args.url)

        print("2/5 尝试获取字幕...")
        try:
            raw_segments = fetch_subtitles_for_metadata(metadata)
            metadata.extra.pop("raw_info", None)
            print("    已获取字幕，跳过音频转写。")
        except SubtitleFetchError as exc:
            print(f"    字幕不可用，进入 ASR 流程：{exc}")
            work_root = Path(args.output) / "_work"
            print("    下载并转换音频...")
            audio_path = download_youtube_audio(metadata, work_root)

            print("    使用 faster-whisper 转写音频...")
            asr_config = load_asr_config(
                model=args.asr_model,
                language=args.asr_language,
                device=args.asr_device,
                compute_type=args.asr_compute_type,
            )
            raw_segments, detected_language = transcribe_audio(audio_path, asr_config)
            metadata.subtitle_language = detected_language or asr_config.language
            metadata.subtitle_source = None
            metadata.transcript_source = "faster-whisper"
            metadata.asr_model = asr_config.model
            metadata.extra.pop("raw_info", None)

        print("3/5 清洗转写文本...")
        cleaned_segments = clean_segments(raw_segments)

        print("4/5 调用 LLM 生成总结...")
        llm_config = load_llm_config(
            provider=args.llm_provider,
            base_url=args.llm_base_url,
            model=args.llm_model,
            api_key=args.llm_api_key,
        )
        chunking_config = load_chunking_config(
            target_minutes=args.chunk_target_minutes,
            max_chars=args.chunk_max_chars,
        )
        summary, chunk_summaries = summarize_with_chunking(metadata, cleaned_segments, llm_config, chunking_config)
        if chunk_summaries:
            metadata.extra["chunk_count"] = len(chunk_summaries)

        result = PipelineResult(metadata, raw_segments, cleaned_segments, summary, chunk_summaries)
        output_dir = export_result(result, Path(args.output))
        print("5/5 Markdown 导出完成。")
        print(f"输出目录：{output_dir.resolve()}")
        return 0
    except VideoSummaryError as exc:
        print(f"处理失败：{exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1
    except OSError as exc:
        print(f"文件系统错误：{exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from .audio import download_video_audio, extract_local_audio
from .cache import find_resume_dir, load_cached_chunk_summaries, load_cached_pipeline_inputs, load_cached_summary
from .cleaner import clean_segments
from .config import load_asr_config, load_chunking_config, load_llm_config
from .errors import SubtitleFetchError, UnsupportedInputError, VideoSummaryError
from .exporter import export_metadata, export_result, export_transcripts, prepare_output_dir, render_chunk_summaries
from .local_file import probe_local_file_metadata
from .llm import summarize_with_chunking
from .models import ChunkSummary, PipelineResult, TranscriptChunk
from .run_state import RunState
from .transcriber import transcribe_audio
from .utils import is_supported_local_media_file, is_supported_video_url
from .youtube import fetch_subtitles_for_metadata, probe_video_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a YouTube, Bilibili, or local media file into Markdown.")
    parser.add_argument("url", help="YouTube/Bilibili video URL or local media file path")
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
    parser.add_argument("--resume", action="store_true", help="Reuse cached transcript and chunk summaries from a previous run.")
    parser.add_argument("--reuse-summary", action="store_true", help="With --resume, reuse summary.md if it already exists.")
    parser.add_argument("--force-chunks", action="store_true", help="With --resume, ignore cached chunk summaries and rerun all chunks.")
    parser.add_argument(
        "--rerun-chunk",
        type=int,
        action="append",
        default=[],
        metavar="N",
        help="With --resume, rerun one chunk index. Repeat to rerun multiple chunks.",
    )
    parser.add_argument("--cookies", help="Path to a yt-dlp cookies.txt file, useful for Bilibili or restricted videos.")
    parser.add_argument("--debug", action="store_true", help="Print technical traceback when a step fails.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_state: RunState | None = None
    current_stage = "startup"

    try:
        if args.reuse_summary and not args.resume:
            parser.error("--reuse-summary 需要和 --resume 一起使用。")
        if args.force_chunks and not args.resume:
            parser.error("--force-chunks 需要和 --resume 一起使用。")
        if args.rerun_chunk and not args.resume:
            parser.error("--rerun-chunk 需要和 --resume 一起使用。")
        if args.force_chunks and args.rerun_chunk:
            parser.error("--force-chunks 和 --rerun-chunk 不能同时使用。")
        if args.reuse_summary and (args.force_chunks or args.rerun_chunk):
            parser.error("--reuse-summary 不能和 --force-chunks 或 --rerun-chunk 同时使用。")
        if args.rerun_chunk and any(index < 1 for index in args.rerun_chunk):
            parser.error("--rerun-chunk 必须是大于等于 1 的 chunk 编号。")
        local_input_path = Path(args.url).expanduser()
        is_url_input = is_supported_video_url(args.url)
        is_local_input = not is_url_input and is_supported_local_media_file(local_input_path)
        if not (is_url_input or is_local_input):
            raise UnsupportedInputError("当前支持 YouTube、B站视频链接，以及本地音视频文件。")
        yt_dlp_extra_args = _yt_dlp_extra_args(args.cookies)

        current_stage = "metadata"
        print("1/5 读取视频元数据...")
        if is_local_input:
            metadata = probe_local_file_metadata(local_input_path)
        else:
            metadata = probe_video_metadata(args.url, yt_dlp_extra_args)
        output_root = Path(args.output)
        output_dir = find_resume_dir(output_root, metadata.title) if args.resume else None
        cached_inputs = load_cached_pipeline_inputs(output_dir) if output_dir is not None else None
        if output_dir is None:
            output_dir = prepare_output_dir(output_root, metadata)
        run_state = RunState(output_dir, args.url, args.resume)
        run_state.set_metadata(metadata)
        run_state.stage("metadata", "completed", output_dir=str(output_dir))

        if cached_inputs is not None:
            current_stage = "transcript_cache"
            metadata, raw_segments, cleaned_segments = cached_inputs
            run_state.set_metadata(metadata)
            run_state.stage(
                "transcript",
                "cached",
                raw_segment_count=len(raw_segments),
                cleaned_segment_count=len(cleaned_segments),
            )
            print(f"2/5 复用已缓存 transcript：{output_dir}")
            print("3/5 跳过清洗，使用已缓存 cleaned transcript。")
        else:
            current_stage = "subtitle"
            run_state.stage("subtitle", "running")
            if is_local_input:
                run_state.stage("subtitle", "skipped", reason="local_file")
                print("2/5 本地文件输入，进入 ASR 流程...")
                work_root = Path(args.output) / "_work"
                current_stage = "audio"
                run_state.stage("audio", "running")
                print("    转换本地音频...")
                audio_path = extract_local_audio(metadata, Path(metadata.source_url), work_root)
                run_state.stage("audio", "completed", audio_path=str(audio_path))
            else:
                print("2/5 尝试获取字幕...")
                try:
                    raw_segments = fetch_subtitles_for_metadata(metadata, yt_dlp_extra_args=yt_dlp_extra_args)
                    metadata.extra.pop("raw_info", None)
                    run_state.set_metadata(metadata)
                    run_state.stage("subtitle", "completed", raw_segment_count=len(raw_segments))
                    print("    已获取字幕，跳过音频转写。")
                    audio_path = None
                except SubtitleFetchError as exc:
                    run_state.stage("subtitle", "failed", error=str(exc))
                    print(f"    字幕不可用，进入 ASR 流程：{exc}")
                    work_root = Path(args.output) / "_work"
                    current_stage = "audio"
                    run_state.stage("audio", "running")
                    print("    下载并转换音频...")
                    audio_path = download_video_audio(metadata, work_root, yt_dlp_extra_args=yt_dlp_extra_args)
                    run_state.stage("audio", "completed", audio_path=str(audio_path))

            if metadata.transcript_source != "subtitle":
                current_stage = "asr"
                run_state.stage("asr", "running")
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
                run_state.set_metadata(metadata)
                run_state.stage("asr", "completed", raw_segment_count=len(raw_segments), language=metadata.subtitle_language)

            current_stage = "clean"
            run_state.stage("clean", "running")
            print("3/5 清洗转写文本...")
            cleaned_segments = clean_segments(raw_segments)
            export_transcripts(metadata, raw_segments, cleaned_segments, output_dir)
            export_metadata(metadata, raw_segments, cleaned_segments, output_dir)
            run_state.stage("clean", "completed", cleaned_segment_count=len(cleaned_segments))
            print(f"    已缓存 transcript：{output_dir.resolve()}")

        current_stage = "llm_config"
        print("4/5 准备生成总结...")
        cached_summary = load_cached_summary(output_dir / "summary.md") if args.resume and args.reuse_summary else None
        run_state.stage("llm", "running")
        cached_chunk_summaries = (
            load_cached_chunk_summaries(output_dir / "chunk_summaries.md")
            if args.resume and not args.force_chunks
            else []
        )
        rerun_chunk_indexes = set(args.rerun_chunk)

        if cached_summary is not None:
            summary = cached_summary
            chunk_summaries = cached_chunk_summaries
            run_state.stage("llm", "cached", chunk_count=len(chunk_summaries))
            print("    复用已缓存 summary.md。")
        else:
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
            run_state.set_configs(llm_config, chunking_config)

            def on_chunk_start(chunk: TranscriptChunk, total_chunks: int, is_cached: bool) -> None:
                state = "复用缓存" if is_cached else "调用 LLM"
                run_state.chunk_started(chunk, total_chunks, is_cached)
                print(f"    Chunk {chunk.index}/{total_chunks} {state}：{_fmt(chunk.start)} - {_fmt(chunk.end)}")

            def on_chunk_done(
                chunk: TranscriptChunk,
                total_chunks: int,
                is_cached: bool,
                chunk_summaries: list[ChunkSummary],
            ) -> None:
                run_state.chunk_completed(chunk, total_chunks, cached=is_cached)
                (output_dir / "chunk_summaries.md").write_text(render_chunk_summaries(metadata, chunk_summaries), encoding="utf-8")

            def on_chunk_error(chunk: TranscriptChunk, total_chunks: int, error: Exception) -> None:
                run_state.chunk_failed(chunk, total_chunks, error)

            started_at = time.monotonic()
            current_stage = "llm"
            summary, chunk_summaries = summarize_with_chunking(
                metadata,
                cleaned_segments,
                llm_config,
                chunking_config,
                cached_chunk_summaries=cached_chunk_summaries,
                rerun_chunk_indexes=rerun_chunk_indexes,
                on_chunk_start=on_chunk_start,
                on_chunk_done=on_chunk_done,
                on_chunk_error=on_chunk_error,
            )
            llm_elapsed = time.monotonic() - started_at
            run_state.stage("llm", "completed", elapsed_seconds=round(llm_elapsed, 1), chunk_count=len(chunk_summaries))
            print(f"    LLM 总结耗时：{llm_elapsed:.1f} 秒")
            metadata.extra["llm"] = {
                "provider": llm_config.provider,
                "base_url": llm_config.base_url,
                "model": llm_config.model,
            }
            metadata.extra["chunking"] = {
                "target_minutes": chunking_config.target_minutes,
                "max_chars": chunking_config.max_chars,
            }
        if chunk_summaries:
            metadata.extra["chunk_count"] = len(chunk_summaries)

        metadata.extra["resume"] = args.resume
        current_stage = "export"
        run_state.stage("export", "running")
        result = PipelineResult(metadata, raw_segments, cleaned_segments, summary, chunk_summaries)
        output_dir = export_result(result, output_root, output_dir)
        run_state.stage("export", "completed")
        run_state.complete()
        print("5/5 Markdown 导出完成。")
        print(f"输出目录：{output_dir.resolve()}")
        return 0
    except VideoSummaryError as exc:
        if run_state is not None:
            run_state.fail(current_stage, exc)
        print(f"处理失败：{exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1
    except OSError as exc:
        if run_state is not None:
            run_state.fail(current_stage, exc)
        print(f"文件系统错误：{exc}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1

def _fmt(seconds: float) -> str:
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _yt_dlp_extra_args(cookies: str | None) -> list[str]:
    args: list[str] = []
    if cookies:
        args.extend(["--cookies", cookies])
    return args


if __name__ == "__main__":
    raise SystemExit(main())

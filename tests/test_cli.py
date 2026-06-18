import json
import unittest
from dataclasses import asdict
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from video_summary.cli import main
from video_summary.config import ChunkingConfig, LLMConfig
from video_summary.models import Segment, VideoMetadata


class CLITests(unittest.TestCase):
    def test_reuse_summary_skips_llm_config(self):
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            output_dir = output_root / "demo"
            output_dir.mkdir()
            metadata = VideoMetadata(
                source_url="https://www.youtube.com/watch?v=demo",
                source_type="youtube",
                title="Demo",
                webpage_url="https://www.youtube.com/watch?v=demo",
                transcript_source="subtitle",
                subtitle_language="en",
            )
            transcript = """# Demo

- Source: https://www.youtube.com/watch?v=demo
- Transcript source: subtitle
- Language: en

[00:01 - 00:02] hello
"""
            (output_dir / "metadata.json").write_text(json.dumps(asdict(metadata)), encoding="utf-8")
            (output_dir / "transcript.raw.md").write_text(transcript, encoding="utf-8")
            (output_dir / "transcript.cleaned.md").write_text(transcript, encoding="utf-8")
            (output_dir / "summary.md").write_text("# Cached summary\n", encoding="utf-8")

            with (
                patch("video_summary.cli.probe_video_metadata", return_value=metadata),
                patch("video_summary.cli.load_llm_config", side_effect=AssertionError("LLM config should not load")),
                patch("video_summary.cli.transcribe_audio", side_effect=AssertionError("ASR should not run")),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                exit_code = main(
                    [
                        "https://www.youtube.com/watch?v=demo",
                        "--output",
                        str(output_root),
                        "--resume",
                        "--reuse-summary",
                    ]
                )

        self.assertEqual(exit_code, 0)

    def test_local_file_input_uses_local_audio_extraction(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "voice.mp3"
            media_path.write_bytes(b"fake")
            wav_path = root / "audio.wav"
            wav_path.write_bytes(b"wav")

            with (
                patch("video_summary.cli.extract_local_audio", return_value=wav_path) as extract_audio,
                patch("video_summary.cli.download_video_audio", side_effect=AssertionError("yt-dlp should not run")),
                patch("video_summary.cli.transcribe_audio", return_value=([Segment(0, 1, "hello", "en")], "en")),
                patch(
                    "video_summary.cli.load_llm_config",
                    return_value=LLMConfig("openai_compatible", "https://example.com/v1", "model", "key"),
                ),
                patch("video_summary.cli.load_chunking_config", return_value=ChunkingConfig(12, 30000)),
                patch("video_summary.cli.summarize_with_chunking", return_value=("# Summary", [])),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                exit_code = main([str(media_path), "--output", str(root / "outputs"), "--asr-model", "small"])

        self.assertEqual(exit_code, 0)
        extract_audio.assert_called_once()


if __name__ == "__main__":
    unittest.main()

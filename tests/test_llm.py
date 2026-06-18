import unittest
from unittest.mock import patch

from video_summary.config import ChunkingConfig, LLMConfig
from video_summary.llm import summarize_with_chunking
from video_summary.models import ChunkSummary, Segment, VideoMetadata


class LLMChunkingTests(unittest.TestCase):
    def test_rerun_chunk_indexes_ignore_only_selected_cached_chunks(self):
        metadata = VideoMetadata(source_url="https://example.com", source_type="video", title="Demo")
        segments = [
            Segment(0, 30, "first", "en"),
            Segment(80, 110, "second", "en"),
        ]
        cached = [
            ChunkSummary(1, 0, 30, "cached one"),
            ChunkSummary(2, 80, 110, "cached two"),
        ]
        llm_config = LLMConfig("openai_compatible", "https://example.com/v1", "model", "key")
        chunking_config = ChunkingConfig(target_minutes=1, max_chars=1000)

        with (
            patch("video_summary.llm.summarize_chunk_with_openai_compatible") as summarize_chunk,
            patch("video_summary.llm.summarize_chunk_summaries_with_openai_compatible", return_value="final"),
        ):
            summarize_chunk.return_value = ChunkSummary(2, 80, 110, "new two")

            summary, chunk_summaries = summarize_with_chunking(
                metadata,
                segments,
                llm_config,
                chunking_config,
                cached_chunk_summaries=cached,
                rerun_chunk_indexes={2},
            )

        self.assertEqual(summary, "final")
        self.assertEqual([item.markdown for item in chunk_summaries], ["cached one", "new two"])
        self.assertEqual(summarize_chunk.call_count, 1)
        self.assertEqual(summarize_chunk.call_args.args[1].index, 2)


if __name__ == "__main__":
    unittest.main()

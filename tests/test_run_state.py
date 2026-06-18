import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from video_summary.config import ChunkingConfig, LLMConfig
from video_summary.models import TranscriptChunk, VideoMetadata
from video_summary.run_state import RunState


class RunStateTests(unittest.TestCase):
    def test_run_state_records_configs_chunks_and_completion(self):
        with TemporaryDirectory() as temp_dir:
            state = RunState(Path(temp_dir), "https://example.com/watch?v=1", resume=True)
            state.set_metadata(VideoMetadata("url", "youtube", "Demo", duration=120))
            state.set_configs(
                LLMConfig("openai_compatible", "https://example.com/v1", "model-a", "secret"),
                ChunkingConfig(target_minutes=12, max_chars=30000),
            )
            chunk = TranscriptChunk(index=1, start=1, end=120, segments=[])
            state.chunk_started(chunk, total_chunks=2, cached=False)
            state.chunk_completed(chunk, total_chunks=2)
            state.complete()

            payload = json.loads((Path(temp_dir) / "run_state.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "completed")
        self.assertTrue(payload["resume"])
        self.assertEqual(payload["llm"]["model"], "model-a")
        self.assertNotIn("secret", json.dumps(payload))
        self.assertEqual(payload["chunking"]["max_chars"], 30000)
        self.assertEqual(payload["chunks"][0]["status"], "completed")
        self.assertEqual(payload["chunks"][0]["start"], "00:01")

    def test_run_state_records_failure(self):
        with TemporaryDirectory() as temp_dir:
            state = RunState(Path(temp_dir), "https://example.com/watch?v=1", resume=False)
            state.fail("llm", RuntimeError("boom"))

            payload = json.loads((Path(temp_dir) / "run_state.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["stage"], "llm")
        self.assertEqual(payload["error"]["type"], "RuntimeError")
        self.assertEqual(payload["error"]["message"], "boom")


if __name__ == "__main__":
    unittest.main()

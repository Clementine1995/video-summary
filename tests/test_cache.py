import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from video_summary.cache import load_cached_chunk_summaries, load_cached_summary, parse_transcript


class CacheTests(unittest.TestCase):
    def test_parse_transcript(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "transcript.cleaned.md"
            path.write_text(
                """# Demo

- Source: https://example.com
- Transcript source: subtitle
- Language: en

[00:01 - 00:03] hello
[01:02:03 - 01:02:05] world
""",
                encoding="utf-8",
            )

            segments = parse_transcript(path)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start, 1)
        self.assertEqual(segments[0].end, 3)
        self.assertEqual(segments[0].text, "hello")
        self.assertEqual(segments[0].language, "en")
        self.assertEqual(segments[1].start, 3723)

    def test_load_cached_chunk_summaries(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "chunk_summaries.md"
            path.write_text(
                """# Demo - 分段摘要

- Source: https://example.com
- Chunk count: 2

## Chunk 1: 00:01 - 12:00

chunk one

## Chunk 2: 12:00 - 24:00

chunk two
""",
                encoding="utf-8",
            )

            summaries = load_cached_chunk_summaries(path)

        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0].index, 1)
        self.assertEqual(summaries[0].start, 1)
        self.assertEqual(summaries[0].end, 720)
        self.assertEqual(summaries[0].markdown, "chunk one")
        self.assertEqual(summaries[1].markdown, "chunk two")

    def test_load_cached_summary(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "summary.md"
            path.write_text("\n# Summary\n\nbody\n", encoding="utf-8")

            summary = load_cached_summary(path)

        self.assertEqual(summary, "# Summary\n\nbody")


if __name__ == "__main__":
    unittest.main()

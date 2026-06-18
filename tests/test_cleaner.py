import unittest

from video_summary.cleaner import clean_segments
from video_summary.models import Segment


class CleanerTests(unittest.TestCase):
    def test_short_segments_do_not_merge_without_limit(self):
        segments = [
            Segment(start=index * 2, end=index * 2 + 1, text=f"短句{index}", language="zh")
            for index in range(40)
        ]

        cleaned = clean_segments(
            segments,
            min_gap_to_merge=1.2,
            min_chars=24,
            max_merged_chars=80,
            max_merged_duration=20,
        )

        self.assertGreater(len(cleaned), 3)
        self.assertTrue(all(len(segment.text) <= 80 for segment in cleaned))
        self.assertTrue(all(segment.end - segment.start <= 20 for segment in cleaned))


if __name__ == "__main__":
    unittest.main()

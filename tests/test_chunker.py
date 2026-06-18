import unittest

from video_summary.chunker import split_segments_into_chunks
from video_summary.models import Segment


class ChunkerTests(unittest.TestCase):
    def test_split_segments_into_time_chunks(self):
        segments = [
            Segment(start=0, end=30, text="intro"),
            Segment(start=40, end=70, text="first idea"),
            Segment(start=80, end=110, text="second idea"),
            Segment(start=130, end=160, text="third idea"),
        ]

        chunks = split_segments_into_chunks(segments, target_minutes=2, max_chars=1000)

        self.assertEqual(len(chunks), 2)
        self.assertEqual([segment.text for segment in chunks[0].segments], ["intro", "first idea", "second idea"])
        self.assertEqual(chunks[0].start, 0)
        self.assertEqual(chunks[0].end, 110)
        self.assertEqual([segment.text for segment in chunks[1].segments], ["third idea"])

    def test_split_segments_into_char_chunks(self):
        segments = [
            Segment(start=0, end=10, text="a" * 10),
            Segment(start=11, end=20, text="b" * 10),
            Segment(start=21, end=30, text="c" * 10),
        ]

        chunks = split_segments_into_chunks(segments, target_minutes=60, max_chars=25)

        self.assertEqual(len(chunks), 2)
        self.assertEqual([segment.text for segment in chunks[0].segments], ["a" * 10, "b" * 10])
        self.assertEqual([segment.text for segment in chunks[1].segments], ["c" * 10])


if __name__ == "__main__":
    unittest.main()

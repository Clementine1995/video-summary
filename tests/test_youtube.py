import unittest

from video_summary.errors import SubtitleFetchError
from video_summary.models import VideoMetadata
from video_summary.youtube import fetch_subtitles_for_metadata, parse_json_subtitle, parse_vtt


class YoutubeTests(unittest.TestCase):
    def test_parse_vtt_removes_tags_and_decodes_entities(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:03.000 align:start position:0%
<c>Tom &amp; Jerry</c> said &quot;hello&quot;

00:00:03.500 --> 00:00:05.000
第二句&#39;内容&#39;
"""

        segments = parse_vtt(content, "en")

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start, 1)
        self.assertEqual(segments[0].end, 3)
        self.assertEqual(segments[0].text, 'Tom & Jerry said "hello"')
        self.assertEqual(segments[1].text, "第二句'内容'")

    def test_parse_vtt_merges_duplicate_cues_with_same_start(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:02.000
repeat

00:00:01.000 --> 00:00:03.000
repeat
"""

        segments = parse_vtt(content, "en")

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].start, 1)
        self.assertEqual(segments[0].end, 3)
        self.assertEqual(segments[0].text, "repeat")

    def test_parse_bilibili_json_subtitle(self):
        content = """{
  "body": [
    {"from": 1.2, "to": 3.4, "content": "第一句"},
    {"from": 4, "to": 5, "content": "第二句 &amp; 内容"}
  ]
}"""

        segments = parse_json_subtitle(content, "zh-CN")

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start, 1.2)
        self.assertEqual(segments[0].end, 3.4)
        self.assertEqual(segments[0].text, "第一句")
        self.assertEqual(segments[1].text, "第二句 & 内容")

    def test_bilibili_without_subtitles_uses_bilibili_wording(self):
        metadata = VideoMetadata(
            source_url="https://www.bilibili.com/video/BV1",
            source_type="bilibili",
            title="Demo",
            webpage_url="https://www.bilibili.com/video/BV1",
            extra={"raw_info": {}},
        )

        with self.assertRaises(SubtitleFetchError) as context:
            fetch_subtitles_for_metadata(metadata)

        self.assertIn("B站视频没有发现可用字幕", str(context.exception))
        self.assertNotIn("YouTube", str(context.exception))


if __name__ == "__main__":
    unittest.main()

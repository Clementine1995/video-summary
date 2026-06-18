import unittest

from video_summary.utils import is_bilibili_url, is_supported_video_url, is_youtube_url


class UtilsTests(unittest.TestCase):
    def test_video_url_detection(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(is_supported_video_url("https://youtu.be/abc"))
        self.assertTrue(is_bilibili_url("https://www.bilibili.com/video/BV1xx411c7mD/"))
        self.assertTrue(is_supported_video_url("https://b23.tv/abc123"))
        self.assertFalse(is_supported_video_url("https://example.com/video"))


if __name__ == "__main__":
    unittest.main()

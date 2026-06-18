import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from video_summary.utils import is_bilibili_url, is_supported_local_media_file, is_supported_video_url, is_youtube_url


class UtilsTests(unittest.TestCase):
    def test_video_url_detection(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(is_supported_video_url("https://youtu.be/abc"))
        self.assertTrue(is_bilibili_url("https://www.bilibili.com/video/BV1xx411c7mD/"))
        self.assertTrue(is_supported_video_url("https://b23.tv/abc123"))
        self.assertFalse(is_supported_video_url("https://example.com/video"))

    def test_local_media_detection(self):
        with TemporaryDirectory() as temp_dir:
            media_path = Path(temp_dir) / "demo.mp4"
            text_path = Path(temp_dir) / "demo.txt"
            media_path.write_bytes(b"demo")
            text_path.write_text("demo", encoding="utf-8")

            self.assertTrue(is_supported_local_media_file(media_path))
            self.assertFalse(is_supported_local_media_file(text_path))
            self.assertFalse(is_supported_local_media_file(Path(temp_dir) / "missing.mp4"))


if __name__ == "__main__":
    unittest.main()

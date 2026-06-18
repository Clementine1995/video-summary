import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from video_summary.local_file import probe_local_file_metadata


class LocalFileTests(unittest.TestCase):
    def test_probe_local_file_metadata_uses_file_name(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "meeting recording.mp3"
            path.write_bytes(b"demo")

            with patch("video_summary.local_file.probe_media_duration", return_value=12.5):
                metadata = probe_local_file_metadata(path)

        self.assertEqual(metadata.source_type, "local_file")
        self.assertEqual(metadata.title, "meeting recording")
        self.assertEqual(metadata.duration, 12.5)
        self.assertEqual(metadata.extractor, "local")
        self.assertTrue(metadata.source_url.endswith("meeting recording.mp3"))


if __name__ == "__main__":
    unittest.main()

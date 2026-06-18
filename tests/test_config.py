import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from video_summary.config import load_chunking_config, load_llm_config
from video_summary.errors import ConfigurationError


class ConfigTests(unittest.TestCase):
    def test_load_chunking_config_reads_env(self):
        env = {
            **os.environ,
            "VIDEO_SUMMARY_CHUNK_TARGET_MINUTES": "8",
            "VIDEO_SUMMARY_CHUNK_MAX_CHARS": "12000",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_chunking_config()

        self.assertEqual(config.target_minutes, 8)
        self.assertEqual(config.max_chars, 12000)

    def test_load_llm_config_reads_local_config_file(self):
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.local.toml"
            config_path.write_text(
                """
[llm]
provider = "deepseek"
api_key = "file-key"
model = "deepseek-v4-flash"
temperature = 0.4
timeout = 30
""",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"VIDEO_SUMMARY_CONFIG": str(config_path)}, clear=True):
                config = load_llm_config()

        self.assertEqual(config.provider, "deepseek")
        self.assertEqual(config.api_key, "file-key")
        self.assertEqual(config.temperature, 0.4)
        self.assertEqual(config.timeout, 30)

    def test_env_overrides_config_file(self):
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.local.toml"
            config_path.write_text(
                """
[chunking]
target_minutes = 8
max_chars = 12000
""",
                encoding="utf-8",
            )
            env = {
                "VIDEO_SUMMARY_CONFIG": str(config_path),
                "VIDEO_SUMMARY_CHUNK_MAX_CHARS": "18000",
            }
            with patch.dict(os.environ, env, clear=True):
                config = load_chunking_config()

        self.assertEqual(config.target_minutes, 8)
        self.assertEqual(config.max_chars, 18000)

    def test_load_chunking_config_rejects_invalid_env(self):
        with patch.dict(os.environ, {"VIDEO_SUMMARY_CHUNK_TARGET_MINUTES": "soon"}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "VIDEO_SUMMARY_CHUNK_TARGET_MINUTES"):
                load_chunking_config()

    def test_load_llm_config_rejects_invalid_timeout(self):
        env = {
            "DEEPSEEK_API_KEY": "test-key",
            "VIDEO_SUMMARY_LLM_TIMEOUT": "fast",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "VIDEO_SUMMARY_LLM_TIMEOUT"):
                load_llm_config(provider="deepseek")


if __name__ == "__main__":
    unittest.main()

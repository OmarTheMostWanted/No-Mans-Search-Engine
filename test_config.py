from __future__ import annotations

import getpass
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import load_community_api_key, save_community_api_key


class LocalConfigKeyTests(unittest.TestCase):
    def test_save_and_load_key_from_local_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.local.json"
            save_community_api_key(" secret-value ", path)
            self.assertEqual(load_community_api_key(path), "secret-value")
            self.assertNotIn("secret-value", repr(__import__("config").SearchConfig()))

    def test_environment_key_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.local.json"
            save_community_api_key("file-key", path)
            with patch.dict(os.environ, {"NMS_ALMANAC_API_KEY": "environment-key"}):
                self.assertEqual(load_community_api_key(path), "environment-key")

    def test_reject_empty_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_community_api_key("  ", Path(directory) / "config.local.json")


if __name__ == "__main__":
    unittest.main()

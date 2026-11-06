from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cache import SQLiteSystemCache
from config import SearchConfig
from generator import iter_portal_addresses, search_systems
from js_bridge import JSBridge
from models import SystemRecord


class ConfigAndAddressTests(unittest.TestCase):
    def test_config_validation(self):
        config = SearchConfig(galaxy=1, search_mode="sequential", start_address="000000000000")
        config.validate()
        self.assertEqual(config.galaxy, 1)
        with self.assertRaises(ValueError):
            SearchConfig(galaxy=0).validate()

    def test_sequential_addresses_are_canonical_and_wrap(self):
        config = SearchConfig(search_mode="sequential", start_address="0FFFFFFFFFFF")
        addresses = iter_portal_addresses(config)
        self.assertEqual([next(addresses) for _ in range(3)],
                         ["0FFFFFFFFFFF", "000000000000", "000000000001"])

    def test_random_addresses_are_reproducible_and_canonical(self):
        left = iter_portal_addresses(SearchConfig(random_seed=77))
        right = iter_portal_addresses(SearchConfig(random_seed=77))
        values = [next(left) for _ in range(5)]
        self.assertEqual(values, [next(right) for _ in range(5)])
        self.assertTrue(all(len(value) == 12 and value[0] == "0" for value in values))

    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.sqlite"
            payload = {"address": "0807F07FFFFF", "galaxy": 0}
            with SQLiteSystemCache(path) as cache:
                cache.set(payload["address"], 0, payload)
                self.assertEqual(cache.get(payload["address"], 0), payload)
                self.assertIsNone(cache.get(payload["address"], 1))


class RealSubmoduleIntegrationTests(unittest.TestCase):
    """Integration tests deliberately execute the checked-out NMS submodule."""

    def test_real_lookup_uses_submodule_and_local_letter_map(self):
        with JSBridge() as bridge:
            record_data = bridge.batch(["0807F07FFFFF"], galaxy=0)[0]
        record = SystemRecord.from_upstream(record_data, "0807F07FFFFF", 1)
        self.assertEqual(record.star_color, record_data["starType"])
        self.assertIn(record.star_color, {"yellow", "green", "blue", "red", "purple"})
        self.assertIsInstance(record.planets, int)
        self.assertIsInstance(record.moons, int)
        self.assertTrue(record_data.get("name"), "local letter-map should provide a generated name")

    def test_search_calls_real_generator_and_returns_systems(self):
        config = SearchConfig(search_mode="sequential", start_address="0807F07FFFFF",
                              max_systems=3, max_matches=3, batch_size=2, duration_seconds=30,
                              cache_enabled=False)
        with JSBridge() as bridge:
            results = search_systems(config, bridge)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(result.portal_address.startswith("0") for result in results))
        self.assertTrue(all(result.galaxy == 1 for result in results))


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from cache import SQLiteSystemCache
from config import SearchConfig
from generator import iter_random_addresses, iter_sequential_addresses, search_systems
from models import SearchResult

# Representative shape from nms-tools/nms-lookup.js's documented return object.
UPSTREAM_SYSTEM = {
    "address": "0807F07FFFFF", "galaxy": 0, "name": "Sranch Op10079",
    "region": "Yihelli Quadrant", "planetNames": ["One", "Two", "Three", "Four"],
    "starType": "yellow", "planets": 4, "moons": 1, "gasGiant": False,
    "safeStart": 0, "planetIndex": 0, "race": "Gek", "economy": "Advanced Mining",
    "econType": "Mining", "econTier": 2, "econDesc": "Adequate", "sell": "24.5",
    "buy": "-18.3", "conflict": "Fractious", "conTier": 1, "abandoned": False,
    "uncharted": False, "outlaw": False, "isBlackHole": False, "isAtlas": False,
    "coords": {"x": 2047, "y": 127, "z": 2047},
}


class FakeBridge:
    def __init__(self, payloads=None):
        self.payloads = payloads or {}
        self.calls = []

    def batch(self, addresses, galaxy=0):
        self.calls.append((list(addresses), galaxy))
        result = []
        for address in addresses:
            payload = dict(self.payloads.get(address, UPSTREAM_SYSTEM))
            payload["address"] = address
            payload["galaxy"] = galaxy
            result.append(payload)
        return result


class SearchBehaviorTests(unittest.TestCase):
    def test_upstream_payload_normalization_and_tiers(self):
        result = SearchResult.from_upstream(UPSTREAM_SYSTEM, UPSTREAM_SYSTEM["address"], 1)
        self.assertEqual(result.star_type, "yellow")
        self.assertEqual(result.race, "gek")
        self.assertEqual(result.economy_tier, 3)  # upstream 0-based to config 1-based
        self.assertEqual(result.conflict_tier, 2)
        self.assertEqual(round(result.core_distance, 2), 2895.22)

    def test_filters_against_upstream_response_fields(self):
        result = SearchResult.from_upstream(UPSTREAM_SYSTEM, UPSTREAM_SYSTEM["address"], 1)
        config = SearchConfig(
            galaxy=1, star_color="yellow", exact_planets=4, min_moons=1,
            economy="advanced mining", economy_tier=3, conflict="fractious",
            conflict_tier=2, race="gek", pirate=False, abandoned=False,
            uncharted=False, black_hole=False, atlas_system=False,
            min_core_distance=2800, max_core_distance=3000,
        )
        config.validate()
        self.assertTrue(result.matches(config))

    def test_missing_upstream_values_do_not_fake_match(self):
        payload = dict(UPSTREAM_SYSTEM)
        payload.pop("suns")
        payload.pop("lushPlanets")
        result = SearchResult.from_upstream(payload, payload["address"], 1)
        self.assertFalse(result.matches(SearchConfig(exact_suns=1)))
        self.assertFalse(result.matches(SearchConfig(min_lush_planets=1)))

    def test_address_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            SearchResult.from_upstream(UPSTREAM_SYSTEM, "0807F07FFFFE", 1)

    def test_sequential_wrap(self):
        addresses = iter_sequential_addresses("FFFFFFFFFFFE")
        self.assertEqual([next(addresses) for _ in range(3)], ["FFFFFFFFFFFE", "FFFFFFFFFFFF", "000000000000"])

    def test_random_seed_is_reproducible_and_12_hex(self):
        a, b = iter_random_addresses(7), iter_random_addresses(7)
        first = [next(a) for _ in range(10)]
        self.assertEqual(first, [next(b) for _ in range(10)])
        self.assertTrue(all(len(item) == 12 for item in first))

    def test_sqlite_cache_roundtrip_and_galaxy_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteSystemCache(Path(directory) / "cache.sqlite") as cache:
                cache.set("0807f07fffff", 0, UPSTREAM_SYSTEM)
                self.assertEqual(cache.get("0807F07FFFFF", 0), UPSTREAM_SYSTEM)
                self.assertIsNone(cache.get("0807F07FFFFF", 1))

    def test_search_uses_cache_and_generator_galaxy_index(self):
        address = "000000000001"
        fake = FakeBridge()
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteSystemCache(Path(directory) / "cache.sqlite") as cache:
                config = SearchConfig(
                    galaxy=1, search_mode="sequential", start_address=address,
                    max_systems=2, max_matches=2, batch_size=1,
                )
                found = search_systems(config, fake, cache)
                self.assertEqual(len(found), 2)
                self.assertEqual(fake.calls[0][1], 0)
                self.assertEqual(cache.get(address, 0)["address"], address)
                count = len(fake.calls)
                search_systems(config, fake, cache)
                self.assertEqual(len(fake.calls), count)


if __name__ == "__main__":
    unittest.main()

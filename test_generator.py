from __future__ import annotations

from config import SearchConfig
from generator import iter_portal_addresses
from models import SystemRecord


def test_config_validation() -> None:
    cfg = SearchConfig(galaxy=1, search_mode="sequential", start_address="000000000000")
    cfg.validate()
    assert cfg.galaxy == 1
    assert cfg.search_mode == "sequential"

    try:
        SearchConfig(galaxy=0).validate()
        raise AssertionError("Galaxy 0 should be rejected")
    except ValueError:
        pass


def test_iter_portal_addresses_sequential() -> None:
    cfg = SearchConfig(
        galaxy=1,
        search_mode="sequential",
        start_address="000000000000",
    )

    first = next(iter_portal_addresses(cfg))
    second = next(iter_portal_addresses(cfg))
    third = next(iter_portal_addresses(cfg))
    assert first == "000000000000"
    assert second == "000000000001"
    assert third == "000000000002"


def test_system_record_matches() -> None:
    record = SystemRecord(
        portal_address="000000000001",
        galaxy=1,
        star_color="yellow",
        planets=4,
        moons=2,
        race="Gek",
        economy="Mining",
        economy_tier=2,
        conflict="Fractious",
        conflict_tier=2,
        pirate=False,
        abandoned=False,
        uncharted=False,
    )

    cfg = SearchConfig(
        galaxy=1,
        star_color="yellow",
        min_planets=3,
        max_moons=3,
        economy="mining",
        economy_tier=2,
        race="gek",
        pirate=False,
        search_mode="random",
        random_seed=123,
    )
    assert record.matches(cfg)

    cfg2 = SearchConfig(
        galaxy=1,
        star_color="green",
        search_mode="random",
        random_seed=123,
    )
    assert not record.matches(cfg2)


if __name__ == "__main__":
    test_config_validation()
    test_iter_portal_addresses_sequential()
    test_system_record_matches()
    print("all tests passed")

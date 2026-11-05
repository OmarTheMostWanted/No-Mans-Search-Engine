
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import re


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

MAX_GALAXY_NUMBER = 255

STAR_COLORS = {
    "yellow",
    "red",
    "green",
    "blue",
}

DOMINANT_RACES = {
    "gek",
    "vy'keen",
    "korvax",
    "uninhabited",
}

SEARCH_MODES = {
    "random",
    "sequential",
}

# The application uses human-friendly, 1-based galaxy numbers.
# The original NMS generator uses 0-based galaxy indices.
def galaxy_to_generator_index(galaxy_number: int) -> int:
    return galaxy_number - 1


def normalize_portal_address(address: str) -> str:
    address = address.strip().upper()

    if not re.fullmatch(r"[0-9A-F]{12}", address):
        raise ValueError(
            "Portal address must contain exactly 12 hexadecimal characters."
        )

    return address


def normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip()

    return value.lower() if value else None


# ---------------------------------------------------------------------
# Search configuration
# ---------------------------------------------------------------------

@dataclass
class SearchConfig:

    # ---------------------------------------------------------------
    # Galaxy
    # ---------------------------------------------------------------

    galaxy: int = 1

    # ---------------------------------------------------------------
    # Star properties
    # ---------------------------------------------------------------

    star_color: str | None = None

    min_suns: int | None = None
    exact_suns: int | None = None

    # ---------------------------------------------------------------
    # Planet properties
    # ---------------------------------------------------------------

    min_planets: int | None = None
    exact_planets: int | None = None

    min_moons: int | None = None
    max_moons: int | None = None

    min_lush_planets: int | None = None
    exact_lush_planets: int | None = None

    # ---------------------------------------------------------------
    # Economy and conflict
    # ---------------------------------------------------------------

    economy: str | None = None
    economy_tier: int | None = None

    conflict: str | None = None
    conflict_tier: int | None = None

    # ---------------------------------------------------------------
    # System ownership and characteristics
    # ---------------------------------------------------------------

    race: str | None = None

    # None = any system
    # True = pirate system only
    # False = non-pirate system only
    pirate: bool | None = None

    abandoned: bool | None = None
    uncharted: bool | None = None
    black_hole: bool | None = None
    atlas_system: bool | None = None

    # ---------------------------------------------------------------
    # Galactic core distance
    # ---------------------------------------------------------------

    min_core_distance: float | None = None
    max_core_distance: float | None = None

    # ---------------------------------------------------------------
    # Search strategy
    # ---------------------------------------------------------------

    search_mode: Literal["random", "sequential"] = "random"

    # Required for sequential searches.
    start_address: str | None = None

    # Used for reproducible random searches.
    random_seed: int | None = None

    # ---------------------------------------------------------------
    # Search duration and performance
    # ---------------------------------------------------------------

    # Default search duration: one hour.
    duration_seconds: int = 3600

    # Number of independent search workers.
    workers: int = 1

    # Number of systems sent to the generator per batch.
    batch_size: int = 100

    # Optional limit on total systems inspected.
    max_systems: int | None = None

    # Optional limit on matching systems.
    max_matches: int | None = None

    # ---------------------------------------------------------------
    # Database and caching
    # ---------------------------------------------------------------

    cache_enabled: bool = True

    cache_path: Path = Path("data/systems.sqlite3")

    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------

    def validate(self) -> None:

        # Galaxy
        if not 1 <= self.galaxy <= MAX_GALAXY_NUMBER:
            raise ValueError(
                f"Galaxy must be between 1 and {MAX_GALAXY_NUMBER}."
            )

        # Star colour
        if self.star_color is not None:
            self.star_color = self.star_color.strip().lower()

            if self.star_color not in STAR_COLORS:
                raise ValueError(
                    f"Invalid star colour: {self.star_color}"
                )

        # Economy and conflict
        self.economy = normalize_optional_string(self.economy)
        self.conflict = normalize_optional_string(self.conflict)

        self.race = normalize_optional_string(self.race)

        if self.race is not None:
            if self.race not in DOMINANT_RACES:
                raise ValueError(
                    f"Invalid dominant race: {self.race}"
                )

        # Economy tier
        if self.economy_tier is not None:
            if self.economy_tier not in (1, 2, 3):
                raise ValueError(
                    "Economy tier must be 1, 2 or 3."
                )

        # Conflict tier
        if self.conflict_tier is not None:
            if self.conflict_tier not in (1, 2, 3):
                raise ValueError(
                    "Conflict tier must be 1, 2 or 3."
                )

        # Suns
        self._validate_min_exact(
            self.min_suns,
            self.exact_suns,
            "sun count",
        )

        # Planets
        self._validate_min_exact(
            self.min_planets,
            self.exact_planets,
            "planet count",
        )

        # Lush planets
        self._validate_min_exact(
            self.min_lush_planets,
            self.exact_lush_planets,
            "lush planet count",
        )

        # Moon count
        self._validate_non_negative(
            self.min_moons,
            "minimum moons",
        )

        self._validate_non_negative(
            self.max_moons,
            "maximum moons",
        )

        if (
            self.min_moons is not None
            and self.max_moons is not None
            and self.min_moons > self.max_moons
        ):
            raise ValueError(
                "Minimum moon count cannot exceed maximum moon count."
            )

        # Core distance
        self._validate_non_negative(
            self.min_core_distance,
            "minimum core distance",
        )

        self._validate_non_negative(
            self.max_core_distance,
            "maximum core distance",
        )

        if (
            self.min_core_distance is not None
            and self.max_core_distance is not None
            and self.min_core_distance > self.max_core_distance
        ):
            raise ValueError(
                "Minimum core distance cannot exceed maximum core distance."
            )

        # Search mode
        if self.search_mode not in SEARCH_MODES:
            raise ValueError(
                f"Invalid search mode: {self.search_mode}"
            )

        if self.search_mode == "sequential":
            if self.start_address is None:
                raise ValueError(
                    "Sequential search requires a starting portal address."
                )

        if self.start_address is not None:
            self.start_address = normalize_portal_address(
                self.start_address
            )

        # Duration and performance
        if self.duration_seconds <= 0:
            raise ValueError(
                "Search duration must be greater than zero."
            )

        if self.workers < 1:
            raise ValueError(
                "At least one worker is required."
            )

        if self.batch_size < 1:
            raise ValueError(
                "Batch size must be greater than zero."
            )

        self._validate_positive(self.max_systems, "maximum systems")
        self._validate_positive(self.max_matches, "maximum matches")

        if self.random_seed is not None:
            if not isinstance(self.random_seed, int):
                raise ValueError("Random seed must be an integer.")

        # Normalize database path
        self.cache_path = Path(self.cache_path)

    @staticmethod
    def _validate_min_exact(minimum, exact, label):

        if minimum is not None and exact is not None:
            raise ValueError(
                f"Specify either minimum or exact {label}, not both."
            )

        SearchConfig._validate_non_negative(minimum, f"minimum {label}")
        SearchConfig._validate_non_negative(exact, f"exact {label}")

    @staticmethod
    def _validate_non_negative(value, label):

        if value is not None and value < 0:
            raise ValueError(
                f"{label.capitalize()} cannot be negative."
            )

    @staticmethod
    def _validate_positive(value, label):

        if value is not None and value <= 0:
            raise ValueError(
                f"{label.capitalize()} must be greater than zero."
            )

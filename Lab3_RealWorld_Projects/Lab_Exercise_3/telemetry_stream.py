"""
telemetry_stream.py
--------------------
Responsibility: TELEMETRY GENERATION ONLY.

This module is responsible for turning a student's personal identifiers
(surname, seed_num, favorite_artist) into a deterministic-but-unique
telemetry stream, and for lazily yielding readings one at a time via a
generator (Requirement #3) so the full stream is never held in memory.

It has no knowledge of validation, processing, or reporting logic —
that lives in diagnostics.py.
"""

import random
import time


# ---------------------------------------------------------------------------
# Student-specific seed construction
# ---------------------------------------------------------------------------
def build_unique_seed(surname: str, seed_num: int, favorite_artist: str) -> int:
    """
    Combine surname + seed_num + favorite_artist into a single reproducible
    integer seed. Using this seed with random.seed() means every run for a
    given student produces the SAME stream, but different students (different
    surname/artist/seed_num) get DIFFERENT streams. This is what makes the
    telemetry "student specific" (Requirement #1).
    """
    identity_string = f"{surname.strip().lower()}-{seed_num}-{favorite_artist.strip().lower()}"
    # Simple, dependency-free deterministic hash (sum of weighted char codes)
    combined = sum((i + 1) * ord(ch) for i, ch in enumerate(identity_string))
    return (combined * 31 + seed_num) % (2**31 - 1)


def build_sensor_names(favorite_artist: str) -> list:
    """
    Derive pseudo-random-but-personalized sensor names from the letters of
    the favorite artist's name, so the sensor list itself is student-specific.
    """
    letters = [c.upper() for c in favorite_artist if c.isalpha()]
    if not letters:
        letters = ["X"]
    unique_letters = sorted(set(letters))[:5] or ["X"]
    return [f"SENSOR-{letter}{i+1}" for i, letter in enumerate(unique_letters)]


# ---------------------------------------------------------------------------
# The telemetry generator (Requirement #3: generator, no full-list storage)
# ---------------------------------------------------------------------------
def telemetry_generator(surname: str, seed_num: int, favorite_artist: str,
                         num_readings: int = 60, corruption_rate: float = 0.15):
    """
    A GENERATOR that yields one telemetry reading at a time.

    Each reading is a dict:
        {
            "reading_id": int,
            "sensor": str,
            "timestamp": float,
            "value": float | str | None,   # may be intentionally invalid
            "unit": str,
        }

    A fraction of readings (controlled by corruption_rate) are intentionally
    corrupted (out-of-range, wrong type, or missing) to give the downstream
    exception-handling logic (Requirement #6) something real to catch.

    Because this is a generator, the caller processes readings one-by-one
    and the full stream is never materialized as a list.
    """
    seed = build_unique_seed(surname, seed_num, favorite_artist)
    rng = random.Random(seed)  # isolated RNG instance, deterministic per student

    sensors = build_sensor_names(favorite_artist)
    unit = "°C"
    normal_low, normal_high = 20.0, 85.0  # plausible equipment operating range

    start_time = time.time()

    for reading_id in range(1, num_readings + 1):
        sensor = sensors[reading_id % len(sensors)]
        timestamp = start_time + reading_id  # simulated, monotonically increasing

        roll = rng.random()
        if roll < corruption_rate * 0.4:
            # Missing reading
            value = None
        elif roll < corruption_rate * 0.7:
            # Wrong type (sensor glitch sends a string)
            value = "ERR_SIGNAL"
        elif roll < corruption_rate:
            # Wild out-of-range spike (e.g. sensor malfunction)
            value = rng.uniform(300.0, 999.0)
        else:
            # Normal-ish reading, with an occasional genuine abnormal spike
            if rng.random() < 0.12:
                value = rng.uniform(normal_high + 1, normal_high + 40)  # real overheat
            else:
                value = rng.uniform(normal_low, normal_high)

        yield {
            "reading_id": reading_id,
            "sensor": sensor,
            "timestamp": round(timestamp, 3),
            "value": value,
            "unit": unit,
        }
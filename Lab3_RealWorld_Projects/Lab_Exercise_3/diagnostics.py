#diagnostics.py
import functools
import time

# Equipment safety threshold (°C) — anything above this is "abnormal"
ABNORMAL_THRESHOLD = 85.0
# A reading is only "valid" if it's a real number within a sane sensor range
SANE_MIN, SANE_MAX = -50.0, 300.0

# ---------------------------------------------------------------------------
# Lambda-based filters/transforms (Requirement #4)
# ---------------------------------------------------------------------------
is_numeric = lambda v: isinstance(v, (int, float))                     # filter
is_within_sane_range = lambda v: SANE_MIN <= v <= SANE_MAX              # filter
to_two_decimals = lambda v: round(float(v), 2)                         # transform
is_abnormal = lambda v: v > ABNORMAL_THRESHOLD                         # filter


# ---------------------------------------------------------------------------
# Decorator to monitor the major processing function (Requirement #5)
# ---------------------------------------------------------------------------
def monitor_processing(func):
    """
    Wraps a processing function to log every call (arguments summary,
    execution time, and outcome) into an execution log that is attached
    to the wrapper itself (func.execution_log), so main.py can print it
    later as part of the assessment/execution trail.
    """
    execution_log = []

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        reading = args[0] if args else kwargs.get("reading")
        rid = reading.get("reading_id", "?") if isinstance(reading, dict) else "?"
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            execution_log.append(
                f"[OK]    reading#{rid:<4} processed in {elapsed_ms:6.3f} ms -> {result['status']}"
            )
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            execution_log.append(
                f"[ERROR] reading#{rid:<4} raised {type(exc).__name__} after {elapsed_ms:6.3f} ms: {exc}"
            )
            raise

    wrapper.execution_log = execution_log
    return wrapper


# ---------------------------------------------------------------------------
# Custom exception for clarity when reporting invalid telemetry
# ---------------------------------------------------------------------------
class InvalidTelemetryError(ValueError):
    """Raised when a telemetry reading fails validation."""


# ---------------------------------------------------------------------------
# Major processing function (decorated + exception-handled) (Req #5, #6)
# ---------------------------------------------------------------------------
@monitor_processing
def process_reading(reading: dict) -> dict:
    """
    Validate and normalize a single telemetry reading.

    Raises InvalidTelemetryError for missing, wrong-typed, or out-of-range
    values. The CALLER (main.py) is responsible for catching this so that
    one bad reading never terminates the stream (Requirement #6).
    """
    raw_value = reading.get("value")

    if raw_value is None:
        raise InvalidTelemetryError(f"Missing value from {reading['sensor']}")

    if not is_numeric(raw_value):
        raise InvalidTelemetryError(
            f"Non-numeric value '{raw_value}' from {reading['sensor']}"
        )

    if not is_within_sane_range(raw_value):
        raise InvalidTelemetryError(
            f"Out-of-range value {raw_value}{reading['unit']} from {reading['sensor']}"
        )

    clean_value = to_two_decimals(raw_value)
    status = "ABNORMAL" if is_abnormal(clean_value) else "NORMAL"

    return {
        "reading_id": reading["reading_id"],
        "sensor": reading["sensor"],
        "value": clean_value,
        "unit": reading["unit"],
        "status": status,
    }


# ---------------------------------------------------------------------------
# Recursive abnormal-condition tracer (Requirement #7)
# ---------------------------------------------------------------------------
def trace_abnormal_streak(processed_results: list, start_index: int, depth: int = 0) -> dict:
    """
    Recursively walks BACKWARD through the list of already-processed,
    valid results starting at `start_index`, to find how far back a run
    of consecutive ABNORMAL readings extends on the SAME sensor.

    Base conditions (recursion stops when any is true):
      1. We've walked off the start of the list (start_index < 0)
      2. We hit a reading that is NORMAL (streak broken)
      3. We hit a reading from a different sensor (streak broken)

    Returns a dict describing the traced streak:
        {"streak_length": int, "sensor": str, "peak_value": float,
         "trace_path": [reading_id, ...]}
    """
    # Base condition 1: ran off the beginning of the data
    if start_index < 0:
        return {"streak_length": depth, "sensor": None, "peak_value": None, "trace_path": []}

    current = processed_results[start_index]

    # Base condition 2: this reading is normal -> streak ends here
    if current["status"] != "ABNORMAL":
        return {"streak_length": depth, "sensor": None, "peak_value": None, "trace_path": []}

    # Look one step further back
    prev_index = start_index - 1
    sensor = current["sensor"]

    # Base condition 3: previous reading belongs to a different sensor
    if prev_index >= 0 and processed_results[prev_index]["sensor"] != sensor:
        return {
            "streak_length": depth + 1,
            "sensor": sensor,
            "peak_value": current["value"],
            "trace_path": [current["reading_id"]],
        }

    # Recursive case: keep tracing backward
    deeper = trace_abnormal_streak(processed_results, prev_index, depth + 1)

    return {
        "streak_length": deeper["streak_length"] if deeper["sensor"] else depth + 1,
        "sensor": sensor,
        "peak_value": max(current["value"], deeper["peak_value"] or current["value"]),
        "trace_path": [current["reading_id"]] + deeper["trace_path"],
    }


# ---------------------------------------------------------------------------
# Final diagnostic report (Requirement #8, #9)
# ---------------------------------------------------------------------------
def generate_report(student_info: dict, total: int, valid: int, invalid: int,
                     abnormal_events: list, execution_log: list) -> dict:
    """
    Assemble the final diagnostic report dict from all accumulated results.
    """
    if abnormal_events:
        overall_status = "CRITICAL" if any(e["trace"]["streak_length"] >= 3 for e in abnormal_events) \
            else "WARNING"
    else:
        overall_status = "NORMAL"

    return {
        "student_info": student_info,
        "total_processed": total,
        "valid_readings": valid,
        "invalid_readings": invalid,
        "abnormal_count": len(abnormal_events),
        "abnormal_events": abnormal_events,
        "overall_status": overall_status,
        "execution_log": execution_log,
    }
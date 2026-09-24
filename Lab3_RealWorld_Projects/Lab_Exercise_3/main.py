
from telemetry_stream import telemetry_generator
from diagnostics import (
    process_reading,
    trace_abnormal_streak,
    generate_report,
    InvalidTelemetryError,
    is_numeric,
)


SURNAME = "ARDIENTE"
SEED_NUM = 2
FAVORITE_ARTIST = "Radiohead"
NUM_READINGS = 60


def run_monitoring_pipeline():
    student_info = {
        "surname": SURNAME,
        "seed_num": SEED_NUM,
        "favorite_artist": FAVORITE_ARTIST,
    }

    print("=" * 70)
    print("STUDENT-SPECIFIC INPUTS")
    print("=" * 70)
    for k, v in student_info.items():
        print(f"  {k:16}: {v}")

    # A lambda transform applied inline as readings stream through
    
    reading_summary = lambda r: f"#{r['reading_id']:<3} {r['sensor']:<10} raw={r['value']}"

    processed_results = []          # only VALID, processed readings
    abnormal_events = []            # traced abnormal streaks
    total_seen = 0
    valid_count = 0
    invalid_count = 0
    invalid_log = []

    print("\n" + "=" * 70)
    print("GENERATED TELEMETRY (raw stream, one reading at a time)")
    print("=" * 70)

    # consumes the generator lazily; nothing is stored in bulk
    for reading in telemetry_generator(SURNAME, SEED_NUM, FAVORITE_ARTIST, NUM_READINGS):
        total_seen += 1
        print(reading_summary(reading))

        try:
            result = process_reading(reading)   # decorator-monitored + may raise
        except InvalidTelemetryError as exc:
            # Requirement #6: invalid data is handled, NOT fatal
            invalid_count += 1
            invalid_log.append(str(exc))
            continue
        except Exception as exc:  # safety net for any unexpected error type
            invalid_count += 1
            invalid_log.append(f"Unexpected error: {exc}")
            continue

        valid_count += 1
        processed_results.append(result)

        # Requirement #7 trigger: when we hit an abnormal reading, recursively
        # trace how far the abnormal streak on this sensor extends.
        if result["status"] == "ABNORMAL":
            idx = len(processed_results) - 1
            trace = trace_abnormal_streak(processed_results, idx)
            abnormal_events.append({"reading_id": result["reading_id"],
                                     "sensor": result["sensor"],
                                     "value": result["value"],
                                     "trace": trace})


    
    print("\n" + "=" * 70)
    print("VALID / INVALID RESULTS")
    print("=" * 70)
    print(f"  Valid readings   : {valid_count}")
    print(f"  Invalid readings : {invalid_count}")
    if invalid_log:
        print("  Sample invalid-reading reasons:")
        for msg in invalid_log[:5]:
            print(f"    - {msg}")
        if len(invalid_log) > 5:
            print(f"    ... and {len(invalid_log) - 5} more")

    print("\n" + "=" * 70)
    print("PROCESSED RESULTS (valid readings, normalized)")
    print("=" * 70)
    for r in processed_results[:10]:
        print(f"  #{r['reading_id']:<3} {r['sensor']:<10} {r['value']:>7}{r['unit']} -> {r['status']}")
    if len(processed_results) > 10:
        print(f"  ... and {len(processed_results) - 10} more valid readings")

    print("\n" + "=" * 70)
    print("RECURSIVE ABNORMAL-CONDITION ANALYSIS")
    print("=" * 70)
    if abnormal_events:
        for event in abnormal_events:
            t = event["trace"]
            print(f"  Reading #{event['reading_id']} ({event['sensor']}, {event['value']}°C):")
            print(f"      streak_length={t['streak_length']}, peak={t['peak_value']}, "
                  f"trace_path(back-to-front)={list(reversed(t['trace_path']))}")
    else:
        print("  No abnormal conditions detected.")

    # Build final report 
    report = generate_report(
        student_info, total_seen, valid_count, invalid_count,
        abnormal_events, process_reading.execution_log
    )

    print("\n" + "=" * 70)
    print("EXECUTION LOG (decorator-captured, first 10 entries)")
    print("=" * 70)
    for line in report["execution_log"][:10]:
        print(f"  {line}")
    if len(report["execution_log"]) > 10:
        print(f"  ... and {len(report['execution_log']) - 10} more log entries")

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL DIAGNOSTIC SUMMARY")
    print("=" * 70)
    print(f"  Total readings processed : {report['total_processed']}")
    print(f"  Valid readings           : {report['valid_readings']}")
    print(f"  Invalid readings         : {report['invalid_readings']}")
    print(f"  Abnormal conditions found: {report['abnormal_count']}")
    print(f"  OVERALL EQUIPMENT STATUS : {report['overall_status']}")
    print("=" * 70)

    return report


if __name__ == "__main__":
    run_monitoring_pipeline()
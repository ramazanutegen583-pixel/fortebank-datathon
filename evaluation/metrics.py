"""Aggregate availability, binary accuracy, localization, and runtime."""

import math
import statistics


def summarize(records: list[dict], tolerance: float = 5.0) -> dict:
    tp = fp = tn = fn = correct = completed = localized = targets = 0
    times = []
    errors = {}
    for record in records:
        actual = record["positive"]
        targets += len(record.get("timecodes", []))
        times.append(record["elapsed_seconds"])
        if record["status"] != "done":
            code = record.get("error_code", "UNKNOWN")
            errors[code] = errors.get(code, 0) + 1
            fn += int(actual)
            continue
        completed += 1
        predicted = record["verdict"] == "violation"
        correct += actual == predicted
        tp += actual and predicted
        fp += not actual and predicted
        tn += not actual and not predicted
        fn += actual and not predicted
        predicted_times = [event["timecode_sec"] for event in record.get("violations", [])]
        remaining = list(predicted_times)
        for target in record.get("timecodes", []):
            if remaining:
                nearest = min(remaining, key=lambda stamp: abs(stamp - target))
                if abs(nearest - target) <= tolerance:
                    localized += 1
                    remaining.remove(nearest)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    ordered = sorted(times)
    return {
        "videos": len(records), "completed": completed,
        "completion_rate": completed / len(records) if records else 0,
        "accuracy_all_inputs": correct / len(records) if records else 0,
        "accuracy_completed": correct / completed if completed else None,
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "localized_within_tolerance": localized, "timestamp_targets": targets,
        "localization_recall": localized / targets if targets else None,
        "timestamp_tolerance_seconds": tolerance,
        "runtime_median_seconds": statistics.median(times) if times else None,
        "runtime_p95_seconds": ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)] if times else None,
        "under_300_seconds": sum(t < 300 for t in times), "errors": errors,
        "scope": "local worker including decode, model loading, evidence and contract conversion; excludes HTTP upload/queue",
    }

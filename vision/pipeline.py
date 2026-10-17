"""Synchronous analyzer implementing the shared product contract."""

from __future__ import annotations

import json
from pathlib import Path
import time

from vision.backend import get_backend
from vision.config import VisionSettings
from vision.offline import network_disabled
from vision.rules import load_catalog, source_for
from vision.video import inspect_video, plan_windows, sample_frames, window_targets


def merge_candidates(candidates: list[dict], distance: float) -> list[dict]:
    """Merge overlapping detections of the same category, keeping strongest evidence."""
    groups = []
    for candidate in sorted(candidates, key=lambda item: item["timestamp"]):
        previous = next((group for group in reversed(groups) if group["rule_id"] == candidate["rule_id"]
                         and candidate["timestamp"] - group["last_timestamp"] <= distance), None)
        if previous is None:
            groups.append({**candidate, "last_timestamp": candidate["timestamp"]})
        else:
            previous["last_timestamp"] = candidate["timestamp"]
            if candidate["confidence"] > previous["confidence"]:
                previous.update(candidate)
    return sorted(groups, key=lambda item: item["timestamp"])


def analyze_video(video_path: Path, output_dir: Path) -> dict:
    settings = VisionSettings.from_env()
    output_dir = Path(output_dir).resolve()
    video_path = Path(video_path).resolve(strict=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    with network_disabled():
        return _analyze(video_path, output_dir, settings)


def _analyze(video_path: Path, output_dir: Path, settings: VisionSettings) -> dict:
    started = time.monotonic()

    def check_deadline():
        if time.monotonic() - started > settings.budget_seconds:
            raise TimeoutError("The local processing budget was exceeded.")

    duration = inspect_video(video_path)
    if duration > settings.max_duration_seconds:
        raise ValueError("Video exceeds the supported local duration limit.")
    windows = plan_windows(duration, settings.window_seconds, settings.overlap_seconds, settings.max_windows)
    catalog = load_catalog()
    rules = {rule["id"]: rule for rule in catalog["rules"]}
    backend = get_backend(settings)
    check_deadline()
    diagnostics = {"duration_seconds": duration, "windows_planned": len(windows), "windows_completed": 0,
                   "model_directory": settings.model_dir.name, "quantization": settings.quantization,
                   "input_mode": settings.input_mode, "offload_visual": settings.offload_visual,
                   "max_frame_pixels": settings.max_frame_pixels, "max_new_tokens": settings.max_new_tokens,
                   "catalog_version": catalog["version"], "passes": []}
    candidates = []
    # Detailed observations are written only beside local evidence, never to stdout.
    diagnostics_path = output_dir / "local-diagnostics.json"

    def save_diagnostics():
        diagnostics["elapsed_seconds"] = round(time.monotonic() - started, 3)
        diagnostics_path.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=True), encoding="utf-8")

    try:
        for start, end in windows:
            check_deadline()
            samples = sample_frames(video_path, window_targets(start, end, settings.frames_per_window),
                                    settings.max_frame_pixels, check_deadline)
            events, raw = backend.analyze(samples, rules, check_deadline)
            diagnostics["passes"].append({"phase": "scan", "start": start, "end": end, "output": raw,
                                           "timings": getattr(backend, "last_timings", [])})
            diagnostics["windows_completed"] += 1
            for event in events:
                # Sparse samples cannot prove that an action never occurred between frames.
                if rules[event["rule_id"]].get("requires_continuous_coverage", False):
                    continue
                if event["confidence"] >= settings.confidence_threshold:
                    candidates.append({**event, "timestamp": samples[event["frame_index"]].timestamp,
                                       "window_start": start, "window_end": end})
            save_diagnostics()
        candidates = merge_candidates(candidates, settings.merge_seconds)
        if len(candidates) > settings.max_candidates:
            raise ValueError("Too many candidates for complete verification.")
        violations = []
        for candidate in candidates:
            check_deadline()
            # Include temporal context on both sides of the proposed action.
            center = candidate["timestamp"]
            start = max(0, candidate["window_start"] - 1)
            end = min(duration, candidate["window_end"] + 1)
            samples = sample_frames(video_path, window_targets(start, end, settings.frames_per_window),
                                    settings.max_frame_pixels, check_deadline)
            selected_rules = {candidate["rule_id"]: rules[candidate["rule_id"]]}
            confirmed, raw = backend.analyze(samples, selected_rules, check_deadline, verification=True)
            diagnostics["passes"].append({"phase": "verify", "start": start, "end": end, "output": raw,
                                           "timings": getattr(backend, "last_timings", [])})
            confirmed = [event for event in confirmed if event["confidence"] >= settings.confidence_threshold]
            if not confirmed:
                continue
            event = max(confirmed, key=lambda item: item["confidence"])
            index = event["frame_index"]
            rule = rules[event["rule_id"]]
            event_time = samples[index].timestamp
            if any(previous["type"] == rule["title"] and
                   abs(previous["timecode_sec"] - event_time) <= settings.merge_seconds
                   for previous in violations):
                continue
            evidence = []
            indices = sorted({max(0, index - 1), index, min(len(samples) - 1, index + 1)})
            evidence_samples = sample_frames(video_path, [samples[i].timestamp for i in indices],
                                             4_000_000, check_deadline)
            for evidence_index, sample in enumerate(evidence_samples):
                relative = f"evidence/event-{len(violations):02d}-frame-{evidence_index:02d}.jpg"
                target = output_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                sample.image.save(target, "JPEG", quality=90)
                evidence.append({"timestamp_sec": sample.timestamp, "image_path": relative})
            violations.append({
                "type": rule["title"], "timecode_sec": event_time,
                "description": event["observation"].strip() + " Possible procedural concern for human review. "
                    + rule["summary"] + " Reference: original 2019 published edition; current applicability requires review.",
                "evidence_frames": evidence, "sources": [source_for(catalog, rule)],
            })
        if len(violations) > settings.max_events:
            raise ValueError("Too many events for a complete bounded result.")
        check_deadline()
        result = {"verdict": "violation" if violations else "no_violation", "violations": violations}
        diagnostics["verified_events"] = len(violations)
        return result
    finally:
        save_diagnostics()

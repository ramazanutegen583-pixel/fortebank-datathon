"""Run local predictions and print aggregate metrics only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from evaluation.metrics import summarize
from server.validation import ProcessingError
from server.worker import WorkerRunner
from vision.config import VisionSettings
from vision.rules import load_catalog

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "local_data" / "manifest.json")
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime" / "evaluation")
    arguments = parser.parse_args()
    if not arguments.output.resolve().is_relative_to((ROOT / "runtime").resolve()):
        parser.error("Detailed evaluation output must stay under the ignored runtime directory.")
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    if manifest.get("purpose") != "organizer_training_only":
        parser.error("This evaluator accepts organizer training material only.")
    items = manifest[arguments.split]
    if arguments.limit:
        items = items[:arguments.limit]
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "records.json").exists():
        parser.error("Use a fresh runtime output directory to preserve prior evaluation results.")
    runner = WorkerRunner("vision.pipeline:analyze_video", 8 * 1024 * 1024, output)
    records = []
    configuration = VisionSettings.from_env()
    catalog_version = load_catalog()["version"]
    try:
        for index, item in enumerate(items):
            started = time.monotonic()
            event_dir = output / f"sample-{index:03d}"
            event_dir.mkdir(parents=True, exist_ok=True)
            record = {"positive": item["positive"], "timecodes": item["timecodes"], "status": "failed"}
            try:
                result = runner.execute(f"evaluation-{index:03d}", Path(item["video"]), event_dir, time.time() + 270)
                if result["ok"]:
                    record.update(result["public"])
                    (event_dir / "result.json").write_text(json.dumps(result, ensure_ascii=True), encoding="utf-8")
                    # Encoded frames stay in the local per-video result, not the aggregate record.
                    record["violations"] = [{"timecode_sec": event["timecode_sec"]}
                                            for event in record["violations"]]
                else:
                    record["error_code"] = result["code"]
            except ProcessingError as error:
                record["error_code"] = error.code
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            records.append(record)
            (output / "records.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
            summary = summarize(records)
            summary.update({"split": arguments.split, "seed": manifest["seed"],
                            "requested_videos": len(items), "is_partial": len(records) < len(manifest[arguments.split])})
            summary["configuration"] = {"model": configuration.model_dir.name,
                                        "quantization": configuration.quantization,
                                        "input_mode": configuration.input_mode,
                                        "quantize_vision": configuration.quantize_vision,
                                        "offload_visual": configuration.offload_visual,
                                        "max_new_tokens": configuration.max_new_tokens,
                                        "frames_per_window": configuration.frames_per_window,
                                        "window_seconds": configuration.window_seconds,
                                        "catalog_version": catalog_version,
                                        "confidence_threshold": configuration.confidence_threshold,
                                        "max_frame_pixels": configuration.max_frame_pixels}
            (output / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(f"Completed local evaluation {index + 1}/{len(items)}; elapsed {record['elapsed_seconds']:.1f}s", flush=True)
        print(json.dumps(summary if records else summarize([]), indent=2))
    finally:
        runner.close()


if __name__ == "__main__":
    main()

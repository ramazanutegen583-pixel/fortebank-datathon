"""Explicitly selected synthetic analyzers for product integration tests only."""

import time
from pathlib import Path

from PIL import Image


def negative(*, video_path: Path, output_dir: Path) -> dict:
    return {"verdict": "no_violation", "violations": []}


def positive(*, video_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 120), (92, 112, 85)).save(output_dir / "frame.jpg", format="JPEG")
    return {"verdict": "violation", "violations": [{
        "type": "Synthetic review event", "timecode_sec": 1,
        "description": "Synthetic event used to verify the interface and evidence mapping.",
        "evidence_frames": [{"timestamp_sec": 1, "image_path": "frame.jpg"}],
        "sources": [{"document_title": "Synthetic rule reference", "section": "Example section",
                     "url": "https://example.invalid/synthetic-rule", "rationale": "Synthetic reasoning for interface verification."}],
    }]}


def slow(*, video_path: Path, output_dir: Path) -> dict:
    time.sleep(12)
    return negative(video_path=video_path, output_dir=output_dir)


def broken(*, video_path: Path, output_dir: Path) -> dict:
    raise RuntimeError("Private detailed content must never leave the local analyzer.")


def invalid(*, video_path: Path, output_dir: Path) -> dict:
    return {"verdict": "violation", "violations": []}


def missing_weights(*, video_path: Path, output_dir: Path) -> dict:
    raise FileNotFoundError("Private weights path must not be included in an API error.")


def local_timeout(*, video_path: Path, output_dir: Path) -> dict:
    raise TimeoutError("Private local processing diagnostics.")


def noisy(*, video_path: Path, output_dir: Path) -> dict:
    print("SYNTHETIC_LOCAL_DIAGNOSTIC", flush=True)
    return negative(video_path=video_path, output_dir=output_dir)

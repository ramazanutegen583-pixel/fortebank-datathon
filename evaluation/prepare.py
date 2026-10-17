"""Create reproducible development and holdout manifests from local labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import re

from evaluation.labels import load_label_rows

ROOT = Path(__file__).resolve().parents[1]


def parse_timecode(value) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if re.fullmatch(r"\d+(?::\d+){1,2}(?:\.\d+)?", text):
        parts = [float(part) for part in text.split(":")]
        return sum(part * 60 ** i for i, part in enumerate(reversed(parts)))
    minutes = re.search(r"(\d+)\s*(?:min|m|\u043c)", text)
    seconds = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:sec|s|\u0441)", text)
    if minutes or seconds:
        return (int(minutes[1]) * 60 if minutes else 0) + (float(seconds[1].replace(",", ".")) if seconds else 0)
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    raise ValueError("Unrecognized local timestamp format.")


def prepare(labels_path: Path, video_dir: Path, output: Path, seed: int = 17) -> dict:
    rows = load_label_rows(labels_path)
    paths = list(video_dir.rglob("*.mov"))
    files = {path.stem: path.resolve() for path in paths}
    if len(files) != len(paths):
        raise ValueError("Video identifiers must be unique within the training archive.")
    groups = {False: [], True: []}
    seen = set()
    for row in rows[1:]:
        cells = {cell["cell"][0]: cell["value"] for cell in row}
        stem = str(cells["A"]).strip()
        if stem in seen:
            raise ValueError("A training clip has duplicate label rows.")
        seen.add(stem)
        if stem not in files:
            raise ValueError("A labeled video is missing from local training storage.")
        raw_label = str(cells["C"]).strip().lower()
        negative_labels = {"0", "negative", "no_violation", "\u0431\u0435\u0437 \u043d\u0430\u0440\u0443\u0448\u0435\u043d\u0438\u044f"}
        positive_labels = {"1", "positive", "violation", "\u043d\u0430\u0440\u0443\u0448\u0435\u043d\u0438\u0435"}
        if raw_label not in negative_labels | positive_labels:
            raise ValueError("Unrecognized local binary label.")
        positive = raw_label in positive_labels
        timestamp = parse_timecode(cells.get("B"))
        groups[positive].append({"video": str(files[stem]), "positive": positive,
                                 "timecodes": [timestamp] if positive and timestamp is not None else []})
    randomizer = random.Random(seed)
    if any(len(group) < 2 for group in groups.values()):
        raise ValueError("At least two literal labels per class are required for a split.")
    manifest = {"version": 1, "purpose": "organizer_training_only", "seed": seed,
                "grouping": "clip; subject/session grouping unavailable", "development": [], "holdout": []}
    for group in groups.values():
        randomizer.shuffle(group)
        boundary = int(len(group) * 0.7)
        manifest["development"].extend(group[:boundary])
        manifest["holdout"].extend(group[boundary:])
    for split in ("development", "holdout"):
        randomizer.shuffle(manifest[split])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    return {split: {"count": len(manifest[split]), "positive": sum(item["positive"] for item in manifest[split])}
            for split in ("development", "holdout")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--videos", type=Path, default=ROOT / "local_data" / "training")
    parser.add_argument("--output", type=Path, default=ROOT / "local_data" / "manifest.json")
    arguments = parser.parse_args()
    if arguments.labels is None:
        candidates = list(arguments.videos.rglob("open_labels.xlsx"))
        if len(candidates) != 1:
            parser.error("Provide --labels with the local organizer training XLSX or extracted JSON.")
        arguments.labels = candidates[0]
    print(json.dumps(prepare(arguments.labels, arguments.videos, arguments.output), indent=2))


if __name__ == "__main__":
    main()

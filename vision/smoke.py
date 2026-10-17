"""Exercise real local weights through the product worker using artificial media."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
import time

import av
from PIL import Image

from server.worker import WorkerRunner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=2, choices=range(2, 146))
    parser.add_argument("--runs", type=int, choices=[1, 2], default=2)
    arguments = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "runtime" / "vision-smoke"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "artificial.mov"
    image = Image.new("RGB", (960, 720), (110, 120, 100))
    with av.open(str(path), mode="w", format="mov") as container:
        stream = container.add_stream("mpeg4", rate=12)
        stream.width, stream.height, stream.pix_fmt = 960, 720, "yuv420p"
        for _ in range(arguments.duration * 12):
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    runner = WorkerRunner("vision.pipeline:analyze_video", 8 * 1024 * 1024, output)
    timings = []
    try:
        for index in range(arguments.runs):
            started = time.monotonic()
            result = runner.execute(f"synthetic-{index}", path, output / f"job-{index}", time.time() + 270)
            elapsed = round(time.monotonic() - started, 3)
            if not result["ok"]:
                print(json.dumps({"ok": False, "code": result["code"], "elapsed_seconds": elapsed}))
                raise SystemExit(1)
            timings.append(elapsed)
            assert result["public"]["verdict"] == "no_violation", "Artificial blank media should have no cash event."
        print(json.dumps({"ok": True, "synthetic_only": True, "duration_seconds": arguments.duration,
                          "cold_seconds": timings[0], "warm_seconds": timings[1] if len(timings) > 1 else None}))
    finally:
        runner.close()


if __name__ == "__main__":
    main()

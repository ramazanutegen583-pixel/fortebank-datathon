"""Decode only the video stream and preserve real presentation timestamps."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from collections.abc import Callable

import av
from PIL import Image


@dataclass
class Sample:
    timestamp: float
    image: Image.Image


def open_video(path: Path):
    return av.open(str(path), format="mov", options={
        "protocol_whitelist": "file", "enable_drefs": "0", "use_absolute_path": "0",
    })


def inspect_video(path: Path) -> float:
    with open_video(path) as container:
        if not container.streams.video:
            raise ValueError("Video stream unavailable.")
        stream = container.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration is not None else (
            container.duration / av.time_base if container.duration else 0
        )
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Video duration unavailable.")
        if stream.width * stream.height > 4096 * 4096:
            raise ValueError("Video resolution exceeds the local processing limit.")
        return duration


def plan_windows(duration: float, window: float, overlap: float, limit: int) -> list[tuple[float, float]]:
    windows = []
    start = 0.0
    while start < duration:
        end = min(duration, start + window)
        windows.append((start, end))
        if end >= duration:
            break
        start += window - overlap
    if len(windows) > limit:
        raise ValueError("Video exceeds the configured temporal coverage limit.")
    return windows


def sample_frames(path: Path, targets: list[float], max_pixels: int,
                  check_deadline: Callable[[], None] = lambda: None) -> list[Sample]:
    """Seek to each interval and select the nearest actual decoded frame to each target."""
    if not targets or any(t < 0 or not math.isfinite(t) for t in targets):
        raise ValueError("Invalid sampling targets.")
    targets = sorted(set(targets))
    samples = []
    with open_video(path) as container:
        stream = container.streams.video[0]
        origin = float((stream.start_time or 0) * stream.time_base)
        offset = int((targets[0] + origin) / stream.time_base)
        container.seek(offset, stream=stream, backward=True)
        previous = None
        index = 0
        for frame in container.decode(stream):
            check_deadline()
            if frame.pts is None:
                continue
            timestamp = max(0.0, float(frame.pts * frame.time_base) - origin)
            if previous is not None and timestamp < previous[0]:
                raise ValueError("Nonmonotonic video timestamps.")
            while index < len(targets) and timestamp >= targets[index]:
                chosen = (timestamp, frame)
                if previous is not None and abs(previous[0] - targets[index]) < abs(timestamp - targets[index]):
                    chosen = previous
                image = chosen[1].to_image().convert("RGB")
                scale = min(1.0, math.sqrt(max_pixels / (image.width * image.height)))
                if scale < 1:
                    image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
                samples.append(Sample(chosen[0], image))
                index += 1
            previous = (timestamp, frame)
            if index == len(targets):
                break
        # The final target may lie after the last frame but before container duration.
        while index < len(targets) and previous is not None:
            if targets[index] - previous[0] > 0.25:
                raise ValueError("Incomplete video coverage.")
            image = previous[1].to_image().convert("RGB")
            scale = min(1.0, math.sqrt(max_pixels / (image.width * image.height)))
            image.thumbnail((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
            samples.append(Sample(previous[0], image))
            index += 1
    if len(samples) != len(targets):
        raise ValueError("Required frames could not be decoded.")
    return samples


def window_targets(start: float, end: float, count: int) -> list[float]:
    last = max(start, end - min(0.1, (end - start) / 4))
    return [start + (last - start) * i / (count - 1) for i in range(count)]

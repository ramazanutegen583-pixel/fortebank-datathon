"""Resumable byte-range downloads for large public setup artifacts."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import shutil
import time
import urllib.request


def download(url: str, target: Path, expected_size: int | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and (expected_size is None or target.stat().st_size == expected_size):
        return
    request = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        url = response.geturl()
        if expected_size is None:
            content_range = response.headers.get("Content-Range", "")
            if response.status != 206 or "/" not in content_range:
                with target.with_suffix(target.suffix + ".partial").open("wb") as output:
                    shutil.copyfileobj(response, output, length=64 * 1024)
                target.with_suffix(target.suffix + ".partial").replace(target)
                return
            expected_size = int(content_range.split("/")[-1])
    chunk_bytes = 2 * 1024 * 1024
    parts = target.with_name(target.name + ".parts")
    parts.mkdir(exist_ok=True)

    def fetch(index: int):
        start, end = index * chunk_bytes, min(expected_size, (index + 1) * chunk_bytes) - 1
        part = parts / f"{index:06d}"
        if part.exists() and part.stat().st_size == end - start + 1:
            return
        for attempt in range(4):
            try:
                request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(request, timeout=40) as response:
                    expected_range = f"bytes {start}-{end}/{expected_size}"
                    if response.status != 206 or response.headers.get("Content-Range") != expected_range:
                        raise RuntimeError("Server did not honor the requested download range.")
                    with part.open("wb") as output:
                        shutil.copyfileobj(response, output, length=64 * 1024)
                if part.stat().st_size != end - start + 1:
                    raise RuntimeError("Incomplete download range.")
                return
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)

    count = (expected_size + chunk_bytes - 1) // chunk_bytes
    workers = min(64, max(1, int(os.environ.get("DOWNLOAD_WORKERS", "16"))))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(fetch, range(count)):
            pass
    partial = target.with_name(target.name + ".partial")
    with partial.open("wb") as output:
        for index in range(count):
            with (parts / f"{index:06d}").open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    if partial.stat().st_size != expected_size:
        raise RuntimeError("Incomplete artifact assembly.")
    partial.replace(target)
    for index in range(count):
        try:
            (parts / f"{index:06d}").unlink()
        except OSError:
            pass
    try:
        parts.rmdir()
    except OSError:
        pass

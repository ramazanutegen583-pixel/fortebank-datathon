"""Translate validated local analysis into the unchanged public API contract."""

from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image

from server.config import ROOT


class ProcessingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ResultAdapter:
    def __init__(self, max_evidence_bytes: int):
        self.max_evidence_bytes = max_evidence_bytes
        self.internal = Draft202012Validator(
            json.loads((ROOT / "contracts/analysis.schema.json").read_text(encoding="utf-8")),
            format_checker=FormatChecker(),
        )
        self.public = Draft202012Validator(
            json.loads((ROOT / "contracts/api.schema.json").read_text(encoding="utf-8")))

    def convert(self, job_id: str, result: dict, output_dir: Path, duration: float) -> tuple[dict, dict]:
        try:
            json.dumps(result, allow_nan=False)
            self.internal.validate(result)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("invalid duration")
            root = output_dir.resolve(strict=True)
            violations = []
            sources_by_event = []
            for event in result["violations"]:
                if event["timecode_sec"] > duration:
                    raise ValueError("event timestamp exceeds video duration")
                frames = []
                for frame in event["evidence_frames"]:
                    if frame["timestamp_sec"] > duration:
                        raise ValueError("frame timestamp exceeds video duration")
                    relative = frame["image_path"]
                    if (PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).drive
                            or ".." in PurePosixPath(relative).parts or "\\" in relative):
                        raise ValueError("invalid evidence path")
                    path = (root / relative).resolve(strict=True)
                    if not path.is_relative_to(root) or not path.is_file():
                        raise ValueError("evidence path escapes output directory")
                    if path.stat().st_size > self.max_evidence_bytes:
                        raise ValueError("evidence exceeds size limit")
                    raw = path.read_bytes()
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.format != "JPEG" or image.width * image.height > 25_000_000:
                            raise ValueError("invalid JPEG dimensions or format")
                        image.verify()
                    with Image.open(io.BytesIO(raw)) as image:
                        image.load()
                    frames.append({"timestamp_sec": frame["timestamp_sec"],
                                   "image_base64": base64.b64encode(raw).decode("ascii")})
                references = []
                for source in event["sources"]:
                    parsed = urlsplit(source["url"])
                    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
                        raise ValueError("invalid public source URL")
                    section = f"; section: {source['section']}" if source["section"] else ""
                    references.append(f"Source: {source['document_title']}{section}\n{source['url']}")
                violations.append({"type": event["type"], "timecode_sec": event["timecode_sec"],
                                   "description": event["description"] + "\n\n" + "\n\n".join(references),
                                   "evidence_frames": frames})
                sources_by_event.append(event["sources"])
            public = {"job_id": job_id, "status": "done", "verdict": result["verdict"], "violations": violations}
            self.public.validate(public)
            return public, {"video_duration_sec": duration, "sources": sources_by_event}
        except Exception as exc:
            raise ProcessingError("INVALID_ANALYSIS_RESULT", "The analyzer returned an invalid result or evidence file.") from exc

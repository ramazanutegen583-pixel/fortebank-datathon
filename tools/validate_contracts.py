"""Validate shared schemas and synthetic fixtures; never inspect competition data."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    contracts = root / "contracts"
    schemas = {
        name: json.loads((contracts / f"{name}.schema.json").read_text(encoding="utf-8"))
        for name in ("api", "analysis")
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)

    count = 0
    for path in sorted((contracts / "examples").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        schema = schemas["analysis" if path.name.startswith("analysis-") else "api"]
        if path.name == "submission.json":
            schema = {
                "$schema": schema["$schema"],
                "$defs": schema["$defs"],
                "$ref": "#/$defs/submission",
            }
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(data)
        if path.name == "done-positive.json":
            for event in data["violations"]:
                for frame in event["evidence_frames"]:
                    raw = base64.b64decode(frame["image_base64"], validate=True)
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.format != "JPEG":
                            raise ValueError("Synthetic evidence must be JPEG")
                        image.verify()
        count += 1
    print(f"OK: 2 schemas, {count} synthetic fixtures; JPEG verified. No competition data read.")


if __name__ == "__main__":
    main()

"""Load verified public references independently of generated observations."""

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "rules" / "catalog.json"


def load_catalog() -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    ids = [rule["id"] for rule in catalog["rules"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("Invalid rule catalog.")
    return catalog


def source_for(catalog: dict, rule: dict) -> dict:
    return {
        "document_title": catalog["document_title"],
        "section": rule["section"],
        "url": catalog["url"],
        "rationale": rule["summary"] + " " + catalog["edition_note"],
    }

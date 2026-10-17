import json

import pytest

JsonSchemaParser = pytest.importorskip("lmformatenforcer").JsonSchemaParser

from vision.formatting import candidate_schema
from vision.rules import load_catalog


def grammar_accepts(value):
    rules = {rule["id"]: rule for rule in load_catalog()["rules"]}
    parser = JsonSchemaParser(candidate_schema(rules, 8))
    for character in json.dumps(value, separators=(",", ":")):
        if character not in parser.get_allowed_characters():
            return False
        parser = parser.add_character(character)
    return parser.can_end()


def sample_event():
    return {"rule_id": "cashier_left_during_service", "frame_index": 3, "confidence": 0.9,
            "conditions_met": [True, True], "observation": "Synthetic visible action."}


def test_generation_can_return_empty_or_populated_events():
    assert grammar_accepts({"scene_supported": False, "events": []})
    assert grammar_accepts({"scene_supported": True, "events": [sample_event()]})


@pytest.mark.parametrize("mutation", [
    lambda event: event.update(rule_id="invented"),
    lambda event: event.update(frame_index=8),
    lambda event: event.update(conditions_met=[True, True, True]),
    lambda event: event.update(observation="x" * 101),
])
def test_generation_cannot_emit_invalid_evidence_structure(mutation):
    event = sample_event()
    mutation(event)
    assert not grammar_accepts({"scene_supported": True, "events": [event]})

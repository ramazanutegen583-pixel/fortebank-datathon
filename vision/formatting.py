"""Constrain local generation to the candidate schema without supplying findings."""


def candidate_schema(rules: dict, frame_count: int) -> dict:
    event = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "rule_id": {"type": "string", "enum": list(rules)},
            "frame_index": {"type": "integer", "enum": list(range(frame_count))},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "conditions_met": {"type": "array", "items": {"type": "boolean"},
                               "minItems": 2, "maxItems": 2},
            "observation": {"type": "string", "minLength": 5, "maxLength": 100},
        },
        "required": ["rule_id", "frame_index", "confidence", "conditions_met", "observation"],
    }
    if not rules or frame_count < 1 or any(len(rule["conditions"]) != 2 for rule in rules.values()):
        raise ValueError("Unsupported candidate generation schema.")
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "scene_supported": {"type": "boolean"},
            "events": {"type": "array", "items": event, "maxItems": 2},
        },
        "required": ["scene_supported", "events"],
    }

import pytest

from evaluation.metrics import summarize
from evaluation.prepare import parse_timecode


def test_failures_are_not_correct_negative_predictions():
    records = [
        {"positive": True, "timecodes": [8], "status": "done", "verdict": "violation",
         "violations": [{"timecode_sec": 10}], "elapsed_seconds": 2},
        {"positive": False, "status": "done", "verdict": "violation", "elapsed_seconds": 3},
        {"positive": False, "status": "failed", "error_code": "TIMEOUT", "elapsed_seconds": 270},
        {"positive": True, "status": "failed", "error_code": "ANALYSIS_FAILED", "elapsed_seconds": 10},
    ]
    report = summarize(records)
    assert report["accuracy_all_inputs"] == 0.25
    assert report["completion_rate"] == 0.5
    assert report["precision"] == report["recall"] == report["f1"] == 0.5
    assert report["localized_within_tolerance"] == 1
    assert report["runtime_p95_seconds"] == 270


@pytest.mark.parametrize("value,expected", [("1:08", 68), ("01:01:08", 3668), ("8 sec", 8),
                                            ("1 min 8 sec", 68), (None, None), (9, 9)])
def test_timecode_parsing(value, expected):
    assert parse_timecode(value) == expected

import json
from pathlib import Path
import shutil
import socket
from types import SimpleNamespace

from PIL import Image
import pytest

from server.validation import ResultAdapter
from vision import pipeline
from vision.backend import InvalidModelOutput, parse_events
from vision.config import VisionSettings
from vision.offline import network_disabled
from vision.rules import load_catalog
from vision.video import inspect_video, plan_windows, sample_frames


def candidate(rule_id="cashier_left_during_service", index=3, confidence=0.95):
    return {"rule_id": rule_id, "frame_index": index, "confidence": confidence,
            "conditions_met": [True, True], "observation": "Synthetic visible action for an integration check."}


class Backend:
    def __init__(self, confirm=True, broken=False):
        self.confirm, self.broken, self.calls = confirm, broken, []

    def analyze(self, samples, rules, check_deadline, verification=False):
        self.calls.append((samples, verification))
        if self.broken:
            raise InvalidModelOutput("Synthetic malformed output.")
        events = [candidate()] if not verification or self.confirm else []
        return events, json.dumps({"events": events})


def test_real_pts_and_pixel_budget(synthetic_video):
    assert inspect_video(synthetic_video) == pytest.approx(3)
    frames = sample_frames(synthetic_video, [0.04, 0.42, 1.69, 2.9], 4096)
    assert [frame.timestamp for frame in frames] == pytest.approx([0, 0.4, 1.7, 2.9])
    assert all(frame.image.width * frame.image.height <= 4200 for frame in frames)
    assert frames[0].image.getpixel((0, 0))[0] < frames[-1].image.getpixel((0, 0))[0]


def test_temporal_coverage_and_limit():
    windows = plan_windows(145, 18, 3, 12)
    assert windows[0][0] == 0 and windows[-1][1] == 145
    assert all(left[1] >= right[0] for left, right in zip(windows, windows[1:]))
    with pytest.raises(ValueError):
        plan_windows(250, 18, 3, 12)


def test_pipeline_contract_and_evidence(synthetic_video, tmp_path, monkeypatch):
    backend = Backend()
    monkeypatch.setattr(pipeline, "get_backend", lambda settings: backend)
    output = tmp_path / "output"
    result = pipeline.analyze_video(synthetic_video, output)
    assert result["verdict"] == "violation"
    assert [verification for samples, verification in backend.calls] == [False, True]
    public, details = ResultAdapter(8 * 1024 * 1024).convert("synthetic", result, output, 3)
    assert public["status"] == "done"
    assert len(public["violations"][0]["evidence_frames"]) == 3
    event = result["violations"][0]
    sample = backend.calls[-1][0][3]
    assert event["timecode_sec"] == sample.timestamp
    frame = event["evidence_frames"][1]
    with Image.open(output / frame["image_path"]) as image:
        assert image.format == "JPEG" and image.size == sample.image.size
    assert details["sources"][0][0]["section"] == "Chapter 2, paragraph 22"


def test_rejected_candidate_is_not_reported(synthetic_video, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "get_backend", lambda settings: Backend(confirm=False))
    assert pipeline.analyze_video(synthetic_video, tmp_path / "out") == {"verdict": "no_violation", "violations": []}


def test_sparse_frames_cannot_establish_absence_of_counting(synthetic_video, tmp_path, monkeypatch):
    class UnsupportedAbsence:
        def analyze(self, samples, rules, check_deadline, verification=False):
            assert not verification
            events = [candidate(rule_id="cash_received_without_count")]
            return events, json.dumps({"events": events})

    monkeypatch.setattr(pipeline, "get_backend", lambda settings: UnsupportedAbsence())
    assert pipeline.analyze_video(synthetic_video, tmp_path / "out") == {"verdict": "no_violation", "violations": []}


def test_malformed_output_never_becomes_negative(synthetic_video, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "get_backend", lambda settings: Backend(broken=True))
    with pytest.raises(InvalidModelOutput):
        pipeline.analyze_video(synthetic_video, tmp_path / "out")


def test_complete_scan_required(synthetic_video, tmp_path, monkeypatch):
    settings = VisionSettings(budget_seconds=0.1)
    ticks = iter(range(100))
    monkeypatch.setattr(pipeline, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    monkeypatch.setattr(pipeline.VisionSettings, "from_env", lambda: settings)
    monkeypatch.setattr(pipeline, "get_backend", lambda settings: Backend())
    with pytest.raises(TimeoutError):
        pipeline.analyze_video(synthetic_video, tmp_path / "out")


def test_video_filename_does_not_change_prediction(synthetic_video, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "get_backend", lambda settings: Backend())
    renamed = tmp_path / "unrelated-name.mov"
    shutil.copyfile(synthetic_video, renamed)
    first = pipeline.analyze_video(synthetic_video, tmp_path / "first")
    second = pipeline.analyze_video(renamed, tmp_path / "second")
    assert first == second


def test_no_network_during_processing():
    with network_disabled():
        with pytest.raises(RuntimeError, match="Network access"):
            socket.create_connection(("example.invalid", 443))
        with pytest.raises(RuntimeError, match="Network access"):
            socket.getaddrinfo("example.invalid", 443)
        with socket.socket() as connection:
            with pytest.raises(RuntimeError, match="Network access"):
                connection.connect(("127.0.0.1", 1234))


@pytest.mark.parametrize("mutation", [
    lambda e: e.update(rule_id="unknown"),
    lambda e: e.update(frame_index=8),
    lambda e: e.update(frame_index=True),
    lambda e: e.update(confidence=float("nan")),
    lambda e: e.update(conditions_met=[True]),
    lambda e: e.update(observation=""),
    lambda e: e.update(source="invented"),
])
def test_invalid_model_candidates_fail(mutation):
    event = candidate()
    mutation(event)
    rules = {r["id"]: r for r in load_catalog()["rules"]}
    with pytest.raises(InvalidModelOutput):
        parse_events(json.dumps({"scene_supported": True, "events": [event]}), rules, 8)


def test_unsupported_visual_conditions_omitted():
    event = candidate()
    event["conditions_met"] = [True, False]
    rules = {r["id"]: r for r in load_catalog()["rules"]}
    assert parse_events(json.dumps({"scene_supported": True, "events": [event]}), rules, 8) == []


def test_unsupported_scene_cannot_include_events():
    rules = {r["id"]: r for r in load_catalog()["rules"]}
    assert parse_events('{"scene_supported":false,"events":[]}', rules, 8) == []
    with pytest.raises(InvalidModelOutput):
        parse_events(json.dumps({"scene_supported": False, "events": [candidate()]}), rules, 8)


def test_merge_preserves_separate_categories_and_distant_events():
    events = [dict(rule_id="one", timestamp=2, confidence=0.8),
              dict(rule_id="one", timestamp=6, confidence=0.9),
              dict(rule_id="two", timestamp=6, confidence=0.9),
              dict(rule_id="one", timestamp=25, confidence=0.9)]
    result = pipeline.merge_candidates(events, 8)
    assert [(event["rule_id"], event["timestamp"]) for event in result] == [("one", 6), ("two", 6), ("one", 25)]

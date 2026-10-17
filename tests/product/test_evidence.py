import pytest

from server.validation import ProcessingError, ResultAdapter
from tests.product.fixtures import positive


@pytest.mark.parametrize("change", ["traversal", "absolute", "windows_absolute", "late_event", "late_frame", "nan", "bad_url", "missing_sources", "not_jpeg", "too_large"])
def test_invalid_evidence_is_rejected_without_leaking_content(tmp_path, change):
    root = tmp_path / "output"
    result = positive(video_path=tmp_path / "unused.mov", output_dir=root)
    event = result["violations"][0]
    if change == "traversal": event["evidence_frames"][0]["image_path"] = "../private.jpg"
    elif change == "absolute": event["evidence_frames"][0]["image_path"] = "/private.jpg"
    elif change == "windows_absolute": event["evidence_frames"][0]["image_path"] = "C:/private.jpg"
    elif change == "late_event": event["timecode_sec"] = 4
    elif change == "late_frame": event["evidence_frames"][0]["timestamp_sec"] = 4
    elif change == "nan": event["timecode_sec"] = float("nan")
    elif change == "bad_url": event["sources"][0]["url"] = "javascript:alert(1)"
    elif change == "missing_sources": event["sources"] = []
    elif change == "not_jpeg": (root / "frame.jpg").write_bytes(b"not an image")
    adapter = ResultAdapter(1 if change == "too_large" else 8 * 1024 * 1024)
    with pytest.raises(ProcessingError) as error:
        adapter.convert("synthetic", result, root, 3)
    assert error.value.code == "INVALID_ANALYSIS_RESULT"
    assert "private" not in error.value.message


def test_symbolic_link_escape_is_rejected(tmp_path):
    root = tmp_path / "output"
    result = positive(video_path=tmp_path / "unused.mov", output_dir=root)
    external = tmp_path / "outside.jpg"
    external.write_bytes((root / "frame.jpg").read_bytes())
    link = root / "link.jpg"
    try:
        link.symlink_to(external)
    except OSError:
        pytest.skip("Creating a symlink requires an OS privilege unavailable to this process")
    result["violations"][0]["evidence_frames"][0]["image_path"] = "link.jpg"
    with pytest.raises(ProcessingError):
        ResultAdapter(8 * 1024 * 1024).convert("synthetic", result, root, 3)

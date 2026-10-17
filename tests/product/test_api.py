import base64
import io
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server.app import create_app
from server.config import Settings
from server.store import JobStore

KEY = "synthetic-test-access-key"
HEADERS = {"X-API-Key": KEY}


def settings(tmp_path, analyzer="negative", **kwargs):
    return Settings(api_key=KEY, runtime_dir=tmp_path / "service", test_mode=True,
                    analyzer=f"tests.product.fixtures:{analyzer}", job_timeout_seconds=20, **kwargs)


def submit(client, video):
    with video.open("rb") as file:
        response = client.post("/api/v1/analyze", headers=HEADERS,
                               files={"file": ("synthetic.mov", file, "video/quicktime")})
    assert response.status_code == 202
    assert set(response.json()) == {"job_id"}
    return response.json()["job_id"]


def wait(client, job_id, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS)
        assert response.status_code == 200
        if response.json()["status"] != "processing":
            return response.json()
        time.sleep(0.04)
    pytest.fail("Synthetic job did not reach a terminal state")


def test_authentication_precedes_upload_parsing(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        for headers in ({}, {"X-API-Key": "wrong"}):
            response = client.post("/api/v1/analyze", headers=headers, content=b"invalid multipart")
            assert response.status_code == 401
        assert client.get("/health").json()["pending_jobs"] == 0
        assert client.get("/ui/jobs/unknown").status_code == 401


def test_negative_result_and_persistence(tmp_path, synthetic_video):
    config = settings(tmp_path)
    with TestClient(create_app(config)) as client:
        job_id = submit(client, synthetic_video)
        result = wait(client, job_id)
        assert result == {"job_id": job_id, "status": "done", "verdict": "no_violation", "violations": []}
        assert client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS).json() == result
        assert client.get(f"/ui/jobs/{job_id}", headers=HEADERS).json()["details"]["video_duration_sec"] == pytest.approx(3)
    with TestClient(create_app(config)) as client:
        assert client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS).json() == result


def test_positive_evidence_and_structured_sources(tmp_path, synthetic_video):
    with TestClient(create_app(settings(tmp_path, "positive"))) as client:
        job_id = submit(client, synthetic_video)
        result = wait(client, job_id)
        assert result["verdict"] == "violation"
        event = result["violations"][0]
        assert set(event) == {"type", "timecode_sec", "description", "evidence_frames"}
        assert "Source: Synthetic rule reference; section: Example section" in event["description"]
        raw = base64.b64decode(event["evidence_frames"][0]["image_base64"], validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            assert image.format == "JPEG"
        details = client.get(f"/ui/jobs/{job_id}", headers=HEADERS).json()
        assert details["details"]["sources"][0][0]["document_title"] == "Synthetic rule reference"
        assert details["elapsed_sec"] > 0
        assert "image_path" not in str(result)


@pytest.mark.parametrize(("analyzer", "code"), [("broken", "ANALYSIS_FAILED"), ("invalid", "INVALID_ANALYSIS_RESULT"), ("missing_weights", "MODEL_UNAVAILABLE")])
def test_processing_failures_are_not_negative_verdicts(tmp_path, synthetic_video, analyzer, code):
    with TestClient(create_app(settings(tmp_path, analyzer))) as client:
        result = wait(client, submit(client, synthetic_video))
        assert result["status"] == "failed"
        assert result["error"]["code"] == code
        assert "verdict" not in result and "violations" not in result
        assert "Private" not in str(result)


def test_missing_analyzer_and_corrupt_video(tmp_path, synthetic_video):
    config = replace(settings(tmp_path), analyzer="tests.product.not_installed:analyze_video")
    with TestClient(create_app(config)) as client:
        assert wait(client, submit(client, synthetic_video))["error"]["code"] == "MODEL_UNAVAILABLE"
        response = client.post("/api/v1/analyze", headers=HEADERS, files={"file": ("corrupt.mov", b"not a video")})
        assert response.status_code == 202
        assert wait(client, response.json()["job_id"])["error"]["code"] == "INVALID_VIDEO"


@pytest.mark.parametrize(("files", "expected"), [
    ({"other": ("a.mov", b"content")}, 400),
    ({"file": ("a.mp4", b"content")}, 415),
    ({"file": ("a.mov", b"")}, 400),
    ({"file": ("a.mov", b"x" * 129)}, 413),
])
def test_upload_rejections(tmp_path, files, expected):
    with TestClient(create_app(settings(tmp_path, max_upload_bytes=128))) as client:
        response = client.post("/api/v1/analyze", headers=HEADERS, files=files)
        assert response.status_code == expected
        assert client.get("/health").json()["pending_jobs"] == 0
        assert list((tmp_path / "service/uploads").glob("*.mov")) == []


def test_request_errors_and_offline_assets(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.get("/api/v1/jobs/unknown", headers=HEADERS).status_code == 404
        assert client.post("/api/v1/analyze", headers=HEADERS, json={}).status_code == 400
        assert client.post("/api/v1/analyze", headers={**HEADERS, "Content-Type": "multipart/form-data; boundary=x", "Content-Length": "-3"}).status_code == 400
        for path in ["/", "/api-reference", "/assets/styles.css", "/assets/app.js", "/assets/mark.svg"]:
            response = client.get(path)
            assert response.status_code == 200
            assert "no-store" in response.headers["cache-control"]
        spec = client.get("/openapi.json").json()
        assert spec["paths"]["/api/v1/analyze"]["post"]["security"] == [{"TeamKey": []}]
        assert "multipart/form-data" in spec["paths"]["/api/v1/analyze"]["post"]["requestBody"]["content"]


def test_chunked_body_size_limit(tmp_path):
    def body():
        yield b'--test-boundary\r\nContent-Disposition: form-data; name="file"; filename="large.mov"\r\n\r\n'
        for _ in range(20):
            yield b"x" * 65536
        yield b"\r\n--test-boundary--\r\n"
    with TestClient(create_app(settings(tmp_path, max_upload_bytes=128))) as client:
        response = client.post("/api/v1/analyze", headers={**HEADERS, "Content-Type": "multipart/form-data; boundary=test-boundary"}, content=body())
        assert response.status_code == 413
        assert client.get("/health").json()["pending_jobs"] == 0


def test_deadline_includes_queue_and_service_remains_responsive(tmp_path, synthetic_video):
    config = replace(settings(tmp_path, "slow", max_pending_jobs=2), job_timeout_seconds=3)
    with TestClient(create_app(config)) as client:
        first = submit(client, synthetic_video)
        second = submit(client, synthetic_video)
        with synthetic_video.open("rb") as file:
            full = client.post("/api/v1/analyze", headers=HEADERS, files={"file": ("synthetic.mov", file)})
        assert full.status_code == 429 and full.headers["retry-after"] == "5"
        assert client.get("/health").status_code == 200
        assert wait(client, first)["error"]["code"] == "TIMEOUT"
        assert wait(client, second)["error"]["code"] == "TIMEOUT"
        time.sleep(0.3)
        assert client.get(f"/api/v1/jobs/{first}", headers=HEADERS).json()["error"]["code"] == "TIMEOUT"


def test_restart_marks_unfinished_jobs_failed(tmp_path):
    runtime = tmp_path / "service"
    runtime.mkdir()
    store = JobStore(runtime / "jobs.sqlite3")
    store.create("interrupted", time.time(), time.time() + 200)
    with TestClient(create_app(settings(tmp_path))) as client:
        result = client.get("/api/v1/jobs/interrupted", headers=HEADERS).json()
        assert result["status"] == "failed" and result["error"]["code"] == "SERVICE_RESTARTED"


def test_substitute_analyzer_requires_explicit_test_mode(tmp_path):
    with pytest.raises(ValueError, match="APP_TEST_MODE"):
        Settings(api_key=KEY, runtime_dir=tmp_path, analyzer="tests.product.fixtures:negative")


def test_runtime_directory_rejects_duplicate_instances(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config)):
        with pytest.raises(RuntimeError, match="already in use"):
            with TestClient(create_app(config)):
                pass


def test_analyzer_diagnostics_are_written_only_to_local_log(tmp_path, synthetic_video):
    config = settings(tmp_path, "noisy")
    with TestClient(create_app(config)) as client:
        result = wait(client, submit(client, synthetic_video))
        assert result["status"] == "done"
        assert "SYNTHETIC_LOCAL_DIAGNOSTIC" not in str(result)
        assert "SYNTHETIC_LOCAL_DIAGNOSTIC" in (config.runtime_dir / "worker.log").read_text()

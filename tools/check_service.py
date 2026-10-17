"""Check the full local HTTP workflow with installed weights and artificial media."""

from pathlib import Path
import argparse
from contextlib import ExitStack
import json
import os
import secrets
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from fastapi.testclient import TestClient
    from server.app import create_app
    from server.config import Settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Check an already running loopback HTTP service instead of ASGI TestClient.")
    arguments = parser.parse_args()
    if arguments.url:
        address = urlparse(arguments.url)
        if address.scheme != "http" or address.hostname not in {"127.0.0.1", "localhost"} or address.username:
            parser.error("Use the local HTTP service URL without embedded credentials.")
    video = ROOT / "runtime" / "vision-smoke" / "artificial.mov"
    if not video.exists():
        raise SystemExit("Run python -m vision.smoke to create the artificial input first.")
    with ExitStack() as stack:
        if arguments.url:
            import httpx
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env", override=False)
            key = os.environ["APP_API_KEY"]
            client = stack.enter_context(httpx.Client(base_url=arguments.url, timeout=120))
        else:
            key = secrets.token_urlsafe(32)
            settings = Settings(api_key=key, runtime_dir=ROOT / "runtime" / "service-smoke")
            client = stack.enter_context(TestClient(create_app(settings)))
        started = time.monotonic()
        with video.open("rb") as stream:
            submission = client.post("/api/v1/analyze", headers={"X-API-Key": key},
                                     files={"file": ("artificial.mov", stream, "video/quicktime")})
        assert submission.status_code == 202
        job = submission.json()["job_id"]
        while time.monotonic() - started < 280:
            response = client.get(f"/api/v1/jobs/{job}", headers={"X-API-Key": key})
            assert response.status_code == 200
            result = response.json()
            if result["status"] != "processing":
                break
            time.sleep(0.25)
        assert result["status"] == "done", "The real local analyzer did not complete successfully."
        assert result["verdict"] == "no_violation"
        print(json.dumps({"ok": True, "synthetic_only": True,
                          "transport": "loopback_http" if arguments.url else "asgi_testclient",
                          "http_end_to_end_seconds": round(time.monotonic() - started, 3)}))


if __name__ == "__main__":
    main()

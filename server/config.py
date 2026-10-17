"""Environment-based service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANALYZER = "vision.pipeline:analyze_video"


@dataclass(frozen=True)
class Settings:
    api_key: str
    runtime_dir: Path = ROOT / "runtime" / "service"
    job_timeout_seconds: float = 270
    upload_timeout_seconds: float = 120
    max_upload_bytes: int = 100 * 1024 * 1024
    max_pending_jobs: int = 8
    max_evidence_bytes: int = 8 * 1024 * 1024
    analyzer: str = DEFAULT_ANALYZER
    test_mode: bool = False

    def __post_init__(self) -> None:
        if len(self.api_key) < 16 or self.api_key.startswith("replace-"):
            raise ValueError("APP_API_KEY must be a private key of at least 16 characters.")
        if not 0 < self.job_timeout_seconds < 300:
            raise ValueError("APP_JOB_TIMEOUT_SECONDS must be greater than 0 and below 300.")
        if self.upload_timeout_seconds <= 0 or self.max_upload_bytes <= 0:
            raise ValueError("Upload limits must be positive.")
        if self.max_pending_jobs < 1 or self.max_evidence_bytes < 1:
            raise ValueError("Queue and evidence limits must be positive.")
        if self.analyzer != DEFAULT_ANALYZER and not self.test_mode:
            raise ValueError("A substitute analyzer requires APP_TEST_MODE=1.")

    @classmethod
    def from_env(cls) -> "Settings":
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
        return cls(
            api_key=os.environ.get("APP_API_KEY", ""),
            runtime_dir=Path(os.environ.get("APP_RUNTIME_DIR", str(ROOT / "runtime" / "service"))).resolve(),
            job_timeout_seconds=float(os.environ.get("APP_JOB_TIMEOUT_SECONDS", "270")),
            upload_timeout_seconds=float(os.environ.get("APP_UPLOAD_TIMEOUT_SECONDS", "120")),
            max_upload_bytes=int(os.environ.get("APP_MAX_UPLOAD_MB", "100")) * 1024 * 1024,
            max_pending_jobs=int(os.environ.get("APP_MAX_PENDING_JOBS", "8")),
            max_evidence_bytes=int(os.environ.get("APP_MAX_EVIDENCE_MB", "8")) * 1024 * 1024,
            analyzer=os.environ.get("APP_ANALYZER", DEFAULT_ANALYZER),
            test_mode=os.environ.get("APP_TEST_MODE", "0") == "1",
        )

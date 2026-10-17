# Deployment

The service runs one HTTP process and one isolated processing worker. Serve the
static interface and API from the same origin. Use Python 3.12 or later.
Native HTTP telemetry and automatic telemetry export are explicitly disabled.

## Local run

From the repository root:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe tools/init_env.py
.venv/Scripts/python.exe -m server
```

On Linux or macOS replace .venv/Scripts/python.exe with .venv/bin/python.
Open http://127.0.0.1:8000. Read the generated APP_API_KEY from .env locally and
enter it in the interface's Access key field. The browser keeps it only in memory.

Do not run multiple server instances against the same runtime directory. A local
file lock rejects this configuration. A single processing worker reuses the
imported analyzer between jobs; a timed-out worker is terminated and recreated.
JPEG validation and public-response preparation run in that process so the
deadline covers the processing path. SQLite preserves terminal results across
restarts; interrupted jobs become failed with SERVICE_RESTARTED.

## Analyzer integration

Provide vision/pipeline.py exporting:

```python
def analyze_video(video_path: Path, output_dir: Path) -> dict:
    ...
```

The full signature and result contract are in ../contracts/README.md. Install
the processing dependencies from vision/requirements.txt when supplied. Restart
the service after changing the analyzer or installed dependencies. Missing code
or weights produces MODEL_UNAVAILABLE; no fallback predictions are generated.

Model diagnostics are redirected to runtime/service/worker.log by default.
Detailed results and images stay in the local runtime directory. Do not publish
the runtime directory or expose it through a static file server.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| APP_API_KEY | Required | Private key, at least 16 characters |
| APP_HOST | 127.0.0.1 | Listening interface |
| APP_PORT | 8000 | Listening port |
| APP_RUNTIME_DIR | runtime/service | Local database, uploads, output files, worker diagnostics |
| APP_MAX_UPLOAD_MB | 100 | Maximum video size in MiB; multipart overhead is bounded separately |
| APP_MAX_PENDING_JOBS | 8 | Total accepted uploads/jobs, including running work |
| APP_JOB_TIMEOUT_SECONDS | 270 | Total deadline from upload receipt through result preparation; must be below 300 |
| APP_UPLOAD_TIMEOUT_SECONDS | 120 | Maximum multipart parsing and upload-copy time |
| APP_MAX_EVIDENCE_MB | 8 | Maximum size of each evidence JPEG in MiB |
| APP_TEST_MODE | 0 | Explicit switch for synthetic integration environments |
| APP_ANALYZER | vision.pipeline:analyze_video | Substitute callable allowed only when test mode is enabled |

Memory use and queue capacity must be sized for the actual hardware. The initial
worker is intended for local inference; it is not a sandbox for untrusted Python
code. Retained uploads and results are not deleted automatically. Plan local
storage retention and permitted data disposal before the event ends.

## Container

```text
docker compose --env-file .env -f deploy/compose.yaml up --build -d
```

The image installs product dependencies and vision/requirements.txt if present.
It excludes competition materials, weights, runtime data, and local credentials.
Weights are mounted read-only and job storage uses a persistent local volume.
The container runs as a non-root user and binds the host loopback interface.
GPU support depends on the analyzer and host runtime and is not configured here.

For the jury's public URL, put the service behind a team-controlled HTTPS reverse
proxy or ingress. Bind only the required service port, preserve X-API-Key, allow
uploads above the configured video limit plus multipart overhead, and permit the
configured upload time. API polling is independent of the analysis duration.
Do not place video processing on an external recognition service.

## Operational endpoints

- GET /health: public liveness, limits, pending-job count, test-mode flag, and
  analyzer-module presence. Presence does not establish loaded-weight readiness.
- GET /api-reference: self-contained documentation with no external scripts.
- GET /openapi.json: machine-readable endpoint documentation and public schemas.
- GET /ui/jobs/{job_id}: authenticated timing and structured sources for the UI.
  The jury's two required endpoints and response formats remain unchanged.

Request errors use a sanitized error object. Additional operational statuses are
408 for upload timeout and 429 with Retry-After for a full queue. These do not
create a successful job. A corrupt .mov file is accepted into a job, then becomes
failed/INVALID_VIDEO after local decoding validation.

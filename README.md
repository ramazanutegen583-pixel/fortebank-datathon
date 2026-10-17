# Forte Review

A local cash-operations video review service with a web interface, authenticated
HTTP API, durable jobs, evidence presentation, and a local visual review pipeline.
Without the required local weights, processing fails
explicitly; the service does not generate fallback predictions.
The analyzer is an experimental baseline. Measured detection quality and known
limits are recorded in [validation](docs/validation.md); passing integration
checks does not establish competition readiness.

## Run locally

Requires Python 3.12 or later.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python.exe -m pip install -r vision/requirements.txt
.venv/Scripts/python.exe tools/fetch_weights.py
.venv/Scripts/python.exe tools/init_env.py
.venv/Scripts/python.exe -m server
```

Open http://127.0.0.1:8000. Copy APP_API_KEY from the generated local .env file
into the interface's Access key field. The key is never embedded in the page
or stored in browser storage. On Linux/macOS use .venv/bin/python instead.

The interface, styles, icons, scripts, and API reference are served locally.
No frontend build or external asset service is required.
The commands above target an NVIDIA CUDA GPU. For device options, weight download
alternatives and synthetic verification, see [video processing](docs/video-processing.md).

## Public API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | /api/v1/analyze | Upload one .mov file in the multipart file field; returns job_id with HTTP 202 |
| GET | /api/v1/jobs/{job_id} | Poll processing, done, or failed |

Both endpoints require X-API-Key. Completed results include the binary verdict,
events, timestamps, descriptions, and JPEG evidence. The public response follows
the unchanged shared JSON schema.

The default upload limit is 100 MiB, the total processing budget is 270 seconds,
and capacity is eight accepted uploads/jobs including running work. A single
isolated processing worker reuses the imported analyzer and is terminated on
timeout. SQLite preserves terminal results after restart.

- [API and analyzer contracts](contracts/README.md)
- [Job response schema](contracts/api.schema.json)
- [Analyzer result schema](contracts/analysis.schema.json)
- [Synthetic contract examples](contracts/examples/)

## Enable video processing

The analyzer implements `vision.pipeline.analyze_video` and uses locally installed
Qwen3-VL-2B weights. It scans overlapping windows, verifies candidates, saves real
JPEG evidence, and attaches references from the public rule catalog. Processing
runs with network connections disabled and does not decode audio or identify people.

Install the appropriate PyTorch build, `vision/requirements.txt`, and the pinned
weights before starting analysis. See [video setup and evaluation](docs/video-processing.md)
for commands, local data handling, candidate categories and limitations.
Module presence does not establish that model weights are available.

[Processing handoff and error mapping](docs/product-handoff.md).

## Validate

```powershell
.venv/Scripts/python.exe -m pip install -r tests/product/requirements.txt
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe tools/validate_contracts.py
```

Product tests generate artificial MOV files and explicitly select synthetic test
analyzers. They cover authentication, uploads, queueing, hard deadlines, persistence,
failure semantics, evidence containment, timestamps, JPEG validation, and source
mapping. Separate contract validation checks both schemas and seven synthetic
examples. Video tests cover temporal coverage, real timestamps, evidence, network
blocking, candidate validation and failure semantics. These checks do not measure
detection quality; run the separate local evaluator for aggregate measurements.

Browser verification uses only artificial recordings and synthetic evidence.

## Configuration and deployment

- [Startup, settings, containers, and public ingress](deploy/README.md)
- [Module ownership and lifecycle](docs/architecture.md)
- [Integration acceptance requirements](docs/integration.md)
- [Technical requirements](docs/requirements.md)
- [Contribution conventions](CONTRIBUTING.md)

The product workstream owns web/, server/, deploy/, and tests/product/.
Video processing owns vision/, evaluation/, rules/, and tests/vision/.
Shared schema changes must be agreed before dependent implementation changes.

Competition materials, weights, credentials, uploads, and detailed results stay
outside version control. Do not publish the local runtime directory. Container
configuration is supplied; its build has not been verified in this environment.

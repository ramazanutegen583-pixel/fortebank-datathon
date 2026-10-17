# Forte Review

A local cash-operations video review service with a web interface, authenticated
HTTP API, durable jobs, and evidence presentation. The video analyzer is supplied
as a separate module. Without that module or its weights, processing fails
explicitly; the service does not generate fallback predictions.

## Run locally

Requires Python 3.12 or later.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe tools/init_env.py
.venv/Scripts/python.exe -m server
```

Open http://127.0.0.1:8000. Copy APP_API_KEY from the generated local .env file
into the interface's Access key field. The key is never embedded in the page
or stored in browser storage. On Linux/macOS use .venv/bin/python instead.

The interface, styles, icons, scripts, and API reference are served locally.
No frontend build or external asset service is required.

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

## Connect the analyzer

Implement vision.pipeline.analyze_video(video_path: Path, output_dir: Path) -> dict
according to the internal contract. Save JPEG files beneath output_dir and return
relative paths plus structured public rule references. The product worker validates
and maps the result to the jury API and interface.

Install vision/requirements.txt when it is supplied, then restart the service.
The interface indicates when the analyzer module is absent. Module presence does
not establish that model weights are available.

[Processing handoff and error mapping](docs/product-handoff.md).

## Validate

```powershell
.venv/Scripts/python.exe -m pip install -r tests/product/requirements.txt
.venv/Scripts/python.exe -m pytest tests/product
.venv/Scripts/python.exe tools/validate_contracts.py
```

Product tests generate artificial MOV files and explicitly select synthetic test
analyzers. They cover authentication, uploads, queueing, hard deadlines, persistence,
failure semantics, evidence containment, timestamps, JPEG validation, and source
mapping. Separate contract validation checks both schemas and seven synthetic
examples. These checks do not measure detection quality.

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

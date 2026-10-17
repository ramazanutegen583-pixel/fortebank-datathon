# Interface contracts v1

These contracts define the boundary between the product service and the local
video processing pipeline. Required public response fields follow the case
specification. HTTP status choices, internal result structures, and the handling
of rule references are project decisions.

The JSON schemas are authoritative for field names, types, required fields, and
verdict consistency. The runtime requirements below add checks that JSON Schema
cannot establish on its own.

## Public HTTP API

Both endpoints require the X-API-Key header. Requests without a valid key are
rejected before processing.

### Submit a video

```http
POST /api/v1/analyze
X-API-Key: <team-key>
Content-Type: multipart/form-data; boundary=<boundary>
```

| Input | Contract |
| --- | --- |
| file | Required multipart file field |
| Format | .mov video |
| Size | Approximately 29 MB in the case description; the configured upload limit must allow a reasonable margin |

A successful submission returns HTTP 202 and the object defined by
api.schema.json#/$defs/submission:

```json
{
  "job_id": "synthetic-job-001"
}
```

The server assigns an opaque job identifier, stores the upload locally, creates
the job in processing, and schedules background analysis. The HTTP request does
not wait for the analyzer to finish.

### Retrieve a job

```http
GET /api/v1/jobs/{job_id}
X-API-Key: <team-key>
```

A known job returns HTTP 200 with exactly one response variant from
[api.schema.json](api.schema.json).

| Status | Required fields | Meaning |
| --- | --- | --- |
| processing | job_id, status | Waiting for or running analysis |
| done | job_id, status, verdict, violations | Analysis completed successfully |
| failed | job_id, status, error | Analysis could not complete |

Processing response:

```json
{
  "job_id": "synthetic-job-001",
  "status": "processing"
}
```

Successful response without detected events:

```json
{
  "job_id": "synthetic-job-001",
  "status": "done",
  "verdict": "no_violation",
  "violations": []
}
```

The violation variant is illustrated in
[done-positive.json](examples/done-positive.json). Its image is an artificial
single-color JPEG; its event description is a synthetic fixture.

### Completed response fields

| Field | Type | Contract |
| --- | --- | --- |
| job_id | string | Nonempty job identifier |
| status | string | Exactly done |
| verdict | string | Exactly violation or no_violation |
| violations | array | Nonempty for violation; empty for no_violation |

Each violation contains:

| Field | Type | Contract |
| --- | --- | --- |
| type | string | Nonempty event category |
| timecode_sec | number | Event timestamp in seconds from the beginning of the video; nonnegative |
| description | string | Observable evidence, reason for review, and public rule references |
| evidence_frames | array | Between 1 and 3 frame objects |

Each public frame object contains:

| Field | Type | Contract |
| --- | --- | --- |
| timestamp_sec | number | Actual frame timestamp in seconds from the beginning of the video |
| image_base64 | string | JPEG bytes encoded as base64, without a data-URL prefix |

An event must be supported by actual frames from the uploaded video.
Timestamps must fall within the video duration. An unobservable banking-system
fact must not be presented as a conclusion from the video.

### Failed response

```json
{
  "job_id": "synthetic-job-001",
  "status": "failed",
  "error": {
    "code": "MODEL_UNAVAILABLE",
    "message": "The required local model is unavailable."
  }
}
```

error.code is a nonempty uppercase identifier using letters, digits, and
underscores, starting with a letter. error.message is a sanitized explanation
between 1 and 500 characters. It must not contain credentials, encoded images,
or detailed competition event content.

Neither processing nor failed responses include verdict or violations.
A missing model, decoding error, timeout, or invalid analyzer output must not
be converted into no_violation.

### Request errors

| HTTP status | Condition |
| --- | --- |
| 400 | Missing file field or malformed upload request |
| 401 | Missing or invalid API key |
| 404 | Unknown job identifier |
| 413 | Configured upload size limit exceeded |
| 415 | Unsupported video format |

These are request failures, not successful job responses. Their response body
is not frozen by the v1 job schema; clients must handle the HTTP status first.
The configured upload limit must be documented before deployment.

### State and timing

The only state transitions are processing → done and processing → failed.
Terminal results remain stable for the lifetime of a retained job.

The jury allows five minutes per video. Measure the full path from receipt of
the upload to a completed result, including queue time and frame encoding.
Configure the processing deadline with enough margin for the complete path.
A timeout produces failed rather than a fabricated result.

## Local analyzer interface

The video processing module exports:

```python
from pathlib import Path
from vision.pipeline import analyze_video

result: dict = analyze_video(
    video_path=Path("/absolute/path/to/input.mov"),
    output_dir=Path("/absolute/path/to/job-output"),
)
```

The signature is:

```python
analyze_video(video_path: Path, output_dir: Path) -> dict
```

| Parameter | Contract |
| --- | --- |
| video_path | Path to the uploaded .mov file readable by the local process |
| output_dir | Directory dedicated to this job's generated evidence files |

The function is synchronous. The server calls it in a background worker.
The analyzer does not expose HTTP endpoints, manage API keys, create job IDs,
or maintain a separate HTTP job queue.

The analyzer creates output_dir when necessary and returns a dictionary matching
[analysis.schema.json](analysis.schema.json). It either returns a complete result
or raises an exception. Partial or unsuccessful processing is not represented
by a successful negative verdict.

### Internal result fields

The top level contains verdict and violations with the same consistency rules
as the public completed response. Each internal violation contains the public
event fields plus sources. Internal frame objects use image_path instead of
image_base64.

| Internal field | Contract |
| --- | --- |
| evidence_frames[].timestamp_sec | Nonnegative timestamp within the input video |
| evidence_frames[].image_path | JPEG path relative to output_dir, using forward slashes |
| sources | At least one public rule reference for each event |
| sources[].document_title | Nonempty document title |
| sources[].section | Section identifier, or null if no precise section is available |
| sources[].url | URI for the public source |
| sources[].rationale | Explanation connecting the rule to the observable action |

Example internal frame reference:

```json
{
  "timestamp_sec": 1,
  "image_path": "evidence/frame-001.jpg"
}
```

The full synthetic internal result is in
[analysis-positive.json](examples/analysis-positive.json).

### Runtime checks

The server and analyzer must enforce these conditions in addition to schema
validation:

- Evidence paths resolve inside output_dir. Absolute paths, parent traversal,
  and symbolic-link escapes are rejected.
- Every referenced file exists, is readable, and decodes as JPEG.
- Timestamps refer to the uploaded video and do not exceed its duration.
- Frames support their associated events; references are real public sources.
- Base64 strings decode successfully to JPEG bytes.
- Analysis does not use network services, audio, facial recognition, labels,
  filenames, or memorized file hashes as a substitute for visual processing.

The current image_path schema checks string shape and extension only.
Path containment and filesystem checks are runtime responsibilities.

## Mapping internal results to public responses

The product service owns this conversion:

1. Validate the analyzer dictionary against analysis.schema.json.
2. Resolve each relative evidence path inside the job's output directory.
3. Read and validate the JPEG, then encode its bytes as base64.
4. Preserve event type and timestamps.
5. Keep sources structured for the local interface. Append each source's title,
   section when present, and URL to the public description.
6. Add job_id and status: done.
7. Validate the completed response against api.schema.json.

Do not add internal sources or image_path fields to the public response.
Both schemas reject unspecified properties.

## Contract changes and validation

A contract change includes the updated schema, corresponding examples, and
migration notes for both modules. Agree on it before changing dependent code.

All examples in examples/ are synthetic and contain no competition frames.
Run the validation command documented in the repository README before merging
changes. Schema and fixture validation checks interface compatibility; detection
quality, evidence relevance, offline operation, and processing latency require
separate local evaluation.

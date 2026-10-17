# Module boundaries

The application consists of a FastAPI product service and a synchronous
local video analyzer. A buildless HTML, CSS, and JavaScript interface is served
from the same Python application. No external scripts, fonts, or image services
are required. The analyzer uses pinned Qwen3-VL-2B weights with bounded temporal
sampling and candidate verification. Public deployment remains a separate step.
See video-processing.md for model setup, resource limits and evaluation.

## Ownership

| Module | Owned directories | Responsibilities |
| --- | --- | --- |
| Product | web/, server/, deploy/, tests/product/ | Upload UI, authentication, job queue, worker lifecycle, response serialization, deployment |
| Video processing | vision/, evaluation/, rules/, tests/vision/ | Video decoding, local analysis, evidence extraction, rule mapping, evaluation |
| Shared contract | contracts/ | Public response schemas, internal result schema, synthetic examples |

The product service owns common application configuration. Processing-specific
dependencies belong in vision/requirements.txt and must be checked for compatibility
before integration.

## Processing lifecycle

1. Validate the API key and multipart upload.
2. Save the video under a server-generated identifier in runtime/uploads/.
3. Create a processing job and return job_id immediately.
4. A background worker calls vision.pipeline.analyze_video with the input path
   and a dedicated output directory.
5. The isolated processing worker checks the video container and duration, then
   calls the analyzer, which saves evidence JPEG files.
6. The analyzer returns the internal result dictionary or raises an exception.
7. The product adapter in the isolated worker validates the result, resolves
   evidence paths safely, encodes JPEG bytes, and maps internal source references
   into the public description, under the same processing deadline.
8. Publish a done result or a failed result with a sanitized error.

The synchronous analyzer must not block the HTTP request handler. If a single GPU
is used, start with one processing worker and reuse loaded weights. Increasing
the number of HTTP requests must not create an uncontrolled number of model copies.

The current implementation persists jobs in local SQLite, uses one reusable
processing child, and terminates that child when a deadline is exceeded. A file
lock prevents multiple service instances from sharing one runtime directory.
See ../deploy/README.md for configuration and startup instructions.

## Local state

| Directory | Contents | Version control |
| --- | --- | --- |
| sources/, local_data/ | Original materials, labels, local dataset splits | Excluded |
| models/ | Downloaded weights | Excluded |
| runtime/ | Uploads, frames, results, detailed local logs | Excluded |
| exports/ | Portable repository bundles | Excluded |
| rules/ | Verified public references and general rule definitions | Included |

Keep descriptions of specific competition events in local results rather than
in public documentation or rule definitions. Use synthetic fixtures for interface
review and integration checks.

## Acceptance boundaries

A valid JSON response establishes structural compatibility only. End-to-end
acceptance additionally requires an actual analyzer, relevant evidence, verified
sources, offline processing, and measured total latency below the jury limit.
The implementation must not substitute test responses in production mode.

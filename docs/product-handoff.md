# Product implementation handoff

The interface, upload API, durable job state, queue, deadline supervision, and
evidence serialization are implemented. Video analysis is supplied separately.

## Processing boundary

The production import is vision.pipeline:analyze_video. Calls receive keyword
arguments video_path and output_dir as pathlib.Path instances. The function runs
in a persistent isolated process. It must return the existing internal contract
or raise an exception. Imported module state is retained across successful jobs.

The product worker validates that input is decodable MOV video and obtains its
duration before calling the analyzer. It validates output structure, timestamps,
evidence containment, JPEG content, and public source URL shape after the call.
It does not verify the semantic correctness of a source or the relevance of a
frame to an event; these remain processing and evaluation responsibilities.

Do not return base64 images from the analyzer. Save JPEG files below output_dir
and return forward-slash relative paths. The product worker encodes them and
appends public rule references to the jury-facing description. The interface
retrieves structured source references separately without altering the jury API.

## Failure handling

- Missing module, import dependency, or FileNotFoundError: MODEL_UNAVAILABLE.
- Invalid MOV container/decoding: INVALID_VIDEO.
- Invalid analyzer dictionary, timestamp, source URL, or evidence: INVALID_ANALYSIS_RESULT.
- Generic analyzer exception: ANALYSIS_FAILED.
- Exceeded total budget: TIMEOUT; the child process is terminated.
- Interrupted application lifecycle: SERVICE_RESTARTED.

Do not depend on exception messages being exposed: client messages are sanitized.
Model diagnostics stay in the local worker log. Restart the service after changing
processing code. Install vision/requirements.txt alongside product requirements
and verify dependency compatibility on the intended hardware.

## Product validation

Run tests with the development requirements in tests/product/requirements.txt:

```powershell
python -m pip install -r tests/product/requirements.txt
python -m pytest tests/product
python tools/validate_contracts.py
```

Tests use generated MOV files and explicitly selected synthetic analyzers under
tests/product/. Production configuration rejects substitute analyzers unless
APP_TEST_MODE=1. The production container excludes the test modules.

Actual detection quality, loaded-model memory, offline inference, GPU behavior,
and the complete runtime with the supplied analyzer require integration testing.
The container recipe is provided, but a container build has not been verified
in this environment because the Docker command is unavailable.

The product suite currently contains 29 passing tests. Desktop and mobile browser
checks exercised upload, polling, synthetic event rendering, evidence preview,
rule references, and the self-contained API reference. Shared contract validation
also passes. No competition recording was used for these checks.

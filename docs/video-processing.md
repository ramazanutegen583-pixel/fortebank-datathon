# Local video processing

The production entry point is `vision.pipeline.analyze_video`. It implements the
existing internal schema and integrates with the product worker without changing
the public API. Predictions use only decoded visual content. Labels, filenames,
known hashes, audio, and identity matching are not inputs to the model.

## Install

Use Python 3.12. Install the product dependencies first, then the matching official
PyTorch build. The following configuration targets an NVIDIA GPU:

```powershell
.venv/Scripts/python.exe -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python.exe -m pip install -r vision/requirements.txt
.venv/Scripts/python.exe tools/fetch_weights.py
.venv/Scripts/python.exe -m vision.smoke
.venv/Scripts/python.exe tools/check_service.py
.venv/Scripts/python.exe -m server
```

The default service check uses ASGI TestClient. To include real loopback HTTP
upload and polling, keep the server running and use another terminal:

```powershell
.venv/Scripts/python.exe tools/check_service.py --url http://127.0.0.1:8000
```

For a functional duration stress check:

```powershell
.venv/Scripts/python.exe -m vision.smoke --duration 145 --runs 1
```

This creates an artificial 145-second recording. Neither artificial check measures
detection quality on competition content.

The installer downloads `Qwen/Qwen3-VL-2B-Instruct` at revision
`89644892e4d85e24eaac8bacfd4f463576704203`. It verifies the safetensors SHA-256
against the repository's pinned LFS pointer, records local file checksums, and
copies the upstream license. Weights remain in ignored `models/qwen3-vl-2b/`.
Downloads happen during setup only. Large downloads resume from completed byte
ranges when the installer is run again.
If the main download is slow, `tools/fetch_weights.py --modelscope` uses the
publisher's alternative weight distribution and verifies the same pinned hash.

An optional larger checkpoint is available through `tools/fetch_weights.py --size 4b`.
It uses revision `ebb281ec70b05090aa6165b016eac8ec08e71b17` and verifies both
weight shards. Set `VISION_MODEL_DIR` to the resulting `models/qwen3-vl-4b`
directory. This alternative has not completed local installation or evaluation;
its accuracy, memory requirements and processing time are unverified.

The default device is CUDA; unavailable hardware fails explicitly. For functional
CPU experiments set `VISION_DEVICE=cpu` and install the official CPU build. CPU
runtime has not been established within the competition's deadline. Do not run
several service instances on one small GPU. The worker retains loaded weights
between jobs and is replaced after a hard timeout.

CUDA defaults to unquantized BF16 (`VISION_QUANTIZATION=none`). With
`VISION_OFFLOAD_VISUAL=1`, the visual encoder moves to system memory after
extracting features and returns to CUDA before the next pass. It is unused during
text generation; releasing its weights and cached allocations leaves more GPU
memory for the language component. This changes device placement, not weights.
CPU mode uses FP32 and ignores this offload option.

Optional `nf4` and `int8` modes use `bitsandbytes==0.48.2` under its MIT license.
They preserve the shared embedding/output head; the visual encoder also stays
in BF16 unless `VISION_QUANTIZE_VISION=1`. Quantization is not the default:
the initial NF4 baseline missed all positive development clips. Compare quality
and timing before using a different configuration.

## Processing

1. Inspect the video stream and reject unsupported duration or resolution.
2. Cover the video using 18-second windows with 3-second overlap.
3. Decode eight ordered frames per window with actual presentation timestamps.
   Each frame is resized to approximately 524,288 pixels, preserving aspect ratio.
   The ordered arrays enter the model's native video processor, with actual
   presentation timestamps and resampling disabled. Audio is never supplied.
4. Ask the local model to identify directly observable conditions from the public
   rule catalog. It first checks for a visible workspace or transaction scene,
   allowing staged tabletop recordings; an unsupported scene cannot contain events. Visible text is treated as
   scene content, never instructions.
5. Restrict token generation to the candidate JSON schema with local
   `lm-format-enforcer`, then independently validate the result. Formatting
   constraints do not establish that an event occurred. A malformed response is retried once;
   a repeated failure raises an error. The model's self-assessed confidence is
   filtered at 0.8; this value is not a calibrated probability.
6. Merge nearby candidates of the same category and independently recheck each
   candidate while preserving its original temporal window and nearby context.
   All conditions must be satisfied twice.
7. Save up to three actual JPEG frames per confirmed event (up to four megapixels,
   independently of the smaller model inputs) and attach a catalog
   reference. The model cannot invent URLs or regulatory section numbers.

All planned windows must finish. Exceeding the candidate limit or processing
budget fails the job instead of returning a partial negative result. The local
budget defaults to 235 seconds; the product's 270-second hard deadline also
includes upload/queue and result conversion. More than 180 seconds of video,
over 12 windows, more than eight verification candidates, or very large frames
are rejected. These limits cover the organizer's stated 10–145-second inputs.

The patch embedding uses a linear projection with the original convolution's
weights and bias. For a nonoverlapping patch with one spatial output, this is the
same operation as the model's Conv3D. It avoids a very slow small-output Conv3D
kernel observed on the Windows CUDA build. Equivalence is checked against real
convolution outputs. No layers or weights are removed.

`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, and telemetry opt-outs are enabled before
loading. Both processor and model use local files and disable remote code. Socket
connections, DNS resolution, and datagram sends are denied during processing.
Only the video stream is decoded. Model observations, detailed diagnostics and
evidence remain under the ignored local runtime directory. Do not copy their
contents to external services, shared logs or issue reports.
Keep these directories outside cloud-synchronized folders. Windows directory
junctions can retain the project-relative `local_data`, `runtime`, `sources`
and `models` paths while their contents reside in a local application-data
directory. Ignore rules cover both directories and junction entries.

## Rule catalog

The initial catalog has six **candidate review categories**, derived from public
rules, independently of the competition event labels:

| Category | Original publication section |
| --- | --- |
| Cashier departure during unfinished client service | 22 |
| Exposure of previously accepted cash outside locking storage | 20 |
| Acceptance/counting after the depositing client departs | 20 |
| Complete acceptance without observed counting | 19(2) |
| Visible transfer of accepted cash into personal storage | 3(7), 20 |
| A directly visible physical risk to cash security | 3(7) |

Each rule includes required visible conditions and explicit exclusions. General
movement, phone use, missing facial identification, uncertain documents, an
occluded hand, or a machine's invisible settings are insufficient. Results are
possible concerns for human review; the system does not establish theft, intent,
bank-account facts or a definitive legal violation.
The counting-omission category is retained as a documented rule but disabled in
the sparse-frame pipeline: it requires uninterrupted observation. A model's
claim cannot override this coverage requirement.

The source is the **original official publication** of National Bank Resolution
No. 231 of 29 November 2019, available in
[Kazakhstanskaya Pravda](https://kazpravda.kz/uploads/redactors/files/5e2ed7157da541580128021.pdf).
Sections 3(7), 19(2), 20 and 22 were checked against its text. The
[consolidated Adilet record](https://adilet.zan.kz/rus/docs/V1900019680) did not
expose its amended text to the verification client. Current amendments and
applicability require human verification; this limitation is attached to every
reference. Do not describe the 2019 text as the verified current edition.

## Local evaluation

```powershell
.venv/Scripts/python.exe tools/fetch_training_data.py --drive-id YOUR_TRAINING_FILE_ID
.venv/Scripts/python.exe -m evaluation.prepare
.venv/Scripts/python.exe -m evaluation.run --split development --limit 4
.venv/Scripts/python.exe -m evaluation.run --split holdout --output runtime/holdout
```

Supply the training archive's file ID from the organizer's link; access details
are kept out of the public repository. The preparation command finds the local
`open_labels.xlsx`, reads literal labels without executing formulas, and leaves
the original workbook unchanged. `--labels` also accepts extracted local JSON.
It makes a seeded, stratified 70/30 clip split. Source/session identities are
unavailable, so related-clip leakage remains possible. The manifest never enters
the production analyzer. Restrict tuning to development clips; evaluating a
holdout repeatedly after tuning invalidates its interpretation as unseen data.
Jury evaluation material must never be added to this preparation workflow.

The runner uses the same isolated worker and contract adapter as the service.
It stores detailed results locally and prints only aggregate metrics and timing.
Failures reduce completion rate and accuracy across all inputs; failed positive
videos reduce recall. Binary accuracy, precision, recall, F1, timestamp recall
within five seconds, and median/p95 runtime are reported. These timings exclude
HTTP upload and queue; the complete service must be timed separately. Supplied
labels do not establish event category or frame relevance, which need local
human review. Synthetic smoke tests do not measure detection quality.
Use a fresh `--output runtime/<run-name>` directory for each evaluation. Earlier
results are preserved rather than overwritten.

## Known limitations

Sparse sampling can miss short actions and cannot prove an action never happened
between frames. A small model may misinterpret cash, documents, hands, roles or
chronology. Two passes reduce some unsupported findings but are correlated and
do not establish correctness. Initial categories may not cover all competition
events or new camera angles. No contest accuracy or end-to-end timing should be
claimed before running the corresponding evaluation.

## Upstream licenses

The [model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) identifies the
weights as Apache-2.0; the
[upstream license](https://github.com/QwenLM/Qwen3-VL/blob/main/LICENSE) permits
commercial use subject to its terms. Transformers, Accelerate and safetensors
use Apache-2.0; PyTorch/torchvision and NumPy use BSD licenses. PyAV is BSD-3-Clause
and bundles FFmpeg components with their own LGPL/GPL notices; preserve and review
the installed distribution's notices when distributing binaries. Pillow uses
the permissive HPND license. Dependencies and weights are components of this
project's implementation, rather than a packaged cash-compliance solution.
The [format enforcer](https://github.com/noamgat/lm-format-enforcer) and its
Interegular dependency use MIT licenses and run locally.

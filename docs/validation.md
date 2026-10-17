# Validation record

Environment: Windows, Python 3.12.14, NVIDIA RTX 4050 Laptop GPU (6 GiB),
PyTorch 2.9.1+cu128, Transformers 4.57.6. Pinned Qwen3-VL-2B weights passed the
upstream SHA-256 check. Measurements below were performed on 17 October 2026.

## Automated and synthetic checks

- 66 tests passed, including product contracts, failures, temporal sampling,
  JPEG evidence, offline behavior, model-output validation and patch-projection
  equivalence and constrained-output grammar.
- Both shared schemas and seven synthetic fixtures passed validation.
- Installed dependencies passed `pip check`.
- The default configuration processed an artificial two-second 960x720 MOV as
  `no_violation`: 30.828 seconds cold and 3.500 seconds with loaded weights.
- An artificial 145-second MOV completed all ten windows as `no_violation` in
  59.344 seconds, including a fresh worker and model load.
- The same duration passed a real loopback HTTP upload, background job and
  polling check in 64.250 seconds. This measures local network transport,
  not a jury connection or public deployment.
- After enabling the catalog 1.2 coverage guard and restarting the service,
  a two-second artificial input passed real loopback HTTP in 19.547 seconds.

Synthetic checks exercise installed weights and the complete HTTP workflow.
Their timing does not establish detection accuracy or timing on real recordings.

## Detection quality

Local evaluation is separate from the synthetic checks. Detailed observations,
frames, encoded images and individual competition results stay under ignored
runtime storage. Only aggregate measurements may be added here.

The seeded split contains 29 development clips (15 positive, 14 negative) and
13 holdout clips (7 positive, 6 negative). Only development clips were used for
configuration comparison. The holdout remains untouched while the baseline is
below a useful development quality level. Clip grouping cannot exclude shared
subjects or recording sessions, whose identities are unavailable.

| Development configuration | Clips | Completed | TP / FP / TN / FN | F1 | Median / p95 seconds |
| --- | ---: | ---: | --- | ---: | --- |
| NF4, image inputs, 262,144 pixels, catalog 1.0 | 29 | 29 | 0 / 0 / 14 / 15 | 0 | 5.812 / 23.609 |
| BF16, image inputs, 65,536 pixels, catalog 1.1 | 8 | 8 | 3 / 5 / 0 / 0 | 0.545 | 22.117 / 36.313 |
| BF16, native video, 524,288 pixels, visual offload, constrained JSON, catalog 1.1 | 8 | 7 | 3 / 4 / 0 / 0 | 0.600 | 43.859 / 75.797 |

The eight-clip check is a development subset, not a full evaluation. The first
configuration predicted every clip negative; the second predicted every clip
positive. Neither demonstrates useful discrimination. F1 alone is misleading
without the confusion counts. These failures are why integration success must
not be presented as a submission-ready detector.

The native-video configuration also predicted all seven completed clips positive;
one negative clip failed because the candidate count exceeded the verification
limit. Across all eight inputs its accuracy was 37.5%, precision 42.9%, and
completion 87.5%. Two of three annotated timestamps were matched within five
seconds. It still lacks useful discrimination; the increased F1 must not be
interpreted as an improvement over a constant positive predictor. Further model
development and locally reviewed event-type annotations are required.

Catalog 1.2 adds a deterministic coverage guard: counting omission cannot be
reported from sparse samples. Post-hoc removal of that category from the seven
completed results did not change their binary confusion counts. That check is
not a fresh model evaluation; no improved accuracy is claimed for the guard.

Worker timings include decoding, weight loading, verification, evidence and
contract conversion; they exclude HTTP upload and queueing. Errors count against
availability and all-input accuracy rather than becoming negative predictions.
Binary labels and timestamps do not validate event category, rule applicability
or frame relevance; those require local human review. The references use the
original 2019 publication, not a verified current consolidated edition.

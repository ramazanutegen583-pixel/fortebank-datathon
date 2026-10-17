# Integration requirements

Both workstreams start from the same shared contract version and implement
their own module boundaries. Keep application code and video processing code
in separate directories and focused commits.

## Product deliverable

- Implement the upload interface and both HTTP endpoints.
- Validate the API key before accepting processing work.
- Run the synchronous analyzer in a background worker.
- Preserve processing, done, and failed states.
- Serialize JPEG evidence and public descriptions according to the schemas.
- Show structured rule sources in the interface.
- Provide repeatable launch and deployment instructions.
- Treat missing processing dependencies as explicit failures in production.

## Video processing deliverable

- Export vision.pipeline.analyze_video(video_path, output_dir).
- Decode .mov input and extract evidence with accurate media timestamps.
- Return the internal schema or raise an exception.
- Use locally installed dependencies and weights without network calls.
- Provide documented dependencies and commercially permitted licenses.
- Keep detailed inspection results local and report aggregate evaluation metrics.
- Record limitations and measured runtime without claiming unperformed checks.

## Handoff

A handoff includes the commit identifier, change description, launch command,
dependency changes, validation performed, remaining limitations, and any requested
contract changes. Detailed competition results are not included in public handoffs.

Shared contract changes must be agreed before implementation. Update schemas,
examples, and interface documentation together. Do not independently invent
additional verdicts, result fields, or HTTP processing endpoints.

## Integration checks

1. Validate both schemas and synthetic examples.
2. Exercise submission, polling, successful completion, and explicit failure.
3. Check invalid keys, malformed uploads, unsupported formats, unknown jobs,
   unavailable weights, and invalid analyzer output.
4. Verify evidence path containment, JPEG decoding, and timestamps.
5. Run the actual analyzer through the complete interface locally.
6. Measure queue time, analysis time, and serialization time together.
7. Verify processing without network access after installing weights.
8. Evaluate detection and localization on held-out recordings separately.

Synthetic fixtures establish integration behavior only. Production readiness
requires successful processing through the actual analyzer and local evaluation.

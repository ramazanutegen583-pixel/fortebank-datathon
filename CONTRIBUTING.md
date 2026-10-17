# Contribution conventions

Read README.md, contracts/README.md, and docs/architecture.md before changing
a module boundary.

## Ownership

- Product owns web/, server/, deploy/, tests/product/, application configuration,
  and deployment instructions.
- Video processing owns vision/, evaluation/, rules/, tests/vision/, and
  vision/requirements.txt.
- Shared schema changes require agreement between both workstreams before
  implementation. Describe the change and update examples in the same commit.
- Use separate working copies. Keep commits focused on the owning module.
- Review and validate changes before merging. Do not overwrite another
  contributor's work or rewrite shared history.

## Data handling

- Keep videos and labels in sources/ or local_data/, weights in models/, and
  generated frames, results, uploads, and detailed logs in runtime/.
- Do not commit these materials or credentials. Do not publish or transmit
  competition videos, frames, encoded frames, or event descriptions to external
  processing services or remote logs.
- Detailed inspection results remain local. Share aggregate metrics, timings,
  and sanitized technical errors.
- Processing must work without network access after weights are installed.
- Do not process audio or implement facial recognition or identification.
- Evaluation videos supplied by the jury must not be used for training.

## Implementation requirements

- Treat the schemas in contracts/ as the source of truth for interfaces.
- Processing errors produce failed jobs, never a default no_violation result.
- Predictions must not depend on filenames, known file hashes, or supplied labels.
- Synthetic responses are allowed only in an explicitly selected test mode.
  Production processing without the required model or weights must fail.
- Verify that code and weight licenses permit commercial use.
- Verify public rule references against primary sources; do not invent sections.
- Validate the affected behavior. Report only measurements actually performed.
  Contract validation does not establish detection quality or processing speed.
- Include a concise change description, validation results, remaining limitations,
  and any interface changes when handing off work.

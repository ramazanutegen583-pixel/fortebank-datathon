# ForteBank Datathon

Interface specifications for a local video review service. The repository contains
shared contracts, synthetic examples, and validation tools. The application and
video processing pipeline have not been implemented yet.

## Contracts

- [HTTP API and analyzer interface](contracts/README.md)
- [Job response schema](contracts/api.schema.json)
- [Analyzer result schema](contracts/analysis.schema.json)
- [Synthetic examples](contracts/examples/)
- [Module boundaries and processing lifecycle](docs/architecture.md)
- [Integration requirements](docs/integration.md)

## Module ownership

| Workstream | Directories | Responsibility |
| --- | --- | --- |
| Product | web/, server/, deploy/, tests/product/ | Upload interface, HTTP API, jobs, result presentation, deployment |
| Video processing | vision/, evaluation/, rules/, tests/vision/ | Local analysis, evidence frames, public rule references, evaluation |
| Shared interfaces | contracts/ | Request and response formats, analyzer interface, synthetic fixtures |

Each workstream implements the published interfaces. Changes to shared contracts
must be agreed and committed before dependent implementation changes.

## Validation

Use a separate Python environment:

```powershell
python -m pip install -r tools/requirements.txt
python tools/validate_contracts.py
```

The validator checks both JSON schemas, all seven synthetic examples, and the
synthetic JPEG fixture. It does not read competition materials.

## Project references

- [Technical requirements](docs/requirements.md)
- [Contribution conventions](CONTRIBUTING.md)

Competition materials, model weights, credentials, and generated results stay
outside version control. Local directories are listed in .gitignore.

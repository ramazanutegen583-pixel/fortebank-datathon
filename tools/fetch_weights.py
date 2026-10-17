"""Install the pinned public weights. This is a setup step, never inference."""

from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path

from downloads import download

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "2b": {
        "revision": "89644892e4d85e24eaac8bacfd4f463576704203",
        "weights": {"model.safetensors": (4255140312,
            "7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0")},
    },
    "4b": {
        "revision": "ebb281ec70b05090aa6165b016eac8ec08e71b17",
        "weights": {
            "model-00001-of-00002.safetensors": (4967229296,
                "30a01a0556622645a3cce87b655bbbbbc1f170c196099f1b666c93202c3339a9"),
            "model-00002-of-00002.safetensors": (3908490048,
                "046296a2a387efb43b0c997d5833c789604d168834f6e0d3064bf7bb13d002a6"),
        },
    },
}
FILES = (
    "chat_template.json", "config.json", "generation_config.json", "merges.txt",
    "preprocessor_config.json", "tokenizer.json",
    "tokenizer_config.json", "video_preprocessor_config.json", "vocab.json",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=MODELS, default="2b")
    parser.add_argument("--modelscope", action="store_true", help="Use the publisher's ModelScope weight mirror; verify the same pinned SHA-256.")
    arguments = parser.parse_args()
    specification = MODELS[arguments.size]
    repository = f"Qwen/Qwen3-VL-{arguments.size.upper()}-Instruct"
    revision = specification["revision"]
    target = ROOT / "models" / f"qwen3-vl-{arguments.size}"
    files = [*specification["weights"], *FILES]
    if len(specification["weights"]) > 1:
        files.append("model.safetensors.index.json")
    manifest = {"repository": repository, "revision": revision, "license": "Apache-2.0", "files": {}}
    for name in files:
        size, expected = specification["weights"].get(name, (None, None))
        destination = target / name
        url = f"https://huggingface.co/{repository}/resolve/{revision}/{name}"
        if arguments.modelscope and name.endswith(".safetensors"):
            url = f"https://modelscope.cn/models/{repository}/resolve/master/{name}"
        download(url, destination, size)
        with destination.open("rb") as content:
            digest = hashlib.file_digest(content, "sha256").hexdigest()
        if expected and digest != expected:
            raise RuntimeError("Downloaded weight checksum mismatch.")
        manifest["files"][name] = {"bytes": destination.stat().st_size, "sha256": digest}
        print(f"Installed {name}", flush=True)
    download("https://raw.githubusercontent.com/QwenLM/Qwen3-VL/main/LICENSE", target / "LICENSE")
    (target / "installation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Local weights installed and verified.")


if __name__ == "__main__":
    main()

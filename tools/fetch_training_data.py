"""Fetch the organizer's training archive into ignored local storage."""

from pathlib import Path
import argparse
import os
import shutil
import zipfile

from downloads import download

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drive-id", default=os.environ.get("TRAINING_DRIVE_ID"))
    arguments = parser.parse_args()
    destination = (ROOT / "local_data" / "training").resolve()
    archive = ROOT / "local_data" / "training.zip"
    if not archive.exists() or archive.stat().st_size != 292563667:
        if not arguments.drive_id or not all(character.isalnum() or character in "-_" for character in arguments.drive_id):
            parser.error("Provide --drive-id from the organizer's training archive link.")
        download(
            "https://drive.usercontent.google.com/download?id=" + arguments.drive_id + "&export=download&confirm=t",
            archive, 292563667,
        )
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination) or "\\" in entry.filename:
                raise ValueError("Archive member escapes local storage.")
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as stream, target.open("wb") as output:
                shutil.copyfileobj(stream, output, length=1024 * 1024)
            count += target.suffix.lower() == ".mov"
    print(f"Training archive extracted locally: {count} videos. No media displayed.")


if __name__ == "__main__":
    main()

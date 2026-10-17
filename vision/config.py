"""Bounded settings for local video processing."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class VisionSettings:
    model_dir: Path = ROOT / "models" / "qwen3-vl-2b"
    device: str = "cuda"
    quantization: str = "none"
    input_mode: str = "video"
    quantize_vision: bool = False
    offload_visual: bool = True
    window_seconds: float = 18
    overlap_seconds: float = 3
    frames_per_window: int = 8
    max_duration_seconds: float = 180
    max_windows: int = 12
    max_frame_pixels: int = 524288
    max_new_tokens: int = 384
    confidence_threshold: float = 0.8
    merge_seconds: float = 8
    max_candidates: int = 8
    max_events: int = 8
    budget_seconds: float = 235

    def __post_init__(self) -> None:
        if self.device not in {"cuda", "cpu"}:
            raise ValueError("VISION_DEVICE must be cuda or cpu.")
        if self.quantization not in {"none", "nf4", "int8"} or (self.device == "cpu" and self.quantization != "none"):
            raise ValueError("VISION_QUANTIZATION must be none, or nf4/int8 on CUDA.")
        if self.input_mode not in {"video", "images"}:
            raise ValueError("VISION_INPUT_MODE must be video or images.")
        if not 0 <= self.overlap_seconds < self.window_seconds:
            raise ValueError("Invalid temporal overlap.")
        if not 2 <= self.frames_per_window <= 12:
            raise ValueError("Use between 2 and 12 frames per window.")
        if not 0 <= self.confidence_threshold <= 1:
            raise ValueError("Invalid confidence threshold.")
        if not 4096 <= self.max_frame_pixels <= 1048576:
            raise ValueError("Invalid frame pixel budget.")
        if not 1 <= self.max_windows <= 30 or not 1 <= self.max_candidates <= 20:
            raise ValueError("Invalid processing limits.")
        if not 0 < self.budget_seconds < 270 or not 1 <= self.max_events <= 20:
            raise ValueError("Invalid processing budget.")

    @classmethod
    def from_env(cls) -> "VisionSettings":
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
        return cls(
            model_dir=Path(os.environ.get("VISION_MODEL_DIR", str(cls.model_dir))).resolve(),
            device=os.environ.get("VISION_DEVICE", "cuda"),
            quantization=os.environ.get("VISION_QUANTIZATION", "none"),
            input_mode=os.environ.get("VISION_INPUT_MODE", "video"),
            quantize_vision=os.environ.get("VISION_QUANTIZE_VISION", "0") == "1",
            offload_visual=os.environ.get("VISION_OFFLOAD_VISUAL", "1") == "1",
            confidence_threshold=float(os.environ.get("VISION_CONFIDENCE_THRESHOLD", "0.8")),
            max_frame_pixels=int(os.environ.get("VISION_MAX_FRAME_PIXELS", "524288")),
            budget_seconds=float(os.environ.get("VISION_BUDGET_SECONDS", "235")),
        )

"""Persistent isolated processing worker with enforceable per-job deadlines."""

from __future__ import annotations

import importlib
import math
import multiprocessing
import time
import threading
from pathlib import Path

from server.validation import ProcessingError, ResultAdapter


def inspect_video(path: Path) -> float:
    import av

    try:
        with av.open(str(path), mode="r", format="mov",
                     options={"protocol_whitelist": "file", "enable_drefs": "0", "use_absolute_path": "0"}) as container:
            if "mov" not in container.format.name.split(",") or not container.streams.video:
                raise ValueError("unsupported container")
            stream = container.streams.video[0]
            duration = float(stream.duration * stream.time_base) if stream.duration is not None and stream.time_base else (
                float(container.duration / av.time_base) if container.duration else 0)
            if duration <= 0 or not math.isfinite(duration):
                raise ValueError("duration unavailable")
            next(container.decode(video=0))
            return duration
    except Exception as exc:
        raise ProcessingError("INVALID_VIDEO", "The file could not be decoded as a supported .mov video.") from exc


def worker_main(connection, analyzer_path: str, max_evidence_bytes: int, log_path: str) -> None:
    import os
    import sys

    # Keep model and native-library diagnostics out of HTTP and server output.
    local_log = open(log_path, "a", encoding="utf-8", buffering=1)
    os.dup2(local_log.fileno(), 1)
    os.dup2(local_log.fileno(), 2)
    sys.stdout = local_log
    sys.stderr = local_log
    # Silence native decoder diagnostics: detailed media errors must stay local.
    import av

    av.logging.set_level(av.logging.PANIC)
    function = None
    adapter = ResultAdapter(max_evidence_bytes)
    while True:
        try:
            command = connection.recv()
        except EOFError:
            return
        if command is None:
            return
        try:
            duration = inspect_video(Path(command["video_path"]))
            if function is None:
                module_name, function_name = analyzer_path.split(":", 1)
                function = getattr(importlib.import_module(module_name), function_name)
                if not callable(function):
                    raise ImportError("analyzer is not callable")
            result = function(video_path=Path(command["video_path"]), output_dir=Path(command["output_dir"]))
            public, details = adapter.convert(command["job_id"], result, Path(command["output_dir"]), duration)
            connection.send({"ok": True, "public": public, "details": details})
        except ProcessingError as exc:
            connection.send({"ok": False, "code": exc.code, "message": exc.message})
        except (ImportError, AttributeError, FileNotFoundError):
            connection.send({"ok": False, "code": "MODEL_UNAVAILABLE", "message": "The local analyzer or required weights are unavailable."})
        except MemoryError:
            connection.send({"ok": False, "code": "RESOURCE_LIMIT", "message": "The processing worker ran out of memory."})
        except TimeoutError:
            connection.send({"ok": False, "code": "TIMEOUT", "message": "The local processing deadline was exceeded."})
        except Exception:
            import traceback

            traceback.print_exc(file=local_log)
            connection.send({"ok": False, "code": "ANALYSIS_FAILED", "message": "The local analyzer could not complete this video."})


class WorkerRunner:
    def __init__(self, analyzer_path: str, max_evidence_bytes: int, runtime_dir: Path):
        self.analyzer_path = analyzer_path
        self.max_evidence_bytes = max_evidence_bytes
        self.log_path = runtime_dir / "worker.log"
        self.process = None
        self.connection = None
        self.closed = False
        self.lifecycle_lock = threading.RLock()

    def start(self) -> None:
        with self.lifecycle_lock:
            if self.closed:
                raise ProcessingError("SERVICE_RESTARTED", "The service is shutting down. Please submit again.")
            if self.process and self.process.is_alive():
                return
            self.stop()
            context = multiprocessing.get_context("spawn")
            self.connection, child = context.Pipe()
            self.process = context.Process(target=worker_main,
                args=(child, self.analyzer_path, self.max_evidence_bytes, str(self.log_path)), daemon=True)
            self.process.start()
            child.close()

    def execute(self, job_id: str, video_path: Path, output_dir: Path, deadline: float) -> dict:
        if time.time() >= deadline:
            raise ProcessingError("TIMEOUT", "The processing deadline was exceeded while waiting in the queue.")
        with self.lifecycle_lock:
            self.start()
            connection = self.connection
            process = self.process
        try:
            connection.send({"job_id": job_id, "video_path": str(video_path), "output_dir": str(output_dir)})
            while time.time() < deadline:
                if connection.poll(min(0.05, max(0, deadline - time.time()))):
                    return connection.recv()
                if not process.is_alive():
                    raise ProcessingError("WORKER_UNAVAILABLE", "The processing worker stopped unexpectedly.")
        except (EOFError, BrokenPipeError, OSError, ValueError, TypeError) as exc:
            self.stop()
            raise ProcessingError("WORKER_UNAVAILABLE", "The processing worker stopped unexpectedly.") from exc
        self.stop()
        raise ProcessingError("TIMEOUT", "The processing deadline was exceeded. Please try again with a shorter video.")

    def stop(self) -> None:
        with self.lifecycle_lock:
            if self.process:
                if self.process.is_alive():
                    self.process.terminate()
                self.process.join(timeout=2)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(timeout=2)
                self.process.close()
            if self.connection:
                self.connection.close()
            self.process = None
            self.connection = None

    def close(self) -> None:
        with self.lifecycle_lock:
            self.closed = True
            self.stop()

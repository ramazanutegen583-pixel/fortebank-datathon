"""Single model-worker scheduling and durable public job state."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from server.config import Settings
from server.store import JobStore
from server.validation import ProcessingError
from server.worker import WorkerRunner


class InstanceLock:
    def __init__(self, path: Path):
        self.file = path.open("a+b")
        try:
            self.file.seek(0)
            if self.file.read(1) == b"":
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            import sys
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError("Runtime directory is already in use. Run one server instance per directory.") from None

    def close(self) -> None:
        self.file.close()


class JobManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lock = InstanceLock(settings.runtime_dir / "service.lock")
        self.store = JobStore(settings.runtime_dir / "jobs.sqlite3")
        self.store.recover()
        self.runner = WorkerRunner(settings.analyzer, settings.max_evidence_bytes, settings.runtime_dir)
        self.queue = asyncio.Queue()
        self.pending = 0
        self.tasks = []

    def reserve(self) -> bool:
        if self.pending >= self.settings.max_pending_jobs:
            return False
        self.pending += 1
        return True

    def release(self) -> None:
        self.pending -= 1

    def enqueue(self, job_id: str, video_path: Path, created_at: float) -> None:
        deadline = created_at + self.settings.job_timeout_seconds
        self.store.create(job_id, created_at, deadline)
        self.queue.put_nowait((job_id, video_path, deadline))

    async def start(self) -> None:
        self.tasks = [asyncio.create_task(self.run()), asyncio.create_task(self.watch_deadlines())]

    async def run(self) -> None:
        while True:
            job_id, path, deadline = await self.queue.get()
            try:
                if self.store.get(job_id)["status"] != "processing":
                    continue
                output_dir = self.settings.runtime_dir / "results" / job_id
                output_dir.mkdir(parents=True, exist_ok=True)
                payload = await asyncio.to_thread(self.runner.execute, job_id, path, output_dir, deadline)
                if not payload["ok"]:
                    raise ProcessingError(payload["code"], payload["message"])
                if time.time() >= deadline:
                    raise ProcessingError("TIMEOUT", "The processing deadline was exceeded before the result was ready.")
                self.store.finish(job_id, payload["public"], payload["details"])
            except ProcessingError as exc:
                self.store.fail(job_id, exc.code, exc.message)
            except asyncio.CancelledError:
                self.store.fail(job_id, "SERVICE_RESTARTED", "The service stopped before processing completed. Please submit again.")
                raise
            except Exception:
                self.store.fail(job_id, "PROCESSING_FAILED", "The service could not complete this video.")
            finally:
                self.release()
                self.queue.task_done()

    async def watch_deadlines(self) -> None:
        while True:
            await asyncio.sleep(0.2)
            self.store.expire()

    async def close(self) -> None:
        # Stop the child before cancelling the coroutine waiting for its response.
        self.runner.close()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.store.recover()
        self.lock.close()

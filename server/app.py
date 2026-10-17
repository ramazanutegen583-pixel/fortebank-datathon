"""HTTP API and offline static interface."""

from __future__ import annotations

import asyncio
import hmac
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from starlette.datastructures import Headers, UploadFile
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from server.config import ROOT, Settings
from server.jobs import JobManager


def request_error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class RequestGuard:
    """Authenticate before multipart parsing and bound even chunked request bodies."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        scope.setdefault("state", {})["received_at"] = time.time()
        headers = Headers(scope=scope)
        protected = scope["path"].startswith(("/api/v1/", "/ui/"))

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
                ]
            await send(message)

        if protected and not hmac.compare_digest(
            headers.get("x-api-key", "").encode("utf-8"), self.settings.api_key.encode("utf-8")
        ):
            return await request_error("UNAUTHORIZED", "A valid X-API-Key header is required.", 401)(scope, receive, safe_send)
        body_limit = self.settings.max_upload_bytes + 1024 * 1024
        if scope["method"] == "POST" and scope["path"] == "/api/v1/analyze":
            if not headers.get("content-type", "").lower().startswith("multipart/form-data"):
                return await request_error("INVALID_UPLOAD", "Send a multipart upload with the file field.", 400)(scope, receive, safe_send)
            try:
                declared = int(headers.get("content-length", "0"))
                if declared < 0:
                    raise ValueError
            except ValueError:
                return await request_error("INVALID_UPLOAD", "Invalid Content-Length header.", 400)(scope, receive, safe_send)
            if declared > body_limit:
                return await request_error("UPLOAD_TOO_LARGE", "The upload exceeds the configured size limit.", 413)(scope, receive, safe_send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > body_limit:
                    raise HTTPException(413, "The upload exceeds the configured size limit.")
            return message

        await self.app(scope, limited_receive, safe_send)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        manager = JobManager(config)
        app.state.jobs = manager
        await manager.start()
        try:
            yield
        finally:
            await manager.close()

    app = FastAPI(title="Forte Review API", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None,
                  telemetry={"tracing": False, "metrics": False, "logs": False,
                             "operation_spans": False, "auto_configure": False})
    app.state.settings = config
    app.add_middleware(RequestGuard, settings=config)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        codes = {400: "INVALID_UPLOAD", 401: "UNAUTHORIZED", 404: "NOT_FOUND", 413: "UPLOAD_TOO_LARGE", 415: "UNSUPPORTED_FORMAT"}
        return request_error(codes.get(exc.status_code, "REQUEST_FAILED"),
                             str(exc.detail) if isinstance(exc.detail, str) else "The request could not be completed.", exc.status_code)

    @app.get("/", include_in_schema=False)
    async def homepage():
        return FileResponse(ROOT / "web/index.html")

    @app.get("/api-reference", include_in_schema=False)
    async def api_reference():
        return FileResponse(ROOT / "web/api.html")

    @app.get("/health", tags=["Service"])
    async def health():
        return {"status": "ok", "test_mode": config.test_mode,
                "analyzer_module_present": config.test_mode or (ROOT / "vision/pipeline.py").is_file(),
                "max_upload_bytes": config.max_upload_bytes, "job_timeout_seconds": config.job_timeout_seconds,
                "pending_jobs": app.state.jobs.pending, "job_capacity": config.max_pending_jobs}

    @app.post("/api/v1/analyze", status_code=202, tags=["Review"],
              openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                  "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}}}}}}})
    async def submit(request: Request):
        manager: JobManager = app.state.jobs
        if not manager.reserve():
            response = request_error("QUEUE_FULL", "The processing queue is full. Please try again shortly.", 429)
            response.headers["Retry-After"] = "5"
            return response
        accepted = False
        job_id = uuid.uuid4().hex
        uploads = config.runtime_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        path = uploads / f"{job_id}.mov"
        try:
            async with asyncio.timeout(config.upload_timeout_seconds):
                async with request.form(max_files=1, max_fields=0) as form:
                    items = list(form.multi_items())
                    if len(items) != 1 or items[0][0] != "file" or not isinstance(items[0][1], UploadFile):
                        return request_error("INVALID_UPLOAD", "Upload exactly one video in the file field.", 400)
                    uploaded = items[0][1]
                    if Path(uploaded.filename or "").suffix.lower() != ".mov":
                        return request_error("UNSUPPORTED_FORMAT", "Only .mov video files are supported.", 415)
                    if uploaded.size is not None and uploaded.size > config.max_upload_bytes:
                        return request_error("UPLOAD_TOO_LARGE", "The video exceeds the configured upload size limit.", 413)
                    size = 0
                    with path.open("wb") as destination:
                        while chunk := await uploaded.read(1024 * 1024):
                            size += len(chunk)
                            if size > config.max_upload_bytes:
                                return request_error("UPLOAD_TOO_LARGE", "The video exceeds the configured upload size limit.", 413)
                            destination.write(chunk)
                    if size == 0:
                        return request_error("INVALID_UPLOAD", "The uploaded file is empty.", 400)
            if time.time() >= request.state.received_at + config.job_timeout_seconds:
                return request_error("UPLOAD_TIMEOUT", "The upload used the available processing time. Please try again.", 408)
            manager.enqueue(job_id, path, request.state.received_at)
            accepted = True
            return JSONResponse({"job_id": job_id}, status_code=202)
        except TimeoutError:
            return request_error("UPLOAD_TIMEOUT", "The upload took too long. Please try again.", 408)
        except HTTPException:
            raise
        except Exception:
            return request_error("INVALID_UPLOAD", "The upload could not be read. Please submit a valid multipart file.", 400)
        finally:
            if not accepted:
                manager.release()
                path.unlink(missing_ok=True)

    def get_job(job_id: str):
        app.state.jobs.store.expire()
        job = app.state.jobs.store.get(job_id)
        if job is None:
            raise HTTPException(404, "The requested job does not exist.")
        return job

    @app.get("/api/v1/jobs/{job_id}", tags=["Review"])
    async def job_result(job_id: str):
        return get_job(job_id)["response"]

    @app.get("/ui/jobs/{job_id}", tags=["Interface"])
    async def job_details(job_id: str):
        job = get_job(job_id)
        return {"job_id": job_id, "status": job["status"], "created_at": job["created_at"],
                "deadline_at": job["deadline"], "elapsed_sec": round((job["completed_at"] or time.time()) - job["created_at"], 3),
                "details": job["details"]}

    app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        contract = json.loads((ROOT / "contracts/api.schema.json").read_text(encoding="utf-8"))

        def remap(value):
            if isinstance(value, dict):
                return {key: (item.replace("#/$defs/", "#/components/schemas/") if key == "$ref" else remap(item))
                        for key, item in value.items()}
            if isinstance(value, list):
                return [remap(item) for item in value]
            return value

        components = schema.setdefault("components", {})
        components.setdefault("schemas", {}).update(remap(contract["$defs"]))
        components["securitySchemes"] = {"TeamKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}
        for path, operations in schema["paths"].items():
            for operation in operations.values():
                if path.startswith(("/api/v1/", "/ui/")):
                    operation["security"] = [{"TeamKey": []}]
        schema["paths"]["/api/v1/analyze"]["post"]["responses"]["202"] = {
            "description": "Accepted", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/submission"}}}}
        schema["paths"]["/api/v1/jobs/{job_id}"]["get"]["responses"]["200"] = {
            "description": "Job status or terminal result", "content": {"application/json": {"schema": {"oneOf": remap(contract["oneOf"])}}}}
        app.openapi_schema = schema
        return schema

    app.openapi = openapi
    return app

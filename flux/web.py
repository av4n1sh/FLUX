"""Authenticated personal Flux API. Run one worker; use a persistent data disk."""
import json
import os
import secrets
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .storage import Store
from .web_controller import WebController
from .web_brain import reply


def create_app(store=None, responder=None, token=None, origins=None):
    token = token or os.environ.get("FLUX_WEB_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("Set FLUX_WEB_TOKEN to a random secret of at least 32 characters.")
    origins = origins or os.environ.get("FLUX_WEB_ORIGINS", "http://localhost:8080").split(",")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins],
                       allow_methods=["POST"], allow_headers=["Authorization", "Content-Type"])
    controller = WebController(store or Store(Path(os.environ.get("FLUX_WEB_DATA", "data/web")) / "flux.db"), responder or reply)
    lock = threading.Lock()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/action")
    async def action(request: Request):
        if not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            raise HTTPException(401, "Invalid access key.")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 150000:
                raise HTTPException(413, "Request is too large.")
        try:
            data = json.loads(body)
            if not isinstance(data, dict) or not isinstance(data.get("action"), str):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "Invalid action request.") from None

        def dispatch():
            if not lock.acquire(blocking=False):
                raise HTTPException(409, "Flux is busy. Try again when the current request finishes.")
            try:
                controller.events = []
                controller.dispatch(json.dumps(data))
                return {"events": controller.events}
            finally:
                lock.release()
        return await run_in_threadpool(dispatch)

    return app

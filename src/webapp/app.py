"""FastAPI web app for long-running credit card statement analysis."""

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from libs.llm.main import (
    GEMINI,
    OPENAI_COMPATIBLE,
    configured_providers,
    load_llm_config,
)
from webapp.jobs import JobManager

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Credit Card Statement Analyzer", version="0.2.0")
manager = JobManager()


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict:
    available, errors = configured_providers()
    defaults = {}
    for provider in (GEMINI, OPENAI_COMPATIBLE):
        try:
            cfg = load_llm_config(provider=provider)
        except ValueError:
            continue
        defaults[provider] = {
            "model": cfg.model,
            "base_url": cfg.base_url,
            "thinking": cfg.thinking,
        }
    return {
        "providers": available,
        "errors": errors,
        "defaults": defaults,
        "max_workers": manager.max_workers,
    }


@app.post("/api/jobs")
async def create_job(
    request: Request,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> dict:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=400, detail="Upload statements as multipart/form-data.")

    form = await request.form(max_files=20, max_fields=10)
    files = [value for value in form.getlist("files") if isinstance(value, StarletteUploadFile)]
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF statement is required.")

    payloads: list[tuple[str, bytes]] = []
    for upload in files:
        raw = (upload.filename or "statement.pdf").replace("\\", "/")
        if not raw.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{raw} is not a PDF.")
        # Folder uploads arrive as relative sub-paths; reject absolute or traversal ones.
        parts = raw.split("/")
        if raw.startswith("/") or ".." in parts:
            raise HTTPException(status_code=400, detail=f"{raw} has an invalid path.")
        name = "/".join(part for part in parts if part)
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{name} exceeds the 25 MB limit.")
        payloads.append((name, data))

    try:
        job = manager.create_job(payloads, provider=provider, model=model, base_url=base_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return manager.describe(job)


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return manager.list_jobs()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return manager.describe(job)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not manager.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or already finished.")
    return {"cancelled": True}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    if not manager.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"deleted": True}


@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: str, after: int = 0) -> StreamingResponse:
    if manager.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    def encode():
        for event in manager.stream_events(job_id, after_seq=after):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(encode(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/transactions")
def job_transactions(job_id: str) -> dict:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    rows = manager.transactions(job)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.loc[df["amount"].notna()]
    return {
        "transactions": df.to_dict(orient="records"),
        "summaries": manager.summaries(job),
        "ignored_invalid_amounts": int(len(rows) - len(df)),
    }


@app.get("/api/jobs/{job_id}/csv")
def job_csv(job_id: str, background: BackgroundTasks) -> FileResponse:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", prefix=f"{job_id}-", delete=False, encoding="utf-8"
    )
    try:
        handle.write(manager.csv_text(job))
    finally:
        handle.close()
    background.add_task(os.unlink, handle.name)
    return FileResponse(
        handle.name,
        media_type="text/csv",
        filename="credit_card_analysis.csv",
    )


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")

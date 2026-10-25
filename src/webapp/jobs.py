"""In-memory job manager for long-running statement analysis.

Jobs run on a shared, bounded worker pool so a single local LLM endpoint is never
flooded. Progress is published as an ordered event stream that the web layer
relays to the browser over Server-Sent Events.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from libs.llm.main import LLMConfig, load_llm_config
from libs.tools.statement_processor import (
    StatementProgress,
    StatementResult,
    StatementUpload,
    get_max_concurrent_statements,
    process_statement,
)
from libs.tools.statement_results import is_populated_statement

CSV_HEADER = "date,transaction_name,amount,category,account,card_name\n"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FileItem:
    index: int
    filename: str
    content: bytes
    stage: str = STATUS_QUEUED
    detail: str = ""
    error: str | None = None
    statement: Any | None = None
    csv_rows: str = ""


@dataclass
class Job:
    id: str
    provider: str
    model: str
    created_at: str
    items: list[FileItem]
    llm_config: LLMConfig
    status: str = STATUS_QUEUED
    started_at: str | None = None
    finished_at: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    finished: bool = False


class JobManager:
    """Thread-safe store of analysis jobs with a shared bounded worker pool."""

    def __init__(
        self,
        max_workers: int | None = None,
        processor: Callable[..., StatementResult] = process_statement,
    ) -> None:
        self.max_workers = (
            get_max_concurrent_statements() if max_workers is None else max_workers
        )
        if self.max_workers < 1:
            raise ValueError("max_workers must be positive")
        self._processor = processor
        self._jobs: dict[str, Job] = {}
        self._events: dict[str, list[dict]] = {}
        self._sequence = 0
        self._condition = threading.Condition()
        self._semaphore = threading.Semaphore(self.max_workers)
        self._threads: list[threading.Thread] = []

    # ---------------------------------------------------------------- jobs ---
    def create_job(
        self,
        files: list[tuple[str, bytes]],
        provider: str | None = None,
        model: str | None = None,
    ) -> Job:
        """Validate configuration and queue a job; raises ValueError on bad config."""
        llm_config = load_llm_config(provider=provider, model=model)
        job = Job(
            id=uuid.uuid4().hex,
            provider=llm_config.provider,
            model=llm_config.model,
            created_at=_now(),
            items=[FileItem(idx, name, data) for idx, (name, data) in enumerate(files)],
            llm_config=llm_config,
        )
        with self._condition:
            self._jobs[job.id] = job
            self._events[job.id] = []
        self._publish(job.id, "", STATUS_QUEUED, f"{len(job.items)} file(s) queued")
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        self._threads.append(thread)
        thread.start()
        return job

    def get_job(self, job_id: str) -> Job | None:
        with self._condition:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        with self._condition:
            jobs = list(self._jobs.values())
        return [self.describe(job) for job in sorted(jobs, key=lambda j: j.created_at)]

    def cancel_job(self, job_id: str) -> bool:
        with self._condition:
            job = self._jobs.get(job_id)
            if job is None or job.finished:
                return False
            job.cancel_event.set()
        self._publish(job_id, "", "cancelling", "waiting for running statements")
        return True

    def delete_job(self, job_id: str) -> bool:
        with self._condition:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            job.cancel_event.set()
            self._jobs.pop(job_id, None)
            self._events.pop(job_id, None)
            self._condition.notify_all()
        return True

    # ------------------------------------------------------------- running ---
    def _run_job(self, job: Job) -> None:
        job.status = STATUS_RUNNING
        job.started_at = _now()
        threads = [
            threading.Thread(target=self._run_item, args=(job, item), daemon=True)
            for item in job.items
        ]
        for thread in threads:
            thread.start()
            self._threads.append(thread)
        for thread in threads:
            thread.join()

        if job.cancel_event.is_set():
            job.status = STATUS_CANCELLED
        else:
            job.status = STATUS_COMPLETED
        job.finished_at = _now()
        with self._condition:
            job.finished = True
            self._condition.notify_all()
        self._publish(job.id, "", job.status, self._outcome_detail(job))

    def _run_item(self, job: Job, item: FileItem) -> None:
        if job.cancel_event.is_set():
            item.stage = STATUS_CANCELLED
            self._publish(job.id, item.filename, STATUS_CANCELLED, "skipped")
            return
        # Global bound: at most max_workers statements across all jobs.
        self._semaphore.acquire()
        try:
            if job.cancel_event.is_set():
                item.stage = STATUS_CANCELLED
                self._publish(job.id, item.filename, STATUS_CANCELLED, "skipped")
                return
            item.stage = "processing"
            self._publish(job.id, item.filename, "processing")
            upload = StatementUpload(item.index, item.filename, item.content)
            result = self._processor(
                upload,
                job.llm_config,
                lambda progress: self._on_progress(job, progress),
            )
            self._apply_result(job, item, result)
        except Exception as exc:  # defensive: worker must never die silently
            item.error = str(exc)
            item.stage = "failed"
            self._publish(job.id, item.filename, "failed", str(exc))
        finally:
            self._semaphore.release()

    def _on_progress(self, job: Job, progress: StatementProgress) -> None:
        item = job.items[progress.index]
        item.stage = progress.stage
        item.detail = progress.detail
        self._publish(job.id, progress.filename, progress.stage, progress.detail)

    def _apply_result(self, job: Job, item: FileItem, result: StatementResult) -> None:
        if result.error is not None:
            item.error = str(result.error)
            item.stage = "failed"
            self._publish(job.id, item.filename, "failed", item.error)
            return
        item.statement = result.statement
        item.csv_rows = result.csv_rows
        if is_populated_statement(result.statement):
            item.stage = "completed"
            self._publish(
                job.id,
                item.filename,
                "completed",
                f"{result.statement.number_of_transactions} transactions",
            )
        else:
            item.stage = "empty"
            self._publish(job.id, item.filename, "empty", "no transactions found")

    # -------------------------------------------------------------- events ---
    def _publish(self, job_id: str, filename: str, stage: str, detail: str = "") -> None:
        with self._condition:
            if job_id not in self._jobs:
                return  # job deleted while its worker was still running
            self._sequence += 1
            event = {
                "seq": self._sequence,
                "job_id": job_id,
                "filename": filename,
                "stage": stage,
                "detail": detail,
                "ts": _now(),
            }
            self._events.setdefault(job_id, []).append(event)
            self._condition.notify_all()

    def stream_events(self, job_id: str, after_seq: int = 0) -> Iterator[dict]:
        """Yield events for a job, blocking until new ones arrive or it finishes."""
        last = after_seq
        while True:
            with self._condition:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                batch = [e for e in self._events.get(job_id, []) if e["seq"] > last]
                finished = job.finished
                if not batch and not finished:
                    self._condition.wait(timeout=1.0)
                    batch = [
                        e for e in self._events.get(job_id, []) if e["seq"] > last
                    ]
                    finished = self._jobs[job_id].finished if job_id in self._jobs else True
            if batch:
                last = batch[-1]["seq"]
                for event in batch:
                    yield event
            if finished and not batch:
                return

    # ------------------------------------------------------------ payloads ---
    def _outcome_detail(self, job: Job) -> str:
        completed = sum(1 for item in job.items if item.stage == "completed")
        empty = sum(1 for item in job.items if item.stage == "empty")
        failed = sum(1 for item in job.items if item.stage == "failed")
        return f"{completed} ok, {empty} empty, {failed} failed"

    def describe(self, job: Job) -> dict:
        return {
            "id": job.id,
            "provider": job.provider,
            "model": job.model,
            "status": job.status,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "total": len(job.items),
            "completed": sum(1 for i in job.items if i.stage == "completed"),
            "empty": sum(1 for i in job.items if i.stage == "empty"),
            "failed": sum(1 for i in job.items if i.stage == "failed"),
            "cancelled": sum(1 for i in job.items if i.stage == STATUS_CANCELLED),
            "files": [
                {
                    "filename": item.filename,
                    "stage": item.stage,
                    "detail": item.detail,
                    "error": item.error,
                }
                for item in job.items
            ],
        }

    def transactions(self, job: Job) -> list[dict]:
        rows: list[dict] = []
        for item in job.items:
            if item.statement is None or not is_populated_statement(item.statement):
                continue
            for transaction in item.statement.transactions:
                rows.append(transaction.model_dump())
        return rows

    def summaries(self, job: Job) -> list[dict]:
        summaries = []
        for item in job.items:
            if item.statement is None or not is_populated_statement(item.statement):
                continue
            statement = item.statement
            summaries.append(
                {
                    "file_name": item.filename,
                    "card_name": statement.card_name,
                    "total_spending": statement.total_spending,
                    "number_of_transactions": statement.number_of_transactions,
                    "due_date": statement.due_date,
                }
            )
        return summaries

    def csv_text(self, job: Job) -> str:
        body = "".join(item.csv_rows for item in job.items if item.csv_rows)
        return CSV_HEADER + body

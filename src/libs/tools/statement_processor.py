import os
import tempfile
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import Callable, Iterator, Sequence

from libs.llm.main import LLMConfig
from libs.tools.pdf_2_image import convert_pdf_to_images
from libs.tools.retry import retry_transient
from libs.tools.state_2_csv import statement_to_csv
from libs.tools.statement_reader import read_statement
from libs.tools.statement_results import is_populated_statement


DEFAULT_MAX_CONCURRENT_STATEMENTS = 2
MAX_CONCURRENT_STATEMENTS_ENV = "MAX_CONCURRENT_STATEMENTS"


@dataclass(frozen=True)
class StatementUpload:
    index: int
    filename: str
    content: bytes


@dataclass(frozen=True)
class StatementResult:
    index: int
    filename: str
    statement: object | None = None
    csv_rows: str = ""
    error: Exception | None = None


@dataclass(frozen=True)
class StatementProgress:
    index: int
    filename: str
    stage: str
    detail: str = ""


def get_max_concurrent_statements(value: str | None = None) -> int:
    """Read and validate the bounded statement worker count."""
    raw_value = value if value is not None else os.getenv(MAX_CONCURRENT_STATEMENTS_ENV)
    if raw_value is None or not raw_value.strip():
        return DEFAULT_MAX_CONCURRENT_STATEMENTS
    try:
        worker_count = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{MAX_CONCURRENT_STATEMENTS_ENV} must be a positive integer") from exc
    if worker_count < 1:
        raise ValueError(f"{MAX_CONCURRENT_STATEMENTS_ENV} must be a positive integer")
    return worker_count


def process_statement(
    upload: StatementUpload,
    llm_config: LLMConfig,
    report_progress: Callable[[StatementProgress], None],
) -> StatementResult:
    """Process one upload entirely within an isolated temporary directory."""
    try:
        with tempfile.TemporaryDirectory(prefix=f"statement-{upload.index}-") as temp_dir:
            report_progress(StatementProgress(upload.index, upload.filename, "converting"))
            safe_filename = Path(upload.filename).name or f"statement-{upload.index}.pdf"
            pdf_path = Path(temp_dir) / safe_filename
            pdf_path.write_bytes(upload.content)
            images_dir = Path(temp_dir) / "images"
            images_dir.mkdir()
            image_paths = convert_pdf_to_images(str(pdf_path), str(images_dir), fmt="png")
            report_progress(StatementProgress(upload.index, upload.filename, "analyzing"))
            statement = retry_transient(
                lambda: read_statement(llm_config, image_paths),
                on_retry=lambda attempt, error, delay: report_progress(
                    StatementProgress(
                        upload.index,
                        upload.filename,
                        "retrying",
                        f"attempt {attempt + 1} in {delay:g}s: {error}",
                    )
                ),
            )
            if not is_populated_statement(statement):
                return StatementResult(
                    index=upload.index,
                    filename=upload.filename,
                    statement=statement,
                )
            return StatementResult(
                index=upload.index,
                filename=upload.filename,
                statement=statement,
                csv_rows=statement_to_csv(statement),
            )
    except Exception as exc:
        return StatementResult(index=upload.index, filename=upload.filename, error=exc)


def process_statements_concurrently(
    uploads: Sequence[StatementUpload],
    llm_config: LLMConfig,
    *,
    max_workers: int,
    processor: Callable[
        [StatementUpload, LLMConfig, Callable[[StatementProgress], None]],
        StatementResult,
    ] = process_statement,
    on_progress: Callable[[StatementProgress], None] | None = None,
) -> Iterator[StatementResult]:
    """Yield isolated results as files complete, without cancelling sibling work."""
    if max_workers < 1:
        raise ValueError("max_workers must be positive")
    progress_events: SimpleQueue[StatementProgress] = SimpleQueue()
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(uploads)))) as executor:
        futures: dict[Future[StatementResult], StatementUpload] = {
            executor.submit(processor, upload, llm_config, progress_events.put): upload
            for upload in uploads
        }
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
            while True:
                try:
                    event = progress_events.get_nowait()
                except Empty:
                    break
                if on_progress is not None:
                    on_progress(event)
            for future in done:
                upload = futures[future]
                try:
                    yield future.result()
                except Exception as exc:
                    yield StatementResult(
                        index=upload.index,
                        filename=upload.filename,
                        error=exc,
                    )

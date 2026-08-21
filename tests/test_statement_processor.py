import ssl
import threading
import time
import unittest

from libs.tools.retry import retry_transient
from libs.tools.statement_processor import (
    StatementProgress,
    StatementResult,
    StatementUpload,
    get_max_concurrent_statements,
    process_statements_concurrently,
)


class StatementProcessorTests(unittest.TestCase):
    def test_worker_configuration_defaults_and_validates(self):
        self.assertEqual(get_max_concurrent_statements(""), 2)
        self.assertEqual(get_max_concurrent_statements("3"), 3)
        for value in ("0", "-1", "two"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                get_max_concurrent_statements(value)

    def test_results_arrive_out_of_order_and_can_be_restored(self):
        uploads = [StatementUpload(i, f"{i}.pdf", b"pdf") for i in range(3)]

        def processor(upload, _config, _report_progress):
            time.sleep((2 - upload.index) * 0.02)
            return StatementResult(upload.index, upload.filename, object(), str(upload.index))

        completed = list(process_statements_concurrently(
            uploads, object(), max_workers=3, processor=processor
        ))
        self.assertNotEqual([result.index for result in completed], [0, 1, 2])
        ordered = sorted(completed, key=lambda result: result.index)
        self.assertEqual("".join(result.csv_rows for result in ordered), "012")

    def test_concurrency_is_bounded(self):
        lock = threading.Lock()
        active = 0
        maximum = 0

        def processor(upload, _config, _report_progress):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.03)
            with lock:
                active -= 1
            return StatementResult(upload.index, upload.filename, object(), "row")

        uploads = [StatementUpload(i, f"{i}.pdf", b"pdf") for i in range(6)]
        list(process_statements_concurrently(
            uploads, object(), max_workers=2, processor=processor
        ))
        self.assertEqual(maximum, 2)

    def test_worker_failure_does_not_cancel_successful_results(self):
        def processor(upload, _config, _report_progress):
            if upload.index == 1:
                raise ValueError("invalid statement")
            return StatementResult(upload.index, upload.filename, object(), "row")

        uploads = [StatementUpload(i, f"{i}.pdf", b"pdf") for i in range(3)]
        results = list(process_statements_concurrently(
            uploads, object(), max_workers=2, processor=processor
        ))
        self.assertEqual(sum(result.error is None for result in results), 2)
        self.assertEqual(sum(result.error is not None for result in results), 1)

    def test_progress_events_are_delivered_on_the_calling_thread(self):
        caller_thread = threading.get_ident()
        callback_threads = []
        stages = []

        def processor(upload, _config, report_progress):
            report_progress(StatementProgress(upload.index, upload.filename, "analyzing"))
            return StatementResult(upload.index, upload.filename, object(), "row")

        def record_progress(event):
            callback_threads.append(threading.get_ident())
            stages.append(event.stage)

        results = list(process_statements_concurrently(
            [StatementUpload(0, "statement.pdf", b"pdf")],
            object(),
            max_workers=1,
            processor=processor,
            on_progress=record_progress,
        ))

        self.assertEqual(len(results), 1)
        self.assertEqual(stages, ["analyzing"])
        self.assertEqual(callback_threads, [caller_thread])

    def test_all_failed_or_empty_results_are_preserved(self):
        results = [
            StatementResult(0, "failed.pdf", error=ValueError("bad")),
            StatementResult(1, "empty.pdf", statement=object(), csv_rows=""),
        ]
        self.assertFalse(any(result.csv_rows.strip() for result in results))

    def test_retries_transient_errors_with_exponential_backoff(self):
        attempts = 0
        delays = []

        def operation():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ssl.SSLError("temporary")
            return "ok"

        self.assertEqual(
            retry_transient(operation, initial_delay=0.5, sleep=delays.append),
            "ok",
        )
        self.assertEqual(delays, [0.5, 1.0])

    def test_retries_server_disconnect_three_total_attempts(self):
        class RemoteProtocolError(Exception):
            pass

        attempts = 0

        def operation():
            nonlocal attempts
            attempts += 1
            raise RemoteProtocolError(
                "Server disconnected without sending a response."
            )

        with self.assertRaises(RemoteProtocolError):
            retry_transient(operation, sleep=lambda _delay: None)
        self.assertEqual(attempts, 3)

    def test_does_not_retry_permanent_errors(self):
        attempts = 0

        def operation():
            nonlocal attempts
            attempts += 1
            raise ValueError("invalid configuration")

        with self.assertRaises(ValueError):
            retry_transient(operation, sleep=lambda _delay: None)
        self.assertEqual(attempts, 1)


if __name__ == "__main__":
    unittest.main()

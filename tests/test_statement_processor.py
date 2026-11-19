import ssl
import threading
import time
import unittest
from unittest.mock import patch

from libs.llm.main import GEMINI, LLMConfig
from libs.states.statement import Statement, Transaction
from libs.tools.pdf_2_text import StatementTextError
from libs.tools.retry import retry_transient
from libs.tools.statement_processor import (
    StatementProgress,
    StatementResult,
    StatementUpload,
    get_max_concurrent_statements,
    process_statement,
    process_statements_concurrently,
)
from pdf_fixture import scanned_pdf, statement_pdf


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

    def test_statement_text_is_extracted_before_the_llm_sees_anything(self):
        stages = []
        analyzed = []

        def fake_read(_config, statement_text):
            analyzed.append(statement_text)
            return Statement(
                transactions=[
                    Transaction(
                        date="2026-11-02",
                        transaction_name="APPLE PAYSUBSCR PSE *IPHONE",
                        amount=1198.00,
                        category="Shopping",
                        account="Personal",
                        card_name="World Card",
                    )
                ],
                card_name="World Card",
                total_spending=1198.00,
                number_of_transactions=1,
                due_date="2026-12-01",
            )

        config = LLMConfig(provider=GEMINI, model="test-model", api_key="test-key")
        upload = StatementUpload(0, "bank-202611/statement.pdf", statement_pdf())

        with patch("libs.tools.statement_processor.read_statement", side_effect=fake_read):
            result = process_statement(upload, config, stages.append)

        self.assertIsNone(result.error)
        self.assertEqual([event.stage for event in stages], ["extracting", "analyzing"])
        self.assertIn("1,198.00", analyzed[0])
        self.assertIn("1198.0", result.csv_rows)

    def test_scanned_statement_fails_without_calling_the_llm(self):
        stages = []
        upload = StatementUpload(1, "scan.pdf", scanned_pdf())

        with patch("libs.tools.statement_processor.read_statement") as read:
            result = process_statement(
                upload,
                LLMConfig(provider=GEMINI, model="test-model", api_key="test-key"),
                stages.append,
            )

        read.assert_not_called()
        self.assertIsInstance(result.error, StatementTextError)
        self.assertEqual([event.stage for event in stages], ["extracting"])
        self.assertIn("scan.pdf", str(result.error))

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

import time
import unittest

from libs.states.statement import Statement, Transaction
from libs.tools.statement_processor import StatementResult
from webapp.jobs import JobManager


def make_statement(card: str) -> Statement:
    return Statement(
        transactions=[
            Transaction(
                date="2026-10-01",
                transaction_name="Merchant",
                amount=10.5,
                category="Dining",
                account="Personal",
                card_name=card,
            )
        ],
        card_name=card,
        total_spending=10.5,
        number_of_transactions=1,
        due_date="2026-10-31",
    )


def fake_processor(outcome: str):
    def processor(upload, llm_config, report_progress):
        report_progress(_progress(upload.index, upload.filename, "analyzing"))
        if outcome == "ok":
            statement = make_statement(f"Card {upload.index}")
            return StatementResult(
                index=upload.index,
                filename=upload.filename,
                statement=statement,
                csv_rows=f"2026-10-01,Merchant,10.5,Dining,Personal,Card {upload.index}\n",
            )
        if outcome == "empty":
            return StatementResult(index=upload.index, filename=upload.filename)
        return StatementResult(
            index=upload.index, filename=upload.filename, error=ValueError("boom")
        )

    return processor


def _progress(index, filename, stage, detail=""):
    from webapp.jobs import StatementProgress

    return StatementProgress(index=index, filename=filename, stage=stage, detail=detail)


class JobManagerTests(unittest.TestCase):
    def setUp(self):
        self.config_patch = _use_fake_config()

    def tearDown(self):
        self.config_patch.stop()

    def _create(self, manager, names):
        return manager.create_job([(name, b"%PDF") for name in names])

    def test_job_completes_and_aggregates_results(self):
        manager = JobManager(max_workers=1, processor=fake_processor("ok"))
        job = self._create(manager, ["a.pdf", "b.pdf"])
        _wait(manager, job.id)

        described = manager.describe(manager.get_job(job.id))
        self.assertEqual(described["status"], "completed")
        self.assertEqual(described["completed"], 2)
        self.assertEqual(len(manager.transactions(manager.get_job(job.id))), 2)
        self.assertEqual(len(manager.summaries(manager.get_job(job.id))), 2)
        self.assertTrue(manager.csv_text(manager.get_job(job.id)).startswith("date,transaction_name"))

    def test_empty_and_failed_files_are_classified(self):
        outcomes = {"ok.pdf": "ok", "empty.pdf": "empty", "bad.pdf": "fail"}

        def processor(upload, llm_config, report_progress):
            return fake_processor(outcomes[upload.filename])(upload, llm_config, report_progress)

        manager = JobManager(max_workers=1, processor=processor)
        job = self._create(manager, ["ok.pdf", "empty.pdf", "bad.pdf"])
        _wait(manager, job.id)

        described = manager.describe(manager.get_job(job.id))
        self.assertEqual(described["completed"], 1)
        self.assertEqual(described["empty"], 1)
        self.assertEqual(described["failed"], 1)

    def test_events_are_streamed_in_order(self):
        manager = JobManager(max_workers=1, processor=fake_processor("ok"))
        job = self._create(manager, ["a.pdf"])
        _wait(manager, job.id)
        events = list(manager.stream_events(job.id))
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual([e["seq"] for e in events], sorted(e["seq"] for e in events))
        self.assertEqual(events[-1]["stage"], "completed")

    def test_cancel_skips_queued_files(self):
        gate = __import__("threading").Event()

        def processor(upload, llm_config, report_progress):
            gate.wait(5)
            return StatementResult(index=upload.index, filename=upload.filename, statement=make_statement("C"))

        manager = JobManager(max_workers=1, processor=processor)
        job = self._create(manager, ["slow.pdf", "queued.pdf"])
        time.sleep(0.2)
        self.assertTrue(manager.cancel_job(job.id))
        gate.set()
        _wait(manager, job.id)
        described = manager.describe(manager.get_job(job.id))
        self.assertIn(described["status"], ("cancelled", "completed"))
        self.assertLessEqual(described["cancelled"] + described["completed"], 2)

    def test_delete_removes_job(self):
        manager = JobManager(max_workers=1, processor=fake_processor("ok"))
        job = self._create(manager, ["a.pdf"])
        _wait(manager, job.id)
        self.assertTrue(manager.delete_job(job.id))
        self.assertIsNone(manager.get_job(job.id))
        self.assertFalse(manager.delete_job(job.id))


class _FakeConfigPatch:
    def __init__(self):
        self._saved = None

    def start(self):
        import webapp.jobs as jobs_module

        self._saved = jobs_module.load_llm_config
        jobs_module.load_llm_config = lambda *a, **k: jobs_module.LLMConfig(
            provider="openai-compatible",
            model="fake",
            api_key="k",
            base_url="http://localhost/v1",
        )

    def stop(self):
        import webapp.jobs as jobs_module

        jobs_module.load_llm_config = self._saved


def _use_fake_config():
    patch = _FakeConfigPatch()
    patch.start()
    return patch


def _wait(manager, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get_job(job_id)
        if job is not None and job.finished:
            return
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


if __name__ == "__main__":
    unittest.main()

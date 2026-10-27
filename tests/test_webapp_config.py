import os
import threading
import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from libs.tools.statement_processor import StatementResult
from webapp.app import app, config
from webapp.jobs import JobManager


class WebappEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = []
        self.processed = threading.Event()

        def processor(upload, config, report_progress):
            self.received.append(config)
            self.processed.set()
            return StatementResult(index=upload.index, filename=upload.filename)

        self.manager = JobManager(max_workers=1, processor=processor)
        self.environment = patch.dict(os.environ, {
            "OPENAI_BASE_URL": "http://default-server:8080/v1",
            "OPENAI_MODEL": "test-model",
            "OPENAI_API_KEY": "test-key",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.manager_patch = patch("webapp.app.manager", self.manager)
        self.manager_patch.start()
        self.addCleanup(self.manager_patch.stop)
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def submit(self, **params):
        return await self.client.post(
            "/api/jobs",
            params={"provider": "openai-compatible", **params},
            files={"files": ("statement.pdf", b"%PDF", "application/pdf")},
        )

    def test_config_exposes_environment_endpoint_default(self):
        defaults = config()["defaults"]["openai-compatible"]
        self.assertEqual(defaults["base_url"], "http://default-server:8080/v1")
        self.assertNotIn("api_key", defaults)

    async def test_job_endpoint_override_reaches_processor_without_changing_defaults(self):
        response = await self.submit(base_url="http://custom-server:8080/v1")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.processed.wait(2))
        self.assertEqual(self.received[0].base_url, "http://custom-server:8080/v1")
        self.assertEqual(self.received[0].api_key, "test-key")

        self.processed.clear()
        response = await self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.processed.wait(2))
        self.assertEqual(self.received[1].base_url, "http://default-server:8080/v1")

    async def test_invalid_endpoint_is_rejected_before_processing(self):
        for endpoint in ("", "localhost:8080/v1", "ftp://server/v1", "http://server:bad/v1"):
            with self.subTest(endpoint=endpoint):
                response = await self.submit(base_url=endpoint)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.manager.list_jobs(), [])


if __name__ == "__main__":
    unittest.main()

import json
import os
import threading
import unittest
from unittest.mock import Mock, patch

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
            params=params,
            files={"files": ("statement.pdf", b"%PDF", "application/pdf")},
        )

    def test_config_reports_configured_and_default_model_without_api_key(self):
        result = config()
        self.assertTrue(result["configured"])
        self.assertEqual(result["defaultModel"], "test-model")
        # The endpoint is env-only and the API key must never reach the browser.
        self.assertNotIn("test-key", json.dumps(result))

    async def test_job_model_override_reaches_processor(self):
        response = await self.submit(model="custom-model")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.processed.wait(2))
        self.assertEqual(self.received[0].model, "custom-model")
        # The endpoint still comes from the environment, never the request.
        self.assertEqual(self.received[0].base_url, "http://default-server:8080/v1")
        self.assertEqual(self.received[0].api_key, "test-key")

        self.processed.clear()
        response = await self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.processed.wait(2))
        # With no model supplied the configured default is used.
        self.assertEqual(self.received[1].model, "test-model")


class ModelsEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.environment = patch.dict(os.environ, {
            "OPENAI_BASE_URL": "http://default-server:8080/v1",
            "OPENAI_MODEL": "test-model",
            "OPENAI_API_KEY": "test-key",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_lists_models_from_endpoint_without_leaking_key(self):
        client = Mock()
        client.models.list.return_value = Mock(data=[Mock(id="m2"), Mock(id="m1")])
        with patch("libs.llm.main.OpenAI", return_value=client):
            response = await self.client.get("/api/models")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["models"], ["m1", "m2"])
        self.assertEqual(body["default"], "test-model")
        self.assertIsNone(body["error"])
        self.assertNotIn("test-key", response.text)

    async def test_lists_models_reports_endpoint_error(self):
        client = Mock()
        client.models.list.side_effect = RuntimeError("offline")
        with patch("libs.llm.main.OpenAI", return_value=client):
            response = await self.client.get("/api/models")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["models"], [])
        self.assertIn("offline", body["error"])
        self.assertEqual(body["default"], "test-model")


if __name__ == "__main__":
    unittest.main()

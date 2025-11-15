import json

from rest_framework import status
from rest_framework.test import APITestCase


class HealthEndpointTests(APITestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_structured_request_logging_emits_json(self):
        with self.assertLogs("app.request", level="INFO") as captured:
            self.client.get("/health/?foo=bar")

        self.assertGreaterEqual(len(captured.output), 1)
        message = captured.output[0].split(":", 2)[2].strip()
        payload = json.loads(message)

        self.assertEqual(payload["event"], "http.request")
        self.assertEqual(payload["path"], "/health/?foo=bar")
        self.assertEqual(payload["method"], "GET")

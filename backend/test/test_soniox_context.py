import asyncio
import json
import unittest

from config import SONIOX_CONFIG, SONIOX_TECH_TERMS
from backend.services.soniox_streaming import SonioxStreamingClient


class SonioxContextTests(unittest.TestCase):
    def test_tech_terms_are_large_unique_and_include_core_products(self):
        self.assertGreaterEqual(len(SONIOX_TECH_TERMS), 100)
        self.assertEqual(len(SONIOX_TECH_TERMS), len(set(SONIOX_TECH_TERMS)))
        self.assertTrue({"MySQL", "Redis", "RabbitMQ", "JVM"}.issubset(SONIOX_TECH_TERMS))

    def test_streaming_request_contains_soniox_context(self):
        class FakeWebSocket:
            def __init__(self):
                self.messages = []

            async def send(self, message):
                self.messages.append(message)

        client = SonioxStreamingClient(
            api_key="test-key",
            context=SONIOX_CONFIG["context"],
        )
        websocket = FakeWebSocket()
        client.ws = websocket

        asyncio.run(client.send_full_client_request())

        request = json.loads(websocket.messages[0])
        self.assertEqual(request["context"]["terms"], SONIOX_TECH_TERMS)
        self.assertEqual(request["context"]["general"][0], {
            "key": "domain",
            "value": "Computer science and software engineering",
        })


if __name__ == "__main__":
    unittest.main()

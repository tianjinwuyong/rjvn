import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "004-手动线"))
from station_product_gate import ProductGateClient, ProductGateUnavailable


class Response:
    def __init__(self, body): self.body = body
    def read(self): return json.dumps(self.body).encode("utf-8")


class ProductGateClientTests(unittest.TestCase):
    def client(self, opener):
        return ProductGateClient("http://mes", "manu_fct", "agent-1", "192.168.6.52", opener=opener)

    def request(self, client):
        return client.evaluate(identifier="PCB-1", operator_id="OP-1",
            occurred_at="2026-08-04T10:00:00+07:00", idempotency_key="evt-1")

    def test_allow_is_returned_only_from_explicit_mes_decision(self):
        result = self.request(self.client(lambda *_args, **_kwargs: Response({"replay": False,
            "decision": {"decisionId":"D1","gateState":"ALLOW","allowed":True,
                         "reasonCode":"PRODUCT_GATE_PASSED","nextAction":"START_STATION_WORK"}})))
        self.assertTrue(result.allowed)

    def test_http_409_is_a_valid_reject_decision(self):
        body = json.dumps({"decision":{"decisionId":"D2","gateState":"REJECT","allowed":False,
            "reasonCode":"MISSING_REQUIRED_STATION","nextAction":"RETURN_TO_MISSING_STATION"}}).encode()
        def reject(*_args, **_kwargs):
            raise urllib.error.HTTPError("http://mes", 409, "conflict", {}, io.BytesIO(body))
        result = self.request(self.client(reject))
        self.assertEqual("REJECT", result.gate_state)
        self.assertFalse(result.allowed)

    def test_network_or_invalid_response_never_allows(self):
        with self.assertRaises(ProductGateUnavailable):
            self.request(self.client(lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline"))))
        with self.assertRaises(ProductGateUnavailable):
            self.request(self.client(lambda *_args, **_kwargs: Response({"ok": True})))


if __name__ == "__main__": unittest.main()

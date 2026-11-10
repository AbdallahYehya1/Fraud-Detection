"""Request-contract tests: no database needed (connection dependency is overridden)."""
import pytest
from fastapi.testclient import TestClient

from fraudinv import api


class NoDb:
    def execute(self, *a, **k):
        raise AssertionError("validation must fail before any database access")


@pytest.fixture
def client():
    api.app.dependency_overrides[api.get_conn] = lambda: NoDb()
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


GOOD = {"step": 357, "type": "TRANSFER", "amount": "1500.25", "name_orig": "C123", "name_dest": "C456"}


@pytest.mark.parametrize("field,value", [
    ("isFraud", 1), ("isFlaggedFraud", 0), ("oldbalanceOrg", 100.0), ("newbalanceDest", 0.0),
    ("dest_prior_count", 3), ("dest_has_prior", 1), ("case_evidence_cutoff_step", 743), ("score", 0.9)])
def test_forbidden_transaction_fields_rejected(client, field, value):
    r = client.post("/score", json={"run_id": "r", "transaction": GOOD | {field: value}})
    assert r.status_code == 422 and "extra" in r.text.lower()


@pytest.mark.parametrize("field,value", [("isFraud", 1), ("evidence_cutoff_step", 800), ("model_version", "x")])
def test_forbidden_top_level_fields_rejected(client, field, value):
    r = client.post("/score", json={"run_id": "r", "transaction": GOOD, field: value})
    assert r.status_code == 422


@pytest.mark.parametrize("patch", [
    {"type": "WIRE"}, {"amount": "-1"}, {"amount": "1.001"}, {"amount": "NaN"}, {"amount": "Infinity"},
    {"step": 0}, {"step": 744}, {"name_dest": "X99"}, {"name_orig": "C1; DROP TABLE x"}])
def test_invalid_values_rejected(client, patch):
    r = client.post("/score", json={"run_id": "r", "transaction": GOOD | patch})
    assert r.status_code == 422


def test_missing_field_rejected(client):
    body = {k: v for k, v in GOOD.items() if k != "name_dest"}
    assert client.post("/score", json={"run_id": "r", "transaction": body}).status_code == 422


def test_model_info_has_no_labels(client):
    r = client.get("/model-info")
    if r.status_code != 200:
        pytest.skip("no frozen model in this checkout")
    text = r.text.lower()
    for name in ("isfraud", "isflaggedfraud", "oldbalance", "newbalance"):
        assert name not in text
    assert r.json()["score_semantics"].startswith("ranking score")

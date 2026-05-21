"""Tests for api/main.py."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import events_service
from api.backoffice_service import load_backoffice_config
from api.main import app, build_reason
from trainer.train import MODEL_PATH, load_dataframes

pytestmark = pytest.mark.skipif(
    not MODEL_PATH.is_file(),
    reason="trained model bundle not found",
)

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommendations_unknown_user():
    response = client.get("/recommendations/UNKNOWN")
    assert response.status_code == 404


def test_recommendations_retail_mobile():
    response = client.get(
        "/recommendations/u001",
        params={"segment": "retail", "channel": "mobile", "limit": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["userId"] == "U001"
    assert body["segment"] == "retail"
    assert body["preferredChannel"] == "mobile"
    assert len(body["recommendations"]) <= 3

    rec = body["recommendations"][0]
    assert rec["eligibility"] is True
    assert "reason" in rec
    assert rec["channel"] == "mobile"
    required = {
        "itemId",
        "title",
        "type",
        "scenario",
        "channel",
        "priority",
        "score",
        "reason",
        "eligibility",
        "action",
    }
    assert required.issubset(rec.keys())


def test_push_adoption_suppressed_for_user_with_push_enabled():
    response = client.get(
        "/recommendations/U001",
        params={"segment": "retail", "channel": "mobile", "limit": 10},
    )
    item_ids = {rec["itemId"] for rec in response.json()["recommendations"]}
    assert "I004" not in item_ids


def test_recommendations_sorted_by_score_then_priority():
    response = client.get(
        "/recommendations/U001",
        params={"segment": "retail", "channel": "mobile", "limit": 5},
    )
    recs = response.json()["recommendations"]
    if len(recs) < 2:
        pytest.skip("not enough recommendations to verify ordering")
    for left, right in zip(recs, recs[1:]):
        assert left["score"] >= right["score"]


def test_build_reason_known_scenario():
    assert "savings" in build_reason("savings_goal").lower()


def test_build_reason_unknown_scenario():
    reason = build_reason("custom_scenario")
    assert "custom scenario" in reason.lower()


@pytest.fixture
def interactions_file(tmp_path: Path, monkeypatch):
    _, _, interactions = load_dataframes()
    path = tmp_path / "interactions.csv"
    interactions.to_csv(path, index=False)
    monkeypatch.setattr(events_service, "INTERACTIONS_PATH", path)
    return path


def test_post_events_stores_interaction(interactions_file: Path):
    response = client.post(
        "/events",
        json={"userId": "U001", "itemId": "I002", "event": "click"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event"]["userId"] == "U001"
    assert body["event"]["itemId"] == "I002"
    assert body["event"]["event"] == "click"
    assert body["event"]["weight"] == 3
    assert "retrain" in body["message"].lower()

    df = pd.read_csv(interactions_file)
    assert df.iloc[-1]["event"] == "click"
    assert df.iloc[-1]["weight"] == 3


def test_post_events_invalid_event(interactions_file: Path):
    response = client.post(
        "/events",
        json={"userId": "U001", "itemId": "I001", "event": "purchase"},
    )
    assert response.status_code == 400


def test_post_events_unknown_user(interactions_file: Path):
    response = client.post(
        "/events",
        json={"userId": "UNKNOWN", "itemId": "I001", "event": "view"},
    )
    assert response.status_code == 404


def test_backoffice_config_endpoint():
    response = client.get("/backoffice/config")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.2.0"
    assert "scenarios" in body
    assert "channels" in body
    assert "frequencyCaps" in body
    assert "allowedItemTypes" in body
    assert "eventWeights" in body
    assert body["eventWeights"]["conversion"] == 5
    assert len(body["demoUsers"]) == 3
    segments = {user["segment"] for user in body["demoUsers"]}
    assert segments == {"retail", "pyme", "corporate"}


def test_load_backoffice_config_from_file():
    config = load_backoffice_config()
    assert "financial_insight" in config["allowedItemTypes"]


def test_backoffice_config_missing_file(tmp_path, monkeypatch):
    from api import backoffice_service

    missing = tmp_path / "missing.json"
    monkeypatch.setattr(backoffice_service, "BACKOFFICE_CONFIG_PATH", missing)
    monkeypatch.setattr(
        "api.main.get_backoffice_config",
        lambda: load_backoffice_config(missing),
    )
    response = client.get("/backoffice/config")
    assert response.status_code == 503

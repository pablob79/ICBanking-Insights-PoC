"""Tests for api/events_service.py."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from api.events_service import (
    EVENT_WEIGHTS,
    InvalidEventError,
    ItemNotFoundError,
    append_event,
    normalize_event,
)
from trainer.recommend import UserNotFoundError
from trainer.train import load_dataframes


@pytest.fixture
def interactions_file(tmp_path: Path) -> Path:
    _, _, interactions = load_dataframes()
    path = tmp_path / "interactions.csv"
    interactions.to_csv(path, index=False)
    return path


def test_normalize_event_rejects_unknown():
    with pytest.raises(InvalidEventError, match="Invalid event"):
        normalize_event("purchase")


def test_normalize_event_accepts_allowed_values():
    assert normalize_event("CLICK") == "click"


def test_append_event_writes_row_with_weight(interactions_file: Path):
    ts = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)
    stored = append_event(
        "u001",
        "i001",
        "conversion",
        interactions_path=interactions_file,
        timestamp=ts,
    )

    assert stored["userId"] == "U001"
    assert stored["itemId"] == "I001"
    assert stored["event"] == "conversion"
    assert stored["weight"] == EVENT_WEIGHTS["conversion"]
    assert stored["channel"] == "mobile"
    assert stored["timestamp"] == "2026-05-21T12:00:00Z"

    df = pd.read_csv(interactions_file)
    last = df.iloc[-1]
    assert last["interaction_id"] == stored["interactionId"]
    assert last["weight"] == 5


def test_append_event_unknown_user(interactions_file: Path):
    with pytest.raises(UserNotFoundError):
        append_event("UNKNOWN", "I001", "view", interactions_path=interactions_file)


def test_append_event_unknown_item(interactions_file: Path):
    with pytest.raises(ItemNotFoundError):
        append_event("U001", "I999", "view", interactions_path=interactions_file)


@pytest.mark.parametrize("event,expected_weight", list(EVENT_WEIGHTS.items()))
def test_event_weights(event: str, expected_weight: int, interactions_file: Path):
    stored = append_event(
        "U002",
        "I002",
        event,
        interactions_path=interactions_file,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert stored["weight"] == expected_weight

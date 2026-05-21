"""Tests for trainer/recommend.py."""

from pathlib import Path

import pandas as pd
import pytest

from trainer.recommend import (
    ModelNotFoundError,
    UserNotFoundError,
    filter_candidate_items,
    load_bundle,
    recommend,
    resolve_user_id,
)
from trainer.train import MODEL_PATH, load_dataframes

pytestmark = pytest.mark.skipif(
    not MODEL_PATH.is_file(),
    reason="trained model bundle not found",
)


def test_load_bundle_reads_trained_model():
    bundle = load_bundle()
    assert "model" in bundle
    assert "dataset" in bundle
    assert len(bundle["users"]) == 15


def test_load_bundle_raises_when_missing(tmp_path):
    with pytest.raises(ModelNotFoundError, match="Missing model bundle"):
        load_bundle(tmp_path / "missing.pkl")


def test_resolve_user_id_is_case_insensitive():
    users = pd.DataFrame({"user_id": ["U001", "U002"]})
    assert resolve_user_id("u001", users) == "U001"


def test_recommend_unknown_user_raises():
    bundle = load_bundle()
    with pytest.raises(UserNotFoundError, match="Unknown user_id"):
        recommend("UNKNOWN", bundle=bundle)


def test_filter_candidate_items_by_segment_and_channel():
    _, items, _ = load_dataframes()
    filtered = filter_candidate_items(items, segment="corporate", channel="web")
    assert len(filtered) >= 5
    for _, row in filtered.iterrows():
        assert "web" in str(row["channels"])


def test_recommend_returns_required_fields():
    recs = recommend("U001", segment="retail", channel="mobile", limit=3)
    assert 1 <= len(recs) <= 3
    required = {
        "itemId",
        "title",
        "type",
        "scenario",
        "channel",
        "priority",
        "score",
        "action",
    }
    assert required.issubset(recs[0].keys())
    assert recs[0]["channel"] == "mobile"
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_recommend_main_scenarios():
    recs_retail = recommend("u001", segment="retail", channel="mobile", limit=5)
    assert recs_retail
    recs_pyme = recommend("u004", segment="pyme", channel="web", limit=5)
    assert all("web" in r["channel"] or r["channel"] == "web" for r in recs_pyme)
    recs_corp = recommend("u007", segment="corporate", channel="web", limit=5)
    assert recs_corp

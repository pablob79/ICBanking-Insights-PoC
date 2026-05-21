"""Tests for trainer/train.py."""

from pathlib import Path

import pandas as pd
import pytest

from trainer.train import (
    DataLoadError,
    aggregate_interactions,
    bucket_manual_transfers,
    bucket_priority,
    build_item_features_list,
    build_user_features_list,
    item_feature_tags,
    load_dataframes,
    user_feature_tags,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def test_load_dataframes_reads_synthetic_csvs():
    users, items, interactions = load_dataframes()
    assert len(users) == 15
    assert len(items) == 24
    assert len(interactions) >= 45


def test_load_dataframes_raises_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("trainer.train.DATA_DIR", tmp_path)
    with pytest.raises(DataLoadError, match="Missing required data file"):
        load_dataframes()


def test_user_feature_tags_include_buckets():
    row = pd.Series(
        {
            "segment": "retail",
            "country": "AR",
            "preferred_channel": "mobile",
            "uses_mobile_app": True,
            "uses_web": False,
            "has_push_enabled": True,
            "has_mfa_enabled": False,
            "manual_transfers_month": 25,
        }
    )
    tags = user_feature_tags(row)
    assert "manual_transfers_month:high" in tags
    assert "has_mfa_enabled:False" in tags


def test_item_feature_tags_include_segment_channel_priority():
    row = pd.Series(
        {
            "type": "product_offer",
            "segments": "pyme",
            "scenario": "collections",
            "channels": "mobile,web",
            "priority_base": 82,
        }
    )
    tags = item_feature_tags(row)
    assert "segment:pyme" in tags
    assert "channel:mobile" in tags
    assert "channel:web" in tags
    assert "priority:high" in tags


def test_bucket_helpers():
    assert bucket_manual_transfers(3) == "low"
    assert bucket_manual_transfers(10) == "medium"
    assert bucket_manual_transfers(30) == "high"
    assert bucket_priority(50) == "low"
    assert bucket_priority(70) == "medium"
    assert bucket_priority(90) == "high"


def test_aggregate_interactions_sums_and_filters_non_positive():
    df = pd.DataFrame(
        {
            "user_id": ["U1", "U1", "U2"],
            "item_id": ["I1", "I1", "I2"],
            "weight": [0.5, -0.3, 1.0],
        }
    )
    result = aggregate_interactions(df)
    assert len(result) == 2
    assert result.loc[result["user_id"] == "U1", "weight"].iloc[0] == pytest.approx(0.2)


def test_build_feature_lists_from_real_data():
    users, items, _ = load_dataframes()
    user_feats = build_user_features_list(users)
    item_feats = build_item_features_list(items)
    assert len(user_feats) == len(users)
    assert len(item_feats) == len(items)
    assert all(len(tags) >= 8 for _, tags in user_feats)

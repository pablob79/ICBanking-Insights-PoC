"""Score and rank items for a user with a trained LightFM model."""

from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Any

# Allow `python trainer/recommend.py` from the project root (not only -m).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np
import pandas as pd

from trainer.train import MODEL_PATH, bucket_priority

DEFAULT_ACTION_BY_TYPE = {
    "financial_insight": "view_detail",
    "product_offer": "apply",
    "adoption_action": "activate",
    "security_recommendation": "review",
    "operational_recommendation": "open",
    "novelty": "learn_more",
}


class ModelNotFoundError(FileNotFoundError):
    """Raised when the trained model bundle is missing."""


class UserNotFoundError(ValueError):
    """Raised when user_id is not in the training users table."""


def load_bundle(path: Path | None = None) -> dict[str, Any]:
    model_path = path or MODEL_PATH
    if not model_path.is_file():
        raise ModelNotFoundError(
            f"Missing model bundle: {model_path}. Run trainer/train.py first."
        )
    with model_path.open("rb") as fh:
        return pickle.load(fh)


def resolve_user_id(user_id: str, users: pd.DataFrame) -> str:
    lookup = {str(uid).lower(): uid for uid in users["user_id"]}
    key = str(user_id).lower()
    if key not in lookup:
        raise UserNotFoundError(f"Unknown user_id: {user_id}")
    return lookup[key]


def _item_segment(row: pd.Series) -> str:
    return str(row["segments"]).strip().strip('"')


def _item_channels(row: pd.Series) -> list[str]:
    return [c.strip() for c in str(row["channels"]).split(",") if c.strip()]


def filter_candidate_items(
    items: pd.DataFrame,
    *,
    segment: str | None = None,
    channel: str | None = None,
) -> pd.DataFrame:
    candidates = items.copy()
    if segment is not None:
        segment = segment.strip().lower()
        candidates = candidates[
            candidates.apply(lambda row: _item_segment(row) == segment, axis=1)
        ]
    if channel is not None:
        channel = channel.strip().lower()
        candidates = candidates[
            candidates.apply(lambda row: channel in _item_channels(row), axis=1)
        ]
    return candidates.reset_index(drop=True)


def item_action(item_type: str, scenario: str) -> str:
    base = DEFAULT_ACTION_BY_TYPE.get(item_type, "view")
    if item_type == "adoption_action" and scenario in {"notifications", "autopay"}:
        return "activate"
    if item_type == "product_offer" and scenario == "lending":
        return "apply"
    return base


def recommend(
    user_id: str,
    segment: str | None = None,
    channel: str | None = None,
    limit: int = 5,
    *,
    bundle: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return top item recommendations for a user, sorted by LightFM score."""
    if limit < 1:
        raise ValueError("limit must be at least 1")

    bundle = bundle or load_bundle()
    model = bundle["model"]
    dataset = bundle["dataset"]
    user_features_matrix = bundle["user_features"]
    item_features_matrix = bundle["item_features"]
    users: pd.DataFrame = bundle["users"]
    items: pd.DataFrame = bundle["items"]

    canonical_user_id = resolve_user_id(user_id, users)
    candidates = filter_candidate_items(items, segment=segment, channel=channel)
    if candidates.empty:
        return []

    user_id_map, _, item_id_map, _ = dataset.mapping()
    if canonical_user_id not in user_id_map:
        raise UserNotFoundError(f"User {canonical_user_id} was not seen during training.")

    user_internal_id = user_id_map[canonical_user_id]
    candidate_item_ids = candidates["item_id"].tolist()
    item_internal_ids = np.array(
        [item_id_map[item_id] for item_id in candidate_item_ids],
        dtype=np.int32,
    )

    scores = model.predict(
        user_internal_id,
        item_internal_ids,
        user_features=user_features_matrix,
        item_features=item_features_matrix,
    )

    scored = candidates.copy()
    scored["score"] = scores
    scored = scored.sort_values("score", ascending=False)

    response_channel = channel.strip().lower() if channel else None
    recommendations: list[dict[str, Any]] = []
    for _, row in scored.iterrows():
        item_channels = _item_channels(row)
        recommendations.append(
            {
                "itemId": row["item_id"],
                "title": row["title"],
                "type": row["type"],
                "scenario": row["scenario"],
                "channel": response_channel or item_channels[0],
                "priority": bucket_priority(row["priority_base"]),
                "priority_base": int(row["priority_base"]),
                "score": float(row["score"]),
                "action": item_action(row["type"], row["scenario"]),
            }
        )
    return recommendations[:limit]


def _print_sample(user_id: str, segment: str, channel: str, limit: int = 5) -> None:
    print(f"\n--- {user_id} | segment={segment} | channel={channel} ---")
    recs = recommend(user_id, segment=segment, channel=channel, limit=limit)
    if not recs:
        print("(no recommendations)")
        return
    for rec in recs:
        print(
            f"  {rec['itemId']} score={rec['score']:.4f} "
            f"[{rec['type']}] {rec['title']} -> {rec['action']}"
        )


if __name__ == "__main__":
    _print_sample("u001", "retail", "mobile")
    _print_sample("u004", "pyme", "web")
    _print_sample("u007", "corporate", "web")

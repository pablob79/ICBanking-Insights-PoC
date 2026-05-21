"""Append interaction events to the synthetic interactions dataset."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from trainer.recommend import UserNotFoundError, resolve_user_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INTERACTIONS_PATH = PROJECT_ROOT / "data" / "interactions.csv"
USERS_PATH = PROJECT_ROOT / "data" / "users.csv"
ITEMS_PATH = PROJECT_ROOT / "data" / "items.csv"

ALLOWED_EVENTS = frozenset(
    {"view", "click", "start_flow", "conversion", "dismiss", "not_interested"}
)

EVENT_WEIGHTS: dict[str, int] = {
    "view": 1,
    "click": 3,
    "start_flow": 4,
    "conversion": 5,
    "dismiss": -1,
    "not_interested": -3,
}

RETRAIN_MESSAGE = (
    "Event stored successfully. Retraining is not automatic; "
    "run `python trainer/train.py` separately to refresh the model."
)


class InteractionsFileError(FileNotFoundError):
    """Raised when interactions.csv is missing."""


class ItemNotFoundError(ValueError):
    """Raised when item_id is not in the items catalog."""


class InvalidEventError(ValueError):
    """Raised when event type is not allowed."""


def _load_users() -> pd.DataFrame:
    if not USERS_PATH.is_file():
        raise FileNotFoundError(f"Missing users file: {USERS_PATH}")
    return pd.read_csv(USERS_PATH)


def _load_items() -> pd.DataFrame:
    if not ITEMS_PATH.is_file():
        raise FileNotFoundError(f"Missing items file: {ITEMS_PATH}")
    return pd.read_csv(ITEMS_PATH)


def resolve_item_id(item_id: str, items: pd.DataFrame) -> str:
    lookup = {str(iid).lower(): iid for iid in items["item_id"]}
    key = str(item_id).lower()
    if key not in lookup:
        raise ItemNotFoundError(f"Unknown item_id: {item_id}")
    return lookup[key]


def normalize_event(event: str) -> str:
    normalized = str(event).strip().lower()
    if normalized not in ALLOWED_EVENTS:
        allowed = ", ".join(sorted(ALLOWED_EVENTS))
        raise InvalidEventError(
            f"Invalid event '{event}'. Allowed values: {allowed}."
        )
    return normalized


def _next_interaction_id(interactions: pd.DataFrame) -> str:
    numeric = (
        interactions["interaction_id"]
        .astype(str)
        .str.replace("INT", "", regex=False)
        .astype(int)
    )
    return f"INT{numeric.max() + 1:03d}"


def append_event(
    user_id: str,
    item_id: str,
    event: str,
    *,
    interactions_path: Path | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Validate and append one interaction row to interactions.csv."""
    path = interactions_path or INTERACTIONS_PATH
    if not path.is_file():
        raise InteractionsFileError(f"Missing interactions file: {path}")

    normalized_event = normalize_event(event)
    users = _load_users()
    items = _load_items()

    canonical_user_id = resolve_user_id(user_id, users)
    canonical_item_id = resolve_item_id(item_id, items)

    user_row = users.loc[users["user_id"] == canonical_user_id].iloc[0]
    channel = str(user_row["preferred_channel"]).strip().lower()
    weight = EVENT_WEIGHTS[normalized_event]
    ts = timestamp or datetime.now(timezone.utc)
    timestamp_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    interactions = pd.read_csv(path)
    interaction_id = _next_interaction_id(interactions)

    stored = {
        "interactionId": interaction_id,
        "userId": canonical_user_id,
        "itemId": canonical_item_id,
        "event": normalized_event,
        "channel": channel,
        "timestamp": timestamp_str,
        "weight": weight,
    }

    new_row = pd.DataFrame(
        [
            {
                "interaction_id": interaction_id,
                "user_id": canonical_user_id,
                "item_id": canonical_item_id,
                "event": normalized_event,
                "channel": channel,
                "timestamp": timestamp_str,
                "weight": weight,
            }
        ]
    )
    pd.concat([interactions, new_row], ignore_index=True).to_csv(path, index=False)
    return stored

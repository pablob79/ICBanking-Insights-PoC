"""Train a LightFM model from synthetic banking interaction data."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from lightfm import LightFM
    from lightfm.data import Dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "lightfm_model.pkl"

REQUIRED_FILES = ("users.csv", "items.csv", "interactions.csv")

USER_FEATURE_COLUMNS = (
    "segment",
    "country",
    "preferred_channel",
    "uses_mobile_app",
    "uses_web",
    "has_push_enabled",
    "has_mfa_enabled",
    "manual_transfers_month",
)

ITEM_RAW_COLUMNS = ("type", "segments", "scenario", "channels", "priority_base")


class DataLoadError(FileNotFoundError):
    """Raised when required CSV inputs are missing."""


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise DataLoadError(f"Missing required data file: {path}")


def load_dataframes() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load users, items and interactions CSVs from data/."""
    missing = [name for name in REQUIRED_FILES if not (DATA_DIR / name).is_file()]
    if missing:
        paths = ", ".join(str(DATA_DIR / name) for name in missing)
        raise DataLoadError(f"Missing required data file(s): {paths}")

    users = pd.read_csv(DATA_DIR / "users.csv")
    items = pd.read_csv(DATA_DIR / "items.csv")
    interactions = pd.read_csv(DATA_DIR / "interactions.csv")
    return users, items, interactions


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def bucket_manual_transfers(count: int | float) -> str:
    count = int(count)
    if count <= 5:
        return "low"
    if count <= 20:
        return "medium"
    return "high"


def bucket_priority(priority: int | float) -> str:
    priority = int(priority)
    if priority < 60:
        return "low"
    if priority < 80:
        return "medium"
    return "high"


def user_feature_tags(row: pd.Series) -> list[str]:
    tags = [
        f"segment:{row['segment']}",
        f"country:{row['country']}",
        f"preferred_channel:{row['preferred_channel']}",
        f"uses_mobile_app:{_parse_bool(row['uses_mobile_app'])}",
        f"uses_web:{_parse_bool(row['uses_web'])}",
        f"has_push_enabled:{_parse_bool(row['has_push_enabled'])}",
        f"has_mfa_enabled:{_parse_bool(row['has_mfa_enabled'])}",
        f"manual_transfers_month:{bucket_manual_transfers(row['manual_transfers_month'])}",
    ]
    return tags


def item_feature_tags(row: pd.Series) -> list[str]:
    segment = str(row["segments"]).strip().strip('"')
    channels = [c.strip() for c in str(row["channels"]).split(",")]
    tags = [
        f"type:{row['type']}",
        f"segment:{segment}",
        f"scenario:{row['scenario']}",
        f"priority:{bucket_priority(row['priority_base'])}",
    ]
    tags.extend(f"channel:{channel}" for channel in channels if channel)
    return tags


def build_user_features_list(users: pd.DataFrame) -> list[tuple[str, list[str]]]:
    missing = [c for c in USER_FEATURE_COLUMNS if c not in users.columns]
    if missing:
        raise ValueError(f"users.csv is missing columns: {', '.join(missing)}")
    return [
        (row["user_id"], user_feature_tags(row))
        for _, row in users.iterrows()
    ]


def build_item_features_list(items: pd.DataFrame) -> list[tuple[str, list[str]]]:
    missing = [c for c in ITEM_RAW_COLUMNS if c not in items.columns]
    if missing:
        raise ValueError(f"items.csv is missing columns: {', '.join(missing)}")
    return [
        (row["item_id"], item_feature_tags(row))
        for _, row in items.iterrows()
    ]


def aggregate_interactions(interactions: pd.DataFrame) -> pd.DataFrame:
    """Sum weights per user-item pair; keep pairs with positive net weight."""
    required = {"user_id", "item_id", "weight"}
    if not required.issubset(interactions.columns):
        missing = required - set(interactions.columns)
        raise ValueError(f"interactions.csv is missing columns: {', '.join(sorted(missing))}")

    aggregated = (
        interactions.groupby(["user_id", "item_id"], as_index=False)["weight"]
        .sum()
        .query("weight > 0")
    )
    if aggregated.empty:
        raise ValueError("No positive-weight interactions found for training.")
    return aggregated


def build_dataset(
    users: pd.DataFrame,
    items: pd.DataFrame,
    user_features: list[tuple[str, list[str]]],
    item_features: list[tuple[str, list[str]]],
) -> Any:
    from lightfm.data import Dataset

    dataset = Dataset()
    all_user_tags = {tag for _, tags in user_features for tag in tags}
    all_item_tags = {tag for _, tags in item_features for tag in tags}
    dataset.fit(
        users["user_id"].tolist(),
        items["item_id"].tolist(),
        user_features=all_user_tags,
        item_features=all_item_tags,
    )
    return dataset


def build_interaction_matrix(
    dataset: Any,
    aggregated: pd.DataFrame,
) -> tuple:
    interaction_tuples = [
        (row["user_id"], row["item_id"], float(row["weight"]))
        for _, row in aggregated.iterrows()
    ]
    return dataset.build_interactions(interaction_tuples)


def train_model(
    interactions_matrix,
    user_features_matrix,
    item_features_matrix,
    *,
    epochs: int = 30,
    num_threads: int = 2,
) -> Any:
    from lightfm import LightFM

    model = LightFM(loss="warp")
    model.fit(
        interactions_matrix,
        user_features=user_features_matrix,
        item_features=item_features_matrix,
        epochs=epochs,
        num_threads=num_threads,
    )
    return model


def save_bundle(
    path: Path,
    *,
    model: Any,
    dataset: Any,
    user_features_matrix,
    item_features_matrix,
    users: pd.DataFrame,
    items: pd.DataFrame,
    interactions: pd.DataFrame,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": model,
        "dataset": dataset,
        "user_features": user_features_matrix,
        "item_features": item_features_matrix,
        "users": users,
        "items": items,
        "interactions": interactions,
    }
    with path.open("wb") as fh:
        pickle.dump(bundle, fh)


def main() -> Path:
    users, items, interactions = load_dataframes()
    user_features = build_user_features_list(users)
    item_features = build_item_features_list(items)
    aggregated = aggregate_interactions(interactions)

    dataset = build_dataset(users, items, user_features, item_features)
    user_features_matrix = dataset.build_user_features(user_features)
    item_features_matrix = dataset.build_item_features(item_features)
    interactions_matrix, _ = build_interaction_matrix(dataset, aggregated)

    model = train_model(
        interactions_matrix,
        user_features_matrix,
        item_features_matrix,
    )
    save_bundle(
        MODEL_PATH,
        model=model,
        dataset=dataset,
        user_features_matrix=user_features_matrix,
        item_features_matrix=item_features_matrix,
        users=users,
        items=items,
        interactions=interactions,
    )
    return MODEL_PATH


if __name__ == "__main__":
    output = main()
    print(f"Model saved to {output}")

"""FastAPI application for ICBanking Insights recommendations."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from api.backoffice_service import (
    BackOfficeConfigError,
    BackOfficeConfigNotFoundError,
    load_backoffice_config,
)
from api.events_service import (
    RETRAIN_MESSAGE,
    InteractionsFileError,
    InvalidEventError,
    ItemNotFoundError,
    append_event,
)
from api.rules_service import is_eligible
from trainer.recommend import (
    ModelNotFoundError,
    UserNotFoundError,
    filter_candidate_items,
    load_bundle,
    recommend,
    resolve_user_id,
)

PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}

SCENARIO_REASONS: dict[str, str] = {
    "savings_goal": "You may benefit from automating savings toward your goals.",
    "spending_alert": "We noticed a change in your spending pattern worth reviewing.",
    "lending": "You have a pre-approved lending option based on your profile.",
    "notifications": "Real-time alerts can help you stay on top of account activity.",
    "access_review": "Review recent sign-ins to keep your account secure.",
    "payments": "A new payment option is available for your day-to-day transactions.",
    "cash_management": "You could earn more by putting idle balances to work.",
    "invoicing": "Simplify tax invoicing from your digital banking channel.",
    "collections": "Collect payments faster with a shareable payment link.",
    "duplicate_payments": "We flagged possible duplicate supplier payments.",
    "payroll": "Digital payroll can reduce manual work for your business.",
    "credentials": "Rotating operator credentials reduces security risk.",
    "working_capital": "Working capital financing may fit your business needs.",
    "reconciliation": "Reconciling with your ERP can save operational time.",
    "portal_update": "Your administrator portal has new capabilities to explore.",
    "bulk_payments": "High transfer volume makes bulk payments a good fit.",
    "liquidity": "Short-term liquidity options are available for treasury balances.",
    "fx": "Current FX conditions may favor your import payments.",
    "signers": "Signer permissions should be reviewed for compliance.",
    "api_integration": "API integration can streamline payments from your ERP.",
    "esg_reporting": "ESG reporting is now available for corporate clients.",
    "autopay": "Automatic bill pay reduces missed due dates.",
    "relationship": "Your business may benefit from a dedicated relationship review.",
    "limits": "Operational limits are approaching expiry and may need renewal.",
}


def build_reason(scenario: str) -> str:
    key = str(scenario).strip().lower()
    if key in SCENARIO_REASONS:
        return SCENARIO_REASONS[key]
    label = key.replace("_", " ")
    return f"Recommended for your profile based on the {label} scenario."


@lru_cache
def get_bundle() -> dict[str, Any]:
    return load_bundle()


@lru_cache
def get_backoffice_config() -> dict[str, Any]:
    return load_backoffice_config()


def _user_row_to_dict(row: Any) -> dict[str, Any]:
    data = row.to_dict()
    for key in ("uses_mobile_app", "uses_web", "has_push_enabled", "has_mfa_enabled"):
        if key in data:
            value = data[key]
            if isinstance(value, str):
                data[key] = value.strip().lower() == "true"
    return data


def _item_row_to_dict(row: Any, channel: str | None, *, item_id: str) -> dict[str, Any]:
    channels = [c.strip() for c in str(row["channels"]).split(",") if c.strip()]
    response_channel = (channel or channels[0]).strip().lower()
    return {
        "itemId": item_id,
        "segment": str(row["segments"]).strip().strip('"'),
        "segments": row["segments"],
        "channel": response_channel,
        "channels": row["channels"],
        "type": row["type"],
        "scenario": row["scenario"],
        "title": row["title"],
        "priority_base": int(row["priority_base"]),
    }


def _sort_key(rec: dict[str, Any]) -> tuple[float, int, int]:
    priority_rank = PRIORITY_ORDER.get(str(rec.get("priority", "")).lower(), 0)
    return (-float(rec["score"]), -int(rec.get("priority_base", 0)), -priority_rank)


app = FastAPI(
    title="ICBanking Insights PoC",
    description="Synthetic recommendations API with LightFM and business rules.",
    version="0.1.0",
)


class EventRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    itemId: str = Field(..., min_length=1)
    event: str = Field(..., min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/recommendations/{user_id}")
def get_recommendations(
    user_id: str,
    segment: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    try:
        bundle = get_bundle()
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    users = bundle["users"]
    items = bundle["items"]

    try:
        canonical_user_id = resolve_user_id(user_id, users)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    user_row = users.loc[users["user_id"] == canonical_user_id].iloc[0]
    user_dict = _user_row_to_dict(user_row)

    segment_filter = segment.strip().lower() if segment else None
    channel_filter = channel.strip().lower() if channel else None

    candidates = filter_candidate_items(
        items, segment=segment_filter, channel=channel_filter
    )
    if candidates.empty:
        return {
            "userId": canonical_user_id,
            "segment": segment_filter or str(user_row["segment"]),
            "preferredChannel": str(user_row["preferred_channel"]),
            "recommendations": [],
        }

    try:
        scored = recommend(
            canonical_user_id,
            segment=segment_filter,
            channel=channel_filter,
            limit=len(candidates),
            bundle=bundle,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    eligible_recommendations: list[dict[str, Any]] = []

    for rec in scored:
        item_row = items.loc[items["item_id"] == rec["itemId"]].iloc[0]
        item_dict = _item_row_to_dict(item_row, rec["channel"], item_id=rec["itemId"])
        ok, _ = is_eligible(user_dict, item_dict)
        if not ok:
            continue

        eligible_recommendations.append(
            {
                "itemId": rec["itemId"],
                "title": rec["title"],
                "type": rec["type"],
                "scenario": rec["scenario"],
                "channel": rec["channel"],
                "priority": rec["priority"],
                "priority_base": rec.get("priority_base", int(item_row["priority_base"])),
                "score": rec["score"],
                "reason": build_reason(rec["scenario"]),
                "eligibility": True,
                "action": rec["action"],
            }
        )

    eligible_recommendations.sort(key=_sort_key)
    recommendations = [
        {k: v for k, v in rec.items() if k != "priority_base"}
        for rec in eligible_recommendations[:limit]
    ]

    response_segment = segment_filter or str(user_row["segment"])
    return {
        "userId": canonical_user_id,
        "segment": response_segment,
        "preferredChannel": str(user_row["preferred_channel"]),
        "recommendations": recommendations,
    }


@app.get("/backoffice/config")
def get_backoffice_settings() -> dict[str, Any]:
    try:
        return get_backoffice_config()
    except BackOfficeConfigNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BackOfficeConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/events")
def track_event(body: EventRequest) -> dict[str, Any]:
    try:
        stored = append_event(body.userId, body.itemId, body.event)
    except InvalidEventError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InteractionsFileError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "event": stored,
        "message": RETRAIN_MESSAGE,
    }


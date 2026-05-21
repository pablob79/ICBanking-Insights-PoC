"""Business eligibility rules (segment, channel, product flags)."""

from __future__ import annotations

from typing import Any

PUSH_NOTIFICATION_SCENARIO = "notifications"
MFA_SECURITY_SCENARIO = "mfa"
MASS_PAYMENTS_SCENARIO = "bulk_payments"

ADOPTION_TYPE = "adoption_action"


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _normalize_segment(value: Any) -> str:
    return str(value or "").strip().strip('"').lower()


def _item_segment(item: dict[str, Any]) -> str:
    return _normalize_segment(item.get("segment") or item.get("segments"))


def _item_channel(item: dict[str, Any]) -> str:
    if item.get("channel"):
        return str(item["channel"]).strip().lower()
    channels = str(item.get("channels", "")).strip().lower()
    if not channels:
        return ""
    return channels.split(",")[0].strip()


def _item_type(item: dict[str, Any]) -> str:
    return str(item.get("type", "")).strip().lower()


def _item_scenario(item: dict[str, Any]) -> str:
    return str(item.get("scenario", "")).strip().lower()


def is_push_notification_adoption(item: dict[str, Any]) -> bool:
    return (
        _item_type(item) == ADOPTION_TYPE
        and _item_scenario(item) == PUSH_NOTIFICATION_SCENARIO
    )


def is_mfa_security_adoption(item: dict[str, Any]) -> bool:
    return (
        _item_type(item) == ADOPTION_TYPE
        and _item_scenario(item) == MFA_SECURITY_SCENARIO
    )


def is_mass_payments_adoption(item: dict[str, Any]) -> bool:
    return (
        _item_type(item) == ADOPTION_TYPE
        and _item_scenario(item) == MASS_PAYMENTS_SCENARIO
    )


def is_eligible(user: dict[str, Any], item: dict[str, Any]) -> tuple[bool, str]:
    """Return whether an item may be shown to a user and a human-readable reason."""
    user_segment = _normalize_segment(user.get("segment"))
    item_segment = _item_segment(item)

    if not user_segment:
        return False, "User segment is missing."
    if not item_segment:
        return False, "Item segment is missing."
    if user_segment != item_segment:
        return (
            False,
            f"Item is for the {item_segment} segment but the user belongs to {user_segment}.",
        )

    channel = _item_channel(item)
    if channel == "mobile" and not _parse_bool(user.get("uses_mobile_app")):
        return False, "Item is for the mobile channel but the user does not use the mobile app."
    if channel == "web" and not _parse_bool(user.get("uses_web")):
        return False, "Item is for the web channel but the user does not use web banking."

    if is_push_notification_adoption(item) and _parse_bool(user.get("has_push_enabled")):
        return False, "Push notification adoption is suppressed because the user already has push enabled."

    if is_mfa_security_adoption(item) and _parse_bool(user.get("has_mfa_enabled")):
        return False, "MFA security adoption is suppressed because the user already has MFA enabled."

    if is_mass_payments_adoption(item):
        manual_transfers = int(user.get("manual_transfers_month", 0) or 0)
        if manual_transfers < 20:
            return (
                False,
                "Mass payments adoption requires at least 20 manual transfers per month "
                f"(user has {manual_transfers}).",
            )

    return True, "User meets segment, channel and eligibility rules."

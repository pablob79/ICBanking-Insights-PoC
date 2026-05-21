"""Tests for api/rules_service."""

import pytest

from api.rules_service import is_eligible


def retail_mobile_user(**overrides) -> dict:
    base = {
        "user_id": "U001",
        "segment": "retail",
        "uses_mobile_app": True,
        "uses_web": False,
        "has_push_enabled": False,
        "has_mfa_enabled": True,
        "manual_transfers_month": 3,
    }
    base.update(overrides)
    return base


def retail_item(**overrides) -> dict:
    base = {
        "itemId": "I001",
        "segment": "retail",
        "channel": "mobile",
        "type": "financial_insight",
        "scenario": "savings_goal",
    }
    base.update(overrides)
    return base


def test_eligible_when_segment_channel_and_flags_match():
    ok, reason = is_eligible(retail_mobile_user(), retail_item())
    assert ok is True
    assert "meets" in reason.lower()


def test_rejects_segment_mismatch():
    ok, reason = is_eligible(
        retail_mobile_user(),
        retail_item(segment="pyme"),
    )
    assert ok is False
    assert "pyme" in reason
    assert "retail" in reason


def test_rejects_mobile_item_without_mobile_app():
    ok, reason = is_eligible(
        retail_mobile_user(uses_mobile_app=False),
        retail_item(channel="mobile"),
    )
    assert ok is False
    assert "mobile" in reason.lower()


def test_rejects_web_item_without_web_banking():
    ok, reason = is_eligible(
        retail_mobile_user(uses_web=False),
        retail_item(channel="web", type="financial_insight", scenario="spending_alert"),
    )
    assert ok is False
    assert "web" in reason.lower()


def test_accepts_web_item_when_user_uses_web():
    ok, reason = is_eligible(
        retail_mobile_user(uses_web=True),
        retail_item(channel="web"),
    )
    assert ok is True


def test_suppresses_push_notification_adoption_when_push_enabled():
    ok, reason = is_eligible(
        retail_mobile_user(has_push_enabled=True),
        retail_item(type="adoption_action", scenario="notifications"),
    )
    assert ok is False
    assert "push" in reason.lower()


def test_allows_push_notification_adoption_when_push_disabled():
    ok, reason = is_eligible(
        retail_mobile_user(has_push_enabled=False),
        retail_item(type="adoption_action", scenario="notifications"),
    )
    assert ok is True


def test_suppresses_mfa_adoption_when_mfa_enabled():
    ok, reason = is_eligible(
        retail_mobile_user(has_mfa_enabled=True),
        retail_item(type="adoption_action", scenario="mfa"),
    )
    assert ok is False
    assert "mfa" in reason.lower()


def test_allows_mfa_adoption_when_mfa_disabled():
    ok, reason = is_eligible(
        retail_mobile_user(has_mfa_enabled=False),
        retail_item(type="adoption_action", scenario="mfa"),
    )
    assert ok is True


def test_mass_payments_requires_twenty_manual_transfers():
    corporate_web_user = {
        "segment": "corporate",
        "uses_mobile_app": False,
        "uses_web": True,
        "has_push_enabled": True,
        "has_mfa_enabled": True,
        "manual_transfers_month": 10,
    }
    bulk_item = {
        "segment": "corporate",
        "channel": "web",
        "type": "adoption_action",
        "scenario": "bulk_payments",
    }
    ok, reason = is_eligible(corporate_web_user, bulk_item)
    assert ok is False
    assert "20" in reason
    assert "10" in reason


def test_mass_payments_eligible_at_twenty_transfers():
    ok, reason = is_eligible(
        {
            "segment": "corporate",
            "uses_web": True,
            "uses_mobile_app": False,
            "manual_transfers_month": 20,
        },
        {
            "segment": "corporate",
            "channel": "web",
            "type": "adoption_action",
            "scenario": "bulk_payments",
        },
    )
    assert ok is True


def test_supports_csv_style_item_keys():
    ok, reason = is_eligible(
        retail_mobile_user(uses_web=True),
        {
            "segments": "retail",
            "channels": "mobile,web",
            "type": "product_offer",
            "scenario": "lending",
        },
    )
    assert ok is True


@pytest.mark.parametrize(
    "user_segment,item_segment",
    [
        ("retail", "retail"),
        ("pyme", "pyme"),
        ("corporate", "corporate"),
    ],
)
def test_all_banking_segments_can_match(user_segment, item_segment):
    user = {
        "segment": user_segment,
        "uses_mobile_app": True,
        "uses_web": True,
        "manual_transfers_month": 25,
    }
    item = {
        "segment": item_segment,
        "channel": "mobile",
        "type": "financial_insight",
        "scenario": "generic",
    }
    ok, _ = is_eligible(user, item)
    assert ok is (user_segment == item_segment)

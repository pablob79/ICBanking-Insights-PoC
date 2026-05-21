# ICBanking Insights — Demo script (business view)

This proof of concept simulates how a digital banking platform could deliver **personalized insights and next-best actions** to customers in three segments: **Retail**, **PyME (SME)** and **Corporate**.

The engine combines:

1. **Machine learning (LightFM)** — ranks content by predicted interest from synthetic interaction history.
2. **Business rules** — filters recommendations by segment, channel, and product or security eligibility (for example, do not promote push alerts if push is already enabled).
3. **BackOffice configuration** — mock policies for scenarios, frequency caps, and demo users.

All data is **synthetic**. No production systems or real customers are involved.

---

## What to say in the opening (2 minutes)

> “Today we show a local PoC for an Insights and Next Best Action module inside ICBanking. The system proposes timely messages—financial insights, product offers, adoption actions, security reminders, and operational tips—on the right channel. Ranking comes from collaborative filtering; the bank’s rules decide what is actually eligible to show. We will walk through three representative users: retail on mobile, PyME on web, and corporate on web.”

---

## Before the demo

1. Train the model: `python trainer/train.py`
2. Start the API: `uvicorn api.main:app --reload --port 8000`
3. Optional: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`
4. Optional: `curl http://127.0.0.1:8000/backoffice/config` → policies and demo users

---

## Demo case 1 — Retail mobile user

### User profile

| Field | Value |
|-------|--------|
| **User ID** | `U001` |
| **Segment** | Retail (individual banking) |
| **Country** | Argentina |
| **Preferred channel** | Mobile app |
| **Digital profile** | Uses mobile only; push notifications **already enabled**; MFA enabled |
| **Risk / adoption** | Low risk; digital adoption score 72 |
| **Business note** | Typical digitally active retail client; not a business user |

### Expected insight types (catalog for retail + mobile)

After business rules, the API should **not** promote push-notification adoption (user already has push). Expect a mix of:

- **Financial insights** — savings, spending alerts  
- **Product offers** — pre-approved personal lending  
- **Adoption actions** — QR payments, automatic bill pay (not push alerts)  
- **Novelties** — new payment features  
- Excludes web-only items (for example home-banking access review) when `channel=mobile`

### API call

```bash
curl "http://127.0.0.1:8000/recommendations/U001?segment=retail&channel=mobile&limit=3"
```

### Expected business interpretation

- The bank surfaces **short, actionable mobile cards** ranked by predicted engagement.  
- Messages should feel like “help me save”, “understand my spending”, or “use a feature I do not use yet”—not generic advertising.  
- Because push is already on, the engine **suppresses** redundant notification campaigns—demonstrating rule-based governance on top of ML.  
- Each item includes a **reason** (scenario-based copy) and an **action** (for example `view_detail`, `apply`, `activate`) for the front end.

### Suggested channel placement

| Placement | Use |
|-----------|-----|
| **Mobile home — insights carousel** | Top 1–3 ranked items |
| **Post-login banner** | Highest priority `product_offer` or `financial_insight` |
| **Deep link from push/inbox** | Only if a follow-up campaign is scheduled; avoid duplicating push-adoption promos for U001 |

### Suggested next step

1. Show the JSON response and read one `title` + `reason` aloud.  
2. Post a click event and explain the feedback loop:

```bash
curl -X POST "http://127.0.0.1:8000/events" \
  -H "Content-Type: application/json" \
  -d '{"userId":"U001","itemId":"I002","event":"click"}'
```

3. Mention that **retraining is manual**: `python trainer/train.py`, then restart uvicorn so the new model is loaded.

---

## Demo case 2 — PyME web user

### User profile

| Field | Value |
|-------|--------|
| **User ID** | `U009` |
| **Segment** | PyME (SME) |
| **Country** | Argentina |
| **Preferred channel** | Web (home banking / business portal) |
| **Digital profile** | Web-only; push and MFA enabled |
| **Products** | Treasury module active; ~18 employees |
| **Business note** | Growing SME using digital channels for operations, not payroll-heavy in this profile |

### Expected insight types (catalog for PyME + web)

- **Financial insights** — duplicate supplier payments, cash-flow signals  
- **Product offers** — payment links, working-capital line  
- **Adoption actions** — AFIP invoicing, digital payroll (if payroll rules apply)  
- **Security** — operator credential rotation  
- **Operational** — ERP reconciliation, relationship manager appointment  
- **Novelties** — portal updates  

### API call

```bash
curl "http://127.0.0.1:8000/recommendations/U009?segment=pyme&channel=web&limit=3"
```

### Expected business interpretation

- Recommendations support **business outcomes**: collect faster, reduce errors, comply with tax/invoicing, secure operator access.  
- Ranking reflects **observed interactions** in the synthetic history; rules ensure the user is eligible for web and PyME segment content.  
- Priority and score together order what the relationship manager or digital portal should highlight first.  
- Suitable narrative for **“digital RM copilot”** or **self-serve business hub**.

### Suggested channel placement

| Placement | Use |
|-----------|-----|
| **PyME web dashboard — “Para tu negocio” panel** | Top 3 recommendations |
| **Post-login checklist** | `adoption_action` with `activate` CTA |
| **Alert center** | `financial_insight` and `security_recommendation` |
| **Optional email digest** | Same items, deep-linking to web flows |

### Suggested next step

1. Compare with retail: same API shape, different **scenario vocabulary** (invoicing, collections, reconciliation).  
2. Open BackOffice config and point to `demoUsers` entry for U009.  
3. Optionally register a `conversion` on a collections offer (`I009`) to show how sales funnels feed the model.

---

## Demo case 3 — Corporate web user

### User profile

| Field | Value |
|-------|--------|
| **User ID** | `U011` |
| **Segment** | Corporate |
| **Country** | Argentina |
| **Preferred channel** | Web (treasury / corporate banking) |
| **Digital profile** | Web-only; push and MFA enabled |
| **Operations** | ~450 employees; **45 manual transfers/month** (meets the bulk-payments eligibility threshold of 20) |
| **Treasury** | Treasury module not flagged in synthetic row; catalog still includes treasury-oriented items for corporate web |

### Expected insight types (catalog for corporate + web)

- **Financial insights** — liquidity / short-term investments  
- **Product offers** — FX for imports  
- **Adoption actions** — bulk payment dispersion (when transfer volume rules pass)  
- **Security** — signer permission audits  
- **Operational** — payment API integration, operational limits  
- **Novelties** — ESG reporting announcements  

### API call

```bash
curl "http://127.0.0.1:8000/recommendations/U011?segment=corporate&channel=web&limit=3"
```

### Expected business interpretation

- Focus shifts to **treasury efficiency, controls, and integration**—not consumer-style messaging.  
- Items emphasize **liquidity, FX, bulk payments, signer governance, ERP connectivity**—aligned with corporate decision makers.  
- Demonstrates that the same platform serves **retail, PyME, and corporate** with segment-aware catalogs and rules.  
- Strong story for **ICBanking Corporate** upsell and operational cross-sell.

### Suggested channel placement

| Placement | Use |
|-----------|-----|
| **Corporate home — treasury snapshot sidebar** | `financial_insight`, `product_offer` |
| **Payments workspace** | `adoption_action` bulk payments, `operational_recommendation` limits |
| **Admin / security module** | `security_recommendation` signers |
| **Integration settings** | API integration recommendation |

### Suggested next step

1. Highlight **bulk_payments** rule: only users with `manual_transfers_month >= 20` see that adoption (U011 qualifies with 45).  
2. Show a user below threshold (for example `U007` with 4 transfers) with the same call—bulk item should not appear after rules.  
3. Close with architecture: events → CSV → retrain → refreshed rankings; BackOffice caps in `/backoffice/config`.

---

## Closing talking points

| Topic | Message |
|-------|---------|
| **Governance** | ML suggests; the bank decides via rules and BackOffice policy. |
| **Channels** | Same engine, different placement and copy per mobile vs web. |
| **Feedback loop** | Events are stored; retraining improves ranking over time. |
| **PoC limits** | Synthetic data, local API, no core banking integration. |
| **Production path** | Replace CSV with warehouse/features, add A/B testing, frequency-cap enforcement in the channel layer. |

---

## Quick reference — all demo calls

```bash
# Health
curl "http://127.0.0.1:8000/health"

# BackOffice
curl "http://127.0.0.1:8000/backoffice/config"

# Recommendations
curl "http://127.0.0.1:8000/recommendations/U001?segment=retail&channel=mobile&limit=3"
curl "http://127.0.0.1:8000/recommendations/U009?segment=pyme&channel=web&limit=3"
curl "http://127.0.0.1:8000/recommendations/U011?segment=corporate&channel=web&limit=3"

# Event + retrain
curl -X POST "http://127.0.0.1:8000/events" \
  -H "Content-Type: application/json" \
  -d '{"userId":"U001","itemId":"I002","event":"click"}'
python trainer/train.py
# Restart uvicorn to load the new model bundle
```

For full technical setup, see the [README](../README.md).

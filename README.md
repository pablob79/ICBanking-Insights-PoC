# ICBanking Insights — Proof of Concept

Local proof of concept for an **Insights & Next Best Action** module. It recommends banking insights, product offers, adoption actions, and operational suggestions using **LightFM** for ranking and a separate **business rules** layer for eligibility.

> **Synthetic data only.** No real customer data, production systems, or credentials.

## Segments

| Segment    | Description                          |
|------------|--------------------------------------|
| `retail`   | Individual / retail banking users    |
| `pyme`     | Small and medium business (SME)      |
| `corporate`| Corporate and treasury users         |

## Project layout

```
data/           Synthetic CSV datasets
trainer/        LightFM training and recommendation helpers
api/            FastAPI service and business rules
backoffice/     Mock BackOffice configuration
ui/             Demo web UI (static)
tests/          Unit tests
docs/           Demo script and documentation
```

## Prerequisites

- Python 3.12+ (tested with 3.12–3.14 on macOS/Linux)
- Virtual environment (recommended)

This PoC uses **[lightfm-next](https://pypi.org/project/lightfm-next/)** (`1.19.0`), a community-maintained fork of LightFM with modern Python support. Imports stay the same (`from lightfm import LightFM`). Windows is not supported by the fork yet.

## Setup and run (step by step)

Run all commands from the project root (`ICBanking-Insights`).

### 1. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Your shell prompt should show `(.venv)`.

### 2. Install requirements

```bash
pip install -r requirements.txt
```

### 3. Train model

Builds the LightFM model from `data/*.csv` and saves the bundle:

```bash
python trainer/train.py
```

Output: `trainer/models/lightfm_model.pkl`

### 4. Run API

```bash
uvicorn api.main:app --reload --port 8000
```

Without activating the venv:

```bash
.venv/bin/uvicorn api.main:app --reload --port 8000
```

Check health:

```bash
curl "http://127.0.0.1:8000/health"
```

### 5. Open demo UI

With the API running, open in a browser:

**http://127.0.0.1:8000/demo/**

Select a demo user (Retail mobile, PyME web, Corporate web), view recommendation cards, and simulate events (`view`, `click`, `conversion`, `dismiss`).

Alternative (static server on another port; CORS is enabled on the API):

```bash
python3 -m http.server 5500 --directory ui
```

Then open http://127.0.0.1:5500 and set API base URL to `http://127.0.0.1:8000`.

### 6. Test recommendations

Retail mobile:

```bash
curl "http://127.0.0.1:8000/recommendations/U001?segment=retail&channel=mobile&limit=3"
```

PyME web:

```bash
curl "http://127.0.0.1:8000/recommendations/U009?segment=pyme&channel=web&limit=3"
```

Corporate web:

```bash
curl "http://127.0.0.1:8000/recommendations/U011?segment=corporate&channel=web&limit=3"
```

CLI alternative (no API):

```bash
python trainer/recommend.py
```

### 7. Post an event

Appends to `data/interactions.csv` (does **not** retrain automatically):

```bash
curl -X POST "http://127.0.0.1:8000/events" \
  -H "Content-Type: application/json" \
  -d '{"userId":"U001","itemId":"I002","event":"click"}'
```

Allowed events: `view`, `click`, `start_flow`, `conversion`, `dismiss`, `not_interested`.

### 8. Retrain model

After new events, refresh the model:

```bash
python trainer/train.py
```

Restart uvicorn (`Ctrl+C`, then run step 4 again) so recommendations use the new `.pkl` (the API caches the bundle in memory).

## Business demo

Step-by-step script for bank stakeholders (three segments, channel placement, talking points):

**[docs/demo_script.md](docs/demo_script.md)**

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/recommendations/{user_id}?segment=retail&channel=mobile&limit=3` | Personalized recommendations |
| POST | `/events` | Track user events (appends to `data/interactions.csv`) |
| GET | `/backoffice/config` | Mock BackOffice settings (scenarios, caps, demo users) |

Recommendation fields: `itemId`, `title`, `type`, `scenario`, `channel`, `priority`, `score`, `reason`, `eligibility`, `action`.

## Datasets (`data/`)

| File               | Purpose                                      |
|--------------------|----------------------------------------------|
| `users.csv`        | Synthetic users by segment                   |
| `items.csv`        | Recommendable insights, offers, actions      |
| `interactions.csv` | Historical events (views, clicks, conversions)|

## Tests

`pytest` is installed **inside `.venv`**, not globally. Activate the venv first:

```bash
source .venv/bin/activate
pytest -v
```

Without activating the venv:

```bash
.venv/bin/python -m pytest -v
```

`pyproject.toml` adds the repo root to `PYTHONPATH` so imports like `api` and `trainer` resolve correctly.

## Constraints

- LightFM score is **not** the only decision criterion; business rules filter candidates first.
- Supports **Retail**, **PyME**, and **Corporate** in data and rules.
- See `IMPLEMENTATION_PLAN.md` for the full roadmap.

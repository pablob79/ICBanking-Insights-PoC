# ICBanking Insights PoC - Implementation Plan

## Objective

Build a proof of concept for an ICBanking Insights & Next Best Action module using LightFM as recommendation engine.

The PoC must recommend banking insights, products, adoption actions and operational suggestions for Retail, SME and Corporate banking users.

## Scope

This is a local PoC. It must not connect to real banking systems, real customer data, production infrastructure or external databases.

Use synthetic data only.

## Architecture

The project must include:

- Synthetic datasets in CSV format.
- LightFM training script.
- Recommendation service.
- FastAPI API.
- Business rules layer.
- Mock BackOffice configuration.
- Event tracking endpoint.
- Basic tests.
- README with setup and demo instructions.

## Main folders

- data/
- trainer/
- api/
- backoffice/
- tests/
- docs/

## Functional concepts

Users represent banking customers or digital banking users.

Items represent things that can be recommended:

- financial insight
- product offer
- adoption action
- security recommendation
- operational recommendation
- bank novelty or announcement

Segments:

- retail
- pyme
- corporate

Channels:

- mobile
- web

Events:

- view
- click
- start_flow
- conversion
- dismiss
- not_interested

## Important constraints

- Do not use real customer data.
- Do not connect to production services.
- Do not add secrets, API keys or credentials.
- Do not execute destructive commands.
- Do not remove files unless explicitly instructed.
- Keep the implementation simple and understandable.
- Prefer Python, FastAPI, Pandas and LightFM.
- Add comments where useful.
- Add tests for core logic.

## Expected API

GET /health

GET /recommendations/{user_id}?segment=retail&channel=mobile&limit=3

POST /events

GET /backoffice/config

## Expected result

The API should return personalized recommendations filtered by:

- user
- segment
- channel
- eligibility rules
- LightFM ranking
- business priority

Each recommendation should include:

- itemId
- title
- type
- scenario
- channel
- score
- priority
- reason
- action
- eligibility

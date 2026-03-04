# Nutrition Tracker API

MVP foundation for Nutrition Tracker based on FastAPI + SQLite + SQLModel.

## Stage 1 scope

- FastAPI project initialized.
- SQLite schema for `users`, `foods`, `meals`, `meal_items`.
- DB init + seed script with:
  - test user: `TEST1234`
  - sample foods including `skyr` and `borowki`

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Initialize DB and seed data

```bash
python scripts/init_db.py
```

This creates `nutrition.db` in project root.

## Run API

```bash
uvicorn app.main:app --reload --port 8090
```

Health check:

`GET /health`

## Stage 2 auth

- Send token in header: `Authorization: Bearer TOKEN8`
- Token format: exactly 8 chars in `[A-Z0-9]`
- `GET /me` returns current user when token is valid

Example:

```bash
curl -H "Authorization: Bearer TEST1234" http://127.0.0.1:8090/me
```

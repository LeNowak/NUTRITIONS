# Nutrition Tracker API

MVP foundation for Nutrition Tracker based on Flask + SQLite + SQLModel.

## Stage 1 scope

- Flask API project initialized.
- SQLite schema for `users`, `foods`, `meals`, `meal_items`.
- DB init + seed script with:
  - test user: `TEST1234`
  - sample foods including `skyr`, `borowki`, and `wolowina`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
source .venv/bin/activate
pip install -r requirements.txt
```

## Initialize DB and seed data

```bash
python scripts/init_db.py
```

This c

## Run API

```bash
python -m app.main
```

Health check:

`GET /health`

Behavior of `POST /eat`:

- Known foods are matched against the dictionary and contribute to kcal, protein, carbs, and fiber.
- Unknown foods can be auto-enriched through Gemini and persisted into the dictionary when `GEMINI_API_KEY` is configured.
- If AI enrichment is unavailable or fails, unknown foods are still saved in the meal history with `0` nutrition values until the dictionary is expanded.
- If text cannot be parsed into weighted items, the raw meal entry is still saved with empty items and zero totals.

Food dictionary management:

- `GET /foods` returns all configured foods except the internal placeholder used for unknown items.
- `POST /foods` creates a new food with `name`, `aliases`, `kcal_per_100g`, `protein_per_100g`, `carbs_per_100g`, and `fiber_per_100g`.
- `PUT /foods/<id>` updates an existing food.
- `DELETE /foods/<id>` removes a food only if it is not already used in meal history.

Optional AI enrichment:

- Configure `GEMINI_API_KEY` to enable automatic estimation of nutrition for unknown foods.
- `GEMINI_MODEL` defaults to `gemini-3.0-flash` and can be overridden through environment variables.

## Stage 2 auth

- Send token in header: `Authorization: Bearer TOKEN8`
- Token format: exactly 8 chars in `[A-Z0-9]`
- `GET /me` returns current user when token is valid

Example:

```bash
curl -H "Authorization: Bearer TEST1234" http://mdtest:8090/me
```

supervisorctl -c ~/tools2/supervisor.conf reread
supervisorctl -c ~/tools2/supervisor.conf update
supervisorctl -c ~/tools2/supervisor.conf status
supervisorctl -c ~/tools2/supervisor.conf restart api

curl -i http://127.0.0.1:8086/health

C:/PROJECTS/NUTRITIONS/.venv/Scripts/Activate.ps1
python scripts/init_db.py
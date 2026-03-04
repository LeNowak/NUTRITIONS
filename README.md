# Nutrition Tracker API

MVP foundation for Nutrition Tracker based on Flask + SQLite + SQLModel.

## Stage 1 scope

- Flask API project initialized.
- SQLite schema for `users`, `foods`, `meals`, `meal_items`.
- DB init + seed script with:
  - test user: `TEST1234`
  - sample foods including `skyr` and `borowki`

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
supervisorctl -c ~/tools2/supervisor.conf restart testb
curl -i http://127.0.0.1:8086/health

C:/PROJECTS/NUTRITIONS/.venv/Scripts/Activate.ps1
python scripts/init_db.py
from fastapi import Depends, FastAPI

from app.auth import get_current_user
from app.database import create_db_and_tables
from app.models import User


app = FastAPI(title="Nutrition Tracker API")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict[str, int | str]:
    return {
        "id": current_user.id or 0,
        "name": current_user.name,
        "token": current_user.token,
    }

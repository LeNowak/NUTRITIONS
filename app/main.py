from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import create_db_and_tables, get_session
from app.models import Food, Meal, MealItem, User
from app.parser import parse_meal_text


app = FastAPI(title="Nutrition Tracker API")


class EatRequest(BaseModel):
    text: str


class MealItemResponse(BaseModel):
    food_name: str
    grams: float
    kcal: float
    protein: float


class MealResponse(BaseModel):
    id: int
    date: date
    raw_text: str
    total_kcal: float
    total_protein: float
    items: list[MealItemResponse]


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


@app.post("/eat", response_model=MealResponse)
def eat(
    request: EatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Meal:
    """
    Endpoint przyjmujący surowy tekst, parsujący go i zapisujący jako posiłek.
    Przykład: {"text": "400g skyr z borowkami 100g"}
    """
    parsed_items = parse_meal_text(request.text)
    if not parsed_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse any food items from text. Examples: '400g skyr', '100g borowki'.",
        )

    meal = Meal(
        user_id=current_user.id,
        date=date.today(),
        raw_text=request.text,
        total_kcal=0.0,
        total_protein=0.0,
    )
    session.add(meal)
    session.commit()
    session.refresh(meal)

    total_kcal = 0.0
    total_protein = 0.0
    meal_items_to_save = []

    for item in parsed_items:
        # Znajdowanie produktu w bazie (po nazwie lub aliasie)
        # Proste dopasowanie: "skyr" w nazwie lub aliasach
        food = session.exec(
            select(Food).where(
                (Food.name.contains(item.food_name)) | (Food.aliases.contains(item.food_name))
            )
        ).first()

        if food:
            item_kcal = (food.kcal_per_100g * item.grams) / 100.0
            item_protein = (food.protein_per_100g * item.grams) / 100.0

            meal_item = MealItem(
                meal_id=meal.id,
                food_id=food.id,
                grams=item.grams,
                kcal=item_kcal,
                protein=item_protein,
                matched_name=food.name,
            )
            meal_items_to_save.append(meal_item)
            total_kcal += item_kcal
            total_protein += item_protein

    if not meal_items_to_save:
        session.delete(meal)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching foods found in database.",
        )

    for mi in meal_items_to_save:
        session.add(mi)

    # Aktualizacja nagłówka posiłku o łączne wartości
    meal.total_kcal = total_kcal
    meal.total_protein = total_protein
    session.add(meal)
    session.commit()
    session.refresh(meal)

    # Przygotowanie odpowiedzi (z mapowaniem na model)
    # FastAPI SQLModel handle relationships but we can return object if fields match
    return meal


@app.get("/meals", response_model=list[MealResponse])
def get_meals(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Meal]:
    """Lista posiłków zalogowanego użytkownika."""
    return session.exec(
        select(Meal).where(Meal.user_id == current_user.id).order_by(Meal.created_at.desc())
    ).all()


@app.get("/stats/today")
def get_stats_today(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, float]:
    """Podsumowanie dzisiejszych kalorii i białka."""
    today = date.today()
    meals = session.exec(
        select(Meal).where(Meal.user_id == current_user.id, Meal.date == today)
    ).all()

    return {
        "kcal": sum(m.total_kcal for m in meals),
        "protein": sum(m.total_protein for m in meals),
    }

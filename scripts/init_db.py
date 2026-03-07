from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

from sqlmodel import Session, select


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import create_db_and_tables, engine
from app.models import Food, Meal, MealItem, User


def seed_user(session: Session) -> User:
    existing_user = session.exec(select(User).where(User.token == "TEST1234")).first()
    if existing_user:
        return existing_user

    user = User(name="Test User", token="TEST1234")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def seed_foods(session: Session) -> int:
    foods_to_seed = [
        Food(
            name="skyr",
            aliases="skyr naturalny|jogurt islandzki",
            kcal_per_100g=63,
            protein_per_100g=11,
            carbs_per_100g=3.6,
            fiber_per_100g=0,
        ),
        Food(
            name="borowki",
            aliases="borowki|borowki amerykanskie|borowki swieze",
            kcal_per_100g=57,
            protein_per_100g=0.7,
            carbs_per_100g=14.5,
            fiber_per_100g=2.4,
        ),
        Food(
            name="platki owsiane",
            aliases="owsianka|platki",
            kcal_per_100g=366,
            protein_per_100g=13,
            carbs_per_100g=56.6,
            fiber_per_100g=10.6,
        ),
        Food(
            name="banan",
            aliases="banana",
            kcal_per_100g=89,
            protein_per_100g=1.1,
            carbs_per_100g=22.8,
            fiber_per_100g=2.6,
        ),
        Food(
            name="wolowina",
            aliases="wołowina|mieso wolowe|mięso wołowe|beef",
            kcal_per_100g=250,
            protein_per_100g=26,
            carbs_per_100g=0,
            fiber_per_100g=0,
        ),
    ]

    inserted = 0
    for food in foods_to_seed:
        existing = session.exec(select(Food).where(Food.name == food.name)).first()
        if existing:
            existing.aliases = food.aliases
            existing.kcal_per_100g = food.kcal_per_100g
            existing.protein_per_100g = food.protein_per_100g
            existing.carbs_per_100g = food.carbs_per_100g
            existing.fiber_per_100g = food.fiber_per_100g
            session.add(existing)
            continue
        session.add(food)
        inserted += 1

    if inserted or foods_to_seed:
        session.commit()
    return inserted


def print_summary(session: Session) -> None:
    users_count = len(session.exec(select(User)).all())
    foods_count = len(session.exec(select(Food)).all())
    meals_count = len(session.exec(select(Meal)).all())
    meal_items_count = len(session.exec(select(MealItem)).all())

    print("Database initialized.")
    print(f"Users: {users_count}")
    print(f"Foods: {foods_count}")
    print(f"Meals: {meals_count}")
    print(f"Meal items: {meal_items_count}")
    print(f"Date: {date.today().isoformat()}")


def main() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        user = seed_user(session)
        inserted_foods = seed_foods(session)
        print(f"User ready: {user.name} ({user.token})")
        print(f"Inserted foods: {inserted_foods}")
        print_summary(session)


if __name__ == "__main__":
    main()

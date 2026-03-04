from datetime import date

from flask import Flask, jsonify, request, send_from_directory
from sqlmodel import Session, select

from app.auth import APIError, get_current_user
from app.database import create_db_and_tables, engine
from app.models import Food, Meal, MealItem, User
from app.parser import calculate_item_nutrition, match_food, parse_meal_text


app = Flask(__name__)
create_db_and_tables()


def _meal_to_response(session: Session, meal: Meal) -> dict:
    items = session.exec(select(MealItem).where(MealItem.meal_id == meal.id)).all()
    serialized_items: list[dict] = []
    for item in items:
        serialized_items.append(
            {
                "food_name": item.matched_name,
                "grams": item.grams,
                "kcal": item.kcal,
                "protein": item.protein,
            }
        )

    return {
        "id": meal.id,
        "date": meal.date.isoformat(),
        "raw_text": meal.raw_text,
        "total_kcal": meal.total_kcal,
        "total_protein": meal.total_protein,
        "items": serialized_items,
    }


@app.errorhandler(APIError)
def handle_api_error(error: APIError):
    response = jsonify({"detail": error.detail})
    for name, value in error.headers.items():
        response.headers[name] = value
    return response, error.status_code


def _get_current_user_or_raise(session: Session) -> User:
    return get_current_user(request, session)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/me")
def me():
    with Session(engine) as session:
        current_user = _get_current_user_or_raise(session)
        return jsonify(
            {
                "id": current_user.id or 0,
                "name": current_user.name,
                "token": current_user.token,
            }
        )


@app.post("/eat")
def eat():
    """
    Endpoint przyjmujący surowy tekst, parsujący go i zapisujący jako posiłek.
    Przykład: {"text": "400g skyr z borowkami 100g"}
    """
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")

    with Session(engine) as session:
        current_user = _get_current_user_or_raise(session)

        parsed_items = parse_meal_text(text)
        if not parsed_items:
            raise APIError(
                status_code=422,
                detail="Could not parse any food items from text. Examples: '400g skyr', '100g borowki'.",
            )

        foods = session.exec(select(Food)).all()
        resolved_items: list[tuple[float, Food, str, float, float]] = []
        unmatched_items: list[str] = []

        for item in parsed_items:
            match = match_food(item.food_name, foods)
            if not match:
                unmatched_items.append(item.food_name)
                continue

            item_kcal, item_protein = calculate_item_nutrition(match.food, item.grams)
            resolved_items.append((item.grams, match.food, match.matched_name, item_kcal, item_protein))

        if unmatched_items:
            raise APIError(
                status_code=422,
                detail=f"Could not match foods from text: {', '.join(unmatched_items)}",
            )

        meal = Meal(
            user_id=current_user.id,
            date=date.today(),
            raw_text=text,
            total_kcal=0.0,
            total_protein=0.0,
        )
        session.add(meal)
        session.commit()
        session.refresh(meal)

        total_kcal = 0.0
        total_protein = 0.0
        for grams, food, matched_name, item_kcal, item_protein in resolved_items:
            meal_item = MealItem(
                meal_id=meal.id,
                food_id=food.id,
                grams=grams,
                kcal=item_kcal,
                protein=item_protein,
                matched_name=matched_name,
            )
            session.add(meal_item)
            total_kcal += item_kcal
            total_protein += item_protein

        meal.total_kcal = total_kcal
        meal.total_protein = total_protein
        session.add(meal)
        session.commit()
        session.refresh(meal)

        return jsonify(_meal_to_response(session, meal))


@app.get("/meals")
def get_meals():
    with Session(engine) as session:
        current_user = _get_current_user_or_raise(session)
        meals = session.exec(
            select(Meal).where(Meal.user_id == current_user.id).order_by(Meal.created_at.desc())
        ).all()
        return jsonify([_meal_to_response(session, meal) for meal in meals])


@app.get("/stats/today")
def get_stats_today():
    with Session(engine) as session:
        current_user = _get_current_user_or_raise(session)
        today = date.today()
        meals = session.exec(
            select(Meal).where(Meal.user_id == current_user.id, Meal.date == today)
        ).all()

        return jsonify(
            {
                "kcal": sum(meal.total_kcal for meal in meals),
                "protein": sum(meal.total_protein for meal in meals),
            }
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082, debug=True)

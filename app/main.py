from datetime import date, datetime, timedelta
import html
import os
import re
import secrets
from urllib.parse import urlencode, urlparse

from flask import Flask, jsonify, redirect, request, send_from_directory
from sqlmodel import Session, select

from app.ai_nutrition import estimate_food_nutrition
from app.auth import APIError, TOKEN_PATTERN, get_current_user
from app.database import create_db_and_tables, engine
from app.models import Food, Meal, MealItem, OAuthAuthorizationCode, User
from app.parser import calculate_item_nutrition, match_food, normalize_text, parse_meal_text


app = Flask(__name__)
create_db_and_tables()

AUTH_CODE_TTL_SECONDS = 300
OPENAI_CALLBACK_HOSTS = {"chat.openai.com", "chatgpt.com"}
SUPPORTED_OAUTH_RESPONSE_TYPES = {"code", "authorization_code"}
UNKNOWN_FOOD_NAME = "__unknown_food__"


def _cleanup_oauth_codes(session: Session) -> None:
    now = datetime.utcnow()
    expired_codes = session.exec(
        select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.expires_at <= now)
    ).all()
    for auth_code in expired_codes:
        session.delete(auth_code)
    if expired_codes:
        session.commit()


def _allowed_redirect_uris_from_env() -> set[str]:
    raw_value = os.getenv("OAUTH_ALLOWED_REDIRECT_URIS", "")
    if not raw_value:
        return set()
    return {uri.strip() for uri in raw_value.split(",") if uri.strip()}


def _is_allowed_redirect_uri(redirect_uri: str) -> bool:
    explicit_allowed = _allowed_redirect_uris_from_env()
    if redirect_uri in explicit_allowed:
        return True

    parsed = urlparse(redirect_uri)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "") in OPENAI_CALLBACK_HOSTS
        and parsed.path.endswith("/oauth/callback")
    )


def _render_oauth_authorize_form(
    *,
    redirect_uri: str,
    state: str,
    client_id: str,
    response_type: str,
    error_message: str = "",
) -> str:
    escaped_error = html.escape(error_message)
    escaped_redirect_uri = html.escape(redirect_uri)
    escaped_state = html.escape(state)
    escaped_client_id = html.escape(client_id)
    escaped_response_type = html.escape(response_type or "code")

    error_block = f"<p style='color:#b00020'>{escaped_error}</p>" if error_message else ""

    return f"""
<!doctype html>
<html lang=\"pl\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>OAuth Login</title>
</head>
<body style=\"font-family: Arial, sans-serif; margin: 24px; max-width: 520px;\">
  <h1>Logowanie Nutrition Tracker</h1>
  <p>Podaj token użytkownika (8 znaków A-Z0-9), aby kontynuować autoryzację.</p>
  {error_block}
  <form method=\"get\" action=\"/oauth/authorize\">
    <input type=\"hidden\" name=\"redirect_uri\" value=\"{escaped_redirect_uri}\" />
    <input type=\"hidden\" name=\"state\" value=\"{escaped_state}\" />
    <input type=\"hidden\" name=\"client_id\" value=\"{escaped_client_id}\" />
    <input type=\"hidden\" name=\"response_type\" value=\"{escaped_response_type}\" />

    <label for=\"token\">TOKEN8</label><br />
    <input id=\"token\" name=\"token\" maxlength=\"8\" required /><br /><br />
    <button type=\"submit\">Autoryzuj</button>
  </form>
</body>
</html>
"""


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
                "carbs": item.carbs,
                "fiber": item.fiber,
            }
        )

    return {
        "id": meal.id,
        "date": meal.date.isoformat(),
        "raw_text": meal.raw_text,
        "total_kcal": meal.total_kcal,
        "total_protein": meal.total_protein,
        "total_carbs": meal.total_carbs,
        "total_fiber": meal.total_fiber,
        "items": serialized_items,
    }


def _food_to_response(food: Food) -> dict:
    return {
        "id": food.id,
        "name": food.name,
        "aliases": food.aliases or "",
        "kcal_per_100g": food.kcal_per_100g,
        "protein_per_100g": food.protein_per_100g,
        "carbs_per_100g": food.carbs_per_100g,
        "fiber_per_100g": food.fiber_per_100g,
    }


@app.errorhandler(APIError)
def handle_api_error(error: APIError):
    response = jsonify({"detail": error.detail})
    for name, value in error.headers.items():
        response.headers[name] = value
    return response, error.status_code


def _get_current_user_or_raise(session: Session) -> User:
    return get_current_user(request, session)


def _get_or_create_unknown_food(session: Session) -> Food:
    unknown_food = session.exec(select(Food).where(Food.name == UNKNOWN_FOOD_NAME)).first()
    if unknown_food:
        return unknown_food

    unknown_food = Food(
        name=UNKNOWN_FOOD_NAME,
        aliases="unknown|nieznany produkt|dowolny wpis",
        kcal_per_100g=0,
        protein_per_100g=0,
        carbs_per_100g=0,
        fiber_per_100g=0,
    )
    session.add(unknown_food)
    session.commit()
    session.refresh(unknown_food)
    return unknown_food


def _clean_food_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _prepare_aliases(name: str, raw_aliases: str) -> str:
    normalized_name = normalize_text(name)
    seen_aliases: set[str] = set()
    cleaned_aliases: list[str] = []

    for alias in raw_aliases.split("|"):
        cleaned_alias = _clean_food_text(alias)
        if not cleaned_alias:
            continue

        normalized_alias = normalize_text(cleaned_alias)
        if not normalized_alias or normalized_alias == normalized_name or normalized_alias in seen_aliases:
            continue

        seen_aliases.add(normalized_alias)
        cleaned_aliases.append(cleaned_alias)

    return "|".join(cleaned_aliases)


def _find_food_by_normalized_name(session: Session, food_name: str, exclude_id: int | None = None) -> Food | None:
    normalized_name = normalize_text(food_name)
    if not normalized_name:
        return None

    foods = session.exec(select(Food)).all()
    for food in foods:
        if exclude_id is not None and food.id == exclude_id:
            continue
        if normalize_text(food.name) == normalized_name:
            return food
    return None


def _get_food_payload() -> dict:
    payload = request.get_json(silent=True) or {}
    name = _clean_food_text(payload.get("name") or "")
    aliases = _prepare_aliases(name, str(payload.get("aliases") or ""))

    try:
        kcal_per_100g = float(payload.get("kcal_per_100g"))
        protein_per_100g = float(payload.get("protein_per_100g"))
        carbs_per_100g = float(payload.get("carbs_per_100g") or 0)
        fiber_per_100g = float(payload.get("fiber_per_100g") or 0)
    except (TypeError, ValueError):
        raise APIError(
            status_code=422,
            detail="kcal_per_100g, protein_per_100g, carbs_per_100g and fiber_per_100g must be numbers.",
        )

    if not name:
        raise APIError(status_code=422, detail="Food name is required.")

    if name == UNKNOWN_FOOD_NAME:
        raise APIError(status_code=422, detail="This food name is reserved.")

    if kcal_per_100g < 0 or protein_per_100g < 0 or carbs_per_100g < 0 or fiber_per_100g < 0:
        raise APIError(status_code=422, detail="Nutrition values must be greater than or equal to zero.")

    return {
        "name": name,
        "aliases": aliases,
        "kcal_per_100g": kcal_per_100g,
        "protein_per_100g": protein_per_100g,
        "carbs_per_100g": carbs_per_100g,
        "fiber_per_100g": fiber_per_100g,
    }


def _get_or_create_food_from_ai(session: Session, food_name: str) -> Food | None:
    estimate = estimate_food_nutrition(food_name)
    if not estimate or not estimate.normalized_name or estimate.normalized_name == UNKNOWN_FOOD_NAME:
        return None

    existing_food = _find_food_by_normalized_name(session, estimate.normalized_name)
    if existing_food:
        return existing_food

    aliases = [alias for alias in estimate.aliases if alias and alias != estimate.normalized_name]
    normalized_input = normalize_text(food_name)
    if normalized_input:
        if normalized_input not in aliases and normalized_input != estimate.normalized_name:
            aliases.append(normalized_input)

    ai_food = Food(
        name=estimate.normalized_name,
        aliases="|".join(dict.fromkeys(aliases)) or None,
        kcal_per_100g=estimate.kcal_per_100g,
        protein_per_100g=estimate.protein_per_100g,
        carbs_per_100g=estimate.carbs_per_100g,
        fiber_per_100g=estimate.fiber_per_100g,
    )
    session.add(ai_food)
    session.commit()
    session.refresh(ai_food)
    return ai_food


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


@app.get("/foods")
def get_foods():
    with Session(engine) as session:
        _get_current_user_or_raise(session)
        foods = session.exec(
            select(Food).where(Food.name != UNKNOWN_FOOD_NAME).order_by(Food.name.asc())
        ).all()
        return jsonify([_food_to_response(food) for food in foods])


@app.post("/foods", strict_slashes=False)
def create_food():
    payload = _get_food_payload()

    with Session(engine) as session:
        _get_current_user_or_raise(session)
        existing_food = _find_food_by_normalized_name(session, payload["name"])
        if existing_food:
            raise APIError(status_code=409, detail="Food with this name already exists.")

        food = Food(**payload)
        session.add(food)
        session.commit()
        session.refresh(food)
        return jsonify(_food_to_response(food)), 201


@app.put("/foods/<int:food_id>", strict_slashes=False)
def update_food(food_id: int):
    payload = _get_food_payload()

    with Session(engine) as session:
        _get_current_user_or_raise(session)
        food = session.get(Food, food_id)
        if not food or food.name == UNKNOWN_FOOD_NAME:
            raise APIError(status_code=404, detail="Food not found.")

        duplicate_food = _find_food_by_normalized_name(session, payload["name"], exclude_id=food_id)
        if duplicate_food:
            raise APIError(status_code=409, detail="Another food with this name already exists.")

        food.name = payload["name"]
        food.aliases = payload["aliases"] or None
        food.kcal_per_100g = payload["kcal_per_100g"]
        food.protein_per_100g = payload["protein_per_100g"]
        food.carbs_per_100g = payload["carbs_per_100g"]
        food.fiber_per_100g = payload["fiber_per_100g"]
        session.add(food)
        session.commit()
        session.refresh(food)
        return jsonify(_food_to_response(food))


@app.delete("/foods/<int:food_id>", strict_slashes=False)
def delete_food(food_id: int):
    with Session(engine) as session:
        _get_current_user_or_raise(session)
        food = session.get(Food, food_id)
        if not food or food.name == UNKNOWN_FOOD_NAME:
            raise APIError(status_code=404, detail="Food not found.")

        existing_meal_item = session.exec(select(MealItem).where(MealItem.food_id == food_id)).first()
        if existing_meal_item:
            raise APIError(status_code=409, detail="Food is already used in meal history and cannot be deleted.")

        session.delete(food)
        session.commit()
        return jsonify({"status": "deleted", "id": food_id})


@app.post("/eat", strict_slashes=False)
def eat():
    """
    Endpoint przyjmujący surowy tekst, parsujący go i zapisujący jako posiłek.
    Przykład: {"text": "400g skyr z borowkami 100g"}
    """
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")

    with Session(engine) as session:
        current_user = _get_current_user_or_raise(session)

        resolved_items: list[tuple[float, Food, str, float, float, float, float]] = []
        parsed_items = parse_meal_text(text)
        if parsed_items:
            foods = session.exec(select(Food)).all()
            unknown_food = _get_or_create_unknown_food(session)

            for item in parsed_items:
                match = match_food(item.food_name, foods)
                if match:
                    item_kcal, item_protein, item_carbs, item_fiber = calculate_item_nutrition(match.food, item.grams)
                    resolved_items.append((item.grams, match.food, match.matched_name, item_kcal, item_protein, item_carbs, item_fiber))
                    continue

                ai_food = _get_or_create_food_from_ai(session, item.food_name)
                if ai_food:
                    foods.append(ai_food)
                    item_kcal, item_protein, item_carbs, item_fiber = calculate_item_nutrition(ai_food, item.grams)
                    resolved_items.append((item.grams, ai_food, ai_food.name, item_kcal, item_protein, item_carbs, item_fiber))
                    continue

                resolved_items.append((item.grams, unknown_food, item.food_name, 0.0, 0.0, 0.0, 0.0))

        meal = Meal(
            user_id=current_user.id,
            date=date.today(),
            raw_text=text,
            total_kcal=0.0,
            total_protein=0.0,
            total_carbs=0.0,
            total_fiber=0.0,
        )
        session.add(meal)
        session.commit()
        session.refresh(meal)

        total_kcal = 0.0
        total_protein = 0.0
        total_carbs = 0.0
        total_fiber = 0.0
        for grams, food, matched_name, item_kcal, item_protein, item_carbs, item_fiber in resolved_items:
            meal_item = MealItem(
                meal_id=meal.id,
                food_id=food.id,
                grams=grams,
                kcal=item_kcal,
                protein=item_protein,
                carbs=item_carbs,
                fiber=item_fiber,
                matched_name=matched_name,
            )
            session.add(meal_item)
            total_kcal += item_kcal
            total_protein += item_protein
            total_carbs += item_carbs
            total_fiber += item_fiber

        meal.total_kcal = total_kcal
        meal.total_protein = total_protein
        meal.total_carbs = total_carbs
        meal.total_fiber = total_fiber
        session.add(meal)
        session.commit()
        session.refresh(meal)

        return jsonify(_meal_to_response(session, meal))


@app.get("/oauth/authorize", strict_slashes=False)
def oauth_authorize():
    redirect_uri = request.args.get("redirect_uri", "").strip()
    state = request.args.get("state", "").strip()
    client_id = request.args.get("client_id", "").strip()
    response_type = request.args.get("response_type", "code").strip()
    token = request.args.get("token", "").strip().upper()

    if not redirect_uri:
        return jsonify({"error": "invalid_request", "error_description": "Missing redirect_uri."}), 400

    if not _is_allowed_redirect_uri(redirect_uri):
        return jsonify({"error": "invalid_request", "error_description": "Invalid redirect_uri."}), 400

    if response_type not in SUPPORTED_OAUTH_RESPONSE_TYPES:
        return jsonify({"error": "unsupported_response_type", "error_description": "Only code is supported."}), 400

    if not state:
        return jsonify({"error": "invalid_request", "error_description": "Missing required state parameter."}), 400

    if not token:
        return _render_oauth_authorize_form(
            redirect_uri=redirect_uri,
            state=state,
            client_id=client_id,
            response_type=response_type,
        )

    if not TOKEN_PATTERN.fullmatch(token):
        return _render_oauth_authorize_form(
            redirect_uri=redirect_uri,
            state=state,
            client_id=client_id,
            response_type=response_type,
            error_message="Niepoprawny token. Wymagane 8 znaków A-Z0-9.",
        ), 400

    with Session(engine) as session:
        user = session.exec(select(User).where(User.token == token)).first()
        if not user:
            return _render_oauth_authorize_form(
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                response_type=response_type,
                error_message="Token nie istnieje w systemie.",
            ), 401

    code = secrets.token_urlsafe(24)
    with Session(engine) as session:
        _cleanup_oauth_codes(session)
        session.add(
            OAuthAuthorizationCode(
                code=code,
                token=token,
                redirect_uri=redirect_uri,
                client_id=client_id or None,
                expires_at=datetime.utcnow() + timedelta(seconds=AUTH_CODE_TTL_SECONDS),
            )
        )
        session.commit()

    query_string = urlencode({"code": code, "state": state})
    separator = "&" if "?" in redirect_uri else "?"
    return redirect(f"{redirect_uri}{separator}{query_string}")


@app.post("/oauth/token", strict_slashes=False)
def oauth_token():
    payload = request.form if request.form else (request.get_json(silent=True) or {})
    grant_type = (payload.get("grant_type") or "").strip()
    code = (payload.get("code") or "").strip()
    redirect_uri = (payload.get("redirect_uri") or "").strip()
    client_id = (payload.get("client_id") or "").strip()

    if grant_type != "authorization_code":
        return jsonify({"error": "unsupported_grant_type", "error_description": "Only authorization_code is supported."}), 400

    if not code or not redirect_uri:
        return jsonify({"error": "invalid_request", "error_description": "Missing code or redirect_uri."}), 400

    with Session(engine) as session:
        _cleanup_oauth_codes(session)
        auth_payload = session.get(OAuthAuthorizationCode, code)
        if not auth_payload:
            return jsonify({"error": "invalid_grant", "error_description": "Authorization code is invalid or expired."}), 400

        if auth_payload.expires_at <= datetime.utcnow():
            session.delete(auth_payload)
            session.commit()
            return jsonify({"error": "invalid_grant", "error_description": "Authorization code expired."}), 400

        if auth_payload.redirect_uri != redirect_uri:
            return jsonify({"error": "invalid_grant", "error_description": "redirect_uri mismatch."}), 400

        stored_client_id = str(auth_payload.client_id or "")
        if stored_client_id and stored_client_id != client_id:
            return jsonify({"error": "invalid_client", "error_description": "client_id mismatch."}), 400

        access_token = auth_payload.token
        session.delete(auth_payload)
        session.commit()

    return jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    )


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
                "carbs": sum(meal.total_carbs for meal in meals),
                "fiber": sum(meal.total_fiber for meal in meals),
            }
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082, debug=True)

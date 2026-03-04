from datetime import date
import html
import os
import secrets
import time
from urllib.parse import urlencode, urlparse

from flask import Flask, jsonify, redirect, request, send_from_directory
from sqlmodel import Session, select

from app.auth import APIError, TOKEN_PATTERN, get_current_user
from app.database import create_db_and_tables, engine
from app.models import Food, Meal, MealItem, User
from app.parser import calculate_item_nutrition, match_food, parse_meal_text


app = Flask(__name__)
create_db_and_tables()

AUTH_CODE_TTL_SECONDS = 300
OPENAI_CALLBACK_HOSTS = {"chat.openai.com", "chatgpt.com"}
oauth_codes: dict[str, dict[str, str | float]] = {}


def _cleanup_oauth_codes() -> None:
    now = time.time()
    expired_codes = [code for code, payload in oauth_codes.items() if float(payload["expires_at"]) <= now]
    for code in expired_codes:
        oauth_codes.pop(code, None)


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
    escaped_response_type = html.escape(response_type or "authorization_code")

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


@app.get("/oauth/authorize", strict_slashes=False)
def oauth_authorize():
    _cleanup_oauth_codes()

    redirect_uri = request.args.get("redirect_uri", "").strip()
    state = request.args.get("state", "").strip()
    client_id = request.args.get("client_id", "").strip()
    response_type = request.args.get("response_type", "authorization_code").strip()
    token = request.args.get("token", "").strip().upper()

    if not redirect_uri:
        return jsonify({"error": "invalid_request", "error_description": "Missing redirect_uri."}), 400

    if not _is_allowed_redirect_uri(redirect_uri):
        return jsonify({"error": "invalid_request", "error_description": "Invalid redirect_uri."}), 400

    if response_type != "authorization_code":
        return jsonify({"error": "unsupported_response_type", "error_description": "Only authorization_code is supported."}), 400

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
    oauth_codes[code] = {
        "token": token,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "expires_at": time.time() + AUTH_CODE_TTL_SECONDS,
    }

    query_string = urlencode({"code": code, "state": state})
    separator = "&" if "?" in redirect_uri else "?"
    return redirect(f"{redirect_uri}{separator}{query_string}")


@app.post("/oauth/token", strict_slashes=False)
def oauth_token():
    _cleanup_oauth_codes()

    payload = request.form if request.form else (request.get_json(silent=True) or {})
    grant_type = (payload.get("grant_type") or "").strip()
    code = (payload.get("code") or "").strip()
    redirect_uri = (payload.get("redirect_uri") or "").strip()
    client_id = (payload.get("client_id") or "").strip()

    if grant_type != "authorization_code":
        return jsonify({"error": "unsupported_grant_type", "error_description": "Only authorization_code is supported."}), 400

    if not code or not redirect_uri:
        return jsonify({"error": "invalid_request", "error_description": "Missing code or redirect_uri."}), 400

    auth_payload = oauth_codes.pop(code, None)
    if not auth_payload:
        return jsonify({"error": "invalid_grant", "error_description": "Authorization code is invalid or expired."}), 400

    if float(auth_payload["expires_at"]) <= time.time():
        return jsonify({"error": "invalid_grant", "error_description": "Authorization code expired."}), 400

    if auth_payload["redirect_uri"] != redirect_uri:
        return jsonify({"error": "invalid_grant", "error_description": "redirect_uri mismatch."}), 400

    stored_client_id = str(auth_payload.get("client_id") or "")
    if stored_client_id and stored_client_id != client_id:
        return jsonify({"error": "invalid_client", "error_description": "client_id mismatch."}), 400

    return jsonify(
        {
            "access_token": auth_payload["token"],
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
            }
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082, debug=True)

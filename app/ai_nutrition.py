from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from app.parser import normalize_text

try:
    from google import genai
except ImportError:  # pragma: no cover - optional dependency at runtime
    genai = None


DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "ggemini-3.1-flash-lite-preview")
HARDCODED_GEMINI_API_KEY = "AIzaSyBB9aUa9s52BknycCP1Fkzf-5xi8Rps7aI"

@dataclass
class NutritionEstimate:
    normalized_name: str
    aliases: list[str]
    kcal_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float


def _extract_json_payload(raw_text: str) -> dict:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Gemini response does not contain a JSON object.")
    return json.loads(raw_text[start : end + 1])


def estimate_food_nutrition(food_name: str) -> Optional[NutritionEstimate]:
    api_key = HARDCODED_GEMINI_API_KEY.strip()
    if not api_key or genai is None:
        return None

    prompt = f"""
Estimate nutrition values for the food named below.
Return only one JSON object with this exact shape:
{{
  "normalized_name": "ascii lowercase food name",
  "aliases": ["alias 1", "alias 2"],
  "kcal_per_100g": 0,
  "protein_per_100g": 0,
  "carbs_per_100g": 0,
  "fiber_per_100g": 0
}}

Rules:
- values must be per 100g edible portion
- use realistic average nutrition data
- aliases should be short synonyms only
- normalized_name must be lowercase ascii and suitable for a database key
- if uncertain, provide a conservative average estimate
- do not include markdown or explanations

Food: {food_name}
""".strip()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=prompt,
        )
        raw_text = getattr(response, "text", "") or ""
        payload = _extract_json_payload(raw_text)

        normalized_name = normalize_text(str(payload.get("normalized_name") or food_name))
        aliases = [normalize_text(str(alias)) for alias in payload.get("aliases", []) if str(alias).strip()]

        return NutritionEstimate(
            normalized_name=normalized_name,
            aliases=aliases,
            kcal_per_100g=max(0.0, float(payload.get("kcal_per_100g", 0))),
            protein_per_100g=max(0.0, float(payload.get("protein_per_100g", 0))),
            carbs_per_100g=max(0.0, float(payload.get("carbs_per_100g", 0))),
            fiber_per_100g=max(0.0, float(payload.get("fiber_per_100g", 0))),
        )
    except Exception:
        return None
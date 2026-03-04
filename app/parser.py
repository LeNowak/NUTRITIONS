from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.models import Food

@dataclass
class ParsedItem:
    food_name: str
    grams: float


@dataclass
class FoodMatch:
    food: Food
    matched_name: str


WEIGHT_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|gram|grams|gramy)\b", re.IGNORECASE)


def normalize_text(value: str) -> str:
    value = value.strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value)
    return value


def split_aliases(aliases: Optional[str]) -> list[str]:
    if not aliases:
        return []
    return [part.strip() for part in aliases.split("|") if part.strip()]

def parse_meal_text(text: str) -> List[ParsedItem]:
    """
    Prosty parser wyciągający gramaturę i nazwę produktu.
    Obsługuje formaty typu: "400g skyr", "skyr 400g", "100g borowki".
    """
    items = []
    # Rozdzielamy po "i", ",", ";", "+" lub nowej linii
    parts = re.split(r"\s+i\s+|,|;|\+|\n", text)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Szukamy liczby z jednostką (np. 400g, 400 g, 0.4kg)
        weight_match = WEIGHT_PATTERN.search(part)
        
        if weight_match:
            grams_value = float(weight_match.group(1).replace(',', '.'))
            unit = weight_match.group(2).lower()
            grams = grams_value * 1000 if unit == "kg" else grams_value
            # Usuwamy gramaturę z tekstu, aby została sama nazwa
            name = part.replace(weight_match.group(0), '').strip()
            # Usuwamy zbędne słowa i znaki
            name = re.sub(r'^(z|i|ze)\s+', '', name)
            if name:
                items.append(ParsedItem(food_name=normalize_text(name), grams=grams))
                
    return items


def match_food(food_name: str, foods: Iterable[Food]) -> Optional[FoodMatch]:
    query = normalize_text(food_name)
    if not query:
        return None

    exact_match: Optional[FoodMatch] = None
    best_partial: Optional[FoodMatch] = None
    best_partial_score = -1

    for food in foods:
        candidates = [food.name, *split_aliases(food.aliases)]
        for candidate in candidates:
            normalized_candidate = normalize_text(candidate)
            if not normalized_candidate:
                continue

            if normalized_candidate == query:
                exact_match = FoodMatch(food=food, matched_name=food.name)
                break

            if query in normalized_candidate or normalized_candidate in query:
                score = min(len(query), len(normalized_candidate))
                if score > best_partial_score:
                    best_partial = FoodMatch(food=food, matched_name=food.name)
                    best_partial_score = score

        if exact_match:
            break

    return exact_match or best_partial


def calculate_item_nutrition(food: Food, grams: float) -> tuple[float, float]:
    kcal = (food.kcal_per_100g * grams) / 100.0
    protein = (food.protein_per_100g * grams) / 100.0
    return kcal, protein

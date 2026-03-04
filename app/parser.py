from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ParsedItem:
    food_name: str
    grams: float

def parse_meal_text(text: str) -> List[ParsedItem]:
    """
    Prosty parser wyciągający gramaturę i nazwę produktu.
    Obsługuje formaty typu: "400g skyr", "skyr 400g", "100g borowki".
    """
    items = []
    # Rozdzielamy po "i", "," lub nowej linii
    parts = re.split(r' i |,| \+ |\n', text.lower())
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Szukamy liczby z "g" (np. 400g, 400 g)
        weight_match = re.search(r'(\d+(?:[.,]\d+)?)\s*g\b', part)
        
        if weight_match:
            grams = float(weight_match.group(1).replace(',', '.'))
            # Usuwamy gramaturę z tekstu, aby została sama nazwa
            name = part.replace(weight_match.group(0), '').strip()
            # Usuwamy zbędne słowa i znaki
            name = re.sub(r'^(z|i|ze)\s+', '', name)
            if name:
                items.append(ParsedItem(food_name=name, grams=grams))
                
    return items

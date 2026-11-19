from collections import defaultdict
from typing import List, Dict, Any, Tuple
from schemas import DailyPlan, AllowedUnit

VOLUME_TO_ML: Dict[str, float] = {
    "tsp": 4.93,
    "tbsp": 14.79,
    "cup": 236.59,
    "ml": 1.0,
}

CANONICAL_SYNONYMS: Dict[str, str] = {
    "garlic clove": "garlic",
    "garlic cloves": "garlic",
    "fresh garlic": "garlic",
    "extra virgin olive oil": "olive oil",
    "extra-virgin olive oil": "olive oil",
    "boneless skinless chicken breast": "chicken breast",
    "chicken breasts": "chicken breast",
    "fresh spinach": "spinach",
    "baby spinach": "spinach",
    "yellow onions": "yellow onion",
    "red onions": "red onion",
}


def normalize_name(raw_name: str) -> str:
    cleaned = " ".join(raw_name.strip().lower().split())
    return CANONICAL_SYNONYMS.get(cleaned, cleaned)


def normalize_unit(quantity: float, unit: str) -> Tuple[float, str]:
    u = unit.strip().lower()
    if u in VOLUME_TO_ML:
        return quantity * VOLUME_TO_ML[u], "ml"
    return quantity, u


def format_display_volume(ml: float) -> Tuple[float, str]:
    if ml >= 236.59:
        return round(ml / 236.59, 2), "cup"
    if ml >= 14.79:
        return round(ml / 14.79, 1), "tbsp"
    return round(ml, 0), "ml"


def consolidate_groceries(schedule: List[DailyPlan]) -> List[Dict[str, Any]]:
    totals: Dict[Tuple[str, str], float] = defaultdict(float)
    aisle_map: Dict[Tuple[str, str], str] = {}

    for day in schedule:
        for meal in day.meals:
            for ing in meal.ingredients:
                canon_name = normalize_name(ing.name)
                unit_str = ing.unit.value if isinstance(ing.unit, AllowedUnit) else str(ing.unit)
                norm_qty, norm_unit = normalize_unit(ing.quantity, unit_str)

                key = (canon_name, norm_unit)
                totals[key] += norm_qty
                aisle_map[key] = ing.aisle.value if hasattr(ing.aisle, "value") else str(ing.aisle)

    consolidated = []
    for (name, unit), qty in totals.items():
        if unit == "ml":
            display_qty, display_unit = format_display_volume(qty)
        else:
            display_qty, display_unit = round(qty, 2), unit

        consolidated.append(
            {
                "item": name.title(),
                "total_quantity": display_qty,
                "unit": display_unit,
                "aisle": aisle_map[(name, unit)],
            }
        )

    return sorted(consolidated, key=lambda x: (x["aisle"], x["item"]))

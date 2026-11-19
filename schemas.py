from enum import Enum
from typing import List, Any
from pydantic import BaseModel, Field, field_validator

BANNED_SCHEMA_KEYWORDS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
}


class AllowedUnit(str, Enum):
    G = "g"
    ML = "ml"
    CUP = "cup"
    TBSP = "tbsp"
    TSP = "tsp"
    WHOLE = "whole"


class AisleCategory(str, Enum):
    PRODUCE = "Produce"
    PROTEIN = "Meat & Seafood"
    DAIRY_ALT = "Dairy & Alternatives"
    PANTRY = "Pantry & Grains"
    SPICES = "Herbs, Spices & Oils"


class NutritionInfo(BaseModel):
    calories: int = Field(description="Total calories per serving")
    protein_g: float = Field(description="Protein in grams")
    carbs_g: float = Field(description="Total carbohydrates in grams")
    fiber_g: float = Field(description="Dietary fiber in grams")
    net_carbs_g: float = Field(description="Total carbs minus fiber (critical for diabetic tracking)")
    fat_g: float = Field(description="Total fat in grams")
    sodium_mg: int = Field(description="Total sodium in milligrams (critical for low-sodium tracking)")


class Ingredient(BaseModel):
    name: str = Field(description="Normalized lowercase singular ingredient name, e.g. 'chicken breast'")
    quantity: float = Field(description="Numeric quantity greater than 0")
    unit: AllowedUnit = Field(description="Standardized measurement unit")
    aisle: AisleCategory = Field(description="Supermarket aisle category")

    @field_validator("unit", mode="before")
    @classmethod
    def coerce_unit(cls, v: Any) -> Any:
        # Model may return "AllowedUnit.G" or "AllowedUnit.CUP" — strip the prefix
        if isinstance(v, str) and "." in v:
            v = v.split(".")[-1].lower()
        return v

    @field_validator("aisle", mode="before")
    @classmethod
    def coerce_aisle(cls, v: Any) -> Any:
        # Model may return "AisleCategory.PRODUCE" — map to the actual string value
        _aisle_map = {
            "PRODUCE": "Produce",
            "PROTEIN": "Meat & Seafood",
            "DAIRY_ALT": "Dairy & Alternatives",
            "PANTRY": "Pantry & Grains",
            "SPICES": "Herbs, Spices & Oils",
        }
        if isinstance(v, str) and "." in v:
            key = v.split(".")[-1].upper()
            v = _aisle_map.get(key, v)
        return v


class Recipe(BaseModel):
    meal_type: str = Field(description="Breakfast, Lunch, or Dinner")
    title: str = Field(description="Recipe title")
    prep_time_minutes: int = Field(description="Preparation and cooking time in minutes")
    ingredients: List[Ingredient]
    instructions: List[str]
    nutrition_per_serving: NutritionInfo
    dietary_notes: str = Field(description="Brief explanation of why this fits the dietary restrictions")


class DailyPlan(BaseModel):
    day: str = Field(description="Day of the week (Monday through Sunday)")
    meals: List[Recipe]


class WeeklyPlanDraft(BaseModel):
    dietary_profile: str
    weekly_schedule: List[DailyPlan]


def assert_strict_schema_compatible(node: Any, path: str = "root") -> None:
    """Ensures no unsupported JSON Schema range/pattern keywords exist before sending to HF Inference Providers."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in BANNED_SCHEMA_KEYWORDS:
                raise ValueError(
                    f"Strict JSON Schema violation at '{path}.{key}': remove range/pattern validator and move constraint into Field(description=...)."
                )
            assert_strict_schema_compatible(value, f"{path}.{key}")
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            assert_strict_schema_compatible(item, f"{path}[{idx}]")

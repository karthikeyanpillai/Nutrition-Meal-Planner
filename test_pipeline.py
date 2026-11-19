import pytest
from pydantic import BaseModel, Field
from schemas import (
    WeeklyPlanDraft,
    DailyPlan,
    Recipe,
    Ingredient,
    NutritionInfo,
    AllowedUnit,
    AisleCategory,
    assert_strict_schema_compatible,
)
from normalizer import consolidate_groceries


def test_production_schemas_have_no_banned_keywords():
    assert_strict_schema_compatible(WeeklyPlanDraft.model_json_schema())
    assert_strict_schema_compatible(DailyPlan.model_json_schema())


def test_schema_linter_catches_min_max_validators():
    class BadModel(BaseModel):
        sodium_mg: int = Field(le=1500)

    with pytest.raises(ValueError, match="maximum"):
        assert_strict_schema_compatible(BadModel.model_json_schema())


def test_volume_and_synonym_grocery_consolidation():
    sample_nutrition = NutritionInfo(
        calories=400, protein_g=30, carbs_g=20, fiber_g=5, net_carbs_g=15, fat_g=15, sodium_mg=250
    )
    day1 = DailyPlan(
        day="Monday",
        meals=[
            Recipe(
                meal_type="Dinner",
                title="Herb Chicken",
                prep_time_minutes=20,
                ingredients=[
                    Ingredient(name="Olive Oil", quantity=2, unit=AllowedUnit.TSP, aisle=AisleCategory.SPICES),
                    Ingredient(name="Garlic Clove", quantity=2, unit=AllowedUnit.WHOLE, aisle=AisleCategory.PRODUCE),
                ],
                instructions=["Cook chicken."],
                nutrition_per_serving=sample_nutrition,
                dietary_notes="Low sodium",
            )
        ],
    )
    day2 = DailyPlan(
        day="Tuesday",
        meals=[
            Recipe(
                meal_type="Lunch",
                title="Salmon Salad",
                prep_time_minutes=15,
                ingredients=[
                    Ingredient(name="extra virgin olive oil", quantity=2, unit=AllowedUnit.TBSP, aisle=AisleCategory.SPICES),
                    Ingredient(name="fresh garlic", quantity=3, unit=AllowedUnit.WHOLE, aisle=AisleCategory.PRODUCE),
                ],
                instructions=["Toss salad."],
                nutrition_per_serving=sample_nutrition,
                dietary_notes="Diabetic friendly",
            )
        ],
    )

    groceries = consolidate_groceries([day1, day2])
    by_item = {g["item"]: g for g in groceries}

    # 2 tsp (9.86ml) + 2 tbsp (29.58ml) = 39.44ml -> ~2.7 tbsp
    assert "Olive Oil" in by_item
    assert by_item["Olive Oil"]["unit"] == "tbsp"
    assert by_item["Olive Oil"]["total_quantity"] == 2.7

    # Garlic synonyms merged into single line (2 + 3 = 5 whole)
    assert by_item["Garlic"]["total_quantity"] == 5.0
    assert by_item["Garlic"]["unit"] == "whole"

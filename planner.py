import os
import json
import copy
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from openai import OpenAI

from schemas import WeeklyPlanDraft, DailyPlan, assert_strict_schema_compatible
from normalizer import consolidate_groceries

# Validate schemas at import time
assert_strict_schema_compatible(WeeklyPlanDraft.model_json_schema())
assert_strict_schema_compatible(DailyPlan.model_json_schema())

# Active Groq models as of November 2026.
# llama-3.1-8b-instant and llama-3.3-70b-versatile were deprecated Aug 16 2026.
CANDIDATE_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
]

STRICT_SCHEMA_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"}

# Free tier OTPM limit is 1000 tokens/min. One DailyPlan (3 meals) fits in ~900 tokens.
# We generate day-by-day to stay under this cap.
MAX_TOKENS_PER_REQUEST = 900

# Days of the week in order
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _patch_schema_for_strict(schema: dict) -> dict:
    """
    Groq strict:true requires additionalProperties:false on every object node.
    Pydantic doesn't emit that by default, so we add it recursively.
    """
    schema = copy.deepcopy(schema)

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)
    return schema


def _call_structured(
    client: OpenAI,
    messages: list[dict],
    schema_model: type[BaseModel],
    schema_name: str,
) -> tuple:
    """Try each model with strict json_schema, fall back to json_object mode."""
    last_error: Optional[Exception] = None

    for model_id in CANDIDATE_MODELS:
        # Attempt 1: json_schema strict:true
        if model_id in STRICT_SCHEMA_MODELS:
            try:
                strict_schema = _patch_schema_for_strict(schema_model.model_json_schema())
                response = client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=MAX_TOKENS_PER_REQUEST,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "strict": True,
                            "schema": strict_schema,
                        },
                    },
                )
                raw_content = response.choices[0].message.content
                return schema_model.model_validate_json(raw_content), model_id
            except Exception as exc:
                last_error = exc
                # fall through to json_object mode

        # Attempt 2: json_object with schema in prompt
        try:
            schema_str = json.dumps(schema_model.model_json_schema(), indent=2)
            augmented = list(messages)
            augmented[0] = {
                **augmented[0],
                "content": (
                    augmented[0]["content"]
                    + f"\n\nRespond with ONLY a valid JSON object matching this schema:\n{schema_str}"
                ),
            }
            response = client.chat.completions.create(
                model=model_id,
                messages=augmented,
                temperature=0.2,
                max_tokens=MAX_TOKENS_PER_REQUEST,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content
            return schema_model.model_validate_json(raw_content), f"{model_id} (json_object)"
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"All models failed. Last error: {last_error}")


def _generate_single_day(
    client: OpenAI,
    day_name: str,
    restrictions: str,
    max_sodium_mg: int,
    max_net_carbs_g: float,
) -> DailyPlan:
    """Generate one day's meals. Small enough to fit within the free-tier OTPM limit."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a clinical registered dietitian. Return strictly valid JSON matching the schema. "
                "Use normalized singular lowercase ingredient names. "
                "Allowed units: g, ml, cup, tbsp, tsp, whole. "
                "Keep ingredient lists concise (3-5 ingredients per meal) to stay within token limits."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate Breakfast, Lunch, and Dinner for {day_name} for: {restrictions}. "
                f"GUARDRAILS: total daily sodium <= {max_sodium_mg}mg, total daily net carbs <= {max_net_carbs_g}g. "
                f"Set day to '{day_name}'."
            ),
        },
    ]
    day, _ = _call_structured(client, messages, DailyPlan, "single_day_plan")
    day.day = day_name
    return day


def _regenerate_single_day(
    client: OpenAI,
    bad_day: DailyPlan,
    restrictions: str,
    max_sodium_mg: int,
    max_net_carbs_g: float,
) -> DailyPlan:
    """Regenerate a day that failed nutritional guardrails."""
    actual_sodium = sum(m.nutrition_per_serving.sodium_mg for m in bad_day.meals)
    actual_carbs = sum(m.nutrition_per_serving.net_carbs_g for m in bad_day.meals)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a clinical registered dietitian. Return strictly valid JSON matching the schema. "
                "Use normalized singular lowercase ingredient names and allowed units (g, ml, cup, tbsp, tsp, whole). "
                "Keep ingredient lists concise (3-5 per meal)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Regenerate Breakfast, Lunch, and Dinner for {bad_day.day} for: {restrictions}. "
                f"Previous attempt had {actual_sodium}mg sodium (must be <= {max_sodium_mg}mg) "
                f"and {actual_carbs:.1f}g net carbs (must be <= {max_net_carbs_g}g). "
                f"Use herbs, lemon, vinegar, low-glycemic vegetables instead of salt or refined starches. "
                f"Set day to '{bad_day.day}'."
            ),
        },
    ]
    repaired, _ = _call_structured(client, messages, DailyPlan, "single_day_plan")
    repaired.day = bad_day.day
    return repaired


def generate_validated_meal_plan(
    restrictions: str = "Type 2 Diabetic-Friendly & Low-Sodium",
    max_sodium_mg: int = 1500,
    max_net_carbs_g: float = 90.0,
    days: int = 7,
    groq_api_key: Optional[str] = None,
    progress_callback=None,
) -> Dict[str, Any]:
    api_key = (groq_api_key or os.environ.get("GROQ_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("Missing Groq API key. Get a free one at https://console.groq.com")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    day_names = DAYS_OF_WEEK[:days]
    schedule: List[DailyPlan] = []
    repaired_days: List[str] = []
    used_model = "model selected from configured Groq fallback list"

    for i, day_name in enumerate(day_names):
        if progress_callback:
            progress_callback(i, days, day_name)

        # Generate this day
        day = _generate_single_day(client, day_name, restrictions, max_sodium_mg, max_net_carbs_g)

        # Guardrail check — repair up to once if violated
        for _ in range(2):
            day_sodium = sum(m.nutrition_per_serving.sodium_mg for m in day.meals)
            day_carbs = sum(m.nutrition_per_serving.net_carbs_g for m in day.meals)
            if day_sodium <= max_sodium_mg and day_carbs <= max_net_carbs_g:
                break
            day = _regenerate_single_day(client, day, restrictions, max_sodium_mg, max_net_carbs_g)
            if day_name not in repaired_days:
                repaired_days.append(day_name)

        schedule.append(day)

        # Small pause between days to stay within per-minute rate limits
        if i < len(day_names) - 1:
            time.sleep(2)

    enriched_days = []
    for day in schedule:
        enriched_days.append(
            {
                **day.model_dump(),
                "daily_sodium_total_mg": sum(m.nutrition_per_serving.sodium_mg for m in day.meals),
                "daily_net_carbs_total_g": round(
                    sum(m.nutrition_per_serving.net_carbs_g for m in day.meals), 1
                ),
                "daily_calories_total": sum(m.nutrition_per_serving.calories for m in day.meals),
            }
        )

    return {
        "model_used": f"Groq / {used_model}",
        "dietary_profile": restrictions,
        "limits": {
            "max_sodium_mg": max_sodium_mg,
            "max_net_carbs_g": max_net_carbs_g,
        },
        "repaired_days": repaired_days,
        "weekly_schedule": enriched_days,
        "consolidated_grocery_list": consolidate_groceries(schedule),
    }

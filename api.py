from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from planner import generate_validated_meal_plan

app = FastAPI(title="Nutrition & Meal Planner API")


class PlanRequest(BaseModel):
    restrictions: str = "Type 2 Diabetic-Friendly & Low-Sodium"
    max_sodium_mg: int = 1500
    max_net_carbs_g: float = 90.0
    days: int = 7


@app.post("/api/meal-plan")
def create_meal_plan(req: PlanRequest):
    try:
        return generate_validated_meal_plan(
            restrictions=req.restrictions,
            max_sodium_mg=req.max_sodium_mg,
            max_net_carbs_g=req.max_net_carbs_g,
            days=req.days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

# Nutrition & Meal Planner

An AI-powered nutrition and meal-planning application built with Python, Streamlit, Groq, Pydantic, and FastAPI. It generates meal plans from dietary preferences and user-defined sodium/net-carbohydrate targets, validates structured AI responses, retries days that exceed configured nutrition guardrails, and consolidates ingredients into a grocery list.

> **Important:** Nutrition values are AI-generated estimates and should not replace advice from a qualified healthcare professional or registered dietitian. The app does not verify nutrition values against a food database.

## Features

- Generate meal plans for 1–7 days
- Customize dietary restrictions and daily sodium/net-carb targets
- Structured outputs validated with Pydantic schemas
- Daily nutrition summaries and guardrail checks
- Regeneration attempt for days that exceed configured limits
- Consolidated grocery list with ingredient synonym and volume normalization
- Download the generated plan as JSON
- Streamlit web interface
- Optional FastAPI endpoint

## Tech Stack

Python · Streamlit · Groq API (OpenAI-compatible client) · OpenAI Python SDK · Pydantic · FastAPI · Pytest

## Repository Structure

```text
Nutrition_Meal_Planner/
├── app.py                 # Streamlit UI
├── planner.py             # Groq calls, structured output, guardrail retry logic
├── schemas.py             # Pydantic models and schema compatibility checks
├── normalizer.py          # Grocery synonym and unit normalization
├── api.py                 # Optional FastAPI service
├── test_pipeline.py       # Tests
├── requirements.txt
├── .env.example           # Placeholder only; never put a real key here
└── .gitignore
```

## Setup

### 1. Clone and enter the project

```bash
git clone https://github.com/YOUR_USERNAME/Nutrition_Meal_Planner.git
cd Nutrition_Meal_Planner
```

### 2. Create a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your Groq API key

Copy `.env.example` to `.env`, then set your key as an environment variable. The app also allows entering the key in the Streamlit sidebar.

**PowerShell (current terminal session):**

```powershell
$env:GROQ_API_KEY = "your_actual_key_here"
```

**macOS/Linux:**

```bash
export GROQ_API_KEY="your_actual_key_here"
```

Get a key from the Groq Console. **Never commit `.env` or a real API key.**

### 5. Run the Streamlit app

```bash
streamlit run app.py
```

### 6. Run tests

```bash
pytest -v
```

### 7. Optional FastAPI service

```bash
uvicorn api:app --reload --port 8000
```

Open the API docs at `http://127.0.0.1:8000/docs`.

## API Endpoint

`POST /api/meal-plan`

Example request:

```json
{
  "restrictions": "Low sodium and diabetic-friendly",
  "max_sodium_mg": 1500,
  "max_net_carbs_g": 90,
  "days": 3
}
```

The API reads `GROQ_API_KEY` from the environment.

## Security Notes

- API keys are loaded from environment variables or entered into a password-style field in the UI.
- `.env` is excluded by `.gitignore`.
- `.env.example` contains only a placeholder.
- Before publishing, review the repository and Git history for secrets. If a key was ever committed or publicly exposed, revoke it in the provider console and create a replacement.

## License

Add a license file if you intend to allow others to reuse or distribute this project.

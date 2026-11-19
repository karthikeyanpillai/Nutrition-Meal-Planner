import json
import os
from collections import defaultdict
import streamlit as st
from planner import generate_validated_meal_plan

st.set_page_config(page_title="Nutrition & Meal Planner", layout="wide")

st.title("Nutrition & Meal Planner — Powered by Groq")
st.caption(
    "Uses Groq's free inference API (llama-3.3-70b / gpt-oss-20b) with strict Pydantic JSON schemas, "
    "single-day nutritional guardrail self-healing, and unit-normalized grocery consolidation."
)

with st.sidebar:
    st.header("Configuration")
    groq_api_key = st.text_input(
        "Groq API Key (free at console.groq.com)",
        value=os.environ.get("GROQ_API_KEY", ""),
        type="password",
        help="Free Groq API key — no credit card required. Get one at https://console.groq.com",
    ).strip()
    restrictions = st.text_input(
        "Dietary Restrictions",
        value="Type 2 Diabetic-Friendly & Low-Sodium",
    )
    max_sodium_mg = st.number_input("Max Daily Sodium (mg)", min_value=500, max_value=4000, value=1500, step=100)
    max_net_carbs_g = st.number_input("Max Daily Net Carbs (g)", min_value=20, max_value=300, value=90, step=5)
    days = st.slider("Number of Days", min_value=1, max_value=7, value=3)

    generate_btn = st.button("Generate Meal Plan", type="primary", use_container_width=True)

if generate_btn:
    if not groq_api_key:
        st.error("Please enter your Groq API key in the sidebar. Get a free one at https://console.groq.com")
    else:
        progress_bar = st.progress(0, text="Starting...")
        status_text = st.empty()

        def update_progress(current: int, total: int, day_name: str):
            pct = int((current / total) * 100)
            progress_bar.progress(pct, text=f"Generating day {current + 1} of {total}: {day_name}...")
            status_text.caption(f"⏳ Each day is generated separately to stay within free-tier limits.")

        try:
            plan = generate_validated_meal_plan(
                restrictions=restrictions,
                max_sodium_mg=int(max_sodium_mg),
                max_net_carbs_g=float(max_net_carbs_g),
                days=int(days),
                groq_api_key=groq_api_key,
                progress_callback=update_progress,
            )
            progress_bar.progress(100, text="Done!")
            status_text.empty()
            st.session_state["meal_plan"] = plan
        except Exception as exc:
            progress_bar.empty()
            status_text.empty()
            st.error(f"Generation failed: {exc}")

plan = st.session_state.get("meal_plan")

if plan:
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.success(f"Generated using **{plan['model_used']}** | Profile: **{plan['dietary_profile']}**")
        if plan["repaired_days"]:
            st.info(f"Auto-repaired guardrail violations on: {', '.join(plan['repaired_days'])}")
    with top_col2:
        st.download_button(
            label="Download Validated JSON",
            data=json.dumps(plan, indent=2),
            file_name="structured-meal-plan.json",
            mime="application/json",
            use_container_width=True,
        )

    left_col, right_col = st.columns([2, 1], gap="large")

    with left_col:
        st.subheader("Daily Meal Schedule & Guardrails")
        day_names = [d["day"] for d in plan["weekly_schedule"]]
        tabs = st.tabs(day_names)

        for tab, day_data in zip(tabs, plan["weekly_schedule"]):
            with tab:
                m1, m2, m3 = st.columns(3)
                sodium_total = day_data["daily_sodium_total_mg"]
                carbs_total = day_data["daily_net_carbs_total_g"]
                cal_total = day_data["daily_calories_total"]

                m1.metric("Total Calories", f"{cal_total} kcal")
                m2.metric(
                    "Daily Sodium",
                    f"{sodium_total} / {plan['limits']['max_sodium_mg']} mg",
                    delta="Within limit" if sodium_total <= plan["limits"]["max_sodium_mg"] else "Exceeded",
                    delta_color="normal" if sodium_total <= plan["limits"]["max_sodium_mg"] else "inverse",
                )
                m3.metric(
                    "Daily Net Carbs",
                    f"{carbs_total} / {plan['limits']['max_net_carbs_g']} g",
                    delta="Within limit" if carbs_total <= plan["limits"]["max_net_carbs_g"] else "Exceeded",
                    delta_color="normal" if carbs_total <= plan["limits"]["max_net_carbs_g"] else "inverse",
                )

                st.progress(min(sodium_total / max(plan["limits"]["max_sodium_mg"], 1), 1.0), text="Sodium Budget")
                st.progress(min(carbs_total / max(plan["limits"]["max_net_carbs_g"], 1), 1.0), text="Net Carbs Budget")

                for meal in day_data["meals"]:
                    nutr = meal["nutrition_per_serving"]
                    with st.expander(
                        f"{meal['meal_type']}: {meal['title']} ({nutr['calories']} kcal | {nutr['sodium_mg']}mg Na | {nutr['net_carbs_g']}g Net Carbs)",
                        expanded=True,
                    ):
                        st.caption(f"Prep time: {meal['prep_time_minutes']} mins — {meal['dietary_notes']}")
                        c_ing, c_inst = st.columns(2)
                        with c_ing:
                            st.markdown("**Ingredients**")
                            for ing in meal["ingredients"]:
                                # ing["unit"] may be an enum like "AllowedUnit.G" — extract the value after the dot
                                unit_raw = ing["unit"]
                                unit_str = unit_raw.split(".")[-1].lower() if "." in str(unit_raw) else str(unit_raw)
                                st.markdown(f"- {ing['quantity']} {unit_str} {ing['name']}")
                        with c_inst:
                            st.markdown("**Instructions**")
                            for idx, step in enumerate(meal["instructions"], start=1):
                                st.markdown(f"{idx}. {step}")

    with right_col:
        st.subheader("Consolidated Grocery List")
        grouped = defaultdict(list)
        for item in plan["consolidated_grocery_list"]:
            grouped[item["aisle"]].append(item)

        for aisle, items in grouped.items():
            st.markdown(f"**{aisle}**")
            for idx, item in enumerate(items):
                unit_raw = item["unit"]
                unit_str = unit_raw.split(".")[-1].lower() if "." in str(unit_raw) else str(unit_raw)
                label = f"{item['item']} — `{item['total_quantity']} {unit_str}`"
                st.checkbox(label, key=f"chk_{aisle}_{item['item']}_{idx}")

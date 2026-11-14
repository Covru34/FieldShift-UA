"""ІНТЕРФЕЙС (точка входу). Запуск: streamlit run app.py
Власник: Людина 2 · гілка feature/ui-app
Тут лише форми, карта, графіки й картки. Дані беруться з data.py, правила з content.py.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from content import (CURRENT_CROPS, DISCLAIMER, SOIL_WATER_ADJ, explain, pick_best,
                     scenarios_for, score)
from data import load_climate, yearly

st.set_page_config(page_title="FieldShift UA", layout="wide")

st.title("FieldShift UA")
st.caption("Прозорий інструмент підтримки рішень щодо сівозміни · дані NASA POWER")

with st.sidebar:
    st.header("Ваше поле")
    lat = st.number_input("Широта", value=48.52, format="%.4f")
    lon = st.number_input("Довгота", value=35.05, format="%.4f")
    soil_type = st.selectbox("Тип ґрунту", list(SOIL_WATER_ADJ))
    current = st.selectbox("Поточна культура", CURRENT_CROPS)
    priority = st.radio("Пріоритет", ["Менше води", "Здоровіший ґрунт", "Дохід"])
    go = st.button("Analyze", type="primary")

if not go:
    st.info("Оберіть точку, ґрунт і пріоритет, потім натисніть Analyze.")
    st.stop()

try:
    raw, source = load_climate(lat, lon)
except Exception as e:
    st.error(f"Не вдалося отримати дані: {e}")
    st.stop()
clim = yearly(raw)
st.caption(f"Джерело даних: {source}")

st.subheader(f"Клімат вашої точки, {clim.index[0]}–{clim.index[-1]}")
for col, name in zip(st.columns(3), clim.columns):
    col.plotly_chart(px.bar(clim, y=name, title=name), use_container_width=True)

st.subheader("Три сценарії")
scenarios = scenarios_for(current)
results = {n: score(c, clim, soil_type) for n, c in scenarios.items()}
best = pick_best(results, priority)

for col, (name, crops) in zip(st.columns(3), scenarios.items()):
    with col.container(border=True):
        st.markdown(f"### {name}" + ("  ✅" if name == best else ""))
        st.caption("Наступні 3 сезони: " + " → ".join(crops))
        for k, v in results[name].items():
            st.progress(v / 10, text=f"{k}: {v}")

st.subheader("Чому саме цей варіант")
st.write(f"**{best}** найкраще відповідає пріоритету «{priority}».")
st.write(explain(clim, scenarios[best], soil_type))

table = pd.DataFrame(results).T
table.insert(0, "Культури", {n: " → ".join(c) for n, c in scenarios.items()})
st.download_button("Завантажити результат (CSV)",
                   table.to_csv().encode("utf-8-sig"), "fieldshift_result.csv", "text/csv")

st.info(DISCLAIMER)
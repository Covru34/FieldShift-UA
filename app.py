"""FieldShift UA — стартовий скелет Streamlit.
Запуск:  pip install streamlit pandas plotly requests streamlit-folium folium
         streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="FieldShift UA", layout="wide")

# ---------- 1. ДАНІ: NASA POWER (з запасним JSON) ----------
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FALLBACK = Path("fallback_dnipro.json")  # збережіть сюди відповідь API заздалегідь


@st.cache_data(show_spinner="Завантажую дані NASA POWER…")
def load_climate(lat: float, lon: float) -> pd.DataFrame:
    params = {
        "parameters": "T2M_MAX,PRECTOTCORR,GWETROOT",
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": "20210101",
        "end": "20251231",
        "format": "JSON",
    }
    try:
        r = requests.get(POWER_URL, params=params, timeout=30)
        r.raise_for_status()
        raw = r.json()
    except Exception:
        raw = json.loads(FALLBACK.read_text())  # без інтернету працює демо
    p = raw["properties"]["parameter"]
    df = pd.DataFrame(p)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(-999, pd.NA).astype(float)


def yearly(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(df.index.year)
    return pd.DataFrame({
        "Опади, мм": g["PRECTOTCORR"].sum(),
        "Днів T>30°C": g["T2M_MAX"].apply(lambda s: (s > 30).sum()),
        "Вологість кореня": g["GWETROOT"].mean(),
    })


# ---------- 2. КУЛЬТУРИ І СЦЕНАРІЇ (вручну заповнює Людина 3) ----------
# water_need: 1=low .. 3=high; решта 0-10
CROPS = {
    "Озима пшениця": dict(water_need=2, drought=6, fixes_n=0, soil=5, repeat_risk=6),
    "Соняшник":      dict(water_need=2, drought=7, fixes_n=0, soil=3, repeat_risk=8),
    "Кукурудза":     dict(water_need=3, drought=3, fixes_n=0, soil=4, repeat_risk=5),
    "Соя":           dict(water_need=2, drought=5, fixes_n=1, soil=8, repeat_risk=6),
    "Горох":         dict(water_need=1, drought=6, fixes_n=1, soil=8, repeat_risk=7),
    "Сорго":         dict(water_need=1, drought=9, fixes_n=0, soil=6, repeat_risk=3),
    "Покривна культура": dict(water_need=1, drought=6, fixes_n=1, soil=10, repeat_risk=1),
}
SCENARIOS = {
    "Поточний":    ["Озима пшениця", "Соняшник", "Кукурудза"],
    "Soil-first":  ["Озима пшениця", "Соя", "Покривна культура"],
    "Water-first": ["Озима пшениця", "Горох", "Сорго"],
}


def score(crops: list[str], climate: pd.DataFrame, priority: str) -> dict:
    """Прозоре правило: кожна оцінка 0-10, береться середнє по культурах."""
    props = [CROPS[c] for c in crops]
    avg = lambda k: sum(p[k] for p in props) / len(props)
    heat_trend = climate["Днів T>30°C"].iloc[-1] / max(climate["Днів T>30°C"].iloc[0], 1)
    heat_w = min(heat_trend, 2.0) / 2  # 0..1, чим спекотніше, тим важливіша посухостійкість
    water = 10 - (avg("water_need") - 1) * 4.5
    soil = avg("soil") * 0.7 + 3 * sum(p["fixes_n"] for p in props) / len(props) * 1.0
    climate_score = avg("drought") * (0.5 + 0.5 * heat_w) + (10 - avg("repeat_risk")) * 0.2
    return {"Вода": round(min(water, 10), 1),
            "Ґрунт": round(min(soil, 10), 1),
            "Клім. ризик": round(min(climate_score, 10), 1)}


# ---------- 3. ІНТЕРФЕЙС ----------
st.title("FieldShift UA")
st.caption("Прозорий інструмент підтримки рішень щодо сівозміни · дані NASA POWER")

with st.sidebar:
    st.header("Ваше поле")
    lat = st.number_input("Широта", value=48.52, format="%.4f")
    lon = st.number_input("Довгота", value=35.05, format="%.4f")
    # Якщо встигнете карту: from streamlit_folium import st_folium; import folium
    #   m = folium.Map([lat, lon], zoom_start=8); out = st_folium(m); out["last_clicked"]
    soil = st.selectbox("Тип ґрунту", ["Чорнозем типовий", "Каштановий", "Супіщаний"])
    current = st.selectbox("Поточна культура", ["Озима пшениця", "Соняшник", "Кукурудза"])
    priority = st.radio("Пріоритет", ["Менше води", "Здоровіший ґрунт", "Дохід"])
    go = st.button("Analyze", type="primary")

if go:
    clim = yearly(load_climate(lat, lon))

    st.subheader("Клімат вашої точки, 2021–2025")
    cols = st.columns(3)
    for col, name in zip(cols, clim.columns):
        col.plotly_chart(px.bar(clim, y=name, title=name), use_container_width=True)

    st.subheader("Три сценарії")
    weights = {"Менше води": "Вода", "Здоровіший ґрунт": "Ґрунт", "Дохід": "Клім. ризик"}
    results = {n: score(c, clim, priority) for n, c in SCENARIOS.items()}
    key = weights[priority]
    best = max(results, key=lambda n: results[n][key])

    for col, (name, crops) in zip(st.columns(3), SCENARIOS.items()):
        with col.container(border=True):
            st.markdown(f"### {name}" + ("  ✅" if name == best else ""))
            st.caption(" → ".join(crops))
            for k, v in results[name].items():
                st.progress(v / 10, text=f"{k}: {v}")

    st.subheader("Чому саме цей варіант")
    st.write(f"**{best}** найкраще відповідає пріоритету «{priority}». "
             f"За 5 років днів із T>30°C стало {int(clim['Днів T>30°C'].iloc[-1])} "
             f"проти {int(clim['Днів T>30°C'].iloc[0])}, опади та вологість кореневої зони нестабільні.")
    st.info("Прогалини: немає польових даних про вологість, цін і історії культур. "
            "Результат є прототипом для обговорення з локальним агрономом.")
else:
    st.info("Оберіть точку, ґрунт і пріоритет, потім натисніть Analyze.")
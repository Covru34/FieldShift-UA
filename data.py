"""ДАНІ NASA POWER.
Власник: Людина 1 · гілка feature/nasa-data
Редагувати можна лише цей файл. Інші файли імпортують звідси два імені функцій
і три назви колонок — їх НЕ перейменовувати без домовленості з командою.

ЩО ВІДДАЄ ЦЕЙ ФАЙЛ (контракт):
    load_climate(lat, lon) -> (daily: DataFrame, source: str)
    yearly(daily)          -> DataFrame, індекс = роки,
                              колонки COL_RAIN, COL_HEAT, COL_WET
"""
import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FALLBACK = Path(__file__).with_name("fallback_dnipro.json")
START, END = "20210101", "20251231"

# Назви колонок спільні для всіх файлів
COL_RAIN = "Опади, мм"
COL_HEAT = "Днів T>30°C"
COL_WET = "Вологість кореня"


@st.cache_data(show_spinner="Завантажую дані NASA POWER…")
def load_climate(lat: float, lon: float) -> tuple[pd.DataFrame, str]:
    """Щоденні дані для точки. Без інтернету бере збережений файл."""
    params = {
        "parameters": "T2M_MAX,PRECTOTCORR,GWETROOT",
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": START,
        "end": END,
        "format": "JSON",
    }
    source = "NASA POWER (онлайн)"
    try:
        r = requests.get(POWER_URL, params=params, timeout=30)
        r.raise_for_status()
        raw = r.json()
    except Exception:
        if not FALLBACK.exists():
            raise RuntimeError(
                "Немає інтернету, а збереженого файлу fallback_dnipro.json поруч з app.py теж немає."
            )
        raw = json.loads(FALLBACK.read_text())
        source = "NASA POWER (збережена копія для Дніпра, без інтернету)"

    df = pd.DataFrame(raw["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(-999, float("nan")).astype(float), source


def yearly(df: pd.DataFrame) -> pd.DataFrame:
    """Річні підсумки: сума опадів, дні спеки, середня вологість кореня."""
    g = df.groupby(df.index.year)
    return pd.DataFrame({
        COL_RAIN: g["PRECTOTCORR"].sum(),
        COL_HEAT: g["T2M_MAX"].apply(lambda s: int((s > 30).sum())),
        COL_WET: g["GWETROOT"].mean().round(2),
    })
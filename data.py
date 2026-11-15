"""ДАНІ NASA POWER.
Власник: Людина 1 · гілка nasa-data
Редагувати можна лише цей файл. Інші файли імпортують звідси функції й назви колонок —
їх НЕ перейменовувати без домовленості з командою.

ЩО ВІДДАЄ ЦЕЙ ФАЙЛ (контракт):
    load_climate(lat, lon)      -> (daily: DataFrame, source: str)      щоденні дані 2021–2025
    yearly(daily)               -> DataFrame, індекс = роки, колонки COL_RAIN, COL_HEAT, COL_WET
    load_baseline(lat, lon)     -> (norm: Series, source: str)          середнє за 1991–2020, індекс COL_*
    vs_baseline(clim, norm)     -> DataFrame                            відхилення від норми, %
    season_summary(daily)       -> DataFrame                            квітень–вересень + липнева спека
"""
import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
HERE = Path(__file__).parent
FALLBACK = HERE / "fallback_dnipro.json"                       # 2021–2025
FALLBACK_BASELINE = HERE / "fallback_baseline_dnipro.json"     # 1991–2020
START, END = "20210101", "20251231"
BASE_START, BASE_END = "19910101", "20201231"

# Назви колонок спільні для всіх файлів
COL_RAIN = "Опади, мм"
COL_HEAT = "Днів T>30°C"
COL_WET = "Вологість кореня"
# Колонки сезону вегетації (квітень–вересень)
COL_RAIN_S = "Опади вегетації, мм"
COL_HEAT_S = "Днів T>30°C у вегетацію"
COL_WET_S = "Вологість кореня у вегетацію"
COL_JULY = "Днів T>30°C у липні"

GROWING_MONTHS = range(4, 10)  # квітень..вересень


def _get_power(lat: float, lon: float, start: str, end: str, fallback: Path,
               label: str) -> tuple[pd.DataFrame, str]:
    """Один запит до NASA POWER; без інтернету бере збережений файл."""
    params = {
        "parameters": "T2M_MAX,PRECTOTCORR,GWETROOT",
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    source = f"NASA POWER, {label} (онлайн)"
    try:
        r = requests.get(POWER_URL, params=params, timeout=120)
        r.raise_for_status()
        raw = r.json()
    except Exception:
        if not fallback.exists():
            raise RuntimeError(
                f"Немає інтернету, а збереженого файлу {fallback.name} поруч з app.py теж немає."
            )
        raw = json.loads(fallback.read_text())
        source = f"NASA POWER, {label} (збережена копія для Дніпра, без інтернету)"

    df = pd.DataFrame(raw["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(-999, float("nan")).astype(float), source


@st.cache_data(show_spinner="Завантажую дані NASA POWER…")
def load_climate(lat: float, lon: float) -> tuple[pd.DataFrame, str]:
    """Щоденні дані 2021–2025 для точки."""
    return _get_power(lat, lon, START, END, FALLBACK, "2021–2025")


def yearly(df: pd.DataFrame) -> pd.DataFrame:
    """Річні підсумки: сума опадів, дні спеки, середня вологість кореня."""
    g = df.groupby(df.index.year)
    return pd.DataFrame({
        COL_RAIN: g["PRECTOTCORR"].sum(),
        COL_HEAT: g["T2M_MAX"].apply(lambda s: int((s > 30).sum())),
        COL_WET: g["GWETROOT"].mean().round(2),
    })


# ============================================================
# НОРМА 1991–2020
# ============================================================
@st.cache_data(show_spinner="Завантажую кліматичну норму 1991–2020…")
def load_baseline(lat: float, lon: float) -> tuple[pd.Series, str]:
    """Середнє річне за 1991–2020. Повертає Series з індексом COL_RAIN, COL_HEAT, COL_WET."""
    raw, source = _get_power(lat, lon, BASE_START, BASE_END, FALLBACK_BASELINE, "норма 1991–2020")
    return yearly(raw).mean().round(2), source


def vs_baseline(clim: pd.DataFrame, norm: pd.Series) -> pd.DataFrame:
    """Відхилення кожного року від норми у відсотках (+ більше за норму, − менше)."""
    out = pd.DataFrame(index=clim.index)
    for col in (COL_RAIN, COL_HEAT, COL_WET):
        base = norm[col]
        out[col] = ((clim[col] - base) / base * 100).round(0) if base else float("nan")
    return out


# ============================================================
# СЕЗОН ВЕГЕТАЦІЇ І ЛИПНЕВА СПЕКА
# ============================================================
def season_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Підсумки квітня–вересня по роках і кількість днів T>30°C у липні."""
    season = df[df.index.month.isin(GROWING_MONTHS)]
    g = season.groupby(season.index.year)
    july = df[df.index.month == 7]
    july_heat = july.groupby(july.index.year)["T2M_MAX"].apply(lambda s: int((s > 30).sum()))
    return pd.DataFrame({
        COL_RAIN_S: g["PRECTOTCORR"].sum(),
        COL_HEAT_S: g["T2M_MAX"].apply(lambda s: int((s > 30).sum())),
        COL_WET_S: g["GWETROOT"].mean().round(2),
        COL_JULY: july_heat,
    })
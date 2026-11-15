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
    agro_indicators(daily)      -> DataFrame                            сухі періоди, GDD, заморозки, злива
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

# Основні показники NASA POWER (працює весь застосунок) і додаткові (заморозки, GDD, поверхня ґрунту).
# Якщо додаткові недоступні, застосунок працює на основних.
PARAMS_CORE = "T2M_MAX,PRECTOTCORR,GWETROOT"
PARAMS_EXT = PARAMS_CORE + ",T2M_MIN,GWETTOP"

# Назви колонок спільні для всіх файлів
COL_RAIN = "Опади, мм"
COL_HEAT = "Днів T>30°C"
COL_WET = "Вологість кореня"
# Колонки сезону вегетації (квітень–вересень)
COL_RAIN_S = "Опади вегетації, мм"
COL_HEAT_S = "Днів T>30°C у вегетацію"
COL_WET_S = "Вологість кореня у вегетацію"
COL_JULY = "Днів T>30°C у липні"
# Агроіндикатори
COL_DRY = "Найдовший сухий період, днів"
COL_HOT35 = "Днів T>35°C"
COL_HEAVY = "Днів з опадами >10 мм"
COL_GDD = "Сума активних температур >10°C, апр–жов"
COL_LAST_FROST = "Останній весняний заморозок"
COL_FIRST_FROST = "Перший осінній заморозок"
COL_TOPWET = "Вологість поверхні ґрунту, кві–трав"

GROWING_MONTHS = range(4, 10)  # квітень..вересень


def _get_power(lat: float, lon: float, start: str, end: str, fallback: Path,
               label: str, extended: bool = False) -> tuple[pd.DataFrame, str]:
    """Запит до NASA POWER. Спершу з додатковими показниками, потім з основними,
    а без інтернету береться збережений файл."""
    tries = [PARAMS_EXT, PARAMS_CORE] if extended else [PARAMS_CORE]
    raw, source = None, f"NASA POWER, {label} (онлайн)"
    for params_str in tries:
        params = {
            "parameters": params_str,
            "community": "AG",
            "latitude": lat,
            "longitude": lon,
            "start": start,
            "end": end,
            "format": "JSON",
        }
        try:
            r = requests.get(POWER_URL, params=params, timeout=120)
            r.raise_for_status()
            raw = r.json()
            break
        except Exception:
            continue
    if raw is None:
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
    return _get_power(lat, lon, START, END, FALLBACK, "2021–2025", extended=True)


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


# ============================================================
# АГРОІНДИКАТОРИ з тих самих даних NASA POWER
# ============================================================
def _max_run(mask) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def agro_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Показники, зрозумілі фермеру. Колонки, для яких бракує даних, пропускаються
    (заморозки й GDD потребують T2M_MIN, поверхня ґрунту — GWETTOP)."""
    out = {}
    years = sorted(set(df.index.year))
    season = df[df.index.month.isin(GROWING_MONTHS)]

    out[COL_DRY] = {y: _max_run((season.loc[season.index.year == y, "PRECTOTCORR"] < 1).values)
                    for y in years}
    out[COL_HOT35] = {y: int((df.loc[df.index.year == y, "T2M_MAX"] > 35).sum()) for y in years}
    out[COL_HEAVY] = {y: int((df.loc[df.index.year == y, "PRECTOTCORR"] > 10).sum()) for y in years}

    if "T2M_MIN" in df.columns:
        gdd, last_f, first_f = {}, {}, {}
        for y in years:
            d = df[df.index.year == y]
            vegetation = d[(d.index.month >= 4) & (d.index.month <= 10)]
            tmean = (vegetation["T2M_MAX"] + vegetation["T2M_MIN"]) / 2
            gdd[y] = round(float((tmean - 10).clip(lower=0).sum()), 0)
            spring = d[(d.index.month <= 6) & (d["T2M_MIN"] < 0)]
            autumn = d[(d.index.month >= 8) & (d["T2M_MIN"] < 0)]
            last_f[y] = spring.index.max().strftime("%d.%m") if len(spring) else "немає"
            first_f[y] = autumn.index.min().strftime("%d.%m") if len(autumn) else "немає"
        out[COL_GDD] = gdd
        out[COL_LAST_FROST] = last_f
        out[COL_FIRST_FROST] = first_f

    if "GWETTOP" in df.columns:
        sow = df[df.index.month.isin([4, 5])]
        out[COL_TOPWET] = {y: round(float(sow.loc[sow.index.year == y, "GWETTOP"].mean()), 2)
                           for y in years}
    return pd.DataFrame(out)
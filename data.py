import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
HERE = Path(__file__).parent
FALLBACK = HERE / "fallback_dnipro.json"
FALLBACK_BASELINE = HERE / "fallback_baseline_dnipro.json"
START, END = "20210101", "20251231"
BASE_START, BASE_END = "19910101", "20201231"

PARAMS_CORE = "T2M_MAX,PRECTOTCORR,GWETROOT"
PARAMS_EXT = PARAMS_CORE + ",T2M_MIN,GWETTOP"

COL_RAIN = "Precipitation, mm"
COL_HEAT = "Days T>30°C"
COL_WET = "Root zone wetness"
COL_RAIN_S = "Growing season precipitation, mm"
COL_HEAT_S = "Days T>30°C in growing season"
COL_WET_S = "Root zone wetness in growing season"
COL_JULY = "Days T>30°C in July"
COL_DRY = "Longest dry spell, days"
COL_HOT35 = "Days T>35°C"
COL_HEAVY = "Days with precipitation >10 mm"
COL_GDD = "Growing degree days >10°C, Apr–Oct"
COL_LAST_FROST = "Last spring frost"
COL_FIRST_FROST = "First autumn frost"
COL_TOPWET = "Topsoil wetness, Apr–May"

GROWING_MONTHS = range(4, 10)


def _get_power(lat: float, lon: float, start: str, end: str, fallback: Path,
               label: str, extended: bool = False) -> tuple[pd.DataFrame, str]:
    tries = [PARAMS_EXT, PARAMS_CORE] if extended else [PARAMS_CORE]
    raw, source = None, f"NASA POWER, {label} (online)"
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
                f"No internet connection, and the saved file {fallback.name} is not next to app.py either."
            )
        raw = json.loads(fallback.read_text())
        source = f"NASA POWER, {label} (saved copy for Dnipro, offline)"

    df = pd.DataFrame(raw["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(-999, float("nan")).astype(float), source


@st.cache_data(show_spinner="Loading NASA POWER data…")
def load_climate(lat: float, lon: float) -> tuple[pd.DataFrame, str]:
    return _get_power(lat, lon, START, END, FALLBACK, "2021–2025", extended=True)


def yearly(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(df.index.year)
    return pd.DataFrame({
        COL_RAIN: g["PRECTOTCORR"].sum(),
        COL_HEAT: g["T2M_MAX"].apply(lambda s: int((s > 30).sum())),
        COL_WET: g["GWETROOT"].mean().round(2),
    })


@st.cache_data(show_spinner="Loading 1991–2020 climate normal…")
def load_baseline(lat: float, lon: float) -> tuple[pd.Series, str]:
    raw, source = _get_power(lat, lon, BASE_START, BASE_END, FALLBACK_BASELINE, "1991–2020 normal")
    return yearly(raw).mean().round(2), source


def vs_baseline(clim: pd.DataFrame, norm: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame(index=clim.index)
    for col in (COL_RAIN, COL_HEAT, COL_WET):
        base = norm[col]
        out[col] = ((clim[col] - base) / base * 100).round(0) if base else float("nan")
    return out


def season_summary(df: pd.DataFrame) -> pd.DataFrame:
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


def _max_run(mask) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def agro_indicators(df: pd.DataFrame) -> pd.DataFrame:
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
            last_f[y] = spring.index.max().strftime("%d.%m") if len(spring) else "none"
            first_f[y] = autumn.index.min().strftime("%d.%m") if len(autumn) else "none"
        out[COL_GDD] = gdd
        out[COL_LAST_FROST] = last_f
        out[COL_FIRST_FROST] = first_f

    if "GWETTOP" in df.columns:
        sow = df[df.index.month.isin([4, 5])]
        out[COL_TOPWET] = {y: round(float(sow.loc[sow.index.year == y, "GWETTOP"].mean()), 2)
                           for y in years}
    return pd.DataFrame(out)
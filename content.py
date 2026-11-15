from datetime import datetime, timedelta
from itertools import product

import numpy as np
import pandas as pd

from data import (COL_DRY, COL_HEAT, COL_HEAT_S, COL_HEAVY, COL_HOT35, COL_LAST_FROST, COL_RAIN, COL_RAIN_S,
                  COL_WET)

CROPS = {
    "Winter wheat":  dict(water_need=2, drought=6, heat_tol=5, frost_sens=0, erosion=7,  fixes_n=0, soil=5,  repeat_risk=4, income=6),
    "Winter barley": dict(water_need=2, drought=7, heat_tol=5, frost_sens=0, erosion=7,  fixes_n=0, soil=5,  repeat_risk=4, income=5),
    "Spring barley": dict(water_need=1, drought=7, heat_tol=6, frost_sens=3, erosion=5,  fixes_n=0, soil=5,  repeat_risk=4, income=4),
    "Oats":          dict(water_need=2, drought=5, heat_tol=4, frost_sens=3, erosion=5,  fixes_n=0, soil=5,  repeat_risk=3, income=3),
    "Rye":           dict(water_need=1, drought=8, heat_tol=7, frost_sens=0, erosion=8,  fixes_n=0, soil=6,  repeat_risk=3, income=3),
    "Corn":          dict(water_need=3, drought=3, heat_tol=4, frost_sens=8, erosion=4,  fixes_n=0, soil=4,  repeat_risk=4, income=7),
    "Sorghum":       dict(water_need=2, drought=9, heat_tol=9, frost_sens=9, erosion=5,  fixes_n=0, soil=6,  repeat_risk=3, income=4),
    "Millet":        dict(water_need=1, drought=9, heat_tol=9, frost_sens=9, erosion=5,  fixes_n=0, soil=6,  repeat_risk=3, income=3),
    "Buckwheat":     dict(water_need=1, drought=4, heat_tol=3, frost_sens=9, erosion=5,  fixes_n=0, soil=6,  repeat_risk=3, income=5),
    "Sunflower":     dict(water_need=3, drought=7, heat_tol=7, frost_sens=5, erosion=4,  fixes_n=0, soil=3,  repeat_risk=9, income=8),
    "Soybean":       dict(water_need=2, drought=5, heat_tol=5, frost_sens=8, erosion=5,  fixes_n=1, soil=8,  repeat_risk=6, income=7),
    "Pea":           dict(water_need=1, drought=6, heat_tol=3, frost_sens=2, erosion=5,  fixes_n=1, soil=8,  repeat_risk=6, income=5),
    "Chickpea":      dict(water_need=1, drought=8, heat_tol=7, frost_sens=4, erosion=5,  fixes_n=1, soil=8,  repeat_risk=5, income=6),
    "Lentil":        dict(water_need=1, drought=7, heat_tol=6, frost_sens=3, erosion=5,  fixes_n=1, soil=8,  repeat_risk=5, income=5),
    "Rapeseed":      dict(water_need=2, drought=4, heat_tol=3, frost_sens=1, erosion=7,  fixes_n=0, soil=6,  repeat_risk=6, income=8),
    "Sugar beet":    dict(water_need=3, drought=3, heat_tol=4, frost_sens=6, erosion=4,  fixes_n=0, soil=4,  repeat_risk=7, income=7),
    "Potato":        dict(water_need=3, drought=3, heat_tol=2, frost_sens=8, erosion=3,  fixes_n=0, soil=3,  repeat_risk=6, income=7),
    "Alfalfa":       dict(water_need=2, drought=8, heat_tol=7, frost_sens=0, erosion=10, fixes_n=1, soil=9,  repeat_risk=2, income=3),
    "Cover crop":    dict(water_need=1, drought=6, heat_tol=6, frost_sens=1, erosion=10, fixes_n=1, soil=10, repeat_risk=1, income=1),
}

CROP_FAMILY = {
    "Winter wheat": "cereals", "Winter barley": "cereals", "Spring barley": "cereals",
    "Oats": "cereals", "Rye": "cereals", "Corn": "cereals", "Sorghum": "cereals",
    "Millet": "cereals", "Buckwheat": "knotweeds", "Sunflower": "asters",
    "Soybean": "legumes", "Pea": "legumes", "Chickpea": "legumes", "Lentil": "legumes",
    "Alfalfa": "legumes", "Rapeseed": "brassicas", "Sugar beet": "goosefoots",
    "Potato": "nightshades", "Cover crop": "mixed",
}

CALENDAR = {
    "Winter wheat": (10, 7), "Winter barley": (9, 7), "Spring barley": (4, 7), "Oats": (4, 8),
    "Rye": (9, 7), "Corn": (5, 10), "Sorghum": (5, 10), "Millet": (5, 9), "Buckwheat": (5, 9),
    "Sunflower": (4, 9), "Soybean": (5, 9), "Pea": (3, 7), "Chickpea": (4, 8), "Lentil": (4, 7),
    "Rapeseed": (8, 7), "Sugar beet": (4, 10), "Potato": (4, 9), "Alfalfa": (4, 10),
    "Cover crop": (3, 11),
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SOIL_WATER_ADJ = {
    "Typical chernozem": 0.0,
    "Ordinary chernozem": -0.2,
    "Southern chernozem": -0.4,
    "Dark chestnut": -0.4,
    "Chestnut": -0.5,
    "Gray forest": -0.3,
    "Sod-podzolic": -0.8,
    "Meadow": 0.3,
    "Alluvial": 0.2,
    "Clay": 0.2,
    "Loam": 0.0,
    "Sandy loam": -1.5,
    "Sandy": -2.0,
}

CURRENT_CROPS = [c for c in CROPS if c != "Cover crop"]
DEFAULT_EXISTING = ["Winter wheat", "Sunflower", "Corn"]

STRATEGIES = {
    "Soil-first":  ["Pea", "Soybean", "Cover crop", "Alfalfa", "Chickpea", "Lentil",
                    "Winter wheat", "Rye", "Winter barley", "Buckwheat"],
    "Water-first": ["Sorghum", "Chickpea", "Millet", "Rye", "Winter barley", "Spring barley",
                    "Lentil", "Pea", "Sunflower", "Winter wheat"],
}
OPTIMIZED_NAME = "Your priorities"
EXISTING_NAME = "Existing"

METRICS = ["Water", "Soil", "Climate risk", "Income (est.)"]

WEIGHT_PRESETS = {
    "Less water":     {"Water": 4, "Soil": 1, "Climate risk": 4, "Income (est.)": 1},
    "Healthier soil": {"Water": 2, "Soil": 5, "Climate risk": 3, "Income (est.)": 1},
    "Income":         {"Water": 1, "Soil": 1, "Climate risk": 1, "Income (est.)": 5},
}

ECON_DEFAULTS = {
    "Winter wheat":  (4.5,   7000,  26000),
    "Winter barley": (4.2,   6300,  24000),
    "Spring barley": (3.5,   6300,  20000),
    "Oats":          (2.8,   6000,  17000),
    "Rye":           (3.8,   5500,  19000),
    "Corn":          (7.0,   6500,  34000),
    "Sorghum":       (4.0,   6000,  20000),
    "Millet":        (2.0,   8000,  14000),
    "Buckwheat":     (1.6,  22000,  17000),
    "Sunflower":     (2.8,  17000,  22000),
    "Soybean":       (2.5,  16000,  24000),
    "Pea":           (3.0,  12000,  18000),
    "Chickpea":      (1.8,  20000,  20000),
    "Lentil":        (1.6,  22000,  19000),
    "Rapeseed":      (3.0,  19000,  30000),
    "Sugar beet":    (45.0,  1800,  65000),
    "Potato":        (22.0,  6000, 115000),
    "Alfalfa":       (7.0,   3500,  14000),
    "Cover crop":    (0.0,      0,   3000),
}
ECON_COLS = ["Yield, t/ha", "Price, UAH/t", "Costs, UAH/ha"]


def econ_table() -> pd.DataFrame:
    return pd.DataFrame(ECON_DEFAULTS, index=ECON_COLS).T.astype(float)


def margins(scenarios: dict[str, list[str]], econ: pd.DataFrame) -> dict[str, float]:
    out = {}
    for name, crops in scenarios.items():
        vals = [econ.loc[c, ECON_COLS[0]] * econ.loc[c, ECON_COLS[1]] - econ.loc[c, ECON_COLS[2]]
                for c in crops]
        out[name] = round(float(np.mean(vals)), 0)
    return out


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _col_mean(df: pd.DataFrame, col: str):
    if df is None or col not in df.columns:
        return None
    vals = pd.to_numeric(df[col], errors="coerce").dropna()
    return float(vals.mean()) if len(vals) else None


def _doy(text) -> int | None:
    try:
        return datetime.strptime(f"{text}.2021", "%d.%m.%Y").timetuple().tm_yday
    except (ValueError, TypeError):
        return None


def _doy_to_text(doy: float) -> str:
    return (datetime(2021, 1, 1) + timedelta(days=int(round(doy)) - 1)).strftime("%d.%m")


def stress_profile(clim: pd.DataFrame, season: pd.DataFrame, ind: pd.DataFrame,
                   rain_shift: float = 0.0, temp_shift: float = 0.0) -> dict:
    r = rain_shift / 100.0
    notes = []

    drought_parts = []
    rain_s = _col_mean(season, COL_RAIN_S)
    if rain_s is not None:
        drought_parts.append(_clip((450 - rain_s * (1 + r)) / 300))
    wet = _col_mean(clim, COL_WET)
    if wet is not None:
        drought_parts.append(_clip((0.6 - wet * (1 + 0.5 * r)) / 0.3))
    dry = _col_mean(ind, COL_DRY)
    if dry is not None:
        drought_parts.append(_clip((dry * max(0.2, 1 - r) - 8) / 22))
    else:
        notes.append("dry-spell length is not available")
    drought = _clip((float(np.mean(drought_parts)) if drought_parts else 0.5) + 0.06 * temp_shift)

    heat_parts = []
    hot35 = _col_mean(ind, COL_HOT35)
    if hot35 is not None:
        heat_parts.append(_clip((hot35 + 4 * temp_shift) / 12))
    heat30 = _col_mean(season, COL_HEAT_S)
    if heat30 is None:
        heat30 = _col_mean(clim, COL_HEAT)
    if heat30 is not None:
        heat_parts.append(_clip((heat30 + 8 * temp_shift - 25) / 45))
    heat = _clip(float(np.mean(heat_parts)) if heat_parts else 0.5)

    last_frost = None
    if ind is not None and COL_LAST_FROST in ind.columns:
        doys = [d for d in (_doy(v) for v in ind[COL_LAST_FROST]) if d is not None]
        if doys:
            mean_doy = float(np.mean(doys)) - 4 * temp_shift
            last_frost = _doy_to_text(mean_doy)
            frost = _clip((mean_doy - 95) / 45)
        else:
            frost = 0.0
    else:
        frost = 0.3
        notes.append("frost dates are not available (T2M_MIN is missing)")

    heavy = _col_mean(ind, COL_HEAVY)
    if heavy is not None:
        erosion = _clip(heavy * (1 + r) / 25)
    else:
        erosion = 0.3
        notes.append("heavy-rain days are not available")

    return {"drought": drought, "heat": heat, "frost": frost, "erosion": erosion,
            "last_frost": last_frost, "notes": notes}


def coverage(crops: list[str]) -> list[int]:
    n = len(crops)
    cells = [-1] * (12 * n)
    for i, c in enumerate(crops):
        sow, harvest = CALENDAR[c]
        start = 12 * i + sow - 1 if sow <= harvest else 12 * (i - 1) + sow - 1
        end = 12 * i + harvest - 1
        for k in range(end - start + 1):
            cells[(start + k) % (12 * n)] = i
    return cells


def bare_share(crops: list[str]) -> float:
    cells = coverage(crops)
    return sum(1 for v in cells if v < 0) / len(cells)


def family_repeats(crops: list[str]) -> int:
    pairs = zip(crops, crops[1:] + crops[:1])
    return sum(1 for a, b in pairs
               if CROP_FAMILY[a] == CROP_FAMILY[b] and CROP_FAMILY[a] != "mixed")


def score(crops: list[str], profile: dict, soil_type: str) -> dict:
    props = [CROPS[c] for c in crops]
    avg = lambda k: sum(p[k] for p in props) / len(props)
    d, h, f, e = profile["drought"], profile["heat"], profile["frost"], profile["erosion"]
    bare = bare_share(crops)
    repeats = family_repeats(crops)
    water = 10 - (avg("water_need") - 1) * (3 + 3 * d) + SOIL_WATER_ADJ[soil_type]
    soil = (avg("soil") * 0.7 + 3 * avg("fixes_n") + 1.5 + (avg("erosion") - 5) * 0.2 * (0.5 + e)
            - 2 * bare * (0.5 + e) - 1.0 * repeats)
    climate = 10 - (0.5 * d * (10 - avg("drought")) + 0.35 * h * (10 - avg("heat_tol"))
                    + 0.25 * f * avg("frost_sens") + 0.2 * avg("repeat_risk") + 0.5 * repeats)
    clip = lambda x: float(round(max(0, min(x, 10)), 1))
    return {"Water": clip(water), "Soil": clip(soil),
            "Climate risk": clip(climate), "Income (est.)": clip(avg("income"))}


def total(metrics: dict, weights: dict) -> float:
    w = {m: weights.get(m, 0) for m in METRICS}
    s = sum(w.values()) or len(METRICS)
    if sum(w.values()) == 0:
        w = {m: 1 for m in METRICS}
    return round(sum(w[m] * metrics[m] for m in METRICS) / s, 1)


def pick_best(results: dict[str, dict], weights: dict) -> str:
    return max(results, key=lambda n: (total(results[n], weights), results[n]["Climate risk"]))


def _compatible(a: str, b: str) -> bool:
    if a == b:
        return False
    return CROP_FAMILY[a] != CROP_FAMILY[b] or CROP_FAMILY[a] == "mixed"


def scenarios_for(current: str) -> dict[str, list[str]]:
    out = {}
    for name, prefs in STRATEGIES.items():
        seq, prev = [], current
        for i in range(3):
            banned = {CROP_FAMILY[prev]}
            if i == 2:
                banned.add(CROP_FAMILY[seq[0]])
            pick = next((c for c in prefs if c not in seq and CROP_FAMILY[c] not in banned), None)
            if pick is None:
                pick = next((c for c in prefs if c not in seq and c != prev), None)
            if pick is None:
                pick = next(c for c in CROPS if c not in seq and c != prev)
            seq.append(pick)
            prev = pick
        out[name] = seq
    return out


def optimized_rotation(current: str, profile: dict, soil_type: str, weights: dict) -> list[str]:
    pool = list(CROPS)
    best, best_key = None, None
    for a, b, c in product(pool, repeat=3):
        if len({a, b, c}) < 3:
            continue
        if not (_compatible(current, a) and _compatible(a, b) and _compatible(b, c)
                and _compatible(c, a)):
            continue
        seq = [a, b, c]
        m = score(seq, profile, soil_type)
        key = (total(m, weights), m["Climate risk"], m["Soil"])
        if best_key is None or key > best_key:
            best, best_key = seq, key
    return best


def sensitivity(scenarios: dict[str, list[str]], clim: pd.DataFrame, season: pd.DataFrame,
                ind: pd.DataFrame, soil_type: str, weights: dict, axis: str,
                values: list[float]) -> pd.DataFrame:
    rows = {}
    for v in values:
        rain, temp = (v, 0.0) if axis == "rain" else (0.0, v)
        p = stress_profile(clim, season, ind, rain, temp)
        rows[v] = {n: total(score(c, p, soil_type), weights) for n, c in scenarios.items()}
    return pd.DataFrame(rows).T


def robustness(results: dict[str, dict], weights: dict, spread: float = 1.0,
               n: int = 500, seed: int = 0) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    wins = {k: 0 for k in results}
    w = {m: weights.get(m, 0) for m in METRICS}
    if sum(w.values()) == 0:
        w = {m: 1 for m in METRICS}
    for _ in range(n):
        tot = {k: sum(w[m] * (v[m] + rng.uniform(-spread, spread)) for m in METRICS)
               for k, v in results.items()}
        wins[max(tot, key=tot.get)] += 1
    return {k: round(v / n * 100, 0) for k, v in wins.items()}


def rotation_checks(crops: list[str]) -> list[tuple[bool, str]]:
    return [
        (len(set(crops)) >= 3, "At least 3 different crops in the rotation"),
        (any(CROPS[c]["fixes_n"] for c in crops), "Includes a nitrogen-fixing (legume) crop"),
        ("Cover crop" in crops, "Includes a cover crop to protect the soil"),
        (not any(a == b for a, b in zip(crops, crops[1:] + crops[:1])),
         "No crop is grown twice in a row"),
        (family_repeats(crops) == 0, "No crop family follows itself (breaks pest and disease cycles)"),
        (bare_share(crops) <= 0.35, "Fields are bare no more than about 35% of the year"),
    ]


def crop_notes(crop: str) -> list[str]:
    p = CROPS[crop]
    notes = []
    if p["fixes_n"]:
        notes.append("Nitrogen-fixing legume: leaves nitrogen for the next crop")
    if p["erosion"] >= 8:
        notes.append("Dense or long-lasting cover: protects soil from erosion")
    if p["soil"] >= 9:
        notes.append("Strongly improves soil structure and organic matter")
    if p["drought"] >= 8:
        notes.append("Tolerates drought well")
    if p["heat_tol"] >= 8:
        notes.append("Tolerates heat well")
    if p["frost_sens"] >= 8:
        notes.append("Sensitive to late spring frost")
    if p["water_need"] == 3:
        notes.append("High water demand")
    if p["repeat_risk"] >= 8:
        notes.append("Needs a long break before returning to the same field")
    return notes


def _pct(first: float, last: float) -> float:
    return (last - first) / first * 100 if first else 0.0


def explain(clim: pd.DataFrame, crops: list[str], soil_type: str, ind: pd.DataFrame | None = None,
            profile: dict | None = None) -> str:
    y0, y1 = clim.index[0], clim.index[-1]
    rain = _pct(clim[COL_RAIN].iloc[0], clim[COL_RAIN].iloc[-1])
    heat0, heat1 = int(clim[COL_HEAT].iloc[0]), int(clim[COL_HEAT].iloc[-1])
    wet = _pct(clim[COL_WET].iloc[0], clim[COL_WET].iloc[-1])

    facts = []
    if heat1 > heat0:
        facts.append(f"days with T>30 °C have increased ({heat0} in {y0} → {heat1} in {y1})")
    elif heat1 < heat0:
        facts.append(f"days with T>30 °C have decreased ({heat0} → {heat1})")
    if rain <= -10:
        facts.append(f"annual precipitation fell by about {abs(rain):.0f}%")
    elif rain >= 10:
        facts.append(f"annual precipitation rose by about {rain:.0f}%")
    if wet <= -10:
        facts.append(f"root zone wetness dropped by about {abs(wet):.0f}%")
    elif wet >= 10:
        facts.append(f"root zone wetness rose by about {wet:.0f}%")
    if ind is not None and COL_DRY in ind.columns:
        d0, d1 = int(ind[COL_DRY].iloc[0]), int(ind[COL_DRY].iloc[-1])
        if d1 > d0:
            facts.append(f"the longest dry spell in the growing season grew from {d0} to {d1} days")
        elif d1 < d0:
            facts.append(f"the longest dry spell in the growing season shrank from {d0} to {d1} days")
    climate_txt = ("According to NASA POWER, " + "; ".join(facts) + ".") if facts else \
        f"According to NASA POWER, no significant climate change is visible between {y0} and {y1}."

    traits = []
    legumes = [c for c in crops if CROPS[c]["fixes_n"]]
    if legumes:
        traits.append(f"legumes ({', '.join(legumes)}) support nitrogen in the soil")
    most_drought = max(crops, key=lambda c: CROPS[c]["drought"])
    if CROPS[most_drought]["drought"] >= 8:
        traits.append(f"{most_drought} tolerates drought well")
    if all(CROPS[c]["water_need"] <= 2 for c in crops):
        traits.append("none of the crops is among the most water-demanding")
    share = bare_share(crops)
    traits.append(f"fields stay bare about {share:.0%} of the time")
    if profile is not None:
        traits.append(f"estimated drought pressure here is {profile['drought'] * 10:.0f}/10 "
                      f"and heat pressure {profile['heat'] * 10:.0f}/10")
    traits_txt = ("Why this option: " + "; ".join(traits) + ".") if traits else ""

    soil_txt = ""
    if SOIL_WATER_ADJ[soil_type] < 0:
        soil_txt = f" The soil type “{soil_type}” retains moisture less well, so the water score is lowered."
    return f"{climate_txt} {traits_txt}{soil_txt}".strip()


GLOSSARY = {
    "NDVI": "Normalized Difference Vegetation Index. A satellite-derived number showing how green "
            "and dense the vegetation is. Low values on a growing field can signal stress, a bare "
            "field or a late crop.",
    "Evapotranspiration": "Water lost to the air from the soil surface (evaporation) and through plant "
                          "leaves (transpiration). Hot, dry, windy weather raises it and dries the soil faster.",
    "Soil moisture anomaly": "How much wetter or drier the soil is compared with its usual level for "
                             "the same time of year. Persistent negative anomalies point to drought stress.",
    "Root zone wetness": "NASA POWER value from 0 (dry) to 1 (saturated) for the soil layer where "
                         "most roots grow.",
    "Topsoil wetness": "The same idea for the upper soil layer. It matters for germination in "
                       "April–May.",
    "Frost risk": "A day with minimum air temperature below 0 °C. A late spring frost can kill "
                  "young shoots of spring-sown crops.",
    "Growing degree days": "Daily mean temperature above 10 °C added up over the season. It shows "
                           "how much heat was available for crop growth.",
    "Dry spell": "A run of consecutive days with less than 1 mm of precipitation.",
    "Water balance": "Water coming in (rain) minus water going out (evapotranspiration, runoff, "
                     "drainage). A negative balance means crops draw on stored soil water.",
    "Bare-field period": "Months when no crop or cover protects the soil. Bare soil loses moisture "
                         "and is more exposed to erosion.",
    "Nitrogen fixation": "Legumes such as soybean, pea, chickpea and alfalfa host bacteria that turn "
                         "air nitrogen into forms the next crop can use.",
    "Cover crop": "A crop grown mainly to protect and feed the soil rather than to harvest.",
    "Satellite vs ground data": "Satellites see large areas regularly but at coarse resolution and "
                                "indirectly. Ground sensors and field notes are precise at one spot "
                                "but sparse. Combining both gives the most reliable picture.",
}

DATA_FUSION_NOTE = (
    "Daily NASA POWER values (about 0.5° grid, roughly 50 km) are aggregated into a few seasonal "
    "indicators for your point: growing-season rainfall, root zone wetness, longest dry spell, "
    "days above 35 °C, last spring frost date and heavy-rain days. Each indicator is rescaled to "
    "a 0–1 pressure and combined with crop traits to score every rotation. Satellite imagery "
    "(NASA GIBS: true color and NDVI at about 250 m) is shown for visual checking and is not "
    "yet part of the score. SMAP, GPM, ECOSTRESS, Landsat, GRACE and GEDI are not used."
)


SOURCES = {
    "FAO 1986 (SSWM)": "https://sswm.info/water-nutrient-cycle/water-use/hardwares/conservation-soil-moisture/crop-selection",
    "FAO, sorghum": "https://www.fao.org/land-water/databases-and-software/crop-information/sorghum/fr/",
    "GRDC, pea": "https://grdc.com.au/resources-and-publications/all-publications/publications/2018/nitrogen-fixation-in-field-pea",
    "EOS, crop rotation": "https://eos.com/uk/blog/sivozmina/",
}

EVIDENCE = {
    "Winter wheat": [("Water requirement per season", "450–650 mm", "FAO 1986 (SSWM)"),
                     ("Return to the same field", "after 1–3 years", "EOS, crop rotation")],
    "Sunflower":    [("Water requirement per season", "600–1000 mm", "FAO 1986 (SSWM)"),
                     ("Return to the same field", "after 6–9 years", "EOS, crop rotation")],
    "Corn":         [("Water requirement per season", "500–800 mm", "FAO 1986 (SSWM)"),
                     ("Return to the same field", "0–5 years", "EOS, crop rotation"),
                     ("Drought tolerance", "lower than sorghum", "FAO, sorghum")],
    "Soybean":      [("Water requirement per season", "450–700 mm", "FAO 1986 (SSWM)"),
                     ("Return to the same field", "after 3–4 years", "EOS, crop rotation"),
                     ("Legume, good precursor for wheat", "yes", "EOS, crop rotation")],
    "Pea":          [("Water requirement per season", "350–500 mm", "FAO 1986 (SSWM)"),
                     ("Nitrogen in stubble and roots", "71–127 kg/ha (depending on variety)", "GRDC, pea"),
                     ("Return to the same field", "after 3–4 years", "EOS, crop rotation")],
    "Sorghum":      [("Water requirement per season", "450–650 mm", "FAO, sorghum"),
                     ("Drought tolerance", "higher than corn", "FAO, sorghum")],
}

REQUIREMENT_SOURCES = [
    ("Farmers' requirements for decision support tools: usability, cost-effectiveness, "
     "performance, relevance to the user, compatibility with regulatory requirements "
     "(Rose et al., 2016, Agricultural Systems)",
     "https://ore.exeter.ac.uk/repository/handle/10871/26816"),
    ("Ukrainian farmers: shortage of skilled staff (72%), cost of technology, "
     "GPS loss due to electronic warfare (89%) — Digital Agro Ukraine 2026 survey",
     "https://itukraine.org.ua/en/technology-exists-signal-doesn-t-89-of-ukrainian-farmers-name-ew-as-the-top-challenge-to-precision-farming/"),
    ("Digital technologies in Ukraine's grain sector: satellite monitoring, NDVI, "
     "need for cost optimization (FAO Agritech Observatory)",
     "https://agritechobservatory.review.fao.org/en/digital-technologies-in-the-grain-sector-of-ukraine"),
    ("EU conditionality: GAEC 7 (crop rotation) and GAEC 6 (soil cover) — a benchmark for crop rotations in Ukraine on the path to the EU",
     "https://agriculture.ec.europa.eu/common-agricultural-policy/income-support/conditionality_en"),
]

DISCLAIMER = (
    "Gaps: there is no field-level soil moisture or soil analysis, no actual prices or farm costs, "
    "no satellite vegetation indices in the score, and the climate data comes from a coarse grid. “Income (est.)” and the default "
    "economic values are examples that the farmer should replace with their own. Crop properties "
    "are set as expert estimates (FAO, open agricultural sources). The result is a prototype for "
    "discussion with a local agronomist."
)
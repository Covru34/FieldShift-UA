import numpy as np
import pandas as pd

from data import COL_DRY, COL_HEAT, COL_RAIN, COL_WET

CROPS = {
    "Winter wheat":  dict(water_need=2, drought=6, fixes_n=0, soil=5, repeat_risk=4, income=6),
    "Winter barley": dict(water_need=2, drought=7, fixes_n=0, soil=5, repeat_risk=4, income=5),
    "Spring barley": dict(water_need=1, drought=7, fixes_n=0, soil=5, repeat_risk=4, income=4),
    "Oats":          dict(water_need=2, drought=5, fixes_n=0, soil=5, repeat_risk=3, income=3),
    "Rye":           dict(water_need=1, drought=8, fixes_n=0, soil=6, repeat_risk=3, income=3),
    "Corn":          dict(water_need=3, drought=3, fixes_n=0, soil=4, repeat_risk=4, income=7),
    "Sorghum":       dict(water_need=2, drought=9, fixes_n=0, soil=6, repeat_risk=3, income=4),
    "Millet":        dict(water_need=1, drought=9, fixes_n=0, soil=6, repeat_risk=3, income=3),
    "Buckwheat":     dict(water_need=1, drought=4, fixes_n=0, soil=6, repeat_risk=3, income=5),
    "Sunflower":     dict(water_need=3, drought=7, fixes_n=0, soil=3, repeat_risk=9, income=8),
    "Soybean":       dict(water_need=2, drought=5, fixes_n=1, soil=8, repeat_risk=6, income=7),
    "Pea":           dict(water_need=1, drought=6, fixes_n=1, soil=8, repeat_risk=6, income=5),
    "Chickpea":      dict(water_need=1, drought=8, fixes_n=1, soil=8, repeat_risk=5, income=6),
    "Lentil":        dict(water_need=1, drought=7, fixes_n=1, soil=8, repeat_risk=5, income=5),
    "Rapeseed":      dict(water_need=2, drought=4, fixes_n=0, soil=6, repeat_risk=6, income=8),
    "Sugar beet":    dict(water_need=3, drought=3, fixes_n=0, soil=4, repeat_risk=7, income=7),
    "Potato":        dict(water_need=3, drought=3, fixes_n=0, soil=3, repeat_risk=6, income=7),
    "Alfalfa":       dict(water_need=2, drought=8, fixes_n=1, soil=9, repeat_risk=2, income=3),
    "Cover crop":    dict(water_need=1, drought=6, fixes_n=1, soil=10, repeat_risk=1, income=1),
}

CROP_FAMILY = {
    "Winter wheat": "cereals", "Winter barley": "cereals", "Spring barley": "cereals",
    "Oats": "cereals", "Rye": "cereals", "Corn": "cereals", "Sorghum": "cereals",
    "Millet": "cereals", "Buckwheat": "knotweeds", "Sunflower": "asters",
    "Soybean": "legumes", "Pea": "legumes", "Chickpea": "legumes", "Lentil": "legumes",
    "Alfalfa": "legumes", "Rapeseed": "brassicas", "Sugar beet": "goosefoots",
    "Potato": "nightshades", "Cover crop": "mixed",
}

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

STRATEGIES = {
    "Conventional": ["Winter wheat", "Sunflower", "Corn", "Rapeseed", "Soybean", "Sugar beet",
                     "Winter barley", "Potato"],
    "Soil-first":   ["Pea", "Soybean", "Cover crop", "Alfalfa", "Chickpea", "Lentil",
                     "Winter wheat", "Rye", "Winter barley", "Buckwheat"],
    "Water-first":  ["Sorghum", "Chickpea", "Millet", "Rye", "Winter barley", "Spring barley",
                     "Lentil", "Pea", "Sunflower", "Winter wheat"],
}

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


def score(crops: list[str], clim: pd.DataFrame, soil_type: str) -> dict:
    props = [CROPS[c] for c in crops]
    avg = lambda k: sum(p[k] for p in props) / len(props)
    heat_trend = clim[COL_HEAT].iloc[-1] / max(clim[COL_HEAT].iloc[0], 1)
    heat_w = min(heat_trend, 2.0) / 2
    water = 10 - (avg("water_need") - 1) * 4.5 + SOIL_WATER_ADJ[soil_type]
    soil = avg("soil") * 0.7 + 3 * avg("fixes_n")
    climate = avg("drought") * (0.5 + 0.5 * heat_w) + (10 - avg("repeat_risk")) * 0.2
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
    ]


def _pct(first: float, last: float) -> float:
    return (last - first) / first * 100 if first else 0.0


def explain(clim: pd.DataFrame, crops: list[str], soil_type: str, ind: pd.DataFrame | None = None) -> str:
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
    traits_txt = ("Why this option: " + "; ".join(traits) + ".") if traits else ""

    soil_txt = ""
    if SOIL_WATER_ADJ[soil_type] < 0:
        soil_txt = f" The soil type “{soil_type}” retains moisture less well, so the water score is lowered."
    return f"{climate_txt} {traits_txt}{soil_txt}".strip()


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
    "Gaps: there is no field data on soil moisture, no actual prices or farm costs, "
    "no satellite vegetation indices and no weather forecast. “Income (est.)” and the default "
    "economic values are examples that the farmer should replace with their own. Crop properties "
    "are set as expert estimates (FAO, open agricultural sources). The result is a prototype for "
    "discussion with a local agronomist."
)
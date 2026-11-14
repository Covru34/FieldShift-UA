"""КУЛЬТУРИ, ПРАВИЛА ОЦІНКИ І ТЕКСТ ПОЯСНЕНЬ.
Власник: Людина 3 · гілка feature/crops-scoring
Новачку достатньо правити лише розділ 1 (таблиці). Розділи 2–3 — формули й текст,
їх змінюйте разом із Людиною 2 або через ШІ.

ЩО ВІДДАЄ ЦЕЙ ФАЙЛ (контракт):
    CROPS, SOIL_WATER_ADJ, CURRENT_CROPS, PRIORITY_KEY, METRICS
    scenarios_for(current)       -> {назва сценарію: [3 культури]}
    score(crops, clim, soil)     -> {метрика: 0..10}
    explain(clim, crops, soil)   -> текст пояснення
"""
import pandas as pd

from data import COL_HEAT, COL_RAIN, COL_WET

# ============================================================
# 1. ТАБЛИЦІ — ТУТ ПРАВИМО ЦИФРИ
#    water_need: 1=мало, 2=середньо, 3=багато (мм за сезон, FAO)
#    drought, soil, repeat_risk, income: шкала 0-10
#    fixes_n: 1 якщо фіксує азот (бобові)
#    income — УМОВНА демо-оцінка, без ринкових даних
# ============================================================
CROPS = {
    "Озима пшениця": dict(water_need=2, drought=6, fixes_n=0, soil=5, repeat_risk=4, income=6),
    "Соняшник":      dict(water_need=3, drought=7, fixes_n=0, soil=3, repeat_risk=9, income=8),
    "Кукурудза":     dict(water_need=3, drought=3, fixes_n=0, soil=4, repeat_risk=4, income=7),
    "Соя":           dict(water_need=2, drought=5, fixes_n=1, soil=8, repeat_risk=6, income=7),
    "Горох":         dict(water_need=1, drought=6, fixes_n=1, soil=8, repeat_risk=6, income=5),
    "Сорго":         dict(water_need=2, drought=9, fixes_n=0, soil=6, repeat_risk=3, income=4),
    "Покривна культура": dict(water_need=1, drought=6, fixes_n=1, soil=10, repeat_risk=1, income=1),
}

# Поправка до оцінки води залежно від ґрунту (припущення: пісок гірше тримає вологу)
SOIL_WATER_ADJ = {"Чорнозем типовий": 0.0, "Каштановий": -0.5, "Супіщаний": -1.5}

CURRENT_CROPS = ["Озима пшениця", "Соняшник", "Кукурудза"]

BASE_SCENARIOS = {
    "Поточний":    ["Озима пшениця", "Соняшник", "Кукурудза"],
    "Soil-first":  ["Озима пшениця", "Соя", "Покривна культура"],
    "Water-first": ["Озима пшениця", "Горох", "Сорго"],
}

# Який пріоритет фермера → яка метрика вирішує
PRIORITY_KEY = {"Менше води": "Вода", "Здоровіший ґрунт": "Ґрунт", "Дохід": "Дохід (умовно)"}
METRICS = ["Вода", "Ґрунт", "Клім. ризик", "Дохід (умовно)"]


# ============================================================
# 2. ФОРМУЛИ ОЦІНКИ
# ============================================================
def scenarios_for(current: str) -> dict[str, list[str]]:
    """Кожен сценарій починається не з тієї культури, що вже росте на полі."""
    out = {}
    for name, seq in BASE_SCENARIOS.items():
        seq = list(seq)
        for _ in range(len(seq)):
            if seq[0] != current:
                break
            seq = seq[1:] + seq[:1]
        out[name] = seq
    return out


def score(crops: list[str], clim: pd.DataFrame, soil_type: str) -> dict:
    """Прозоре правило: оцінки 0-10, середнє по культурах сценарію."""
    props = [CROPS[c] for c in crops]
    avg = lambda k: sum(p[k] for p in props) / len(props)
    heat_trend = clim[COL_HEAT].iloc[-1] / max(clim[COL_HEAT].iloc[0], 1)
    heat_w = min(heat_trend, 2.0) / 2  # 0..1: чим спекотніше, тим важливіша посухостійкість
    water = 10 - (avg("water_need") - 1) * 4.5 + SOIL_WATER_ADJ[soil_type]
    soil = avg("soil") * 0.7 + 3 * avg("fixes_n")
    climate = avg("drought") * (0.5 + 0.5 * heat_w) + (10 - avg("repeat_risk")) * 0.2
    clip = lambda x: float(round(max(0, min(x, 10)), 1))
    return {"Вода": clip(water), "Ґрунт": clip(soil),
            "Клім. ризик": clip(climate), "Дохід (умовно)": clip(avg("income"))}


def pick_best(results: dict[str, dict], priority: str) -> str:
    """Переможець за пріоритетом; при рівності вирішує кліматичний ризик."""
    key = PRIORITY_KEY[priority]
    return max(results, key=lambda n: (results[n][key], results[n]["Клім. ризик"]))


# ============================================================
# 3. ТЕКСТ ПОЯСНЕННЯ (складається з реальних цифр)
# ============================================================
def _pct(first: float, last: float) -> float:
    return (last - first) / first * 100 if first else 0.0


def explain(clim: pd.DataFrame, crops: list[str], soil_type: str) -> str:
    y0, y1 = clim.index[0], clim.index[-1]
    rain = _pct(clim[COL_RAIN].iloc[0], clim[COL_RAIN].iloc[-1])
    heat0, heat1 = int(clim[COL_HEAT].iloc[0]), int(clim[COL_HEAT].iloc[-1])
    wet = _pct(clim[COL_WET].iloc[0], clim[COL_WET].iloc[-1])

    facts = []
    if heat1 > heat0:
        facts.append(f"днів із T>30 °C стало більше ({heat0} у {y0} → {heat1} у {y1})")
    elif heat1 < heat0:
        facts.append(f"днів із T>30 °C стало менше ({heat0} → {heat1})")
    if rain <= -10:
        facts.append(f"річні опади зменшилися приблизно на {abs(rain):.0f}%")
    elif rain >= 10:
        facts.append(f"річні опади зросли приблизно на {rain:.0f}%")
    if wet <= -10:
        facts.append(f"вологість кореневої зони впала приблизно на {abs(wet):.0f}%")
    elif wet >= 10:
        facts.append(f"вологість кореневої зони зросла приблизно на {wet:.0f}%")
    climate_txt = ("За даними NASA POWER " + "; ".join(facts) + ".") if facts else \
        f"За даними NASA POWER суттєвих змін клімату між {y0} і {y1} не видно."

    traits = []
    legumes = [c for c in crops if CROPS[c]["fixes_n"]]
    if legumes:
        traits.append(f"бобові ({', '.join(legumes)}) підтримують азот у ґрунті")
    most_drought = max(crops, key=lambda c: CROPS[c]["drought"])
    if CROPS[most_drought]["drought"] >= 8:
        traits.append(f"{most_drought} добре переносить посуху")
    if all(CROPS[c]["water_need"] <= 2 for c in crops):
        traits.append("жодна культура не належить до найвибагливіших до води")
    traits_txt = ("Чому цей варіант: " + "; ".join(traits) + ".") if traits else ""

    soil_txt = ""
    if SOIL_WATER_ADJ[soil_type] < 0:
        soil_txt = f" Ґрунт «{soil_type}» гірше тримає вологу, тому оцінку води знижено."
    return f"{climate_txt} {traits_txt}{soil_txt}".strip()


DISCLAIMER = (
    "Прогалини: немає польових даних про вологість ґрунту, цін на зерно та історії культур. "
    "«Дохід» — умовна демо-оцінка. Властивості культур задані як експертні оцінки "
    "(FAO, відкриті аграрні джерела). Результат є прототипом для обговорення з локальним агрономом."
)
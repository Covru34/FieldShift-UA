"""КУЛЬТУРИ, ПРАВИЛА ОЦІНКИ, ЕКОНОМІКА, ДОКАЗИ, ТЕКСТИ.
Власник: Людина 3 · гілка scoring-explanations
Новачку достатньо правити лише розділ 1 (таблиці) і розділ 5 (джерела).
Розділи 2–4 — формули й тексти, їх змінюйте разом із Людиною 2 або через ШІ.

ЩО ВІДДАЄ ЦЕЙ ФАЙЛ (контракт):
    CROPS, SOIL_WATER_ADJ, CURRENT_CROPS, METRICS, WEIGHT_PRESETS, EVIDENCE, SOURCES, REQUIREMENT_SOURCES
    scenarios_for(current)             -> {назва сценарію: [3 культури]}
    score(crops, clim, soil)           -> {метрика: 0..10}
    total(metrics, weights)            -> одне число 0..10
    pick_best(results, weights)        -> назва найкращого сценарію
    robustness(results, weights)       -> {сценарій: % випадків, коли він найкращий}
    econ_table()                       -> DataFrame (редагується фермером)
    margins(scenarios, econ)           -> {сценарій: грн/га/рік}
    rotation_checks(crops)             -> [(ok, текст)]
    explain(clim, crops, soil)         -> текст пояснення
"""
import numpy as np
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

METRICS = ["Вода", "Ґрунт", "Клім. ризик", "Дохід (умовно)"]

# Пресети ваг 0..5 для пріоритетів фермера (фермер може підкрутити повзунками)
# «Менше води» враховує і низьке споживання, і посухостійкість, тому клімат-ризик має високу вагу.
WEIGHT_PRESETS = {
    "Менше води":       {"Вода": 4, "Ґрунт": 1, "Клім. ризик": 4, "Дохід (умовно)": 1},
    "Здоровіший ґрунт": {"Вода": 2, "Ґрунт": 5, "Клім. ризик": 3, "Дохід (умовно)": 1},
    "Дохід":            {"Вода": 1, "Ґрунт": 1, "Клім. ризик": 1, "Дохід (умовно)": 5},
}

# ============================================================
# 2. ЕКОНОМІКА. УВАГА: цифри нижче — ПРИКЛАДИ-ЗАПОВНЮВАЧІ, не ринкові дані.
#    Фермер має ввести свої: урожайність т/га, ціна грн/т, витрати грн/га.
# ============================================================
ECON_DEFAULTS = {
    #                    т/га, грн/т, грн/га
    "Озима пшениця":     (4.5,  7000, 26000),
    "Соняшник":          (2.8, 17000, 22000),
    "Кукурудза":         (7.0,  6500, 34000),
    "Соя":               (2.5, 16000, 24000),
    "Горох":             (3.0, 12000, 18000),
    "Сорго":             (4.0,  6000, 20000),
    "Покривна культура": (0.0,     0,  3000),
}
ECON_COLS = ["Урожайність, т/га", "Ціна, грн/т", "Витрати, грн/га"]


def econ_table() -> pd.DataFrame:
    return pd.DataFrame(ECON_DEFAULTS, index=ECON_COLS).T.astype(float)


def margins(scenarios: dict[str, list[str]], econ: pd.DataFrame) -> dict[str, float]:
    """Середня валова маржа за 3 сезони, грн/га на рік (сума: урожай·ціна − витрати)."""
    out = {}
    for name, crops in scenarios.items():
        vals = [econ.loc[c, ECON_COLS[0]] * econ.loc[c, ECON_COLS[1]] - econ.loc[c, ECON_COLS[2]]
                for c in crops]
        out[name] = round(float(np.mean(vals)), 0)
    return out


# ============================================================
# 3. ФОРМУЛИ ОЦІНКИ
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


def total(metrics: dict, weights: dict) -> float:
    """Зважена оцінка 0..10. Якщо всі ваги нульові, рахуємо їх рівними."""
    w = {m: weights.get(m, 0) for m in METRICS}
    s = sum(w.values()) or len(METRICS)
    if sum(w.values()) == 0:
        w = {m: 1 for m in METRICS}
    return round(sum(w[m] * metrics[m] for m in METRICS) / s, 1)


def pick_best(results: dict[str, dict], weights: dict) -> str:
    """Переможець за зваженою оцінкою; при рівності вирішує кліматичний ризик."""
    return max(results, key=lambda n: (total(results[n], weights), results[n]["Клім. ризик"]))


def robustness(results: dict[str, dict], weights: dict, spread: float = 1.0,
               n: int = 500, seed: int = 0) -> dict[str, float]:
    """Наскільки висновок стійкий: n разів змінюємо кожну оцінку на випадкові ±spread балів
    і рахуємо, у скількох % випадків кожен сценарій виявляється найкращим."""
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
    """Орієнтовні перевірки сівозміни за логікою вимог ЄС до сівозмін і покриття ґрунту
    (GAEC 6–7). Це НЕ юридична перевірка відповідності."""
    return [
        (len(set(crops)) >= 3, "Щонайменше 3 різні культури в ротації"),
        (any(CROPS[c]["fixes_n"] for c in crops), "Є азотфіксуюча (бобова) культура"),
        ("Покривна культура" in crops, "Є покривна культура для захисту ґрунту"),
        (not any(a == b for a, b in zip(crops, crops[1:] + crops[:1])),
         "Немає тієї самої культури двічі поспіль"),
    ]


# ============================================================
# 4. ТЕКСТ ПОЯСНЕННЯ (складається з реальних цифр)
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


# ============================================================
# 5. ДЖЕРЕЛА Й ДОКАЗИ
# ============================================================
SOURCES = {
    "FAO 1986 (SSWM)": "https://sswm.info/water-nutrient-cycle/water-use/hardwares/conservation-soil-moisture/crop-selection",
    "FAO, сорго": "https://www.fao.org/land-water/databases-and-software/crop-information/sorghum/fr/",
    "GRDC, горох": "https://grdc.com.au/resources-and-publications/all-publications/publications/2018/nitrogen-fixation-in-field-pea",
    "EOS, сівозміна": "https://eos.com/uk/blog/sivozmina/",
}

# (показник, значення, ключ у SOURCES)
EVIDENCE = {
    "Озима пшениця": [("Потреба у воді за сезон", "450–650 мм", "FAO 1986 (SSWM)"),
                      ("Повернення на те саме поле", "через 1–3 роки", "EOS, сівозміна")],
    "Соняшник":      [("Потреба у воді за сезон", "600–1000 мм", "FAO 1986 (SSWM)"),
                      ("Повернення на те саме поле", "через 6–9 років", "EOS, сівозміна")],
    "Кукурудза":     [("Потреба у воді за сезон", "500–800 мм", "FAO 1986 (SSWM)"),
                      ("Повернення на те саме поле", "0–5 років", "EOS, сівозміна"),
                      ("Посухостійкість", "нижча, ніж у сорго", "FAO, сорго")],
    "Соя":           [("Потреба у воді за сезон", "450–700 мм", "FAO 1986 (SSWM)"),
                      ("Повернення на те саме поле", "через 3–4 роки", "EOS, сівозміна"),
                      ("Бобова, попередник для пшениці", "так", "EOS, сівозміна")],
    "Горох":         [("Потреба у воді за сезон", "350–500 мм", "FAO 1986 (SSWM)"),
                      ("Азот у стерні й коренях", "71–127 кг/га (залежно від сорту)", "GRDC, горох"),
                      ("Повернення на те саме поле", "через 3–4 роки", "EOS, сівозміна")],
    "Сорго":         [("Потреба у воді за сезон", "450–650 мм", "FAO, сорго"),
                      ("Посухостійкість", "вища, ніж у кукурудзи", "FAO, сорго")],
}

# Джерела ВИМОГ до інструмента (з чого виведено функції сайту)
REQUIREMENT_SOURCES = [
    ("Вимоги фермерів до інструментів підтримки рішень: зручність, економічна ефективність, "
     "результативність, релевантність користувачу, сумісність із вимогами регуляторів "
     "(Rose et al., 2016, Agricultural Systems)",
     "https://ore.exeter.ac.uk/repository/handle/10871/26816"),
    ("Українські аграрії: нестача кваліфікованих кадрів (72%), вартість технологій, "
     "втрата GPS через РЕБ (89%) — опитування Digital Agro Ukraine 2026",
     "https://itukraine.org.ua/en/technology-exists-signal-doesn-t-89-of-ukrainian-farmers-name-ew-as-the-top-challenge-to-precision-farming/"),
    ("Цифрові технології в зерновому секторі України: супутниковий моніторинг, NDVI, "
     "потреба в оптимізації витрат (FAO Agritech Observatory)",
     "https://agritechobservatory.review.fao.org/en/digital-technologies-in-the-grain-sector-of-ukraine"),
    ("Умовність ЄС: GAEC 7 (сівозміна) і GAEC 6 (покриття ґрунту) — орієнтир для сівозмін в Україні на шляху до ЄС",
     "https://agriculture.ec.europa.eu/common-agricultural-policy/income-support/conditionality_en"),
]

DISCLAIMER = (
    "Прогалини: немає польових даних про вологість ґрунту, фактичних цін і витрат господарства, "
    "супутникових індексів рослинності та прогнозу погоди. «Дохід (умовно)» і економічні значення "
    "за замовчуванням є прикладами, які фермер має замінити своїми. Властивості культур задані як "
    "експертні оцінки (FAO, відкриті аграрні джерела). Результат є прототипом для обговорення "
    "з локальним агрономом."
)
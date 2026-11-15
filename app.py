"""ІНТЕРФЕЙС (точка входу). Запуск: python -m streamlit run app.py
Власник: Людина 2 · гілка interface
Тут лише форми, графіки й картки. Дані беруться з data.py, правила з content.py.
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from content import (CROPS, CURRENT_CROPS, DISCLAIMER, ECON_COLS, EVIDENCE, METRICS, SOIL_WATER_ADJ,
                     SOURCES, REQUIREMENT_SOURCES, WEIGHT_PRESETS, econ_table, explain, margins,
                     pick_best, robustness, rotation_checks, scenarios_for, score, total)
from data import (COL_HEAT, COL_JULY, load_baseline, load_climate, season_summary, vs_baseline,
                  yearly)

st.set_page_config(page_title="FieldShift UA", layout="wide")

# Карта Leaflet (без збірки): повертає координати подвійного кліку.
# Файл компонента: components/map_picker/index.html
_map_picker = components.declare_component(
    "map_picker", path=str(Path(__file__).parent / "components" / "map_picker"))
_dialog = getattr(st, "dialog", None) or st.experimental_dialog


@_dialog("Оберіть місце на карті", width="large")
def map_dialog() -> None:
    st.caption("Двічі клікніть по карті, щоб поставити 📍. Тема карти — у правому верхньому куті.")
    val = _map_picker(lat=st.session_state["lat"], lon=st.session_state["lon"],
                      theme=st.session_state.get("map_theme", "Звичайна"), zoom=6,
                      key=f"map_picker_{st.session_state.get('map_n', 0)}", default=None)
    if val and val.get("id") != st.session_state.get("_last_pick"):
        st.session_state["_last_pick"] = val["id"]
        st.session_state["_pending"] = (float(val["lat"]), float(val["lon"]))
        st.session_state["map_theme"] = val.get("theme") or "Звичайна"
        st.session_state["map_n"] = st.session_state.get("map_n", 0) + 1
        st.rerun()


st.title("FieldShift UA")
st.caption("Прозорий інструмент підтримки рішень щодо сівозміни · дані NASA POWER · "
           "працює без GPS: точку задають координатами")

# ---------------- Введення ----------------
# координати з карти застосовуємо до віджетів до їх створення
st.session_state.setdefault("lat", 48.52)
st.session_state.setdefault("lon", 35.05)
if "_pending" in st.session_state:
    st.session_state["lat"], st.session_state["lon"] = st.session_state.pop("_pending")

with st.sidebar:
    st.header("Ваше поле")
    pick_map = st.button("📍 Обрати місце на карті")
    lat = st.number_input("Широта", format="%.4f", key="lat")
    lon = st.number_input("Довгота", format="%.4f", key="lon")
    soil_type = st.selectbox("Тип ґрунту", list(SOIL_WATER_ADJ))
    current = st.selectbox("Поточна культура", CURRENT_CROPS)
    preset = st.radio("Головний пріоритет", list(WEIGHT_PRESETS))
    with st.expander("Налаштувати важливість критеріїв (0–5)"):
        weights = {m: st.slider(m, 0, 5, WEIGHT_PRESETS[preset][m], key=f"w_{m}_{preset}")
                   for m in METRICS}
    if st.button("Analyze", type="primary"):
        st.session_state["ready"] = True

if pick_map:
    map_dialog()

if not st.session_state.get("ready"):
    st.info("Оберіть точку, ґрунт і пріоритет, потім натисніть Analyze.")
    st.stop()

# ---------------- Дані ----------------
try:
    raw, source = load_climate(lat, lon)
except Exception as e:
    st.error(f"Не вдалося отримати дані: {e}")
    st.stop()
clim = yearly(raw)
season = season_summary(raw)
try:
    norm, norm_source = load_baseline(lat, lon)
    dev = vs_baseline(clim, norm)
except Exception:
    norm, dev = None, None

# ---------------- Розрахунок ----------------
scenarios = scenarios_for(current)
results = {n: score(c, clim, soil_type) for n, c in scenarios.items()}
totals = {n: total(results[n], weights) for n in results}
best = pick_best(results, weights)

tab_res, tab_clim, tab_econ, tab_risk, tab_proof, tab_about = st.tabs(
    ["Результат", "Клімат", "Економіка", "Надійність і ризики", "Докази й джерела", "Про метод"])

# ---- Результат ----
with tab_res:
    st.subheader("Три сценарії на наступні 3 сезони")
    for col, (name, crops) in zip(st.columns(3), scenarios.items()):
        with col.container(border=True):
            st.markdown(f"### {name}" + ("  ✅" if name == best else ""))
            st.caption(" → ".join(crops))
            st.metric("Загальна оцінка", f"{totals[name]} / 10")
            for k, v in results[name].items():
                st.progress(v / 10, text=f"{k}: {v}")
    st.subheader("Чому саме цей варіант")
    st.write(f"**{best}** має найвищу загальну оцінку за вашими пріоритетами "
             f"({', '.join(f'{m}: {w}' for m, w in weights.items())}).")
    st.write(explain(clim, scenarios[best], soil_type))

    table = pd.DataFrame(results).T
    table.insert(0, "Культури", {n: " → ".join(c) for n, c in scenarios.items()})
    table["Загальна оцінка"] = pd.Series(totals)
    st.download_button("Завантажити результат (CSV)", table.to_csv().encode("utf-8-sig"),
                       "fieldshift_result.csv", "text/csv")

# ---- Клімат ----
with tab_clim:
    st.caption(f"Джерело: {source}" + (f" · норма: {norm_source}" if norm is not None else ""))
    st.subheader(f"Клімат вашої точки, {clim.index[0]}–{clim.index[-1]}")
    for col, name in zip(st.columns(3), clim.columns):
        fig = px.bar(clim, y=name, title=name)
        if norm is not None:
            fig.add_hline(y=float(norm[name]), line_dash="dash", annotation_text="норма 1991–2020")
        col.plotly_chart(fig, use_container_width=True)
        if dev is not None:
            col.caption(f"{clim.index[-1]}: {dev[name].iloc[-1]:+.0f}% до норми")
    st.subheader("Сезон вегетації (квітень–вересень) і спека в липні")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(season, y=season.columns[0], title=season.columns[0]), use_container_width=True)
    c2.plotly_chart(px.bar(season, y=COL_JULY, title=COL_JULY), use_container_width=True)
    if norm is None:
        st.warning("Норму 1991–2020 завантажити не вдалося: порівняння не показано.")

# ---- Економіка ----
with tab_econ:
    st.subheader("Орієнтовна маржа сівозміни")
    st.warning("Значення в таблиці є прикладами-заповнювачами, а не ринковими даними. "
               "Введіть власні: урожайність, ціну продажу й витрати вашого господарства.")
    econ = st.data_editor(econ_table(), key="econ", use_container_width=True)
    mar = margins(scenarios, econ)
    st.plotly_chart(px.bar(x=list(mar), y=list(mar.values()), labels={"x": "", "y": "грн/га на рік"},
                           title="Середня валова маржа за 3 сезони, грн/га на рік"),
                    use_container_width=True)
    st.caption("Маржа = урожайність × ціна − витрати, середнє по культурах сценарію. "
               "Це не враховує ризик посухи: дивіться вкладку «Надійність і ризики».")

# ---- Надійність і ризики ----
with tab_risk:
    st.subheader("Наскільки стійкий висновок")
    rob = robustness(results, weights)
    st.plotly_chart(px.bar(x=list(rob), y=list(rob.values()),
                           labels={"x": "", "y": "% випадків як найкращий"},
                           title="Якщо кожна оцінка помилена на ±1 бал"), use_container_width=True)
    st.caption("Ми 500 разів випадково змінюємо кожну оцінку на ±1 бал і рахуємо, "
               "який сценарій виходить найкращим. Висока частка означає стійкий висновок.")
    st.subheader("Орієнтири за вимогами ЄС до сівозмін і покриття ґрунту")
    for col, (name, crops) in zip(st.columns(3), scenarios.items()):
        with col.container(border=True):
            st.markdown(f"**{name}**")
            for ok, text in rotation_checks(crops):
                st.write(("✅ " if ok else "⚠️ ") + text)
    st.caption("Це орієнтири за логікою GAEC 6–7, а не юридична перевірка відповідності.")

# ---- Докази ----
with tab_proof:
    st.subheader("Властивості культур і джерела")
    crops_shown = sorted({c for cs in scenarios.values() for c in cs}, key=list(CROPS).index)
    for c in crops_shown:
        with st.expander(c):
            st.write(pd.DataFrame([CROPS[c]]).rename(index={0: "оцінка"}).T)
            for what, value, src in EVIDENCE.get(c, []):
                st.markdown(f"- {what}: **{value}** ([{src}]({SOURCES[src]}))")
            if c not in EVIDENCE:
                st.caption("Для цієї культури джерела ще не додано (експертна оцінка).")
    st.caption("Цифри без посилання є експертними оцінками і потребують перевірки агрономом.")

# ---- Про метод ----
with tab_about:
    st.subheader("Як рахуються оцінки")
    st.markdown(
        "- **Вода**: потреба культур у воді за сезон (FAO), з поправкою на тип ґрунту.\n"
        "- **Ґрунт**: користь культур для ґрунту плюс бонус за фіксацію азоту.\n"
        "- **Клімат. ризик**: посухостійкість (важливіша, якщо зростає кількість днів спеки) "
        "і ризик повторного вирощування.\n"
        "- **Дохід (умовно)**: демо-оцінка; реальну маржу дивіться на вкладці «Економіка».\n"
        "- **Загальна оцінка** — середнє зважене за вашими пріоритетами."
    )
    st.subheader("З чого виведено вимоги до інструмента")
    for text, url in REQUIREMENT_SOURCES:
        st.markdown(f"- [{text}]({url})")
    st.info(DISCLAIMER)
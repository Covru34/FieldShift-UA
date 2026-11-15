from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from content import (CROPS, CURRENT_CROPS, DISCLAIMER, EVIDENCE, METRICS, SOIL_WATER_ADJ,
                     SOURCES, REQUIREMENT_SOURCES, WEIGHT_PRESETS, econ_table, explain, margins,
                     pick_best, robustness, rotation_checks, scenarios_for, score, total)
from data import (COL_DRY, COL_FIRST_FROST, COL_GDD, COL_HEAVY, COL_HOT35, COL_JULY,
                  COL_LAST_FROST, COL_TOPWET, agro_indicators, load_baseline, load_climate,
                  season_summary, vs_baseline, yearly)

st.set_page_config(page_title="FieldShift UA", layout="wide")

_map_picker = components.declare_component(
    "map_picker", path=str(Path(__file__).parent / "components" / "map_picker"))
_dialog = getattr(st, "dialog", None) or st.experimental_dialog


def apply_pick(val) -> None:
    if val and val.get("id") != st.session_state.get("_last_pick"):
        st.session_state["_last_pick"] = val["id"]
        st.session_state["_pending"] = (float(val["lat"]), float(val["lon"]))
        theme = (val.get("theme") or "Standard").split(" (")[0]
        st.session_state["map_theme"] = theme
        st.session_state["map_n"] = st.session_state.get("map_n", 0) + 1
        st.rerun()


@_dialog("Choose a location on the map", width="large")
def map_dialog() -> None:
    st.caption("Double-click the map to drop a 📍. Layers (including NASA imagery) "
               "can be switched in the top right corner.")
    val = _map_picker(lat=st.session_state["lat"], lon=st.session_state["lon"],
                      theme=st.session_state.get("map_theme", "Standard"), zoom=6,
                      key=f"map_picker_{st.session_state.get('map_n', 0)}", default=None)
    apply_pick(val)


st.title("FieldShift UA")
st.caption("A transparent decision-support tool for crop rotation · NASA POWER and NASA GIBS data · "
           "works without GPS: the location is set by coordinates")

st.session_state.setdefault("lat", 48.52)
st.session_state.setdefault("lon", 35.05)
if "_pending" in st.session_state:
    st.session_state["lat"], st.session_state["lon"] = st.session_state.pop("_pending")

with st.sidebar:
    st.header("Your field")
    pick_map = st.button("📍 Choose location on map")
    lat = st.number_input("Latitude", format="%.4f", key="lat")
    lon = st.number_input("Longitude", format="%.4f", key="lon")
    soil_type = st.selectbox("Soil type", list(SOIL_WATER_ADJ))
    current = st.selectbox("Current crop", CURRENT_CROPS)
    preset = st.radio("Main priority", list(WEIGHT_PRESETS))
    with st.expander("Adjust criteria importance (0–5)"):
        weights = {m: st.slider(m, 0, 5, WEIGHT_PRESETS[preset][m], key=f"w_{m}_{preset}")
                   for m in METRICS}
    if st.button("Analyze", type="primary"):
        st.session_state["ready"] = True

if pick_map:
    map_dialog()

if not st.session_state.get("ready"):
    st.info("Choose a location, soil type and priority, then click Analyze.")
    st.stop()

try:
    raw, source = load_climate(lat, lon)
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()
clim = yearly(raw)
season = season_summary(raw)
ind = agro_indicators(raw)
try:
    norm, norm_source = load_baseline(lat, lon)
    dev = vs_baseline(clim, norm)
except Exception:
    norm, dev = None, None

scenarios = scenarios_for(current)
results = {n: score(c, clim, soil_type) for n, c in scenarios.items()}
totals = {n: total(results[n], weights) for n in results}
best = pick_best(results, weights)

(tab_res, tab_clim, tab_nasa, tab_econ, tab_risk, tab_proof, tab_about) = st.tabs(
    ["Result", "Climate", "NASA: satellite and agro indicators", "Economics",
     "Reliability and risks", "Evidence and sources", "About the method"])

with tab_res:
    st.subheader("Three scenarios for the next 3 seasons")
    for col, (name, crops) in zip(st.columns(3), scenarios.items()):
        with col.container(border=True):
            st.markdown(f"### {name}" + ("  ✅" if name == best else ""))
            st.caption(" → ".join(crops))
            st.metric("Overall score", f"{totals[name]} / 10")
            for k, v in results[name].items():
                st.progress(v / 10, text=f"{k}: {v}")
    st.subheader("Why this option")
    st.write(f"**{best}** has the highest overall score for your priorities "
             f"({', '.join(f'{m}: {w}' for m, w in weights.items())}).")
    st.write(explain(clim, scenarios[best], soil_type, ind))

    table = pd.DataFrame(results).T
    table.insert(0, "Crops", {n: " → ".join(c) for n, c in scenarios.items()})
    table["Overall score"] = pd.Series(totals)
    st.download_button("Download result (CSV)", table.to_csv().encode("utf-8-sig"),
                       "fieldshift_result.csv", "text/csv")

with tab_clim:
    st.caption(f"Source: {source}" + (f" · normal: {norm_source}" if norm is not None else ""))
    st.subheader(f"Climate at your location, {clim.index[0]}–{clim.index[-1]}")
    for col, name in zip(st.columns(3), clim.columns):
        fig = px.bar(clim, y=name, title=name)
        if norm is not None:
            fig.add_hline(y=float(norm[name]), line_dash="dash", annotation_text="1991–2020 normal")
        col.plotly_chart(fig, use_container_width=True)
        if dev is not None:
            col.caption(f"{clim.index[-1]}: {dev[name].iloc[-1]:+.0f}% vs normal")
    st.subheader("Growing season (April–September) and July heat")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(season, y=season.columns[0], title=season.columns[0]), use_container_width=True)
    c2.plotly_chart(px.bar(season, y=COL_JULY, title=COL_JULY), use_container_width=True)
    if norm is None:
        st.warning("Could not load the 1991–2020 normal: comparison is not shown.")

with tab_nasa:
    st.subheader("NASA satellite image over your location")
    st.caption("NASA GIBS layers (Terra satellite, MODIS instrument): true color and NDVI, "
               "the green biomass index (the higher, the denser the vegetation). "
               "Switch the layer in the top right corner. Internet is required. "
               "Resolution is about 250 m, so this is an overview of the area, not an image of a specific field.")
    val = _map_picker(lat=lat, lon=lon, theme="NASA: true color", zoom=9,
                      key=f"map_sat_{st.session_state.get('map_n', 0)}", default=None)
    apply_pick(val)

    st.subheader("Agro indicators from NASA POWER data")
    show = ind.copy()
    cols_chart = [c for c in (COL_DRY, COL_HOT35, COL_HEAVY, COL_GDD, COL_TOPWET) if c in show.columns]
    for row in range(0, len(cols_chart), 3):
        for col, name in zip(st.columns(3), cols_chart[row:row + 3]):
            col.plotly_chart(px.bar(show, y=name, title=name), use_container_width=True)
    frost_cols = [c for c in (COL_LAST_FROST, COL_FIRST_FROST) if c in show.columns]
    if frost_cols:
        st.markdown("**Frosts (T min < 0 °C)**")
        st.dataframe(show[frost_cols], use_container_width=True)
    else:
        st.info("Frosts, growing degree days and topsoil wetness will not be shown: "
                "the data has no T2M_MIN and GWETTOP. Download the updated file "
                "fallback_dnipro.json (see README) or connect to the internet.")
    st.caption("Dry spell: consecutive days with precipitation below 1 mm in April–September. "
               "Growing degree days: the sum of daily mean temperature above 10 °C "
               "from April to October. Frost: minimum temperature below 0 °C. "
               "Everything is calculated from daily NASA POWER data.")
    st.markdown(
        "NASA sources: [NASA POWER](https://power.larc.nasa.gov/) · "
        "[NASA GIBS](https://nasa-gibs.github.io/gibs-api-docs/) · "
        "[NASA Worldview](https://worldview.earthdata.nasa.gov/)")

with tab_econ:
    st.subheader("Approximate rotation margin")
    st.warning("The values in the table are placeholder examples, not market data. "
               "Enter your own: yield, selling price and costs of your farm.")
    econ = st.data_editor(econ_table(), key="econ", use_container_width=True)
    mar = margins(scenarios, econ)
    st.plotly_chart(px.bar(x=list(mar), y=list(mar.values()), labels={"x": "", "y": "UAH/ha per year"},
                           title="Average gross margin over 3 seasons, UAH/ha per year"),
                    use_container_width=True)
    st.caption("Margin = yield × price − costs, averaged over the crops in the scenario. "
               "It does not account for drought risk: see the “Reliability and risks” tab.")

with tab_risk:
    st.subheader("How robust is the conclusion")
    rob = robustness(results, weights)
    st.plotly_chart(px.bar(x=list(rob), y=list(rob.values()),
                           labels={"x": "", "y": "% of cases ranked best"},
                           title="If each score is off by ±1 point"), use_container_width=True)
    st.caption("We randomly shift each score by ±1 point 500 times and count "
               "which scenario comes out best. A high share means a robust conclusion.")
    st.subheader("Benchmarks based on EU crop rotation and soil cover requirements")
    for col, (name, crops) in zip(st.columns(3), scenarios.items()):
        with col.container(border=True):
            st.markdown(f"**{name}**")
            for ok, text in rotation_checks(crops):
                st.write(("✅ " if ok else "⚠️ ") + text)
    st.caption("These are benchmarks following the logic of GAEC 6–7, not a legal compliance check.")

with tab_proof:
    st.subheader("Crop properties and sources")
    crops_shown = sorted({c for cs in scenarios.values() for c in cs}, key=list(CROPS).index)
    for c in crops_shown:
        with st.expander(c):
            st.write(pd.DataFrame([CROPS[c]]).rename(index={0: "score"}).T)
            for what, value, src in EVIDENCE.get(c, []):
                st.markdown(f"- {what}: **{value}** ([{src}]({SOURCES[src]}))")
            if c not in EVIDENCE:
                st.caption("No sources have been added for this crop yet (expert estimate).")
    st.caption("Figures without a link are expert estimates and need to be verified by an agronomist.")

with tab_about:
    st.subheader("How the scores are calculated")
    st.markdown(
        "- **Water**: crop water requirement per season (FAO), adjusted for soil type.\n"
        "- **Soil**: benefit of the crops to the soil plus a bonus for nitrogen fixation.\n"
        "- **Climate risk**: drought tolerance (more important if the number of hot days grows) "
        "and the risk of growing the same crop repeatedly.\n"
        "- **Income (est.)**: a demo estimate; see the real margin on the “Economics” tab.\n"
        "- **Overall score** is the average weighted by your priorities."
    )
    st.subheader("Which NASA data the analysis is based on")
    st.markdown(
        "- **NASA POWER**: daily T2M_MAX, T2M_MIN, PRECTOTCORR, GWETROOT, GWETTOP "
        "(2021–2025), 1991–2020 normal.\n"
        "- **NASA GIBS**: Terra/MODIS imagery (true color and NDVI) on the map.\n"
        "- Agro indicators (dry spell, heat above 35 °C, heavy rain, growing degree days, "
        "frosts) are calculated from POWER data."
    )
    st.subheader("Where the tool's requirements come from")
    for text, url in REQUIREMENT_SOURCES:
        st.markdown(f"- [{text}]({url})")
    st.info(DISCLAIMER)
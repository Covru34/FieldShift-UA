import json
import socket
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
UA = "FieldShiftUA/1.0 (crop rotation decision support)"


def _get_json(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _finish(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["time"] = pd.to_datetime(d["time"])
    d["temp"] = (d["tmax"] + d["tmin"]) / 2
    d["rain"] = d["rain"].fillna(0.0)
    d["label"] = d["time"].dt.weekday.map(lambda i: DAYS[i]) + "<br>" + d["time"].dt.strftime("%d.%m")
    return d.reset_index(drop=True)


def parse_open_meteo(data: dict) -> pd.DataFrame:
    d = pd.DataFrame(data["daily"]).rename(columns={
        "temperature_2m_max": "tmax", "temperature_2m_min": "tmin", "precipitation_sum": "rain"})
    d["time"] = pd.to_datetime(d["time"])
    h = pd.DataFrame(data["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    hum = h.groupby(h["time"].dt.normalize())["relative_humidity_2m"].mean()
    d["humidity"] = d["time"].map(hum)
    return _finish(d[["time", "tmax", "tmin", "rain", "humidity"]])


def _open_meteo(lat: float, lon: float) -> pd.DataFrame:
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "hourly": "relative_humidity_2m"})
    return parse_open_meteo(_get_json(f"https://api.open-meteo.com/v1/forecast?{q}"))


def parse_met_no(data: dict, lon: float) -> pd.DataFrame:
    off = timedelta(hours=round(lon / 15))
    days = defaultdict(lambda: {"t": [], "h": [], "p": 0.0, "n": 0})
    for ts in data["properties"]["timeseries"]:
        t = datetime.fromisoformat(ts["time"].replace("Z", "+00:00")) + off
        det = ts["data"]["instant"]["details"]
        day = days[t.date()]
        day["n"] += 1
        day["t"].append(det["air_temperature"])
        if "relative_humidity" in det:
            day["h"].append(det["relative_humidity"])
        nxt = ts["data"].get("next_1_hours") or ts["data"].get("next_6_hours")
        if nxt:
            day["p"] += nxt["details"].get("precipitation_amount", 0.0)
    rows = [(str(k), max(v["t"]), min(v["t"]), v["p"],
             sum(v["h"]) / len(v["h"]) if v["h"] else 0.0)
            for k, v in sorted(days.items()) if v["n"] >= 3][:7]
    if not rows:
        raise ValueError("MET Norway returned no data")
    return _finish(pd.DataFrame(rows, columns=["time", "tmax", "tmin", "rain", "humidity"]))


def _met_no(lat: float, lon: float) -> pd.DataFrame:
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.4f}&lon={lon:.4f}"
    return parse_met_no(_get_json(url), lon)


def _why(e: Exception) -> str:
    r = getattr(e, "reason", e)
    if isinstance(r, socket.gaierror):
        return "could not find the server (no internet, or DNS/VPN blocks the site)"
    if isinstance(r, (socket.timeout, TimeoutError)):
        return "the server did not respond in time"
    return str(r)


def get_forecast(lat: float, lon: float):
    errors = []
    for name, fn in (("Open-Meteo", _open_meteo), ("MET Norway", _met_no)):
        try:
            return fn(lat, lon), name
        except Exception as e:
            errors.append(f"{name}: {_why(e)}")
    raise RuntimeError("; ".join(errors))
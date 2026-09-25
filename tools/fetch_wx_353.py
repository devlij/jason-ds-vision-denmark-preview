#!/usr/bin/env python3
"""One Open-Meteo HTTP request per scene for DK-01-353 through DK-01-365.

Each call sleeps so the HTTP Date second is not shared. Nothing here is reused
from an earlier retrieval.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CPH = ZoneInfo("Europe/Copenhagen")
OUT = Path(__file__).resolve().parent / "wx-dk-01-353-365.json"

SITES = [
    ("DK-01-353", 55.68497, 12.58955),
    ("DK-01-354", 55.67529, 12.57790),
    ("DK-01-355", 55.07396, 14.81501),
    ("DK-01-356", 55.93509, 12.30079),
    ("DK-01-357", 55.65369, 11.07988),
    ("DK-01-358", 55.18885, 11.72520),
    ("DK-01-359", 55.09654, 10.24576),
    ("DK-01-360", 55.32993, 8.76179),
    ("DK-01-361", 55.05695, 8.95042),
    ("DK-01-362", 56.95464, 8.68917),
    ("DK-01-363", 62.35981, -6.54361),
    ("DK-01-364", 68.70959, -52.85130),
    ("DK-01-365", 64.17825, -51.74482),
]


def fetch_one(entry: str, lat: float, lon: float) -> dict:
    query = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "current": "temperature_2m,cloud_cover,wind_speed_10m,precipitation,snowfall,weather_code,is_day",
            "daily": "sunrise,sunset",
            "timezone": "Europe/Copenhagen",
            "forecast_days": "1",
            "past_days": "1",
            "wind_speed_unit": "kmh",
        }
    )
    url = "https://api.open-meteo.com/v1/forecast?" + query
    req = urllib.request.Request(url, headers={"User-Agent": "JasonDsVisionDenmark/1.0"})
    started = datetime.now(CPH).replace(microsecond=0)
    with urllib.request.urlopen(req, timeout=40) as resp:
        http_date = resp.headers.get("Date")
        received = datetime.now(CPH).replace(microsecond=0)
        body = json.loads(resp.read().decode())
    if not http_date:
        raise SystemExit(f"{entry} missing HTTP Date")
    current = body["current"]
    daily = body["daily"]
    if len(daily["time"]) < 2:
        raise SystemExit(f"{entry} daily {daily['time']}")
    valid = current["time"]
    hour = valid[11:13]
    if not received.strftime("%Y-%m-%dT%H") == f"2026-09-25T{hour}":
        raise SystemExit(f"{entry} valid {valid} received {received.isoformat()}")
    if int(current["interval"]) != 900:
        raise SystemExit(f"{entry} interval {current['interval']}")
    if int(current["is_day"]) != 1:
        raise SystemExit(f"{entry} is_day {current['is_day']}")
    # yesterday is the first daily row when past_days=1
    return {
        "retrieved": received.isoformat(),
        "retrieved_start": started.isoformat(),
        "http_date": http_date,
        "request_lat": lat,
        "request_lon": lon,
        "lat": body["latitude"],
        "lon": body["longitude"],
        "temp": current["temperature_2m"],
        "cloud": current["cloud_cover"],
        "wind": current["wind_speed_10m"],
        "precip": current["precipitation"],
        "snow": current["snowfall"],
        "code": current["weather_code"],
        "is_day": current["is_day"],
        "valid": valid,
        "current_interval": current["interval"],
        "sunrise_today": daily["sunrise"][1],
        "sunset_today": daily["sunset"][1],
        "sunset_yesterday": daily["sunset"][0],
        "sunrise_yesterday": daily["sunrise"][0],
        "utc_offset": body.get("utc_offset_seconds"),
        "elevation": body.get("elevation"),
    }


def main() -> None:
    rows = {}
    seen_dates = set()
    for entry, lat, lon in SITES:
        row = fetch_one(entry, lat, lon)
        key = (row["retrieved"], row["http_date"])
        if key in seen_dates:
            raise SystemExit(f"reused stamp {entry} {key}")
        seen_dates.add(key)
        rows[entry] = row
        print(entry, row["retrieved"], row["http_date"], row["valid"], row["code"], row["temp"], row["cloud"])
        time.sleep(2.2)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT, "count", len(rows))


if __name__ == "__main__":
    main()

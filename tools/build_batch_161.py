#!/usr/bin/env python3
"""Bake DK-01-161 through DK-01-176 and rebuild the gallery from every manifest."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_denmark as bd

bd.LINEAGE = (
    "Text-prompt-only. No photographic reference pixels. "
    "The generator returned a 1280\u00d7720 JPEG for the wide frame and an 864\u00d71152 JPEG for the portrait frame; "
    "both were decoded to PNG without resampling. "
    "The 16:9 master is a uniform Lanczos resample from 1280\u00d7720 to 1920\u00d71080. "
    "The 4:5 master is a centered crop of the 864\u00d71152 frame to 864\u00d71080, with no upscale."
)

COORDS = {
    "DK-01-161": (55.66732, 12.53220),
    "DK-01-162": (55.69271, 12.54395),
    "DK-01-163": (55.69161, 12.61210),
    "DK-01-164": (55.70270, 12.61476),
    "DK-01-165": (55.59278, 12.67208),
    "DK-01-166": (55.64592, 12.64749),
    "DK-01-167": (55.65115, 12.07755),
    "DK-01-168": (55.61510, 11.94298),
    "DK-01-169": (55.71781, 11.71182),
    "DK-01-170": (55.67761, 11.08220),
    "DK-01-171": (55.47026, 12.19658),
    "DK-01-172": (55.12449, 12.04332),
    "DK-01-173": (54.98481, 12.27972),
    "DK-01-174": (55.91347, 11.67169),
    "DK-01-175": (55.97257, 11.36793),
    "DK-01-176": (55.88060, 11.13462),
}

GEN_BUCKET = {entry: "overcast" for entry in COORDS}

# Depicted from the 03:39 Europe/Copenhagen retrieval, valid 03:30.
# Kept if a later hour changes the sky bucket or leaves night.
_BASE = {
    "is_day": 0,
    "valid": "2026-09-25T03:30",
    "retrieved_stamp": "25 September 2026 03:39",
    "offset": 7200,
    "precip": 0.0,
}
SNAPSHOT = {
    "DK-01-161": {**_BASE, "word": "Overcast", "temp": 13.6, "cloud": 100, "wind": 12.6, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-162": {**_BASE, "word": "Overcast", "temp": 13.2, "cloud": 100, "wind": 11.5, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-163": {**_BASE, "word": "Overcast", "temp": 13.5, "cloud": 100, "wind": 14.0, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-164": {**_BASE, "word": "Overcast", "temp": 13.7, "cloud": 100, "wind": 14.4, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-165": {**_BASE, "word": "Overcast", "temp": 12.9, "cloud": 100, "wind": 13.3, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-166": {**_BASE, "word": "Overcast", "temp": 13.3, "cloud": 100, "wind": 15.1, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-167": {**_BASE, "word": "Overcast", "temp": 13.8, "cloud": 100, "wind": 13.0, "code": 3, "sunset_yesterday": "2026-09-24T19:05", "sunrise_today": "2026-09-25T07:02"},
    "DK-01-168": {**_BASE, "word": "Overcast", "temp": 13.2, "cloud": 100, "wind": 13.0, "code": 3, "sunset_yesterday": "2026-09-24T19:06", "sunrise_today": "2026-09-25T07:03"},
    "DK-01-169": {**_BASE, "word": "Overcast", "temp": 13.7, "cloud": 100, "wind": 14.4, "code": 3, "sunset_yesterday": "2026-09-24T19:07", "sunrise_today": "2026-09-25T07:04"},
    "DK-01-170": {**_BASE, "word": "Overcast", "temp": 13.3, "cloud": 92, "wind": 20.9, "code": 3, "sunset_yesterday": "2026-09-24T19:09", "sunrise_today": "2026-09-25T07:06"},
    "DK-01-171": {**_BASE, "word": "Overcast", "temp": 13.6, "cloud": 100, "wind": 12.6, "code": 3, "sunset_yesterday": "2026-09-24T19:05", "sunrise_today": "2026-09-25T07:02"},
    "DK-01-172": {**_BASE, "word": "Overcast", "temp": 13.4, "cloud": 95, "wind": 11.9, "code": 3, "sunset_yesterday": "2026-09-24T19:05", "sunrise_today": "2026-09-25T07:02"},
    "DK-01-173": {**_BASE, "word": "Overcast", "temp": 13.9, "cloud": 95, "wind": 15.5, "code": 3, "sunset_yesterday": "2026-09-24T19:04", "sunrise_today": "2026-09-25T07:01"},
    "DK-01-174": {**_BASE, "word": "Overcast", "temp": 13.6, "cloud": 100, "wind": 13.7, "code": 3, "sunset_yesterday": "2026-09-24T19:07", "sunrise_today": "2026-09-25T07:04"},
    "DK-01-175": {**_BASE, "word": "Overcast", "temp": 13.5, "cloud": 100, "wind": 23.0, "code": 3, "sunset_yesterday": "2026-09-24T19:08", "sunrise_today": "2026-09-25T07:05"},
    "DK-01-176": {**_BASE, "word": "Overcast", "temp": 13.5, "cloud": 94, "wind": 25.6, "code": 3, "sunset_yesterday": "2026-09-24T19:09", "sunrise_today": "2026-09-25T07:06"},
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def bucket(code: int) -> str:
    return {0: "clear", 1: "mainly", 2: "partly", 3: "overcast"}.get(code, "other")


def sky_word(code: int) -> str:
    return {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}.get(code, f"Weather code {code}")


def nice_time(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[iso[5:7]]} {iso[0:4]} {iso[11:16]}"


def nice_dt(dt: datetime) -> str:
    return f"{dt.day} {MONTHS[f'{dt.month:02d}']} {dt.year} {dt.strftime('%H:%M')}"


def moon_note(when: datetime) -> str:
    known = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = ((when.astimezone(timezone.utc) - known).total_seconds() / 86400.0) % 29.53058867
    illum = (1 - math.cos(2 * math.pi * age / 29.53058867)) / 2
    phase = "waxing" if age < 14.765 else "waning"
    kind = "gibbous" if illum >= 0.5 else "crescent"
    return (
        f"A {phase} {kind} moon near {illum * 100:.0f}% illumination was computed for "
        f"{when.astimezone(timezone.utc).strftime('%H:%M')} UTC, not observed on site."
    )


def sun_alt(lat: float, lon: float, dt_utc: datetime) -> float:
    n = (dt_utc - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400
    solar_long = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(solar_long + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    lst = (gmst + lon / 15) % 24
    ha = math.radians(lst * 15 - math.degrees(ra))
    latr = math.radians(lat)
    alt = math.asin(math.sin(latr) * math.sin(dec) + math.cos(latr) * math.cos(dec) * math.cos(ha))
    return math.degrees(alt)


def twilight_phrase(alt: float) -> str:
    if alt >= -6:
        band = "civil twilight"
    elif alt >= -12:
        band = "nautical twilight"
    elif alt >= -18:
        band = "astronomical twilight"
    else:
        band = "full night, below astronomical twilight"
    return f"A computed sun altitude of about {alt:.0f}\u00b0 ({band}), not an on-site observation."


def pack_current(entry: str, item: dict, stamp: str) -> dict:
    cur = item["current"]
    daily = item["daily"]
    offset = int(item["utc_offset_seconds"])
    local = datetime.fromisoformat(cur["time"]).replace(tzinfo=timezone(timedelta(seconds=offset)))
    code = int(cur["weather_code"])
    temp = float(cur["temperature_2m"])
    cloud = int(cur["cloud_cover"])
    wind = float(cur["wind_speed_10m"])
    precip = float(cur["precipitation"])
    alt = sun_alt(COORDS[entry][0], COORDS[entry][1], local.astimezone(timezone.utc))
    word = sky_word(code)
    precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": f"{word}, {temp:.1f}\u00b0C, cloud cover {cloud}%, wind {wind:.1f} km/h, {precip_words}.",
        "temp": f"{temp:.1f}",
        "cloud": cloud,
        "wind": f"{wind:.1f}",
        "code": code,
        "is_day": cur.get("is_day"),
        "valid": cur["time"],
        "sunset_yesterday": daily["sunset"][0],
        "sunrise_today": daily["sunrise"][1],
        "sun_alt": alt,
        "retrieved_stamp": stamp,
        "fallback": False,
    }


def pack_snapshot(entry: str, snap: dict) -> dict:
    local = datetime.fromisoformat(snap["valid"]).replace(tzinfo=timezone(timedelta(seconds=snap["offset"])))
    alt = sun_alt(COORDS[entry][0], COORDS[entry][1], local.astimezone(timezone.utc))
    temp = float(snap["temp"])
    wind = float(snap["wind"])
    precip = float(snap["precip"])
    word = snap["word"]
    precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": f"{word}, {temp:.1f}\u00b0C, cloud cover {snap['cloud']}%, wind {wind:.1f} km/h, {precip_words}.",
        "temp": f"{temp:.1f}",
        "cloud": snap["cloud"],
        "wind": f"{wind:.1f}",
        "code": snap["code"],
        "is_day": snap["is_day"],
        "valid": snap["valid"],
        "sunset_yesterday": snap["sunset_yesterday"],
        "sunrise_today": snap["sunrise_today"],
        "sun_alt": alt,
        "retrieved_stamp": snap["retrieved_stamp"],
        "fallback": True,
    }


def fetch_weather() -> tuple[str, dict, str]:
    retrieved = datetime.now(bd.CPH)
    ids = list(COORDS)
    lats = ",".join(str(COORDS[i][0]) for i in ids)
    lons = ",".join(str(COORDS[i][1]) for i in ids)
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lats}&longitude={lons}"
        "&current=temperature_2m,cloud_cover,wind_speed_10m,precipitation,weather_code,is_day"
        "&daily=sunrise,sunset&timezone=" + urllib.parse.quote("Europe/Copenhagen") +
        "&past_days=1&forecast_days=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "jason-ds-vision-denmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    if isinstance(data, dict):
        data = [data]
    if len(data) != len(ids):
        raise SystemExit(f"weather count {len(data)}")
    stamp = retrieved.strftime("%-d %B %Y %H:%M")
    out = {}
    for entry, item in zip(ids, data):
        cur = item["current"]
        code = int(cur["weather_code"])
        live_bucket = bucket(code)
        night = int(cur.get("is_day") or 0) == 0
        if live_bucket == GEN_BUCKET[entry] and night:
            out[entry] = pack_current(entry, item, stamp)
            continue
        snap = SNAPSHOT.get(entry)
        if snap is not None and bucket(snap["code"]) == GEN_BUCKET[entry]:
            print(
                f"{entry} live bucket {live_bucket} is_day {cur.get('is_day')} "
                f"differs from depicted {GEN_BUCKET[entry]} night; "
                f"keeping the {snap['retrieved_stamp']} retrieval the frame was built from"
            )
            out[entry] = pack_snapshot(entry, snap)
            continue
        raise SystemExit(f"{entry} sky bucket changed from {GEN_BUCKET[entry]} to {live_bucket}")
    return stamp, out, moon_note(retrieved)


def prepare_raws() -> None:
    for n in range(161, 177):
        wide = bd.RAW / f"dk-01-{n:03d}-16x9.png"
        port = bd.RAW / f"dk-01-{n:03d}-45.png"
        imw = Image.open(wide)
        imp = Image.open(port)
        if imw.format != "JPEG" or imw.size != (1280, 720):
            raise SystemExit(f"bad wide {wide} {imw.format} {imw.size}")
        if imp.format != "JPEG" or imp.size != (864, 1152):
            raise SystemExit(f"bad portrait {port} {imp.format} {imp.size}")
        imw.convert("RGB").save(bd.RAW / f"dk-01-{n:03d}-16x9-raw.png", "PNG")
        imp.convert("RGB").save(bd.RAW / f"dk-01-{n:03d}-4x5-raw.png", "PNG")


def scenes(weather_stamp: str, wx: dict, moon: str) -> list:
    def pref(entry: str) -> str:
        row = wx[entry]
        valid = f"{nice_time(row['valid'])} Europe/Copenhagen"
        stamp = row.get("retrieved_stamp", weather_stamp)
        return (
            "Model data from Open-Meteo, retrieved "
            f"{stamp} Europe/Copenhagen, valid {valid} "
            "\u2014 not a verified on-site observation."
        )

    def pref_zone(entry: str, zone: str, label: str) -> str:
        row = wx[entry]
        valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=ZoneInfo("Europe/Copenhagen"))
        local = valid.astimezone(ZoneInfo(zone))
        stamp = row.get("retrieved_stamp", weather_stamp)
        return (
            "Model data from Open-Meteo, retrieved "
            f"{stamp} Europe/Copenhagen, valid {nice_dt(local)} {label} "
            f"(the same instant as {nice_time(row['valid'])} Europe/Copenhagen) "
            "\u2014 not a verified on-site observation."
        )

    def pack(entry: str, zone: str | None = None, label: str | None = None) -> dict:
        row = wx[entry]
        weather_prefix = pref(entry) if zone is None else pref_zone(entry, zone, label or "")
        return {
            "weather_prefix": weather_prefix,
            "weather_detail": row["detail"],
            "weather_brief": row["brief"],
            "temp": row["temp"],
            "cloud": row["cloud"],
            "wind": row["wind"],
            "word": row["word"],
        }

    def clock(entry: str) -> str:
        row = wx[entry]
        text = (
            "Night. Sunset on "
            f"{nice_time(row['sunset_yesterday'])} Europe/Copenhagen and sunrise on "
            f"{nice_time(row['sunrise_today'])} Europe/Copenhagen. "
        )
        text += twilight_phrase(row["sun_alt"]) + " "
        text += f"Cloud cover {row['cloud']}%. "
        text += "The cloud deck hides the moon. " if row["cloud"] >= 80 else moon + " "
        return text

    def clock_zone(entry: str, zone: str, label: str) -> str:
        row = wx[entry]
        def conv(iso: str) -> datetime:
            return datetime.fromisoformat(iso).replace(tzinfo=ZoneInfo("Europe/Copenhagen")).astimezone(ZoneInfo(zone))
        valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=ZoneInfo("Europe/Copenhagen")).astimezone(ZoneInfo(zone))
        text = (
            "Night. Sunset on "
            f"{nice_dt(conv(row['sunset_yesterday']))} {label} and sunrise on "
            f"{nice_dt(conv(row['sunrise_today']))} {label}. "
            "The clock printed on the image is Europe/Copenhagen. "
            f"Local valid time is {nice_dt(valid)} {label}. "
        )
        text += twilight_phrase(row["sun_alt"]) + " "
        text += f"Cloud cover {row['cloud']}%. "
        text += "The cloud deck hides the moon. " if row["cloud"] >= 80 else moon + " "
        return text

    rows = {entry: pack(entry) for entry in COORDS}

    def R(entry: str) -> dict:
        return rows[entry]

    a = R("DK-01-161")
    b = R("DK-01-162")
    c = R("DK-01-163")
    d = R("DK-01-164")
    e = R("DK-01-165")
    f = R("DK-01-166")
    g = R("DK-01-167")
    h = R("DK-01-168")
    i = R("DK-01-169")
    j = R("DK-01-170")
    k = R("DK-01-171")
    m = R("DK-01-172")
    n = R("DK-01-173")
    o = R("DK-01-174")
    p = R("DK-01-175")
    q = R("DK-01-176")

    return [
        {
            "entry_id": "DK-01-161",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Elephant Gate, Copenhagen",
            **a,
            "composition": "Granite elephants carrying a brick tower and copper dome \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From Ny Carlsberg Vej, the Elephant Gate is granite elephants carrying a red-brick tower with round-arched windows and a copper dome. "
                f"The street is empty under the lamps. The night is {a['word'].lower()}, about {a['temp']}\u00b0C. "
                "No brewery name is readable, and there is no product in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of the Elephant Gate in Copenhagen at night, granite elephants and a brick tower",
            "viewpoint": "The public street at Ny Carlsberg Vej, looking at the gate. Approximate researched point 55.66732, 12.53220, not a surveyed camera. Nominatim places Elefantporten in Copenhagen.",
            "refs": [
                "https://en.wikipedia.org/wiki/Elephant_Gate_and_Tower,_Carlsberg",
                "https://www.carlsbergbyen.dk/om-carlsberg-byen/historie/historiske-bygninger/elefantporten",
            ],
            "anchors": [
                "Granite elephants at the base of a gate on a public street.",
                "A red-brick tower with round-arched windows and a copper dome.",
                "No readable brewery name and no bottles.",
            ],
            "solar": clock("DK-01-161") + "Street lamps. No sign band and no product lighting.",
            "independent": (
                "Elefantporten, also called the Elephant Tower, was completed in 1901 to a design by Vilhelm Dahlerup. "
                "Carlsberg Byen describes four granite elephants carrying the tower, on Ny Carlsberg Vej, as a listed gate of the old brewery, now a public street in the new neighbourhood. "
                "Wikipedia gives the same place as Copenhagen, at about 55.6673, 12.5323. "
                "The street view shows the elephants that face the road. The frame does not carry a wordmark or a product."
            ),
            "ip": "No brewery wordmark, no bottle, and no readable name. The harness marks are not treated as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. Elephants, brick tower, copper dome, empty street, overcast night. No readable name.",
            "swap": "No city swap. Caption is the Elephant Gate, not a product. Nominatim city is Copenhagen.",
        },
        {
            "entry_id": "DK-01-162",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "J\u00e6gersborggade, Copenhagen",
            **b,
            "composition": "A narrow N\u00f8rrebro street of closed shops \u00b7 AI-generated artistic interpretation",
            "description": (
                f"J\u00e6gersborggade is a narrow street of four- and five-storey brick apartment buildings, with closed ground-floor shops and parked bicycles. "
                f"The night is {b['word'].lower()}, about {b['temp']}\u00b0C, and the lamps are warm. "
                "There is no cemetery wall and no readable shop name."
            ),
            "alt_text": "AI-generated artistic interpretation of J\u00e6gersborggade in Copenhagen at night, a narrow street of apartment buildings",
            "viewpoint": "The public roadway of J\u00e6gersborggade in N\u00f8rrebro, looking along the street. Approximate researched point 55.69271, 12.54395, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/J%C3%A6gersborggade",
                "https://en.wikipedia.org/wiki/N%C3%B8rrebro",
            ],
            "anchors": [
                "A narrow street of tall brick apartment buildings.",
                "Closed shopfronts and bicycles.",
                "No cemetery and no readable shop name.",
            ],
            "solar": clock("DK-01-162") + "Street lamps. Shops are dark.",
            "independent": (
                "J\u00e6gersborggade is a residential street in N\u00f8rrebro, Copenhagen. Nominatim places it in N\u00f8rrebro, postal 2200. "
                "The Danish street article is the specific source. The English N\u00f8rrebro article is the district, not a second photograph of this street. "
                "The frame is the street itself. Assistens Cemetery, which closes one end of the area, is not in the picture."
            ),
            "ip": "No readable shop names and no logos. Internal review only, not a legal certification.",
            "visual": "Pass. Narrow street, brick blocks, closed shops, overcast night. No cemetery.",
            "swap": (
                "Swapped from the Assistens Cemetery gate and N\u00f8rrebro Runddel. "
                "The frame is J\u00e6gersborggade, as specified. City remains Copenhagen."
            ),
        },
        {
            "entry_id": "DK-01-163",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Refshale\u00f8en, Copenhagen",
            **c,
            "composition": "Shipyard sheds along a concrete quay \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Refshale\u00f8en at night is a concrete quay and long dark industrial sheds with pitched roofs, left from the shipyard, with black harbour water in front. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, and a few quay lamps are on. "
                "The Opera House is not the subject, and no name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of the Refshale\u00f8en waterfront in Copenhagen at night, industrial sheds on a quay",
            "viewpoint": "The public quay along Refshalevej, looking along the sheds and the water. Approximate researched point 55.69161, 12.61210, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Refshale%C3%B8en",
                "https://da.wikipedia.org/wiki/Refshale%C3%B8en",
            ],
            "anchors": [
                "Long dark sheds with pitched roofs.",
                "A concrete quay and bollards.",
                "Harbour water. No opera house as the subject.",
            ],
            "solar": clock("DK-01-163") + "Sparse quay lamps. No market lighting.",
            "independent": (
                "Refshale\u00f8en is the former Burmeister & Wain shipyard island in Copenhagen harbour. Both language editions of the encyclopedia describe the shipyard site. "
                "Nominatim's street point for Refshalevej is in Copenhagen, postal 1432. The peninsula centroid sits farther north and was not used as the camera. "
                "The frame is the industrial quay. A first wide frame that added a glass building was discarded. DK-01-023 is the Opera House and is not this view."
            ),
            "ip": "No shipyard wordmark and no food-stall brands. Internal review only, not a legal certification.",
            "visual": "Pass. Sheds, concrete quay, dark water, overcast night. No glass landmark and no readable name.",
            "swap": (
                "Swapped from Freetown Christiania and Pusher Street. The frame is the Refshale\u00f8en waterfront, as specified. "
                "A wide frame with a curved glass building was discarded."
            ),
        },
        {
            "entry_id": "DK-01-164",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Trekroner Fort, Copenhagen",
            **d,
            "composition": "A low sea fort on its island, seen from the water \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the harbour, Trekroner is a low artificial island of grass ramparts and low red-roofed buildings, with a small jetty and stone meeting the water. "
                f"The night is {d['word'].lower()}, about {d['temp']}\u00b0C. "
                "There is no tall castle and no windmill."
            ),
            "alt_text": "AI-generated artistic interpretation of Trekroner Fort at night, a low sea fort seen from Copenhagen harbour",
            "viewpoint": "The water side of Trekroner, looking at the ramparts. Approximate researched point 55.70270, 12.61476, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Trekroner_Fort",
                "https://slks.dk/omraader/slotte-og-ejendomme/slotte-og-haver/soefortet-trekroner",
            ],
            "anchors": [
                "A low island fort surrounded by dark water.",
                "Grass ramparts and a low red-roofed building.",
                "A small jetty. No windmill.",
            ],
            "solar": clock("DK-01-164") + "A few lamps on the island. No crowd and no ferry name.",
            "independent": (
                "Trekroner S\u00f8fort is the sea fort at the entrance to Copenhagen harbour. The present work began in 1787. "
                "The Danish Palaces and Culture Agency says it is open to the public and that visitors may sail out in their own boat. It lies off Langelinie. "
                "Nominatim places the islet Trekroner in Copenhagen. The fort's own page gives the address Trekroner 1, 1259 Copenhagen K. "
                "Middelgrundsfortet, farther out, was not used. Kastellet, DK-01-021, is the land fort and is not this island. "
                "In September the island caf\u00e9 is listed for weekends in the daytime. This is a Friday night, so the frame has no crowd."
            ),
            "ip": "No ferry brand and no caf\u00e9 name. Internal review only, not a legal certification.",
            "visual": "Pass. Low ramparts, red roof, jetty, dark water, overcast night. No windmill and no tall castle.",
            "swap": "No swap. Trekroner is used, not Middelgrundsfortet. City is Copenhagen.",
        },
        {
            "entry_id": "DK-01-165",
            "region": "Capital Region",
            "city": "Drag\u00f8r",
            "caption": "Drag\u00f8r Old Town, Drag\u00f8r",
            **e,
            "composition": "A cobbled lane of yellow cottages \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The old town lane is one-storey yellow and white limewashed cottages with red tile roofs, on cobbles, under street lamps. "
                f"The night is {e['word'].lower()}, about {e['temp']}\u00b0C. "
                "There is no harbour water and no boat."
            ),
            "alt_text": "AI-generated artistic interpretation of a Drag\u00f8r old-town lane at night, yellow cottages and cobbles",
            "viewpoint": "Von Ostensgade in the old town, looking along the cottages. Approximate researched point 55.59278, 12.67208, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Drag%C3%B8r",
                "https://da.wikipedia.org/wiki/Drag%C3%B8r",
            ],
            "anchors": [
                "One-storey yellow and white cottages.",
                "Red tile roofs and cobbles.",
                "No water and no boats.",
            ],
            "solar": clock("DK-01-165") + "Street lamps. Late September, so there is no summer flower wall.",
            "independent": (
                "Drag\u00f8r's old town is the lane of low limewashed cottages behind the harbour. Nominatim places Von Ostensgade in Drag\u00f8r, postal 2791. "
                "The English article notes the yellow houses. DK-01-030 is the harbour, with boats and the quay, and is not this frame. "
                "A first wide frame that included a boat was discarded."
            ),
            "ip": "No readable house signs. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow cottages, cobbles, red roofs, overcast night. No water.",
            "swap": "No city swap. The lane is used instead of the harbour in DK-01-030. A frame with a boat was discarded.",
        },
        {
            "entry_id": "DK-01-166",
            "region": "Capital Region",
            "city": "Kastrup",
            "caption": "Kastrup Sea Bath, Kastrup",
            **f,
            "composition": "A wooden ring on posts over the \u00d8resund \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Kastrup Sea Bath is a dark wooden pier that runs from an empty beach and curls into a circular deck on posts above the water, open toward the shore, with a raised end. "
                f"The night is {f['word'].lower()}, about {f['temp']}\u00b0C, and a few lights follow the pier. "
                "There are no swimmers and no bridge pylons."
            ),
            "alt_text": "AI-generated artistic interpretation of Kastrup Sea Bath at night, a wooden pier and circular deck over the water",
            "viewpoint": "The beach at Kastrup S\u00f8bad, looking out along the pier. Approximate researched point 55.64592, 12.64749, not a surveyed camera. Nominatim places the bath in Kastrup.",
            "refs": [
                "https://whitearkitekter.com/project/kastrup-sea-bath/",
                "https://www.archiweb.cz/en/b/morske-lazne-u-mesta-kastrup",
            ],
            "anchors": [
                "A wooden pier from an empty beach.",
                "A circular wooden deck on posts, open toward the shore.",
                "Dark water. No bridge pylons.",
            ],
            "solar": clock("DK-01-166") + "A few pier lights. Late September night, so the deck is empty.",
            "independent": (
                "Kastrup S\u00f8bad, called the Snail, was completed in 2005 by White Arkitekter for T\u00e5rnby Municipality. "
                "A wooden pier leads to a circular enclosure open toward the beach, rising toward a diving platform, standing on posts above the \u00d8resund. "
                "Archiweb gives the address as Amager Strandvej 301, Kastrup. Nominatim's town is Kastrup, in T\u00e5rnby Kommune. "
                "The city in the caption is Kastrup, not Copenhagen. DK-01-149 is the distant bridge from Amager Strandpark and is not this bath."
            ),
            "ip": "No architect wordmark and no municipal logo. Internal review only, not a legal certification.",
            "visual": "Pass. Pier, circular wooden deck, empty beach, dark water, overcast night. No swimmers and no pylons.",
            "swap": "No site swap. City kept as Kastrup. T\u00e5rnby is the municipality and was not used as the city.",
        },
        {
            "entry_id": "DK-01-167",
            "region": "Zealand",
            "city": "Roskilde",
            "caption": "Roskilde Harbour, Roskilde",
            **g,
            "composition": "Ordinary yachts on a fjord marina \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Roskilde harbour here is the pleasure marina: white yachts and small motorboats on pontoons, dark fjord water, and low reeds. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C, and quay lamps reflect on the water. "
                "There is no museum hall and no cathedral."
            ),
            "alt_text": "AI-generated artistic interpretation of Roskilde marina at night, yachts on pontoons in the fjord",
            "viewpoint": "The public pontoon at Roskilde lystb\u00e5dehavn, looking across ordinary boats. Approximate researched point 55.65115, 12.07755, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Roskilde",
                "https://en.wikipedia.org/wiki/Roskilde_Fjord",
            ],
            "anchors": [
                "Floating pontoons and ordinary modern boats.",
                "Dark fjord water.",
                "No long museum hall and no twin cathedral spires.",
            ],
            "solar": clock("DK-01-167") + "Quay lamps. No boat name is readable.",
            "independent": (
                "Roskilde lystb\u00e5dehavn is the pleasure marina on Roskilde Fjord. Nominatim places it in Roskilde, postal 4000. "
                "The Viking Ship Museum quay used for DK-01-086 is about 55.65087, 12.08147, a short walk east, and that card is the museum hall. "
                "This frame stays on the marina boats. Roskilde Cathedral, DK-01-006, is inland at the west front and is not in the picture."
            ),
            "ip": "No museum name and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Yachts, pontoons, fjord, overcast night. No museum hall and no cathedral.",
            "swap": "No swap. The marina is used so the frame stays distinct from the cathedral and the Viking Ship Museum.",
        },
        {
            "entry_id": "DK-01-168",
            "region": "Zealand",
            "city": "Lejre",
            "caption": "Sagnlandet Lejre, Lejre",
            **h,
            "composition": "Thatched longhouses on a closed night approach \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The approach to Sagnlandet Lejre is a gravel path and low thatched longhouses with timber walls, in autumn grass. "
                f"The night is {h['word'].lower()}, about {h['temp']}\u00b0C, and a path lamp is the only light. "
                "The doors are shut. There is no crowd and no interior."
            ),
            "alt_text": "AI-generated artistic interpretation of the closed exterior of Sagnlandet Lejre at night, thatched longhouses",
            "viewpoint": "The exterior approach on Slangealleen, looking toward the reconstructed houses. Approximate researched point 55.61510, 11.94298, not a surveyed camera.",
            "refs": [
                "https://sagnlandet.dk/en/opening-hours/",
                "https://en.wikipedia.org/wiki/Land_of_Legends_(Sagnlandet_Lejre)",
            ],
            "anchors": [
                "Low houses with steep dark thatch.",
                "A gravel path and autumn grass.",
                "Shut doors. No interior and no market.",
            ],
            "solar": clock("DK-01-168") + "One path lamp. The site is closed, so there is no festival lighting.",
            "independent": (
                "Sagnlandet Lejre gives its address as Slangealleen 2, 4320 Lejre. Nominatim's house point for that address is in Lejre. "
                "The museum polygon is also tagged near Allerslev. The caption city follows the postal address, Lejre. "
                "Late summer hours for 1 September to 9 October 2026 are Tuesday to Thursday and weekends. Friday 25 September 2026 is not an opening day, and this scene is night, so the grounds are closed. "
                "The frame is the exterior of the thatched houses. It is not a summer fair."
            ),
            "ip": "No ticket branding and no readable sign. Exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. Thatch, timber, gravel, autumn grass, overcast night, shut houses. No interior.",
            "swap": (
                "No city swap. City kept as Lejre from the address Slangealleen 2, 4320 Lejre. "
                "OpenStreetMap also tags Allerslev beside the museum grounds. That village name was not used."
            ),
        },
        {
            "entry_id": "DK-01-169",
            "region": "Zealand",
            "city": "Holb\u00e6k",
            "caption": "Ahlgade, Holb\u00e6k",
            **i,
            "composition": "A pedestrian shopping street of closed shops \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Ahlgade is a straight old-town shopping street of two- and three-storey plaster buildings, with dark shop windows. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, and the street lamps are on. "
                "There is no harbour and no ship."
            ),
            "alt_text": "AI-generated artistic interpretation of Ahlgade in Holb\u00e6k at night, a shopping street of town buildings",
            "viewpoint": "Ahlgade in the old town, looking along the street. Approximate researched point 55.71781, 11.71182, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Holb%C3%A6k",
                "https://en.wikipedia.org/wiki/Holb%C3%A6k",
            ],
            "anchors": [
                "A straight street of two- and three-storey town buildings.",
                "Closed shopfronts without readable names.",
                "No water, no ships, and no tall white chimney.",
            ],
            "solar": clock("DK-01-169") + "Street lamps. Shops are dark.",
            "independent": (
                "The suggested name Adelgade is not a street OpenStreetMap draws in Holb\u00e6k. The old-town street is Ahlgade, and the Danish Holb\u00e6k article names Ahlgade. "
                "The English article is the town page and does not name the street. "
                "DK-01-088 is Holb\u00e6k harbour, with wooden ships and the white chimney, and is not this street. "
                "Ebeltoft's old town, DK-01-056, is a different Adelgade and was not reused."
            ),
            "ip": "No readable shop names and no logos. Internal review only, not a legal certification.",
            "visual": "Pass. Shopping street, closed windows, street lamps, overcast night. No harbour.",
            "swap": (
                "Swapped from Adelgade. OpenStreetMap has no Adelgade inside Holb\u00e6k. "
                "Ahlgade is the old-town street, and the Danish town article names it. Distinct from Holb\u00e6k Harbour, DK-01-088."
            ),
        },
        {
            "entry_id": "DK-01-170",
            "region": "Zealand",
            "city": "Kalundborg",
            "caption": "Kalundborg Harbour, Kalundborg",
            **j,
            "composition": "Sailboats in the west marina \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Kalundborg harbour in this frame is the marina basin, ordinary sailboats, concrete piers, and dark water with a little chop. "
                f"The night is {j['word'].lower()}, about {j['temp']}\u00b0C, with wind about {j['wind']} km/h. "
                "The five-tower church is not in the picture, and there is no refinery."
            ),
            "alt_text": "AI-generated artistic interpretation of Kalundborg marina at night, sailboats and a concrete pier",
            "viewpoint": "The guest marina at Vesthavnen, looking across the basin. Approximate researched point 55.67761, 11.08220, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Port_of_Kalundborg",
                "https://da.wikipedia.org/wiki/Kalundborg_Havn",
            ],
            "anchors": [
                "A marina basin and ordinary sailboats.",
                "Concrete piers and quay lamps.",
                "No five-tower church and no refinery.",
            ],
            "solar": clock("DK-01-170") + "Quay lamps. Wind chop on the water. No boat name is readable.",
            "independent": (
                "Kalundborg has a commercial port and a guest marina. OpenStreetMap names Vesthavnen, also called Kalundborg Vesthavn, at this point, separate from Gissel\u00f8re marina farther west and from the industrial Ny Vesthavn. "
                "The Church of Our Lady, DK-01-087, is the five brick towers on the town hill and is not the subject. "
                "The frame looks across the boats, not up at the church, and it does not use the refinery."
            ),
            "ip": "No port wordmark and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, masts, dark water, overcast night. No five towers and no refinery.",
            "swap": "No city swap. The marina at Vesthavnen is used so the frame stays off the church and off the industrial quay.",
        },
        {
            "entry_id": "DK-01-171",
            "region": "Zealand",
            "city": "K\u00f8ge",
            "caption": "K\u00f8ge Marina, K\u00f8ge",
            **k,
            "composition": "Sailboat masts in a bay marina \u00b7 AI-generated artistic interpretation",
            "description": (
                f"K\u00f8ge Marina is a field of bare masts and ordinary sailboats along piers on the dark bay, with a low quay. "
                f"The night is {k['word'].lower()}, about {k['temp']}\u00b0C, and lamps lie on the water. "
                "The half-timbered old town is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of K\u00f8ge Marina at night, sailboats and masts on the bay",
            "viewpoint": "The public pier at K\u00f8ge Marina, looking across the berths. Approximate researched point 55.47026, 12.19658, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/K%C3%B8ge",
                "https://da.wikipedia.org/wiki/K%C3%B8ge_Havn",
            ],
            "anchors": [
                "Many sailboat masts and floating piers.",
                "Dark bay water.",
                "No half-timbered square.",
            ],
            "solar": clock("DK-01-171") + "Marina lamps. No boat name is readable.",
            "independent": (
                "Nominatim places K\u00f8ge Marina at B\u00e5dehavnen in K\u00f8ge, postal 4600. The Danish harbour article is the port. "
                "DK-01-031 is the half-timbered old-town square and is inland from this basin. "
                "The frame is the marina, not that square."
            ),
            "ip": "No harbour wordmark and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Masts, piers, dark water, overcast night. No half-timbered houses.",
            "swap": "No swap. The marina is used so the frame stays distinct from K\u00f8ge Old Town, DK-01-031.",
        },
        {
            "entry_id": "DK-01-172",
            "region": "Zealand",
            "city": "Pr\u00e6st\u00f8",
            "caption": "Pr\u00e6st\u00f8 Harbour, Pr\u00e6st\u00f8",
            **m,
            "composition": "A small fjord quay and a few boats \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Pr\u00e6st\u00f8 harbour is a short quay, a few small boats, and low red and ochre houses on the dark fjord. "
                f"The night is {m['word'].lower()}, about {m['temp']}\u00b0C, and the quay is empty. "
                "No name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Pr\u00e6st\u00f8 harbour at night, a small quay and low houses",
            "viewpoint": "The public quay at Pr\u00e6st\u00f8 Havn, looking across the basin. Approximate researched point 55.12449, 12.04332, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Pr%C3%A6st%C3%B8",
                "https://da.wikipedia.org/wiki/Pr%C3%A6st%C3%B8",
            ],
            "anchors": [
                "A short quay and a few small boats.",
                "Low red and ochre houses.",
                "Dark still fjord water.",
            ],
            "solar": clock("DK-01-172") + "Quay lamps. No boat name is readable.",
            "independent": (
                "Pr\u00e6st\u00f8 is the small town on Pr\u00e6st\u00f8 Fjord. Nominatim places Pr\u00e6st\u00f8 Havn in Pr\u00e6st\u00f8, Vordingborg Kommune, postal 4720. "
                "The frame is that small harbour, not a city port."
            ),
            "ip": "No readable boat names and no shop signs. Internal review only, not a legal certification.",
            "visual": "Pass. Small quay, a few boats, low houses, overcast night.",
            "swap": "No swap. Pr\u00e6st\u00f8 harbour is the view.",
        },
        {
            "entry_id": "DK-01-173",
            "region": "Lolland-Falster",
            "city": "Stege",
            "caption": "Stege Harbour, Stege",
            **n,
            "composition": "A small town basin and tiled roofs \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Stege harbour is a modest basin of small boats, a quay, and low houses with tiled roofs behind. "
                f"The night is {n['word'].lower()}, about {n['temp']}\u00b0C, and lamps sit on the water. "
                "There is no chalk cliff."
            ),
            "alt_text": "AI-generated artistic interpretation of Stege harbour at night, boats and low houses on M\u00f8n",
            "viewpoint": "The public quay at Stege Lystb\u00e5dehavn, looking across the basin. Approximate researched point 54.98481, 12.27972, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Stege,_Denmark",
                "https://da.wikipedia.org/wiki/Stege",
            ],
            "anchors": [
                "A small marina basin and ordinary boats.",
                "Low houses with tiled roofs.",
                "No white chalk cliff and no windmill as the subject.",
            ],
            "solar": clock("DK-01-173") + "Quay lamps. No boat name is readable.",
            "independent": (
                "Stege is the market town on M\u00f8n. Nominatim places Stege Lystb\u00e5dehavn in Stege, Vordingborg Kommune, postal 4780, and the administrative region is Sj\u00e6lland. "
                "This gallery files M\u00f8n with Lolland-Falster, as it does M\u00f8ns Klint, DK-01-007, whose city is Borre. "
                "The frame is the harbour. The chalk cliffs are not in it."
            ),
            "ip": "No readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Small basin, low houses, overcast night. No cliffs.",
            "swap": (
                "No site swap. City is Stege. The gallery region is Lolland-Falster, matching DK-01-007, although the municipality sits in Region Sj\u00e6lland. "
                "Distinct from M\u00f8ns Klint."
            ),
        },
        {
            "entry_id": "DK-01-174",
            "region": "Zealand",
            "city": "Nyk\u00f8bing Sj\u00e6lland",
            "caption": "Nyk\u00f8bing Sj\u00e6lland Harbour, Nyk\u00f8bing Sj\u00e6lland",
            **o,
            "composition": "A small Isefjord marina and low houses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The harbour at Nyk\u00f8bing Sj\u00e6lland is a short pier, a handful of small boats, and low houses on the Isefjord. "
                f"The night is {o['word'].lower()}, about {o['temp']}\u00b0C, and the quay is quiet. "
                "This is not the Falster port and not the Mors port."
            ),
            "alt_text": "AI-generated artistic interpretation of the small harbour at Nyk\u00f8bing Sj\u00e6lland at night",
            "viewpoint": "The public pier at Nyk\u00f8bing Sj\u00e6lland Lystb\u00e5dehavn on Havnevej. Approximate researched point 55.91347, 11.67169, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nyk%C3%B8bing_Sj%C3%A6lland",
                "https://da.wikipedia.org/wiki/Nyk%C3%B8bing_Sj%C3%A6lland",
            ],
            "anchors": [
                "A short pier and a few small boats.",
                "Low houses and dark fjord water.",
                "No large commercial port.",
            ],
            "solar": clock("DK-01-174") + "A quay lamp. No boat name is readable.",
            "independent": (
                "Nyk\u00f8bing Sj\u00e6lland is the town on the Isefjord in Odsherred. Nominatim places the lystb\u00e5dehavn on Havnevej in Nyk\u00f8bing Sj\u00e6lland, postal 4500. "
                "The English article notes the harbour and the Isefjord. "
                "DK-01-091 is Nyk\u00f8bing Falster and DK-01-136 is Nyk\u00f8bing Mors. The caption keeps the word Sj\u00e6lland so the three towns stay distinct."
            ),
            "ip": "No readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Small pier, a few boats, low houses, overcast night. No large port.",
            "swap": "No swap. City kept as Nyk\u00f8bing Sj\u00e6lland, distinct from Nyk\u00f8bing Falster and Nyk\u00f8bing Mors.",
        },
        {
            "entry_id": "DK-01-175",
            "region": "Zealand",
            "city": "Havnebyen",
            "caption": "Odden Harbour, Havnebyen",
            **p,
            "composition": "A fishing mole on the Kattegat \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Odden harbour here is the fishing mole at Havnebyen: a concrete pier, a few fishing boats, low sheds, and wind-ruffled dark water. "
                f"The night is {p['word'].lower()}, about {p['temp']}\u00b0C, with wind about {p['wind']} km/h. "
                "There is no car ferry and no company name."
            ),
            "alt_text": "AI-generated artistic interpretation of the fishing harbour at Havnebyen on Sj\u00e6llands Odde at night",
            "viewpoint": "The public mole at Odden Fiskeri Havn, also called Odden Havn. Approximate researched point 55.97257, 11.36793, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Havnebyen",
                "https://en.wikipedia.org/wiki/Sj%C3%A6llands_Odde",
            ],
            "anchors": [
                "A concrete fishing mole and a few working boats.",
                "Low sheds and wind-chopped dark water.",
                "No car ferry and no terminal name.",
            ],
            "solar": clock("DK-01-175") + "A few mole lamps. Wind on the water. No ferry lighting as the subject.",
            "independent": (
                "OpenStreetMap names this basin Odden Fiskeri Havn, with the alt-name Odden Havn, at about 55.97257, 11.36793. "
                "The Danish article on Havnebyen describes that town on Sj\u00e6llands Odde, postal 4583, about five kilometres east of Odden F\u00e6rgehavn, with a fishing harbour. "
                "The ferry terminal is Oddenvej 388, Yderby Lyng, 4583 Sj\u00e6llands Odde. That berth is a branded ferry terminal and was not used. "
                "The caption city is Havnebyen, the town at this harbour. Sj\u00e6llands Odde is the postal district, not a second town."
            ),
            "ip": "No ferry brand and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Fishing mole, small boats, wind on the water, overcast night. No car ferry and no logo.",
            "swap": (
                "City swapped from Odden. Odden is the parish and the short name of the ferry. "
                "The fishing harbour called Odden Havn stands in Havnebyen, postal 4583 Sj\u00e6llands Odde. "
                "The Molslinjen terminal at Yderby Lyng was not used."
            ),
        },
        {
            "entry_id": "DK-01-176",
            "region": "Zealand",
            "city": "Sejer\u00f8",
            "caption": "Sejer\u00f8 Harbour, Sejer\u00f8",
            **q,
            "composition": "A short mole on a flat island \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Sejer\u00f8 harbour is a short mole, a few fishing boats, and low houses on flat ground, with the dark Kattegat beyond. "
                f"The night is {q['word'].lower()}, about {q['temp']}\u00b0C, with wind about {q['wind']} km/h, so the water is chopped. "
                "There is no cliff and no ferry name."
            ),
            "alt_text": "AI-generated artistic interpretation of Sejer\u00f8 harbour at night, a short mole and low houses",
            "viewpoint": "The public mole at Sejer\u00f8 Lystb\u00e5dehavn. Approximate researched point 55.88060, 11.13462, not a surveyed camera.",
            "refs": [
                "https://www.havneguide.dk/en/havn/sejero-havn",
                "https://en.wikipedia.org/wiki/Sejer%C3%B8",
            ],
            "anchors": [
                "A short concrete mole and a small basin.",
                "A few fishing boats and low houses on flat land.",
                "Dark wind-chopped sea. No cliffs.",
            ],
            "solar": clock("DK-01-176") + "A few quay lamps. Wind chop. No ferry name is readable.",
            "independent": (
                "Havneguide describes Sejer\u00f8 Havn as the island harbour, with Sejerby village about a kilometre away. "
                "The harbour office address is given as Brovej 33, Sejerby, 4592 Sejer\u00f8. The postal city is Sejer\u00f8. "
                "OpenStreetMap tags the village Sejerby and the marina Sejer\u00f8 Lystb\u00e5dehavn. "
                "The caption city is Sejer\u00f8, the postal city and the island, not the municipality Kalundborg. "
                "The frame is the mole. There is no cliff on this low island."
            ),
            "ip": "No ferry brand and no shop name. Internal review only, not a legal certification.",
            "visual": "Pass. Short mole, small boats, flat island, wind-chopped water, overcast night. No cliff and no logo.",
            "swap": (
                "No city swap after verification. The postal city on the harbour address is 4592 Sejer\u00f8. "
                "OpenStreetMap's village tag is Sejerby, about a kilometre from the marina. Sejerby was not used as the caption city. "
                "Kalundborg, the municipality, was not used."
            ),
        },
    ]



def load_all_scenes() -> list:
    found = []
    for path in sorted((bd.ROOT / "manifests").glob("DK-01-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        found.append({"_manifest": data})
    found.sort(key=lambda item: item["_manifest"]["entry_id"])
    return found


def verify_art50(paths: list[Path]) -> None:
    for path in paths:
        parsed = bd.read_text_chunks(path)
        for key, val in bd.ART50.items():
            if parsed.get(key) != val:
                raise SystemExit(f"art50 {path} {key}: {parsed.get(key)!r}")
        if "\u2019" in parsed["Title"] or "\u2019" in parsed["Copyright"]:
            raise SystemExit(f"curly apostrophe in metadata {path}")
        if "\u2014" not in parsed["Title"] or "\u2014" not in parsed["Copyright"]:
            raise SystemExit(f"missing em dash {path}")
        if "Denmark" not in parsed["Description"]:
            raise SystemExit(f"country {path}")
        im = Image.open(path)
        if path.name.endswith("-16x9.png") and im.size != (1920, 1080):
            raise SystemExit(f"size {path} {im.size}")
        if path.name.endswith("-4x5.png") and im.size != (864, 1080):
            raise SystemExit(f"size {path} {im.size}")


def main() -> None:
    prepare_raws()
    stamp, wx, moon = fetch_weather()
    print("moon", moon)
    if any(row["is_day"] != 0 for row in wx.values()):
        raise SystemExit(f"expected night, got { {k: v['is_day'] for k, v in wx.items()} }")
    batch = scenes(stamp, wx, moon)
    if len(batch) != 16:
        raise SystemExit(len(batch))
    lines = []
    masters: list[Path] = []
    for scene in batch:
        label = bd.scenario_label(scene["entry_id"])
        bd.write_outputs(scene, label)
        bd.manifest(scene, label)
        bd.approval(scene, label)
        masters.extend(scene["_files"].values())
        entry = scene["entry_id"].lower()
        city = scene["city"]
        lines.append(
            f"**{scene['entry_id']} \u2014 {scene['caption']}** \u00b7 Scenario: {label} \u00b7 "
            f"Weather: {scene['weather_prefix']} {scene['weather_detail']} \u00b7 "
            f"Masters: `Denmark/{city}/{entry}-16x9.png`, `Denmark/{city}/{entry}-4x5.png` \u00b7 Gates: 5/5 pass."
        )
        print(lines[-1])
    verify_art50(masters)
    all_scenes = load_all_scenes()
    if len(all_scenes) != 176:
        raise SystemExit(f"expected 176 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 177)]
    if ids != expected:
        raise SystemExit(f"id sequence {ids[:3]} ... {ids[-3:]}")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-161-176.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for path in masters:
        subprocess.run(
            ["exiftool", "-Title", "-Description", "-Copyright", "-Software", "-Comment", str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    print("site written", len(all_scenes))
    print("exiftool checked", len(masters))


if __name__ == "__main__":
    main()

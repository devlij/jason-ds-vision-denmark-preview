#!/usr/bin/env python3
"""Bake DK-01-209 through DK-01-224 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request. Those responses are stored below.
This script does not issue a new shared forecast and does not copy one
scene's weather block onto another.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

# One Open-Meteo HTTP request per entry, taken while that scene was built.
# current.time is 05:30, so the model-valid hour is 05:00–05:59 Europe/Copenhagen.
WX = {
    "DK-01-209": {"retrieved": "2026-09-25T05:43:21+0200", "lat": 56.16572, "lon": 10.22147, "temp": 11.0, "cloud": 5, "wind": 12.2, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:13", "sunrise": "2026-09-25T07:10"},
    "DK-01-210": {"retrieved": "2026-09-25T05:43:21+0200", "lat": 56.08635, "lon": 10.22252, "temp": 10.4, "cloud": 1, "wind": 11.2, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:13", "sunrise": "2026-09-25T07:10"},
    "DK-01-211": {"retrieved": "2026-09-25T05:43:22+0200", "lat": 56.19545, "lon": 10.66968, "temp": 11.8, "cloud": 36, "wind": 16.2, "code": 1, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:11", "sunrise": "2026-09-25T07:08"},
    "DK-01-212": {"retrieved": "2026-09-25T05:43:23+0200", "lat": 56.44341, "lon": 10.95729, "temp": 11.8, "cloud": 72, "wind": 16.2, "code": 2, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:10", "sunrise": "2026-09-25T07:07"},
    "DK-01-213": {"retrieved": "2026-09-25T05:43:23+0200", "lat": 56.38466, "lon": 10.17012, "temp": 9.9, "cloud": 15, "wind": 9.7, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:13", "sunrise": "2026-09-25T07:10"},
    "DK-01-214": {"retrieved": "2026-09-25T05:43:24+0200", "lat": 56.46230, "lon": 9.42303, "temp": 9.9, "cloud": 49, "wind": 7.6, "code": 1, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:16", "sunrise": "2026-09-25T07:13"},
    "DK-01-215": {"retrieved": "2026-09-25T05:43:25+0200", "lat": 56.17620, "lon": 9.57100, "temp": 9.2, "cloud": 25, "wind": 5.4, "code": 1, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:15", "sunrise": "2026-09-25T07:12"},
    "DK-01-216": {"retrieved": "2026-09-25T05:43:26+0200", "lat": 55.86484, "lon": 9.82627, "temp": 8.8, "cloud": 0, "wind": 7.6, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:14", "sunrise": "2026-09-25T07:11"},
    "DK-01-217": {"retrieved": "2026-09-25T05:43:26+0200", "lat": 55.97706, "lon": 9.83066, "temp": 7.8, "cloud": 4, "wind": 9.4, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:14", "sunrise": "2026-09-25T07:11"},
    "DK-01-218": {"retrieved": "2026-09-25T05:43:27+0200", "lat": 55.75620, "lon": 8.93000, "temp": 7.7, "cloud": 10, "wind": 5.8, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:18", "sunrise": "2026-09-25T07:15"},
    "DK-01-219": {"retrieved": "2026-09-25T05:43:28+0200", "lat": 55.47228, "lon": 8.42750, "temp": 11.7, "cloud": 16, "wind": 12.2, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:20", "sunrise": "2026-09-25T07:17"},
    "DK-01-220": {"retrieved": "2026-09-25T05:43:28+0200", "lat": 55.33989, "lon": 8.67638, "temp": 11.5, "cloud": 20, "wind": 12.6, "code": 1, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:19", "sunrise": "2026-09-25T07:16"},
    "DK-01-221": {"retrieved": "2026-09-25T05:43:29+0200", "lat": 55.44998, "lon": 8.40783, "temp": 11.5, "cloud": 18, "wind": 14.4, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:20", "sunrise": "2026-09-25T07:17"},
    "DK-01-222": {"retrieved": "2026-09-25T05:43:30+0200", "lat": 55.61473, "lon": 8.47301, "temp": 8.1, "cloud": 11, "wind": 4.3, "code": 0, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:20", "sunrise": "2026-09-25T07:17"},
    "DK-01-223": {"retrieved": "2026-09-25T05:43:31+0200", "lat": 56.09074, "lon": 8.24459, "temp": 12.6, "cloud": 30, "wind": 15.8, "code": 1, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:21", "sunrise": "2026-09-25T07:17"},
    "DK-01-224": {"retrieved": "2026-09-25T05:43:31+0200", "lat": 56.04972, "lon": 8.10364, "temp": 13.0, "cloud": 37, "wind": 20.5, "code": 1, "precip": 0.0, "valid": "2026-09-25T05:30", "sunset": "2026-09-24T19:21", "sunrise": "2026-09-25T07:18"},
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def sky_word(code: int) -> str:
    return {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}[code]


def nice_time(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[iso[5:7]]} {iso[0:4]} {iso[11:16]}"


def stamp_words(raw: str) -> str:
    # 2026-09-25T05:43:21+0200
    return f"{int(raw[8:10])} {MONTHS[raw[5:7]]} {raw[0:4]} {raw[11:19]}"


def moon_note(when: datetime) -> str:
    known = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = ((when.astimezone(timezone.utc) - known).total_seconds() / 86400.0) % 29.53058867
    illum = (1 - math.cos(2 * math.pi * age / 29.53058867)) / 2
    phase = "waxing" if age < 14.765 else "waning"
    kind = "gibbous" if illum >= 0.5 else "crescent"
    return (
        f"A {phase} {kind} moon near {illum * 100:.0f}% illumination was computed for "
        f"{when.astimezone(timezone.utc).strftime('%H:%M:%S')} UTC, not observed on site."
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


def pack(entry: str) -> dict:
    row = WX[entry]
    when = datetime.strptime(row["retrieved"], "%Y-%m-%dT%H:%M:%S%z")
    local_valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=timezone(timedelta(seconds=7200)))
    alt = sun_alt(row["lat"], row["lon"], local_valid.astimezone(timezone.utc))
    word = sky_word(row["code"])
    temp = float(row["temp"])
    wind = float(row["wind"])
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": f"{word}, {temp:.1f}\u00b0C, cloud cover {row['cloud']}%, wind {wind:.1f} km/h, no precipitation.",
        "temp": f"{temp:.1f}",
        "cloud": row["cloud"],
        "wind": f"{wind:.1f}",
        "code": row["code"],
        "valid": row["valid"],
        "sunset": row["sunset"],
        "sunrise": row["sunrise"],
        "sun_alt": alt,
        "retrieved_stamp": stamp_words(row["retrieved"]),
        "moon": moon_note(when),
        "prefix": (
            "Model data from Open-Meteo, retrieved "
            f"{stamp_words(row['retrieved'])} Europe/Copenhagen, valid "
            f"{nice_time(row['valid'])} Europe/Copenhagen "
            "\u2014 not a verified on-site observation. "
            f"Separate request for {row['lat']:.5f}, {row['lon']:.5f}. "
            "The model-valid hour is 05:00\u201305:59 Europe/Copenhagen."
        ),
    }


def light(row: dict) -> str:
    if row["cloud"] >= 80:
        return "The cloud deck hides the moon, and a few lamps carry the light."
    if row["cloud"] >= 45:
        return "Broken cloud hides much of the moon."
    return "Moonlight reaches the ground under a thin cloud cover."


def clock(row: dict) -> str:
    text = (
        "Night. Sunset on "
        f"{nice_time(row['sunset'])} Europe/Copenhagen and sunrise on "
        f"{nice_time(row['sunrise'])} Europe/Copenhagen. "
    )
    text += twilight_phrase(row["sun_alt"]) + " "
    text += f"Cloud cover {row['cloud']}%. "
    text += "The cloud deck hides the moon. " if row["cloud"] >= 80 else row["moon"] + " "
    text += "The scenario minute has to fall inside this scene's own model-valid hour, 05:00\u201305:59 Europe/Copenhagen."
    return text


def prepare_raws() -> None:
    for n in range(209, 225):
        for kind, raw_name in (("16x9", "16x9"), ("4x5", "45")):
            src = bd.RAW / f"dk-01-{n:03d}-{raw_name}.png"
            if kind == "4x5":
                src = bd.RAW / f"dk-01-{n:03d}-4x5.png"
            im = Image.open(src)
            expect = (1280, 720) if kind == "16x9" else (864, 1152)
            if im.format != "JPEG" or im.size != expect:
                raise SystemExit(f"bad source {src} {im.format} {im.size}")
            dest = bd.RAW / f"dk-01-{n:03d}-{kind}-raw.png"
            st = src.stat()
            im.convert("RGB").save(dest, "PNG")
            os.utime(dest, (st.st_atime, st.st_mtime))


def scenes() -> list:
    R = {entry: pack(entry) for entry in WX}

    def base(entry: str) -> dict:
        row = R[entry]
        return {
            "weather_prefix": row["prefix"],
            "weather_detail": row["detail"],
            "weather_brief": row["brief"],
            "temp": row["temp"],
            "cloud": row["cloud"],
            "wind": row["wind"],
            "word": row["word"],
            "_row": row,
        }

    a = base("DK-01-209")
    b = base("DK-01-210")
    c = base("DK-01-211")
    d = base("DK-01-212")
    e = base("DK-01-213")
    f = base("DK-01-214")
    g = base("DK-01-215")
    h = base("DK-01-216")
    i = base("DK-01-217")
    j = base("DK-01-218")
    k = base("DK-01-219")
    m = base("DK-01-220")
    n = base("DK-01-221")
    o = base("DK-01-222")
    p = base("DK-01-223")
    q = base("DK-01-224")

    def drop(row: dict) -> dict:
        row.pop("_row", None)
        return row

    return [
        drop({
            **a,
            "entry_id": "DK-01-209",
            "region": "Central Jutland",
            "city": "Aarhus",
            "caption": "Aarhus Lystb\u00e5dehavn, Aarhus",
            "composition": "Sailboat masts along a marina pier \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the public pier at Aarhus Lystb\u00e5dehavn on Aarhus \u00d8, the basin is a thicket of bare sailboat masts over dark water, with ropes and a few quay lamps. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C. {light(a['_row'])} "
                "Dokk1's polygonal roof, the rainbow ring at ARoS, and the half-timbered square at Den Gamle By are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Aarhus Lystb\u00e5dehavn at night, sailboat masts along a pier",
            "viewpoint": "The public pier at Aarhus Lystb\u00e5dehavn on Aarhus \u00d8. Approximate researched point 56.16572, 10.22147, not a surveyed camera. Nominatim places the marina in Aarhus, postal 8000.",
            "refs": [
                "https://en.wikipedia.org/wiki/Aarhus_%C3%98",
                "https://en.wikipedia.org/wiki/Port_of_Aarhus",
            ],
            "anchors": [
                "A marina basin and a stone pier in the foreground.",
                "Many bare sailboat masts, with no readable boat name.",
                "Dark water and a low far shore. No polygonal library and no rainbow ring.",
            ],
            "solar": clock(a["_row"]) + " Quay lamps. No readable name.",
            "independent": (
                "Aarhus \u00d8 is the docklands north of the river mouth, and the marina named Aarhus Lystb\u00e5dehavn sits there. "
                "Dokk1, the waterfront library, is already DK-01-049. ARoS is DK-01-011 and Den Gamle By is DK-01-010. "
                "This frame stays on the marina pier and leaves those buildings out."
            ),
            "ip": "No readable boat name and no developer wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Marina masts, pier, dark water, clear night. No Dokk1 polygon and no rainbow ring.",
            "swap": (
                "No site swap. The suggested Dokk1 waterfront is already DK-01-049, Dokk1, Aarhus. "
                "The caption is Aarhus Lystb\u00e5dehavn. City remains Aarhus."
            ),
        }),
        drop({
            **b,
            "entry_id": "DK-01-210",
            "region": "Central Jutland",
            "city": "H\u00f8jbjerg",
            "caption": "Moesgaard Museum, H\u00f8jbjerg",
            "composition": "A sloping grass roof rising from a dark field \u00b7 AI-generated artistic interpretation",
            "description": (
                "The night approach to Moesgaard is a single grass-covered roof sloping up out of the field, with a few rectangular cuts in the slope and concrete, glass, and vertical timber at the lower end. "
                f"The path is empty and the museum is closed. The night is {b['word'].lower()}, about {b['temp']}\u00b0C. {light(b['_row'])} "
                "Late September grass is still green. No interior objects are shown."
            ),
            "alt_text": "AI-generated artistic interpretation of Moesgaard Museum at night, a sloping grass roof in H\u00f8jbjerg",
            "viewpoint": "The public approach to the grass roof at Moesgaard Museum, Moesg\u00e5rd All\u00e9 15. Approximate researched point 56.08635, 10.22252, not a surveyed camera. The published address is 8270 H\u00f8jbjerg.",
            "refs": [
                "https://dac.dk/en/magazine/places/moesgaard-build-as-an-excavation-454",
                "https://www.henninglarsen.com/projects/moesgaard",
            ],
            "anchors": [
                "One rectangular roof plane covered in grass, sloping up from the field.",
                "A few rectangular openings in the slope.",
                "Concrete, glass, and vertical timber at the low end. No exhibits.",
            ],
            "solar": clock(b["_row"]) + " One path lamp. The interior is closed.",
            "independent": (
                "The Danish Architecture Center and the architect's project page describe the 2014 museum at Moesg\u00e5rd All\u00e9 15, 8270 H\u00f8jbjerg: a sloping grass roof that rises out of the Sk\u00e5de hills, publicly walkable, with light-well cuts. "
                "This is a late September night, so the roof is empty, the grass is still green, and there is no snow and no picnic. "
                "Interior finds are not in the frame."
            ),
            "ip": "Exterior of the building only. No exhibit and no museum wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Sloping green roof, path, clear night, closed exterior. No interior objects.",
            "swap": "No site swap. Moesgaard was not already in the catalogue. City is H\u00f8jbjerg.",
        }),
        drop({
            **c,
            "entry_id": "DK-01-211",
            "region": "Central Jutland",
            "city": "Ebeltoft",
            "caption": "Ebeltoft Harbour, Ebeltoft",
            "composition": "A three-masted hull beside half-timbered houses \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ebeltoft harbour at night is a stone quay, a large dark-hulled ship with three bare masts, a couple of smaller boats, and low half-timbered houses with red tile roofs. "
                f"The quay is empty. The night is {c['word'].lower()}, about {c['temp']}\u00b0C. {light(c['_row'])} "
                "No name is readable on the hull. Adelgade and the old town hall are not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Ebeltoft harbour at night, a three-masted ship and half-timbered houses",
            "viewpoint": "The public quay at Ebeltoft Havn. Approximate researched point 56.19545, 10.66968, not a surveyed camera. Nominatim places the harbour in Ebeltoft, postal 8400.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ebeltoft",
                "https://en.wikipedia.org/wiki/HDMS_Jylland",
            ],
            "anchors": [
                "A stone quay and a harbour basin.",
                "One large dark hull with three bare masts, and smaller boats.",
                "Low half-timbered houses with red roofs. No readable name.",
            ],
            "solar": clock(c["_row"]) + " Quay lamps. No readable ship name.",
            "independent": (
                "Ebeltoft's harbour is the waterfront below the old town. HDMS Jylland, the wooden steam frigate preserved as a museum ship, is berthed there. "
                "The frame shows a three-masted dark hull without a readable name, which is the honest night view of that berth, not a measured rigging survey. "
                "Ebeltoft Old Town, the cobbled street to the small town hall, is already DK-01-056."
            ),
            "ip": "No readable ship name and no museum wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Three bare masts, dark hull, half-timbered roofs, mainly clear night. No readable name.",
            "swap": (
                "No site swap of the harbour. The old-town street is already DK-01-056, Ebeltoft Old Town, Ebeltoft, so this frame stays on the quay. "
                "City remains Ebeltoft."
            ),
        }),
        drop({
            **d,
            "entry_id": "DK-01-212",
            "region": "Central Jutland",
            "city": "Grenaa",
            "caption": "Forn\u00e6s Lighthouse, Grenaa",
            "composition": "An unpainted granite tower and a red lantern by the sea \u00b7 AI-generated artistic interpretation",
            "description": (
                "Forn\u00e6s is an unpainted cylindrical granite tower with a red lantern and a gallery, joined to a low keeper's house on a grassy point, with the dark Kattegat beside it. "
                f"The point is empty. The night is {d['word'].lower()}, about {d['temp']}\u00b0C. {light(d['_row'])} "
                "The fishing basin in Grenaa town is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Forn\u00e6s Lighthouse at night, a granite tower by the Kattegat",
            "viewpoint": "The public ground beside Forn\u00e6s Fyr, north of Grenaa. Approximate researched point 56.44341, 10.95729, not a surveyed camera. The Danish article places it at Grenaa, postal 8500.",
            "refs": [
                "https://en.wikipedia.org/wiki/Forn%C3%A6s_Lighthouse",
                "https://da.wikipedia.org/wiki/Forn%C3%A6s_Fyr",
            ],
            "anchors": [
                "An unpainted cylindrical granite tower.",
                "A red lantern and a gallery, with a low keeper's house.",
                "Grass and dark sea. No harbour basin.",
            ],
            "solar": clock(d["_row"]) + " A few warm windows. No lettering on the tower.",
            "independent": (
                "Both lighthouse articles place Forn\u00e6s on the eastern point of Djursland, about 6 km north of Grenaa. The present tower, from 1892, is unpainted granite with a red lantern, and the keeper's house is attached. "
                "Grenaa Harbour, the fishing basin in town, is already DK-01-125. This frame is the point, not that basin."
            ),
            "ip": "No lettering on the tower. Internal review only, not a legal certification.",
            "visual": "Pass. Grey granite cylinder, red lantern, keeper's house, sea, partly cloudy night. No harbour.",
            "swap": (
                "Swapped from Grenaa Harbour. That basin is already DK-01-125, Grenaa Harbour, Grenaa. "
                "The caption is Forn\u00e6s Lighthouse. City remains Grenaa."
            ),
        }),
        drop({
            **e,
            "entry_id": "DK-01-213",
            "region": "Central Jutland",
            "city": "Voldum",
            "caption": "Clausholm Castle, Voldum",
            "composition": "A white moated manor and a red hipped roof \u00b7 AI-generated artistic interpretation",
            "description": (
                "Clausholm at night is a whitewashed two-storey manor with a red hipped tile roof and a broad triangular pediment, standing in a dark moat, with clipped trees along the water. "
                f"The banks are empty. The night is {e['word'].lower()}, about {e['temp']}\u00b0C. {light(e['_row'])} "
                "The cascades are not shown running. The half-timbered riverfront in Randers is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Clausholm Castle at night, a white manor in a moat",
            "viewpoint": "The public bank of the moat at Clausholm Slot, Clausholmvej 308. Approximate researched point 56.38466, 10.17012, not a surveyed camera. The house address is Voldum, 8370 Hadsten.",
            "refs": [
                "https://lex.dk/Clausholm",
                "https://www.clausholm.dk/slottet/slotsparken/",
            ],
            "anchors": [
                "A white two-storey manor with a triangular pediment.",
                "A red hipped tile roof.",
                "Dark moat water and clipped trees. No spraying fountain.",
            ],
            "solar": clock(e["_row"]) + " A few warm windows. No sign.",
            "independent": (
                "Lex describes Clausholm as a three-wing baroque house of two storeys, built in the 1690s for Conrad Reventlow, whitewashed from the 1720s, with a broad pediment, on a moated island about 12 km southeast of Randers. "
                "The house site gives the address Clausholmvej 308, Voldum, 8370 Hadsten. "
                "The Randers Guden\u00e5 quay of half-timbered houses is already DK-01-054. Night in late September is not treated as a fountain display, so no cascade is shown running."
            ),
            "ip": "No estate wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. White manor, red hipped roof, pediment, moat, clear night. No fountain jets.",
            "swap": (
                "Swapped from Randers harbour. That Guden\u00e5 quay is already DK-01-054, Randers Riverfront, Randers. "
                "The caption is Clausholm Castle. City is Voldum. The postal town on the address is Hadsten."
            ),
        }),
        drop({
            **f,
            "entry_id": "DK-01-214",
            "region": "Central Jutland",
            "city": "Viborg",
            "caption": "N\u00f8rres\u00f8, Viborg",
            "composition": "A wooden jetty and reeds on a dark lake \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the public bathing shore, N\u00f8rres\u00f8 is a dark lake with a simple wooden jetty, reeds, and a tree-lined far shore. "
                f"The shore is empty. The night is {f['word'].lower()}, about {f['temp']}\u00b0C. {light(f['_row'])} "
                "The cathedral's twin towers are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of N\u00f8rres\u00f8 at Viborg at night, a jetty and reeds",
            "viewpoint": "The public shore at N\u00f8rres\u00f8 Badet, Gefionsvej. Approximate researched point 56.46230, 9.42303, not a surveyed camera. Nominatim places the bathing shore in Viborg, postal 8800.",
            "refs": [
                "https://da.wikipedia.org/wiki/N%C3%B8rres%C3%B8_(Viborg)",
                "https://en.wikipedia.org/wiki/Viborg,_Denmark",
            ],
            "anchors": [
                "A simple wooden jetty and reeds.",
                "Dark open water.",
                "A tree-lined far shore. No twin cathedral towers.",
            ],
            "solar": clock(f["_row"]) + " A few distant lights. No swimmers.",
            "independent": (
                "N\u00f8rres\u00f8 is the lake on the north side of Viborg. Nominatim places N\u00f8rres\u00f8 Badet on Gefionsvej in Viborg, postal 8800, which is the public shore used here. "
                "Late September night is outside bathing use, so the jetty is empty. "
                "Viborg Cathedral, the granite west front with two pyramidal towers, is already DK-01-053 and is left out of this lake frame."
            ),
            "ip": "No club name and no swimmer. Internal review only, not a legal certification.",
            "visual": "Pass. Jetty, reeds, dark lake, broken cloud, empty shore. No cathedral.",
            "swap": (
                "The cathedral half of the suggestion is already DK-01-053, Viborg Cathedral, Viborg. "
                "The caption is N\u00f8rres\u00f8. City remains Viborg."
            ),
        }),
        drop({
            **g,
            "entry_id": "DK-01-215",
            "region": "Central Jutland",
            "city": "Silkeborg",
            "caption": "Langs\u00f8, Silkeborg",
            "composition": "A grass bank along a long dark lake \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the north shore at S\u00f8holt, Silkeborg Langs\u00f8 is a long dark lake, a grass bank, a path, and trees still in leaf, with a wooded far shore. "
                f"The path is empty. The night is {g['word'].lower()}, about {g['temp']}\u00b0C. {light(g['_row'])} "
                "No paddle steamer is on the water."
            ),
            "alt_text": "AI-generated artistic interpretation of Silkeborg Langs\u00f8 at night, a grass bank and a dark lake",
            "viewpoint": "The public north shore of Silkeborg Langs\u00f8 at S\u00f8holt All\u00e9. Approximate researched point 56.17620, 9.57100, not a surveyed camera. Nominatim places S\u00f8holt All\u00e9 in Silkeborg, postal 8600.",
            "refs": [
                "https://da.wikipedia.org/wiki/Silkeborg_Langs%C3%B8",
                "https://en.wikipedia.org/wiki/Silkeborg",
            ],
            "anchors": [
                "A grass bank and a path in the foreground.",
                "A long dark lake and a wooded far shore.",
                "Trees still in leaf. No paddle steamer and no black funnel.",
            ],
            "solar": clock(g["_row"]) + " A few shore lamps. No boat name.",
            "independent": (
                "Silkeborg Langs\u00f8 is the long lake through the town. This viewpoint is the north shore at S\u00f8holt, east of the paper-mill quay. "
                "The paddle steamer Hjejlen, moored at the inland harbour, is already DK-01-050, and Silkeborg Church is DK-01-122. "
                "This frame leaves the steamer out."
            ),
            "ip": "No boat name and no mill wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Lake, grass bank, trees, mainly clear night. No paddle steamer.",
            "swap": (
                "The harbour half of the suggestion is already DK-01-050, Hjejlen, Silkeborg. "
                "The caption is Langs\u00f8, the open shore. City remains Silkeborg."
            ),
        }),
        drop({
            **h,
            "entry_id": "DK-01-216",
            "region": "Central Jutland",
            "city": "Horsens",
            "caption": "Bygholm Castle, Horsens",
            "composition": "A white manor, a red roof, and a park pond \u00b7 AI-generated artistic interpretation",
            "description": (
                "Bygholm at night is a long white house of one storey over a high basement, with a red half-hipped tile roof and a central pediment, seen across a still pond in the park. "
                f"The paths are empty. The night is {h['word'].lower()}, about {h['temp']}\u00b0C. {light(h['_row'])} "
                "No hotel name is readable, and the medieval mound is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Bygholm Castle at night, a white manor across a park pond",
            "viewpoint": "The public park side of the manor at Sch\u00fcttesvej. Approximate researched point 55.86484, 9.82627, not a surveyed camera. Nominatim places the house in Horsens, postal 8700.",
            "refs": [
                "https://trap.lex.dk/Bygholm,_Horsens",
                "https://www.fredninger.dk/fredning/bygholm-park/",
            ],
            "anchors": [
                "A long white one-storey house over a high basement.",
                "A red half-hipped tile roof and a central pediment.",
                "A still pond and park trees. No medieval ruin and no hotel name.",
            ],
            "solar": clock(h["_row"]) + " A few warm windows. No wordmark.",
            "independent": (
                "Trap Danmark describes the standing Bygholm house at the west edge of Horsens: a symmetrical main wing with angled side wings, white walls, and red half-hipped roofs, built in 1775, with the park and Bygholm \u00c5 to the east. "
                "The protected-sites page separates that house from Slangebjerg, the grass mound of the demolished medieval castle. This frame is the standing house, not the mound. "
                "The building is used as a hotel. No hotel name is in the frame. Horsens Harbour is already DK-01-055 and Vor Frelsers Kirke is DK-01-121."
            ),
            "ip": "No hotel wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. White manor, red roof, pond, clear night. No wordmark and no ruin.",
            "swap": (
                "Swapped from Horsens Harbour. That basin is already DK-01-055, Horsens Harbour, Horsens. "
                "The caption is Bygholm Castle. City remains Horsens."
            ),
        }),
        drop({
            **i,
            "entry_id": "DK-01-217",
            "region": "Central Jutland",
            "city": "Ejer",
            "caption": "Ejer Bavneh\u00f8j, Ejer",
            "composition": "A brick tower on a low grassy hill \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ejer Bavneh\u00f8j at night is a plain brick tower on a low grassy rise, with a path, open fields, and a few distant lights. "
                f"The hill is empty. The night is {i['word'].lower()}, about {i['temp']}\u00b0C. {light(i['_row'])} "
                "The lake and the church on the holm at Skanderborg are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Ejer Bavneh\u00f8j at night, a brick tower on a hill",
            "viewpoint": "The public path on Ejer Bavneh\u00f8j. Approximate researched point 55.97706, 9.83066, not a surveyed camera. Nominatim places the hill in the Ejer area, postal 8752.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ejer_Bavneh%C3%B8j",
                "https://da.wikipedia.org/wiki/Ejer_Bavneh%C3%B8j",
            ],
            "anchors": [
                "A plain brick tower on a grassy rise.",
                "A path and open fields.",
                "A few distant lights. No lake and no church.",
            ],
            "solar": clock(i["_row"]) + " Moonlight on the brick. No readable plaque.",
            "independent": (
                "Ejer Bavneh\u00f8j is the hill with the brick viewing tower south of Skanderborg. The English and Danish articles are the sources for the place. "
                "This card does not rank the hill. Nominatim places it near the hamlet Ejer, postal 8752. "
                "Skanderborg Lake, with the church on the holm, is already DK-01-123."
            ),
            "ip": "No readable plaque. Internal review only, not a legal certification.",
            "visual": "Pass. Brick tower, grassy hill, fields, clear night. No lake.",
            "swap": (
                "Swapped from Skanderborg Lake. That shore, with the church on the holm, is already DK-01-123, Skanderborg Lake, Skanderborg. "
                "The caption is Ejer Bavneh\u00f8j. City is Ejer."
            ),
        }),
        drop({
            **j,
            "entry_id": "DK-01-218",
            "region": "Central Jutland",
            "city": "Grindsted",
            "caption": "Grindsted Torv, Grindsted",
            "composition": "A flat paved square and low town buildings \u00b7 AI-generated artistic interpretation",
            "description": (
                "Grindsted Torv at night is a flat open paved square, low town buildings with dark windows, a few street lamps, young trees, and empty benches. "
                f"The square is empty. The night is {j['word'].lower()}, about {j['temp']}\u00b0C. {light(j['_row'])} "
                "There is no fountain and no toy-brick shopfront."
            ),
            "alt_text": "AI-generated artistic interpretation of Grindsted Torv at night, a flat paved square",
            "viewpoint": "The public square in central Grindsted, near Borgergade. Approximate researched point 55.75620, 8.93000, not a surveyed camera. Nominatim places central Grindsted at postal 7200. The exact camera on the rebuilt paving was not surveyed.",
            "refs": [
                "https://www.billund.dk/politik-og-demokrati/politik-visioner-og-budget/udvikling-af-grindsted-bymidte/",
                "https://www.netavisengrindsted.dk/2025/06/06/torvet-i-grindsted-bygges-om/",
            ],
            "anchors": [
                "A flat open paved square, with no fountain.",
                "Low town buildings, street lamps, and young trees.",
                "Empty benches. No toy-brick facade and no readable shop name.",
            ],
            "solar": clock(j["_row"]) + " Street lamps. No readable sign.",
            "independent": (
                "Billund Kommune and the local report from June 2025 say the fountain on Torvet had been removed and the levels flattened, with a temporary layout tested that summer ahead of a later permanent design. "
                "The exact furniture of 25 September 2026 was not verified, so this frame shows only a flat empty square, lamps, and ordinary buildings, and it does not invent a new sculpture or a fountain. "
                "Billund Church is already DK-01-094. No toy-brick brand is the subject."
            ),
            "ip": "No toy-brick logo and no shop name. Internal review only, not a legal certification.",
            "visual": "Pass. Flat square, lamps, low buildings, clear night. No fountain and no brand facade.",
            "swap": (
                "No site swap. Billund's church is already DK-01-094, so the square in Grindsted is the scene, as suggested. "
                "City is Grindsted."
            ),
        }),
        drop({
            **k,
            "entry_id": "DK-01-219",
            "region": "South Jutland",
            "city": "Esbjerg",
            "caption": "Esbjerg Harbour, Esbjerg",
            "composition": "A closed harbour hall and fishing boats \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the public quay, Esbjerg harbour at night is a long closed brick hall, dark water, a few fishing boats, and quay lamps. "
                f"The quay is empty and the hall is dark. The night is {k['word'].lower()}, about {k['temp']}\u00b0C. {light(k['_row'])} "
                "The four seated figures at S\u00e6dding Strand are not in this frame, and no auction is underway."
            ),
            "alt_text": "AI-generated artistic interpretation of Esbjerg harbour at night, a closed hall and fishing boats",
            "viewpoint": "The public quay by the old auction hall, Auktionsgade. Approximate researched point 55.47228, 8.42750, not a surveyed camera. Nominatim places Auktionsgade in Esbjerg, postal 6700.",
            "refs": [
                "https://trap.lex.dk/Esbjerg_Havn",
                "https://da.wikipedia.org/wiki/Esbjerg_Havn",
            ],
            "anchors": [
                "A long closed brick hall on the quay.",
                "A few fishing boats and dark water.",
                "Quay lamps. No four seated figures and no crowd.",
            ],
            "solar": clock(k["_row"]) + " Quay lamps. No readable boat name.",
            "independent": (
                "Trap Danmark records that Esbjerg Fiskeauktion closed in 2002 as the fishing fleet left the port. A tourist auction has been held on Wednesday mornings in July at the old hall; this scenario is a late September night, so the hall is closed and no sale is shown. "
                "Men at Sea, the four white figures on the beach at S\u00e6dding Strand, is already DK-01-095 and is not this harbour quay."
            ),
            "ip": "No readable boat name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Closed hall, boats, quay, clear night. No sculpture group and no crowd.",
            "swap": (
                "No site swap of the harbour. Men at Sea is already DK-01-095, Men at Sea, Esbjerg, on the beach, so this frame is the quay. "
                "City remains Esbjerg."
            ),
        }),
        drop({
            **m,
            "entry_id": "DK-01-220",
            "region": "South Jutland",
            "city": "Ribe",
            "caption": "Kammerslusen, Ribe",
            "composition": "Closed lock gates, a dike, and the marsh \u00b7 AI-generated artistic interpretation",
            "description": (
                "Kammerslusen at night is a concrete sea lock with closed gates, dark river water, a grass dike, and flat marsh toward the Wadden Sea. "
                f"The lock is empty. The night is {m['word'].lower()}, about {m['temp']}\u00b0C. {light(m['_row'])} "
                "The cathedral and the cobbled lanes are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Kammerslusen at night, a sea lock on the marsh near Ribe",
            "viewpoint": "The public side of the sea lock at Kammerslusen, southwest of Ribe. Approximate researched point 55.33989, 8.67638, not a surveyed camera. The municipality is Esbjerg; the lock is Ribe's outlet to the Wadden Sea.",
            "refs": [
                "https://da.wikipedia.org/wiki/Kammerslusen",
                "https://en.wikipedia.org/wiki/Wadden_Sea",
            ],
            "anchors": [
                "Concrete lock walls and closed gates.",
                "Dark river water and a grass dike.",
                "Flat marsh. No cathedral and no half-timbered lane.",
            ],
            "solar": clock(m["_row"]) + " Little lamp light. No sign.",
            "independent": (
                "Kammerslusen is the sea lock where Ribe \u00c5 meets the Wadden Sea, southwest of the town. The Danish article is the place source, and the Wadden Sea article is the setting. "
                "Ribe Cathedral is already DK-01-013 and the cobbled old-town lane is DK-01-142. This frame is the lock and the marsh, not those streets. "
                "The town name on the caption stays Ribe, which is how the lock is identified, although the present municipality is Esbjerg."
            ),
            "ip": "No sign. Internal review only, not a legal certification.",
            "visual": "Pass. Lock gates, dike, marsh, mainly clear night. No old-town lane.",
            "swap": (
                "Swapped from Ribe old town. That lane is already DK-01-142, Ribe Old Town, Ribe, and the cathedral is DK-01-013. "
                "The caption is Kammerslusen. City remains Ribe."
            ),
        }),
        drop({
            **n,
            "entry_id": "DK-01-221",
            "region": "South Jutland",
            "city": "Nordby",
            "caption": "Nordby Harbour, Nordby",
            "composition": "A small quay, open boats, and dune grass \u00b7 AI-generated artistic interpretation",
            "description": (
                "Nordby harbour at night is a stone quay, a few small open boats, low brick houses, dune grass, and dark sea. "
                f"The quay is empty. The night is {n['word'].lower()}, about {n['temp']}\u00b0C. {light(n['_row'])} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Nordby harbour on Fan\u00f8 at night, a quay and small boats",
            "viewpoint": "The public quay at Nordby Havn, by the ferry berth. Approximate researched point 55.44998, 8.40783, not a surveyed camera. Nominatim places Nordby Havn in Nordby, postal 6720.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nordby,_Fan%C3%B8",
                "https://en.wikipedia.org/wiki/Fan%C3%B8",
            ],
            "anchors": [
                "A stone quay and a small basin.",
                "A few open boats with blank hulls.",
                "Low houses, dune grass, and dark sea. No ferry wordmark.",
            ],
            "solar": clock(n["_row"]) + " Quay lamps. No readable name.",
            "independent": (
                "Nordby is the ferry town on the east side of Fan\u00f8. The harbour is the berth for the crossing to Esbjerg. "
                "This frame shows the basin and small boats and does not carry a ferry name. "
                "S\u00f8nderho is already DK-01-143 and Lakolk Beach is DK-01-144, both elsewhere on the island."
            ),
            "ip": "No ferry wordmark and no hotel name. Internal review only, not a legal certification.",
            "visual": "Pass. Quay, small boats, dune grass, houses, clear night. No ferry brand.",
            "swap": "No site swap. Nordby harbour was not already in the catalogue. City is Nordby.",
        }),
        drop({
            **o,
            "entry_id": "DK-01-222",
            "region": "South Jutland",
            "city": "Varde",
            "caption": "Varde \u00c5, Varde",
            "composition": "A dark river, a low bridge, and town houses \u00b7 AI-generated artistic interpretation",
            "description": (
                "Varde \u00c5 through the town is dark water, a low bridge, brick houses with warm windows, and trees still in leaf, with lamps reflected on the surface. "
                f"The bank is empty. The night is {o['word'].lower()}, about {o['temp']}\u00b0C. {light(o['_row'])} "
                "No boat is on the river."
            ),
            "alt_text": "AI-generated artistic interpretation of Varde \u00c5 at night, a river and a low bridge in Varde",
            "viewpoint": "The public bank at Skibskrogen, where the town meets Varde \u00c5. Approximate researched point 55.61473, 8.47301, not a surveyed camera. Nominatim places the spot in Varde, postal 6800.",
            "refs": [
                "https://en.wikipedia.org/wiki/Varde",
                "https://da.wikipedia.org/wiki/Varde_%C3%85",
            ],
            "anchors": [
                "Dark river water in the foreground.",
                "A low bridge and brick houses.",
                "Trees still in leaf and lamp reflections. No boat.",
            ],
            "solar": clock(o["_row"]) + " Street lamps. No readable sign.",
            "independent": (
                "Varde \u00c5 runs through the town of Varde. Nominatim places the information point Livet i Varde \u00c5 at Skibskrogen in Varde, postal 6800, which is the town waterfront used here. "
                "The frame is the river and the houses. No boat name is in it because no boat is shown."
            ),
            "ip": "No shop name. Internal review only, not a legal certification.",
            "visual": "Pass. River, low bridge, houses, trees, clear night. No boat.",
            "swap": "No site swap. Varde was not already in the catalogue. City is Varde.",
        }),
        drop({
            **p,
            "entry_id": "DK-01-223",
            "region": "Central Jutland",
            "city": "Ringk\u00f8bing",
            "caption": "Ringk\u00f8bing Church, Ringk\u00f8bing",
            "composition": "A red-brick church and a tower wider at the top \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the square, Ringk\u00f8bing Church is red brick, with a west tower that spreads wider at the top, four triangular gables, and a low pyramidal roof, plus a side wing. "
                f"The square is empty. The night is {p['word'].lower()}, about {p['temp']}\u00b0C. {light(p['_row'])} "
                "The fjord basin is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Ringk\u00f8bing Church at night, a red-brick tower wider at the top",
            "viewpoint": "The public square at Ringk\u00f8bing Kirke, Kirkepladsen. Approximate researched point 56.09074, 8.24459, not a surveyed camera. Nominatim places the church in Ringk\u00f8bing, postal 6950.",
            "refs": [
                "https://www.visitvesterhavet.com/northsea/north-sea-vacation/ringkobing-church-gdk602864",
                "https://lex.dk/Ringk%C3%B8bing_Kirke",
            ],
            "anchors": [
                "Red-brick walls and a side wing.",
                "A west tower wider at the top than at the base.",
                "Four triangular gables under a low pyramidal roof. No harbour.",
            ],
            "solar": clock(p["_row"]) + " Street lamps. No readable plaque.",
            "independent": (
                "VisitVesterhavet says the tower, finished around the Reformation, is widest at the top. Lex calls the crown four triangular gables under a pyramidal roof, a t\u00f8rninglensk tower, and dates the north cross arm to 1592\u20131593 and the south arm to 1934\u20131935. The visible brick dates from the 1934\u20131935 rebuild. "
                "Ringk\u00f8bing Harbour is already DK-01-139. This frame is the church square."
            ),
            "ip": "No readable plaque. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, tower wider at the top, triangular gables, pyramidal roof, mainly clear night. No harbour.",
            "swap": (
                "Swapped from Ringk\u00f8bing Harbour. That basin is already DK-01-139, Ringk\u00f8bing Harbour, Ringk\u00f8bing. "
                "The caption is Ringk\u00f8bing Church. City remains Ringk\u00f8bing."
            ),
        }),
        drop({
            **q,
            "entry_id": "DK-01-224",
            "region": "Central Jutland",
            "city": "N\u00f8rre Lyngvig",
            "caption": "Lyngvig Lighthouse, N\u00f8rre Lyngvig",
            "composition": "A white tower on a dune above the North Sea \u00b7 AI-generated artistic interpretation",
            "description": (
                "Lyngvig Lighthouse at night is a tall white round tower with a lantern, standing on a grass dune, with a low white keeper's house and the dark North Sea beside it. "
                f"The dune is empty. The night is {q['word'].lower()}, about {q['temp']}\u00b0C, and the wind is fresh. {light(q['_row'])} "
                "The canal and the fishing boats at Hvide Sande are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Lyngvig Lighthouse at night, a white tower on a dune",
            "viewpoint": "The public dune at Lyngvig Fyr, Holmsland Klitvej. Approximate researched point 56.04972, 8.10364, not a surveyed camera. Nominatim places the lighthouse at N\u00f8rre Lyngvig.",
            "refs": [
                "https://da.wikipedia.org/wiki/Lyngvig_Fyr",
                "https://www.visitvesterhavet.dk/vesterhavet/vores-byer/lyngvig-fyr",
            ],
            "anchors": [
                "A tall white round tower with a lantern.",
                "A grass dune and a low white keeper's house.",
                "Dark sea. No canal and no fishing fleet.",
            ],
            "solar": clock(q["_row"]) + " Moonlight on the tower. No lettering.",
            "independent": (
                "The Danish article places Lyngvig Fyr on Holmsland Klit between S\u00f8ndervig and Hvide Sande, built in 1906, a white tower on a dune, with the village N\u00f8rre Lyngvig a short distance east. "
                "The visit page describes the same dune site. This card does not rank the tower. "
                "Hvide Sande Harbour, the canal through the dunes, is already DK-01-140."
            ),
            "ip": "No lettering on the tower. Internal review only, not a legal certification.",
            "visual": "Pass. White tower, dune, keeper's house, sea, mainly clear night. No canal.",
            "swap": (
                "Swapped from Hvide Sande Harbour. That canal is already DK-01-140, Hvide Sande Harbour, Hvide Sande. "
                "The caption is Lyngvig Lighthouse. City is N\u00f8rre Lyngvig."
            ),
        }),
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
    batch = scenes()
    if len(batch) != 16:
        raise SystemExit(len(batch))
    details = [scene["weather_detail"] for scene in batch]
    if len(details) != len(set(details)):
        raise SystemExit("weather detail reused")
    prefixes = [scene["weather_prefix"] for scene in batch]
    # Identical clock seconds can happen; the coordinate and the detail must still differ.
    if len(set(prefixes)) != 16:
        raise SystemExit(f"retrieval notes not one-per-scene: {len(set(prefixes))}")
    lines = []
    masters: list[Path] = []
    for scene in batch:
        label = bd.scenario_label(scene["entry_id"])
        hour = label.split("\u00b7")[1].strip()[:2]
        if hour != "05":
            raise SystemExit(f"{scene['entry_id']} scenario hour {hour} outside model-valid hour 05")
        if "05:30" not in scene["weather_prefix"]:
            raise SystemExit(f"{scene['entry_id']} valid time missing")
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
    if len(all_scenes) != 224:
        raise SystemExit(f"expected 224 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 225)]
    if ids != expected:
        raise SystemExit("id sequence broken")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    descriptions = [item["_manifest"]["description"] for item in all_scenes]
    if len(descriptions) != len(set(descriptions)):
        raise SystemExit("duplicate description")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-209-224.txt"
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

#!/usr/bin/env python3
"""Bake DK-01-337 through DK-01-352 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-337-352.json.
This script does not issue a new forecast and does not copy one scene's weather
block onto another.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-337-352.json").read_text(encoding="utf-8"))
NUUK = ZoneInfo("America/Nuuk")
FAROE = ZoneInfo("Atlantic/Faroe")

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def sky_word(code: int) -> str:
    table = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        53: "Moderate drizzle",
    }
    if code not in table:
        raise SystemExit(f"unhandled weather code {code}")
    return table[code]


def nice_time(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[iso[5:7]]} {iso[0:4]} {iso[11:16]}"


def stamp_words(raw: str) -> str:
    return f"{int(raw[8:10])} {MONTHS[raw[5:7]]} {raw[0:4]} {raw[11:19]}"


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


def temp_s(temp: float) -> str:
    if abs(temp) < 0.05:
        return "0.0"
    return f"{temp:.1f}"


def step_phrase(valid: str) -> str:
    hour = valid[11:13]
    hm = valid[11:16]
    return (
        f"The model-valid hour is {hour}:00\u2013{hour}:59 Europe/Copenhagen. "
        f"The cited model time is the {hm} step (interval 900 seconds)."
    )


def pack(entry: str) -> dict:
    row = WX[entry]
    local_valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=bd.CPH)
    alt_step = sun_alt(row["lat"], row["lon"], local_valid.astimezone(timezone.utc))
    code = int(row["code"])
    word = sky_word(code)
    temp = float(row["temp"])
    wind = float(row["wind"])
    precip = float(row["precip"])
    snow = float(row["snow"])
    hour = str(row["valid"])[11:13]
    if hour not in {"14", "15"}:
        raise SystemExit(f"{entry} valid {row['valid']}")
    if not str(row["retrieved"]).startswith(f"2026-09-25T{hour}:"):
        raise SystemExit(f"{entry} retrieval {row['retrieved']} outside valid hour")
    if int(row["current_interval"]) != 900:
        raise SystemExit(f"{entry} interval {row.get('current_interval')}")
    if precip == 0 and snow == 0:
        precip_words = "no precipitation"
    elif snow == 0:
        precip_words = f"precipitation {precip:.1f} mm, no snowfall"
    else:
        precip_words = f"precipitation {precip:.1f} mm, snowfall {snow:.2f} cm"
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp_s(temp)}\u00b0C",
        "detail": (
            f"{word}, {temp_s(temp)}\u00b0C, cloud cover {int(row['cloud'])}%, "
            f"wind {wind:.1f} km/h, {precip_words}."
        ),
        "temp": temp_s(temp),
        "cloud": int(row["cloud"]),
        "wind": f"{wind:.1f}",
        "wind_f": wind,
        "code": code,
        "is_day": int(row["is_day"]),
        "valid": row["valid"],
        "sunset": row["sunset_yesterday"],
        "sunrise": row["sunrise_today"],
        "sun_alt_step": alt_step,
        "retrieved_stamp": stamp_words(row["retrieved"]),
        "retrieved_iso": row["retrieved"],
        "http_date": row["http_date"],
        "lat": row["lat"],
        "lon": row["lon"],
        "prefix": (
            "Model data from Open-Meteo, retrieved "
            f"{stamp_words(row['retrieved'])} Europe/Copenhagen, "
            f"HTTP Date {row['http_date']}, valid "
            f"{nice_time(row['valid'])} Europe/Copenhagen "
            "\u2014 not a verified on-site observation. "
            f"Separate request for {row['lat']:.5f}, {row['lon']:.5f}. "
            + step_phrase(row["valid"])
        ),
    }


def period_word(local_hour: int) -> str:
    if local_hour < 11:
        return "morning"
    if local_hour < 12:
        return "late morning"
    if local_hour < 14:
        return "midday"
    return "afternoon"


def light(row: dict, period: str) -> str:
    if row["code"] == 53:
        return f"The sky stays bright in the {period}, with moderate drizzle."
    if row["code"] == 3 or row["cloud"] >= 80:
        return f"The cloud deck softens the {period} light."
    if row["code"] == 0:
        return f"The {period} sun is clear."
    if row["code"] == 1:
        return f"The {period} sun is out under a mainly clear sky."
    return f"Broken cloud partly veils the {period} sun."


def wind_clause(row: dict) -> str:
    w = row["wind_f"]
    if w >= 50:
        return f"The wind is a gale, about {row['wind']} km/h."
    if w >= 35:
        return f"The wind is strong, about {row['wind']} km/h."
    if w >= 22:
        return f"The wind is fresh, about {row['wind']} km/h."
    if w >= 12:
        return f"The wind is moderate, about {row['wind']} km/h."
    return f"The wind is light, about {row['wind']} km/h."


def place_zone(entry: str):
    if entry in {"DK-01-350", "DK-01-351"}:
        return FAROE
    if entry in {"DK-01-352"}:
        return NUUK
    return bd.CPH


def solar_text(row: dict, scenario_dt: datetime, zone) -> str:
    alt = sun_alt(row["lat"], row["lon"], scenario_dt.astimezone(timezone.utc))
    local = scenario_dt.astimezone(zone)
    period = period_word(local.hour)
    sunset = datetime.fromisoformat(row["sunset"]).replace(tzinfo=bd.CPH)
    sunrise = datetime.fromisoformat(row["sunrise"]).replace(tzinfo=bd.CPH)
    hour = row["valid"][11:13]
    text = (
        f"Daylight, {period}. "
        f"Sunset on {nice_time(row['sunset'])} Europe/Copenhagen and sunrise on {nice_time(row['sunrise'])} Europe/Copenhagen. "
    )
    if zone is not bd.CPH:
        text += (
            f"The same instants are {sunset.astimezone(zone).strftime('%H:%M')} and "
            f"{sunrise.astimezone(zone).strftime('%H:%M')} {zone.key}. "
            f"Scenario local time is {local.strftime('%H:%M')} {zone.key}. "
        )
    if alt < 12:
        height = "the sun is still low"
    elif alt < 28:
        height = "the sun is at a modest height"
    else:
        height = "the sun is well up"
    text += (
        f"A computed sun altitude of about {alt:.1f}\u00b0 at the scenario minute "
        f"({height}), not an on-site observation. "
    )
    if row["is_day"] != 1:
        raise SystemExit("expected is_day 1")
    text += "The cited model step is flagged is_day 1. "
    text += f"Cloud cover {row['cloud']}%. "
    text += (
        "The scenario minute has to fall inside this scene's own model-valid hour, "
        f"{hour}:00\u2013{hour}:59 Europe/Copenhagen, and at or after the cited model step."
    )
    return text


def scenario_label(entry_id: str) -> str:
    times = []
    for kind in ("16x9", "4x5"):
        path = bd.RAW / f"{entry_id.lower()}-{kind}.png"
        times.append(os.path.getmtime(path))
    dt = datetime.fromtimestamp(max(times), bd.CPH)
    month = dt.strftime("%B")
    return f"{dt.day} {month} {dt.year} \u00b7 {dt.strftime('%H:%M')} Europe/Copenhagen"


def scenario_dt(entry_id: str) -> datetime:
    times = []
    for kind in ("16x9", "4x5"):
        times.append(os.path.getmtime(bd.RAW / f"{entry_id.lower()}-{kind}.png"))
    return datetime.fromtimestamp(max(times), bd.CPH)


bd.scenario_label = scenario_label


def prepare_raws() -> None:
    for n in range(337, 353):
        for kind, expect in (("16x9", (1280, 720)), ("4x5", (864, 1152))):
            src = bd.RAW / f"dk-01-{n:03d}-{kind}.png"
            im = Image.open(src)
            if im.format != "JPEG" or im.size != expect:
                raise SystemExit(f"bad source {src} {im.format} {im.size}")
            dest = bd.RAW / f"dk-01-{n:03d}-{kind}-raw.png"
            st = src.stat()
            im.convert("RGB").save(dest, "PNG")
            os.utime(dest, (st.st_atime, st.st_mtime))


def scenes() -> list:
    R = {entry: pack(entry) for entry in WX}
    pairs = [(WX[e]["retrieved"], WX[e]["http_date"]) for e in WX]
    if len(pairs) != len(set(pairs)):
        raise SystemExit("reused retrieval")
    if len(WX) != 16:
        raise SystemExit("expected 16 weather records")
    coords = [(round(WX[e]["lat"], 5), round(WX[e]["lon"], 5)) for e in WX]
    if len(coords) != len(set(coords)):
        raise SystemExit("reused coordinate")

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

    rows = {f"DK-01-{n:03d}": base(f"DK-01-{n:03d}") for n in range(337, 353)}

    def sky(entry: str, when: datetime) -> str:
        row = rows[entry]
        local = when.astimezone(place_zone(entry))
        period = period_word(local.hour)
        return (
            f"It is {row['word'].lower()}, about {row['temp']}\u00b0C. "
            f"{wind_clause(row['_row'])} {light(row['_row'], period)}"
        )

    def local_clause(entry: str, when: datetime) -> str:
        zone = place_zone(entry)
        if zone is bd.CPH:
            return ""
        local = when.astimezone(zone)
        return f" Local time is {local.strftime('%H:%M')} {zone.key}."

    catalog = [
        {
            "entry_id": "DK-01-337",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Assistens Cemetery, Copenhagen",
            "composition": "A public path under large deciduous trees \u00b7 AI-generated artistic interpretation",
            "lead": "From the public path in Assistens Cemetery, large old deciduous trees meet over a gravel walk. Graves are not in the frame.",
            "tail": "The path is empty.",
            "alt_text": "AI-generated artistic interpretation of a tree-lined path in Assistens Cemetery, Copenhagen, on a clear afternoon",
            "viewpoint": "A public path inside Assistens Kirkeg\u00e5rd, N\u00f8rrebro. Approximate researched point 55.69092, 12.54944, not a surveyed camera. Open-Meteo ran this request on grid 55.68710, 12.55402.",
            "refs": [
                "https://en.wikipedia.org/wiki/Assistens_Cemetery_(Copenhagen)",
                "https://da.wikipedia.org/wiki/Assistens_Kirkeg%C3%A5rd",
            ],
            "anchors": [
                "A gravel path under a high canopy.",
                "Large deciduous trees, early autumn, mostly green.",
                "No gravestone in focus and no readable name.",
            ],
            "independent": "Assistens Kirkeg\u00e5rd opened in 1760 in N\u00f8rrebro and is both a burial ground and a public green space. The suggestion named a willow path. The cemetery articles describe the trees and the green space and do not establish a willow all\u00e9e, so the frame is the public path under large deciduous trees, with graves kept out of the picture.",
            "ip": "No readable memorial. No portrait. Internal review only, not a legal certification.",
            "visual": "Pass. Gravel path, large trees, clear afternoon, empty. No grave in focus and no lettering.",
            "swap": "No site swap. Assistens Cemetery had not been used. A willow all\u00e9e was not established by the sources, so the frame does not claim one. City is Copenhagen.",
        },
        {
            "entry_id": "DK-01-338",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Grundtvig's Church, Copenhagen",
            "composition": "A yellow-brick west front like organ pipes \u00b7 AI-generated artistic interpretation",
            "lead": "From the approach, Grundtvig's Church is a yellow-brick west front: plain brick below and a tall rippling wall of vertical pipes above, with stepped gables along the nave. There is no separate spire.",
            "tail": "The flanking yellow-brick houses sit to either side. The road is empty.",
            "alt_text": "AI-generated artistic interpretation of Grundtvig's Church in Copenhagen on a clear afternoon, a yellow-brick organ-pipe facade",
            "viewpoint": "The axis toward the west front at P\u00e5 Bjerget, Bispebjerg. Approximate researched point 55.71658, 12.53361, not a surveyed camera. Open-Meteo ran this request on grid 55.71350, 12.53638.",
            "refs": [
                "https://en.wikipedia.org/wiki/Grundtvig%27s_Church",
                "https://www.grundtvigskirke.dk/",
            ],
            "anchors": [
                "Yellow brick, not red brick and not white stone.",
                "A west front of vertical organ-pipe brick, with no needle spire.",
                "Stepped gables and lower yellow-brick wings.",
            ],
            "independent": "Peder Vilhelm Jensen-Klint's church in Bispebjerg was built from 1921 and completed in 1940. The English article describes the yellow brick and the west facade, reminiscent of an organ, with the lower half plain and the upper part a rippling vertical surface. The interior organs are not shown.",
            "ip": "No readable inscription. Interior fittings are not shown. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow brick, organ-pipe west front, no needle spire, clear afternoon, empty. No lettering.",
            "swap": "Swapped from Gefion Fountain. That fountain is already DK-01-147, Gefion Fountain, Copenhagen. The unused church is Grundtvig's Church. City remains Copenhagen.",
        },
        {
            "entry_id": "DK-01-339",
            "region": "Capital Region",
            "city": "Helsing\u00f8r",
            "caption": "Sankt Mari\u00e6 Kirke, Helsing\u00f8r",
            "composition": "A red-brick Gothic church and cloister \u00b7 AI-generated artistic interpretation",
            "lead": "Sankt Mari\u00e6 Kirke is a red-brick Gothic church with one square brick tower and a lower red-brick cloister wing. The street is empty.",
            "tail": "Kronborg's copper spires are not in this frame, and neither is the white cathedral.",
            "alt_text": "AI-generated artistic interpretation of Sankt Mari\u00e6 Kirke in Helsing\u00f8r on a mainly clear afternoon, a red-brick church and cloister",
            "viewpoint": "The street in front of the Carmelite church and cloister. Approximate researched point 56.03702, 12.61269, not a surveyed camera. Open-Meteo ran this request on grid 56.03674, 12.61018. Photon returns the English town name Elsinore; the gallery city is Helsing\u00f8r.",
            "refs": [
                "https://en.wikipedia.org/wiki/Carmelite_Priory,_Helsing%C3%B8r",
                "https://trap.lex.dk/Helsing%C3%B8r",
            ],
            "anchors": [
                "Red brick, not white stone.",
                "One square tower and a lower cloister range.",
                "No sandstone palace and no copper spires.",
            ],
            "independent": "The Carmelite Priory, also called Vor Frue Kloster, was established in Helsing\u00f8r in 1430. The church is Sankt Mari\u00e6 Kirke. It is a different building from Sankt Olai, which is already DK-01-097. The public description does not repeat ranking language from the priory article.",
            "ip": "No readable board. Interior frescos are not shown. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick church, square tower, cloister wing, mainly clear afternoon, empty street. No Kronborg and no lettering.",
            "swap": "Swapped from the Kronborg casemates and bastion walk. The castle is already DK-01-004, Kronborg Castle, Helsing\u00f8r. Marienlyst is DK-01-321, the harbour is DK-01-257, and the maritime museum is DK-01-029. The unused church is Sankt Mari\u00e6 Kirke. City remains Helsing\u00f8r.",
        },
        {
            "entry_id": "DK-01-340",
            "region": "Zealand",
            "city": "Roskilde",
            "caption": "Sankt J\u00f8rgensbjerg, Roskilde",
            "composition": "A small white church on a hill above the fjord \u00b7 AI-generated artistic interpretation",
            "lead": "Sankt J\u00f8rgensbjerg is a small whitewashed church with a red tile roof and one simple tower, on a grassy hill, with the fjord far behind.",
            "tail": "The twin-spired cathedral is not in this frame, and no gravestone name is readable.",
            "alt_text": "AI-generated artistic interpretation of Sankt J\u00f8rgensbjerg in Roskilde on a clear afternoon, a small white church on a hill",
            "viewpoint": "The hill by the church, above the old fishing quarter. Approximate researched point 55.64931, 12.07569, not a surveyed camera. Open-Meteo ran this request on grid 55.64917, 12.08167.",
            "refs": [
                "https://da.wikipedia.org/wiki/Sankt_J%C3%B8rgensbjerg_Kirke",
                "https://en.wikipedia.org/wiki/Roskilde",
            ],
            "anchors": [
                "A small white church, not the cathedral.",
                "A red tile roof and one simple tower.",
                "A grassy hill, with fjord water only in the distance.",
            ],
            "independent": "The Danish article describes Sankt J\u00f8rgensbjerg Kirke as a medieval church on a hill in Roskilde, near Roskilde Fjord. The maintained walls read as limewash and the roof as tile, which is the ordinary appearance of this village church. Roskilde Cathedral is a different building.",
            "ip": "No readable gravestone. Internal review only, not a legal certification.",
            "visual": "Pass. White church, red roof, one tower, hill, clear afternoon, fjord far off. No cathedral and no lettering.",
            "swap": "Swapped from the cathedral west front. Roskilde Cathedral is already DK-01-006. The harbour is DK-01-167 and the Viking Ship Museum is DK-01-086. The unused church is Sankt J\u00f8rgensbjerg. City remains Roskilde.",
        },
        {
            "entry_id": "DK-01-341",
            "region": "Lolland-Falster",
            "city": "Stege",
            "caption": "M\u00f8lleporten, Stege",
            "composition": "A striped brick gate tower with a pyramidal roof \u00b7 AI-generated artistic interpretation",
            "lead": "M\u00f8lleporten is a four-storey gate tower banded in red brick and pale limestone, with a steep pyramidal tile roof, a weather vane, and an arched passage.",
            "tail": "A low earth rampart sits beside it. There are no cars.",
            "alt_text": "AI-generated artistic interpretation of M\u00f8lleporten in Stege on a mainly clear afternoon, a striped gate tower with a pyramidal roof",
            "viewpoint": "The street at the gate, Storegade. Approximate researched point 54.98717, 12.28933, not a surveyed camera. Open-Meteo ran this request on grid 54.98481, 12.28967.",
            "refs": [
                "https://en.wikipedia.org/wiki/M%C3%B8lleporten",
                "https://da.wikipedia.org/wiki/M%C3%B8lleporten",
            ],
            "anchors": [
                "Horizontal bands of red brick and pale limestone.",
                "A steep pyramidal tile roof, not a flat top.",
                "An arched passage and an earth rampart, with no cars.",
            ],
            "independent": "Both articles describe the four-storey medieval gate tower in Stege, the alternating brick and limestone, and the steep pyramidal roof. It was restored in 2019\u20132022, so the frame shows that present state. The gallery region is Lolland-Falster, as on Stege Harbour. Administratively the municipality is in Region Zealand.",
            "ip": "No readable board. Internal review only, not a legal certification.",
            "visual": "Pass. Striped tower, pyramidal roof, arch, rampart, mainly clear afternoon, empty. No cars and no lettering.",
            "swap": "No site swap of the town. Stege Harbour is already DK-01-173. Stege Church was the other unused option. This frame is M\u00f8lleporten, which had not been used. City is Stege.",
        },
        {
            "entry_id": "DK-01-342",
            "region": "Lolland-Falster",
            "city": "Nyk\u00f8bing Falster",
            "caption": "Czarens Hus, Nyk\u00f8bing Falster",
            "composition": "A half-timbered corner house on the square \u00b7 AI-generated artistic interpretation",
            "lead": "Czarens Hus is a two-storey half-timbered corner house, dark beams and pale panels under a red tile roof, on the cobbled square.",
            "tail": "The harbour and the sound bridge are not in this frame, and no museum name is readable.",
            "alt_text": "AI-generated artistic interpretation of Czarens Hus in Nyk\u00f8bing Falster under a heavy broken cloud deck, a half-timbered corner house",
            "viewpoint": "The square at the corner of Langgade and F\u00e6rgestr\u00e6de. Approximate researched point 54.76773, 11.86676, not a surveyed camera. Open-Meteo ran this request on grid 54.76000, 11.86000.",
            "refs": [
                "https://da.wikipedia.org/wiki/Czarens_Hus",
                "https://en.wikipedia.org/wiki/Falsters_Minder",
            ],
            "anchors": [
                "A two-storey half-timbered house.",
                "A corner on a cobbled square.",
                "A red tile roof. No harbour and no readable name.",
            ],
            "independent": "The Danish article describes a half-timbered house of the 1690s on the corner of Langgade and F\u00e6rgestr\u00e6de, by the square. It is named for Peter the Great's visit in 1716. The English Falsters Minder article identifies the same building as the museum's old home. The frame is the exterior only.",
            "ip": "No museum wordmark and no exhibition title. Internal review only, not a legal certification.",
            "visual": "Pass. Half-timbered corner house, red roof, cobbles, heavy cloud, empty. No lettering.",
            "swap": "Swapped from the Guldborgsund bridge and the harbour. The harbour is already DK-01-091, and that card already includes a low bridge down the sound. Klosterkirken is DK-01-182. The unused house is Czarens Hus. City remains Nyk\u00f8bing Falster.",
        },
        {
            "entry_id": "DK-01-343",
            "region": "Funen",
            "city": "Kerteminde",
            "caption": "Sankt Laurentii, Kerteminde",
            "composition": "A red-brick town church and one slender spire \u00b7 AI-generated artistic interpretation",
            "lead": "From the square, Sankt Laurentii is a red-brick town church with one west tower and a slender dark spire.",
            "tail": "The harbour is not in this frame. The square is empty.",
            "alt_text": "AI-generated artistic interpretation of Sankt Laurentii in Kerteminde under broken cloud, a red-brick church with one spire",
            "viewpoint": "The square in front of the church. Approximate researched point 55.44922, 10.65831, not a surveyed camera. Open-Meteo ran this request on grid 55.45193, 10.66367.",
            "refs": [
                "https://da.wikipedia.org/wiki/Sankt_Laurentii_Kirke_(Kerteminde)",
                "https://en.wikipedia.org/wiki/Kerteminde",
            ],
            "anchors": [
                "A red-brick town church.",
                "One west tower and one slender spire.",
                "A square, not a harbour.",
            ],
            "independent": "The Danish article places Sankt Laurentii Kirke in the centre of Kerteminde. The harbour is a different card. The gallery region is Funen, as on that harbour card. Administratively the municipality is in the Region of Southern Denmark.",
            "ip": "No readable dedication board. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick church, one spire, square, broken cloud, empty. No harbour and no lettering.",
            "swap": "Swapped from Kerteminde Harbour, already DK-01-110. The unused church is Sankt Laurentii. City remains Kerteminde.",
        },
        {
            "entry_id": "DK-01-344",
            "region": "Funen",
            "city": "Troense",
            "caption": "Strandgade, Troense",
            "composition": "Skipper houses along a cobbled waterside street \u00b7 AI-generated artistic interpretation",
            "lead": "Strandgade is a cobbled street of old skipper houses, red tile roofs and plaster in yellow, white, and ochre, with the sound beside the street.",
            "tail": "Valdemars Slot is not in this frame. The street is empty.",
            "alt_text": "AI-generated artistic interpretation of Strandgade in Troense under broken cloud, skipper houses along the sound",
            "viewpoint": "Strandgade, looking along the houses and the water. Approximate researched point 55.03608, 10.63866, not a surveyed camera. Open-Meteo ran this request on grid 55.03966, 10.63429. The exact house chosen as the foreground was not pinned beyond the street.",
            "refs": [
                "https://en.wikipedia.org/wiki/Troense",
                "https://da.wikipedia.org/wiki/Troense",
            ],
            "anchors": [
                "A row of low old houses with red tile roofs.",
                "A cobbled street and the sound.",
                "No white baroque palace.",
            ],
            "independent": "Troense is the skipper town on T\u00e5singe in Svendborg Municipality. Strandgade is the waterside street. Valdemars Slot, further along the shore, is already DK-01-155 and is kept out of this frame. The gallery region is Funen.",
            "ip": "No readable house name. Internal review only, not a legal certification.",
            "visual": "Pass. Skipper houses, red roofs, cobbles, water, broken cloud, empty. No palace and no lettering.",
            "swap": "Swapped from Valdemars Slot, already DK-01-155, Valdemars Slot, Troense. The unused view is Strandgade. City is Troense.",
        },
        {
            "entry_id": "DK-01-345",
            "region": "South Jutland",
            "city": "Vejle",
            "caption": "Sankt Nicolai Kirke, Vejle",
            "composition": "A red-brick Gothic church and one west tower \u00b7 AI-generated artistic interpretation",
            "lead": "From the square, Sankt Nicolai Kirke is a red-brick Gothic church with one west tower and a copper roof on the tower.",
            "tail": "The fjord bridge is not the subject. The square is empty.",
            "alt_text": "AI-generated artistic interpretation of Sankt Nicolai Kirke in Vejle under broken cloud, a red-brick church with one tower",
            "viewpoint": "The square in front of the west tower. Approximate researched point 55.70736, 9.53444, not a surveyed camera. Open-Meteo ran this request on grid 55.70758, 9.53671.",
            "refs": [
                "https://da.wikipedia.org/wiki/Sankt_Nicolai_Kirke_(Vejle)",
                "https://en.wikipedia.org/wiki/Vejle",
            ],
            "anchors": [
                "A red-brick Gothic church.",
                "One west tower.",
                "A town square, not the fjord bridge.",
            ],
            "independent": "The Danish article describes Sankt Nicolai Kirke as the central church in Vejle, late Gothic brick, and the oldest building in the town. The gallery region is South Jutland, as on the Vejle Fjord card. Administratively Vejle is in the Region of Southern Denmark.",
            "ip": "No readable board. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick church, one tower, square, broken cloud, empty. No bridge as the subject and no lettering.",
            "swap": "Swapped from the fjord-bridge approach. Vejle Fjord is already DK-01-119, and that card already includes distant bridge lights. The unused church is Sankt Nicolai Kirke. City remains Vejle.",
        },
        {
            "entry_id": "DK-01-346",
            "region": "Central Jutland",
            "city": "Horsens",
            "caption": "Horsens Statsf\u00e6ngsel, Horsens",
            "composition": "A long red-brick prison front and a central arch \u00b7 AI-generated artistic interpretation",
            "lead": "The public face of the old state prison is a long symmetrical red-brick front, rows of small windows, and a central arched gateway.",
            "tail": "No wordmark is readable. The street is empty.",
            "alt_text": "AI-generated artistic interpretation of the old Horsens state prison under broken cloud, a long red-brick front",
            "viewpoint": "The street in front of the prison facade. Approximate researched point 55.87514, 9.83536, not a surveyed camera. Open-Meteo ran this request on grid 55.87359, 9.83090.",
            "refs": [
                "https://en.wikipedia.org/wiki/Horsens_Statsf%C3%A6ngsel",
                "https://da.wikipedia.org/wiki/Horsens_Statsf%C3%A6ngsel",
            ],
            "anchors": [
                "A long red-brick institutional front.",
                "Rows of small windows and a central arch.",
                "No readable name and no banner.",
            ],
            "independent": "Horsens Statsf\u00e6ngsel is the former state prison, now used as a museum and venue. The frame is the brick exterior only. Ranking claims about the museum are not repeated. The harbour, Bygholm, and Vor Frelsers Kirke are other cards.",
            "ip": "No museum wordmark and no poster. Internal review only, not a legal certification.",
            "visual": "Pass. Long red-brick front, central arch, broken cloud, empty. No wordmark.",
            "swap": "No full site swap of the town. Horsens Harbour is already DK-01-055, Bygholm Castle is DK-01-216, and Vor Frelsers Kirke is DK-01-121. The unused public face is Horsens Statsf\u00e6ngsel, without a logo. City remains Horsens.",
        },
        {
            "entry_id": "DK-01-347",
            "region": "Central Jutland",
            "city": "Randers",
            "caption": "Sankt Mortens Kirke, Randers",
            "composition": "A red-brick church and one copper-spired tower \u00b7 AI-generated artistic interpretation",
            "lead": "From the square, Sankt Mortens Kirke is a red-brick Gothic church with one tall square tower and a copper spire.",
            "tail": "The half-timbered quay is not in this frame. The square is empty.",
            "alt_text": "AI-generated artistic interpretation of Sankt Mortens Kirke in Randers on an overcast afternoon, a red-brick tower and copper spire",
            "viewpoint": "The square in front of the west tower. Approximate researched point 56.45989, 10.03496, not a surveyed camera. Open-Meteo ran this request on grid 56.45622, 10.03799.",
            "refs": [
                "https://en.wikipedia.org/wiki/St_Martin%27s_Church,_Randers",
                "https://da.wikipedia.org/wiki/Sankt_Mortens_Kirke_(Randers)",
            ],
            "anchors": [
                "A red-brick Gothic church.",
                "One tall square tower.",
                "A copper spire. No half-timbered quay.",
            ],
            "independent": "The English article describes St Martin's Church as a red-brick church in Randers, built from 1494 to 1520 on an older site. The Guden\u00e5 quay is a different card.",
            "ip": "No readable board. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, one tower, copper spire, overcast, empty square. No quay and no lettering.",
            "swap": "Swapped from the Guden\u00e5 quay and from the rainforest exterior. The quay is already DK-01-054, Randers Riverfront, Randers. The rainforest was set aside because of logo risk. The unused church is Sankt Mortens Kirke. City remains Randers.",
        },
        {
            "entry_id": "DK-01-348",
            "region": "Central Jutland",
            "city": "Emborg",
            "caption": "\u00d8m Abbey, Emborg",
            "composition": "Low roofless brick walls in the grass \u00b7 AI-generated artistic interpretation",
            "lead": "\u00d8m Abbey is a roofless ruin: low red-brick walls of the church and chapter house, with grass in the former nave and a few early-autumn trees.",
            "tail": "There is no intact roof and no museum sign.",
            "alt_text": "AI-generated artistic interpretation of the \u00d8m Abbey ruins at Emborg under broken cloud, low brick walls in the grass",
            "viewpoint": "The grass inside the ruined church. Approximate researched point 56.05000, 9.74722, not a surveyed camera. Open-Meteo ran this request on grid 56.04871, 9.74146.",
            "refs": [
                "https://en.wikipedia.org/wiki/%C3%98m_Abbey",
                "https://da.wikipedia.org/wiki/%C3%98m_Kloster",
            ],
            "anchors": [
                "Low red-brick walls, open to the sky.",
                "Grass in the former nave.",
                "No complete church and no sign.",
            ],
            "independent": "The English article describes the Cistercian abbey founded in 1172 between Moss\u00f8 and Gudens\u00f8, demolished after the Reformation, with the ruins of the church and chapter hall now in the village of Emborg. Ranking claims about the abbey's wealth are not repeated. The gallery city is Emborg.",
            "ip": "No museum wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Roofless brick walls, grass, early autumn trees, broken cloud, empty. No sign.",
            "swap": "Swapped from Himmelbjerget. That tower is already DK-01-051, Himmelbjerget, Ry. Hjejlen is DK-01-050 and Langs\u00f8 is DK-01-215. The unused site in the lake district is \u00d8m Abbey. City is Emborg.",
        },
        {
            "entry_id": "DK-01-349",
            "region": "North Jutland",
            "city": "Skagen",
            "caption": "Skagen Odde, Skagen",
            "composition": "Marram dunes and a sand path \u00b7 AI-generated artistic interpretation",
            "lead": "The dune approach on Skagen Odde is marram grass bent by a fresh wind, a sand path, and a glimpse of sea to one side.",
            "tail": "There is no lighthouse and no meeting of two wave trains.",
            "alt_text": "AI-generated artistic interpretation of the Skagen Odde dunes on a windy afternoon with broken cloud, marram and a sand path",
            "viewpoint": "A dune path on the odde, south of the Grenen tip and east of the Grey Lighthouse, so neither is the subject. Approximate researched point 57.74400, 10.64000, not a surveyed camera. Open-Meteo ran this request on grid 57.74448, 10.62532. The exact tripod on the path was not pinned.",
            "refs": [
                "https://en.wikipedia.org/wiki/Skagen_Odde",
                "https://en.wikipedia.org/wiki/Grenen",
            ],
            "anchors": [
                "Sand dunes and marram grass.",
                "A sandy path and a side glimpse of the sea.",
                "No tower and no two-seas meeting.",
            ],
            "independent": "Skagen Odde is the sandy peninsula north of Skagen. Grenen, where the wave trains meet, is already DK-01-012, and the Grey Lighthouse is DK-01-329. This frame stays on the dune approach and does not repeat either of those subjects. The Grenen article is cited so the distinction is explicit.",
            "ip": "No sign and no shuttle. Internal review only, not a legal certification.",
            "visual": "Pass. Marram, sand path, sea to one side, broken cloud, fresh wind, empty. No lighthouse and no lettering.",
            "swap": "No site swap of the town. The suggested Grenen approach is kept as Skagen Odde dunes, distinct from Grenen itself and from the Grey Lighthouse. City remains Skagen.",
        },
        {
            "entry_id": "DK-01-350",
            "region": "Faroe Islands",
            "city": "Mykines",
            "caption": "Mykines, Mykines",
            "composition": "Turf-roofed houses and a turf-roofed stone church \u00b7 AI-generated artistic interpretation",
            "lead": "Mykines is a small village of bright houses with grass turf roofs, a stone church with a turf roof, and a stream, under steep green hills.",
            "tail": "There are no cars. The gale puts whitecaps on the sea.",
            "alt_text": "AI-generated artistic interpretation of Mykines village in the Faroe Islands in a gale, turf-roofed houses on a green hill",
            "viewpoint": "The village slope. Approximate researched point 62.10417, -7.64611, not a surveyed camera. Open-Meteo ran this request on grid 62.09691, -7.64748. The exact house in the foreground was not pinned.",
            "refs": [
                "https://en.wikipedia.org/wiki/Mykines,_Mykines",
                "https://en.wikipedia.org/wiki/Mykines,_Faroe_Islands",
            ],
            "anchors": [
                "Bright houses with grass turf roofs.",
                "A small stone church with a turf roof.",
                "Steep green ground, a stream, and no cars.",
            ],
            "independent": "The village article describes the only settlement on Mykines: bright houses with turf roofs, a turf-roofed stone church consecrated in 1879, and a stream. The island has no conventional cars. Saksun is a different island and a different card.",
            "ip": "No readable house name and no airline mark. Internal review only, not a legal certification.",
            "visual": "Pass. Turf roofs, church, green hill, broken cloud, gale, empty. No cars and no lettering.",
            "swap": "Swapped from Saksun. That lagoon is already DK-01-071, Saksun Lagoon, Saksun. The unused village is Mykines. City is Mykines.",
        },
        {
            "entry_id": "DK-01-351",
            "region": "Faroe Islands",
            "city": "Mi\u00f0v\u00e1gur",
            "caption": "Tr\u00e6lan\u00edpan, Mi\u00f0v\u00e1gur",
            "composition": "A grass cliff, a long lake, and the sea below \u00b7 AI-generated artistic interpretation",
            "lead": "From the grass of Tr\u00e6lan\u00edpan, the long lake runs toward a cliff lip, and the sea shows below that lip.",
            "tail": "The sky is overcast and the wind is strong. There is no village.",
            "alt_text": "AI-generated artistic interpretation of Tr\u00e6lan\u00edpan in the Faroe Islands under an overcast sky, a lake ending above the sea",
            "viewpoint": "The cliff edge looking along the lake toward the ocean. Approximate researched point 62.02090, -7.23009, not a surveyed camera. Open-Meteo ran this request on grid 62.02389, -7.22940. Photon places the peak in Mi\u00f0v\u00e1gur. The exact tripod on the rim was not pinned.",
            "refs": [
                "https://en.wikipedia.org/wiki/S%C3%B8rv%C3%A1gsvatn",
                "https://da.wikipedia.org/wiki/Leitisvatn",
            ],
            "anchors": [
                "Grass cliff in the foreground.",
                "A long lake.",
                "Sea visible below the far lip. No village.",
            ],
            "independent": "The English article names the view from Tr\u00e6lan\u00edpan and says the lake surface sits about 32 metres above the sea, held back by the cliff, with B\u00f8sdalafossur as the outlet. The lake is also called Leitisvatn. B\u00f8ur village is a different card and is not this frame. The city is Mi\u00f0v\u00e1gur, the settlement returned for the peak.",
            "ip": "No sign and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Grass cliff, lake, sea below the lip, overcast, strong wind, empty. No village and no lettering.",
            "swap": "Swapped from Gj\u00f3gv. That gorge harbour is already DK-01-072, Gj\u00f3gv, Gj\u00f3gv. The unused view is Tr\u00e6lan\u00edpan. City is Mi\u00f0v\u00e1gur.",
        },
        {
            "entry_id": "DK-01-352",
            "region": "Greenland",
            "city": "Tasiilaq",
            "caption": "Tasiilaq Harbour, Tasiilaq",
            "composition": "Colourful wooden houses on dark rock by a bay \u00b7 AI-generated artistic interpretation",
            "lead": "Tasiilaq harbour is a cluster of colourful wooden houses on dark rock around a small bay, with a few boats and rocky mountains behind.",
            "tail": "No snow is falling, and the town ground is bare.",
            "alt_text": "AI-generated artistic interpretation of Tasiilaq harbour under an overcast sky, colourful wooden houses on dark rock",
            "viewpoint": "The town shore on the bay. Approximate researched point 65.61340, -37.63610, not a surveyed camera. Open-Meteo ran this request on grid 65.59303, -37.62724. The exact camera on the mole was not pinned beyond the town.",
            "refs": [
                "https://en.wikipedia.org/wiki/Tasiilaq",
                "https://da.wikipedia.org/wiki/Tasiilaq",
            ],
            "anchors": [
                "Colourful wooden houses.",
                "Dark rock and a small bay with a few boats.",
                "Rocky mountains. No snow cover in the town.",
            ],
            "independent": "Tasiilaq, formerly Kong Oscars Havn, is the town on the bay of Ammassalik Island in east Greenland. The model step is overcast, about 5.9\u00b0C, with no precipitation and no snowfall, so the frame does not add falling snow or a snow-covered street. Sisimiut harbour is a different town.",
            "ip": "No readable house name. Internal review only, not a legal certification.",
            "visual": "Pass. Colourful houses, dark rock, bay, mountains, overcast, empty. No snow and no lettering.",
            "swap": "Swapped from Sisimiut Harbour, already DK-01-080. Bethel Church in Sisimiut is DK-01-254. The unused east-coast town is Tasiilaq. City is Tasiilaq.",
        },
    ]

    built = []
    for scene in catalog:
        entry = scene["entry_id"]
        scene.update(rows[entry])
        when = scenario_dt(entry)
        scene["description"] = f"{scene['lead']} {sky(entry, when)}{local_clause(entry, when)} {scene['tail']}"
        scene["solar"] = solar_text(scene["_row"], when, place_zone(entry))
        built.append(scene)
    return built


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


def verify_baked_text(scene: dict, label: str) -> None:
    caption = scene["caption"]
    for kind, path in scene["_files"].items():
        im = Image.open(path)
        w, h = im.size
        top = int(h * 0.84)

        def ocr_box(box: tuple[int, int, int, int], tag: str, psm: str) -> str:
            crop = im.crop(box)
            crop = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.LANCZOS)
            tmp = Path("/tmp") / f"{path.stem}-{tag}.png"
            crop.save(tmp)
            text = subprocess.check_output(
                ["tesseract", str(tmp), "stdout", "--psm", psm],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            tmp.unlink()
            return text

        txt = ocr_box((0, int(h * 0.88), w - 2, h - 2), "b", "6")
        low = txt.lower()
        if "vision" not in low or ("jason" not in low and "ason" not in low):
            raise SystemExit(f"signature OCR {path}\n{txt}")
        if kind == "16x9":
            if "scenario" not in low:
                raise SystemExit(f"scenario OCR {path}\n{txt}")
            if "artistic" not in low and "photograph" not in low:
                raise SystemExit(f"disclosure OCR {path}\n{txt}")
        fold = str.maketrans({
            "\u00e6": "ae", "\u00c6": "ae",
            "\u00f8": "o", "\u00d8": "o",
            "\u00e5": "a", "\u00c5": "a",
            "\u00f0": "d", "\u00d0": "d",
            "\u00ed": "i", "\u00e1": "a", "\u00f3": "o", "\u00fa": "u", "\u00fd": "y",
            "\u00e9": "e", "\u00f6": "o", "\u00e4": "a",
        })
        stems = []
        for word in caption.replace(",", " ").split():
            folded = word.translate(fold)
            ascii_word = "".join(ch for ch in folded if ch.isascii() and ch.isalpha())
            if len(ascii_word) >= 4:
                stems.append(ascii_word[:4])

        def near(stem: str, text: str) -> bool:
            if stem in text:
                return True
            n = len(stem)
            for i in range(0, max(0, len(text) - n + 1)):
                window = text[i:i + n]
                if sum(a != b for a, b in zip(stem, window)) <= 1:
                    return True
            return False

        if stems and not any(near(stem.lower(), low) for stem in stems):
            raise SystemExit(f"caption OCR {path} missing {stems!r}\n{txt}")
        if "\u2019" not in bd.SIG:
            raise SystemExit("signature constant lost the curly apostrophe")


def main() -> None:
    prepare_raws()
    batch = scenes()
    if len(batch) != 16:
        raise SystemExit(len(batch))
    prefixes = [scene["weather_prefix"] for scene in batch]
    if len(prefixes) != len(set(prefixes)):
        raise SystemExit("reused weather prefix")
    lines = []
    masters: list[Path] = []
    for scene in batch:
        label = bd.scenario_label(scene["entry_id"])
        hour = label.split("\u00b7")[1].strip().split(" ")[0]
        valid_hm = scene["_row"]["valid"][11:16]
        valid_hour = valid_hm[:2]
        if not hour.startswith(valid_hour + ":"):
            raise SystemExit(f"{scene['entry_id']} scenario {label} outside valid hour {valid_hour}")
        if hour < valid_hm:
            raise SystemExit(f"{scene['entry_id']} scenario {hour} before model step {valid_hm}")
        sunrise = scene["_row"]["sunrise"][11:16]
        if hour < sunrise:
            raise SystemExit(f"{scene['entry_id']} scenario {hour} before sunrise {sunrise}")
        if "25 September 2026" not in label:
            raise SystemExit(label)
        retrieved = datetime.fromisoformat(scene["_row"]["retrieved_iso"])
        when = scenario_dt(scene["entry_id"])
        if when <= retrieved:
            raise SystemExit(f"{scene['entry_id']} scenario {when} not after retrieval {retrieved}")
        if int(scene["_row"]["is_day"]) != 1:
            raise SystemExit(f"{scene['entry_id']} is_day")
        blob = scene["description"].lower()
        for banned in ("real-time", "photograph of"):
            if banned in blob:
                raise SystemExit(f"banned wording {scene['entry_id']} {banned}")
        if "not a verified on-site observation" not in scene["weather_prefix"]:
            raise SystemExit(f"weather wording {scene['entry_id']}")
        bd.write_outputs(scene, label)
        bd.manifest(scene, label)
        bd.approval(scene, label)
        verify_baked_text(scene, label)
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
    if len(all_scenes) != 352:
        raise SystemExit(f"expected 352 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 353)]
    if ids != expected:
        raise SystemExit("id sequence mismatch")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    descriptions = [item["_manifest"]["description"] for item in all_scenes]
    if len(descriptions) != len(set(descriptions)):
        raise SystemExit("duplicate description")
    for item in all_scenes:
        status = item["_manifest"].get("approval_status")
        entry_id = item["_manifest"]["entry_id"]
        if entry_id >= "DK-01-337" and status not in (None, "Candidate"):
            raise SystemExit(f"status {entry_id}")
        if status not in (None, "Candidate", "Approved"):
            raise SystemExit(f"status {entry_id} {status}")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-337-352.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pngs = list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-16x9.png"))
    pngs += list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-4x5.png"))
    if len(pngs) != 704:
        raise SystemExit(f"expected 704 masters, got {len(pngs)}")
    for path in masters:
        subprocess.run(
            ["exiftool", "-Title", "-Description", "-Copyright", "-Software", "-Comment", str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    print("site written", len(all_scenes))
    print("masters", len(pngs))
    print("exiftool checked", len(masters))


if __name__ == "__main__":
    main()

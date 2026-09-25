#!/usr/bin/env python3
"""Bake DK-01-177 through DK-01-192 and rebuild the gallery from every manifest."""

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
    "DK-01-177": (54.83099, 11.13500),
    "DK-01-178": (54.77045, 11.49463),
    "DK-01-179": (54.66467, 11.72309),
    "DK-01-180": (54.65378, 11.35291),
    "DK-01-181": (54.82315, 12.13802),
    "DK-01-182": (54.76570, 11.86928),
    "DK-01-183": (54.57222, 11.92320),
    "DK-01-184": (54.89073, 12.04712),
    "DK-01-185": (55.00333, 11.91833),
    "DK-01-186": (55.22604, 11.75618),
    "DK-01-187": (55.42507, 11.53767),
    "DK-01-188": (55.43354, 11.68759),
    "DK-01-189": (55.39409, 11.26527),
    "DK-01-190": (55.33389, 11.13684),
    "DK-01-191": (55.25222, 11.28766),
    "DK-01-192": (55.21343, 12.15997),
}

GEN_BUCKET = {entry: "overcast" for entry in COORDS}

# Depicted from the 03:54 Europe/Copenhagen retrieval, valid 03:45.
# Kept if a later hour changes the sky bucket or leaves night.
_BASE = {
    "is_day": 0,
    "valid": "2026-09-25T03:45",
    "retrieved_stamp": "25 September 2026 03:54",
    "offset": 7200,
    "precip": 0.0,
    "word": "Overcast",
    "code": 3,
}
SNAPSHOT = {
    "DK-01-177": {**_BASE, "temp": 12.3, "cloud": 96, "wind": 15.2, "sunset_yesterday": "2026-09-24T19:09", "sunrise_today": "2026-09-25T07:06"},
    "DK-01-178": {**_BASE, "temp": 12.1, "cloud": 91, "wind": 15.1, "sunset_yesterday": "2026-09-24T19:08", "sunrise_today": "2026-09-25T07:04"},
    "DK-01-179": {**_BASE, "temp": 12.3, "cloud": 95, "wind": 17.0, "sunset_yesterday": "2026-09-24T19:07", "sunrise_today": "2026-09-25T07:03"},
    "DK-01-180": {**_BASE, "temp": 12.3, "cloud": 94, "wind": 15.5, "sunset_yesterday": "2026-09-24T19:08", "sunrise_today": "2026-09-25T07:05"},
    "DK-01-181": {**_BASE, "temp": 13.4, "cloud": 93, "wind": 12.5, "sunset_yesterday": "2026-09-24T19:05", "sunrise_today": "2026-09-25T07:02"},
    "DK-01-182": {**_BASE, "temp": 13.2, "cloud": 94, "wind": 15.7, "sunset_yesterday": "2026-09-24T19:06", "sunrise_today": "2026-09-25T07:03"},
    "DK-01-183": {**_BASE, "temp": 12.9, "cloud": 96, "wind": 19.3, "sunset_yesterday": "2026-09-24T19:06", "sunrise_today": "2026-09-25T07:03"},
    "DK-01-184": {**_BASE, "temp": 13.5, "cloud": 91, "wind": 17.2, "sunset_yesterday": "2026-09-24T19:05", "sunrise_today": "2026-09-25T07:02"},
    "DK-01-185": {**_BASE, "temp": 14.0, "cloud": 97, "wind": 16.6, "sunset_yesterday": "2026-09-24T19:06", "sunrise_today": "2026-09-25T07:03"},
    "DK-01-186": {**_BASE, "temp": 13.5, "cloud": 98, "wind": 9.4, "sunset_yesterday": "2026-09-24T19:07", "sunrise_today": "2026-09-25T07:03"},
    "DK-01-187": {**_BASE, "temp": 13.2, "cloud": 100, "wind": 13.3, "sunset_yesterday": "2026-09-24T19:07", "sunrise_today": "2026-09-25T07:04"},
    "DK-01-188": {**_BASE, "temp": 12.7, "cloud": 100, "wind": 13.7, "sunset_yesterday": "2026-09-24T19:07", "sunrise_today": "2026-09-25T07:04"},
    "DK-01-189": {**_BASE, "temp": 13.2, "cloud": 99, "wind": 20.2, "sunset_yesterday": "2026-09-24T19:08", "sunrise_today": "2026-09-25T07:05"},
    "DK-01-190": {**_BASE, "temp": 13.1, "cloud": 97, "wind": 25.6, "sunset_yesterday": "2026-09-24T19:09", "sunrise_today": "2026-09-25T07:06"},
    "DK-01-191": {**_BASE, "temp": 13.1, "cloud": 100, "wind": 20.2, "sunset_yesterday": "2026-09-24T19:08", "sunrise_today": "2026-09-25T07:05"},
    "DK-01-192": {**_BASE, "temp": 13.5, "cloud": 96, "wind": 10.8, "sunset_yesterday": "2026-09-24T19:05", "sunrise_today": "2026-09-25T07:02"},
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
    data = []
    for start in range(0, len(ids), 4):
        chunk = ids[start:start + 4]
        lats = ",".join(str(COORDS[i][0]) for i in chunk)
        lons = ",".join(str(COORDS[i][1]) for i in chunk)
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={lats}&longitude={lons}"
            "&current=temperature_2m,cloud_cover,wind_speed_10m,precipitation,weather_code,is_day"
            "&daily=sunrise,sunset&timezone=" + urllib.parse.quote("Europe/Copenhagen") +
            "&past_days=1&forecast_days=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "jason-ds-vision-denmark/1.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            piece = json.loads(resp.read())
        if isinstance(piece, dict):
            piece = [piece]
        if len(piece) != len(chunk):
            raise SystemExit(f"weather count {len(piece)} for {chunk}")
        data.extend(piece)
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
    for n in range(177, 193):
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

    def pack(entry: str) -> dict:
        row = wx[entry]
        return {
            "weather_prefix": pref(entry),
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

    rows = {entry: pack(entry) for entry in COORDS}

    def R(entry: str) -> dict:
        return rows[entry]

    a = R("DK-01-177")
    b = R("DK-01-178")
    c = R("DK-01-179")
    d = R("DK-01-180")
    e = R("DK-01-181")
    f = R("DK-01-182")
    g = R("DK-01-183")
    h = R("DK-01-184")
    i = R("DK-01-185")
    j = R("DK-01-186")
    k = R("DK-01-187")
    m = R("DK-01-188")
    n = R("DK-01-189")
    o = R("DK-01-190")
    p = R("DK-01-191")
    q = R("DK-01-192")

    return [
        {
            "entry_id": "DK-01-177",
            "region": "Lolland-Falster",
            "city": "Nakskov",
            "caption": "Nakskov Church, Nakskov",
            **a,
            "composition": "Light-red brick nave, slate roofs, and a copper spire \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the square, Sankt Nikolaj Kirke shows a high light-red-brick nave, lower aisles, dark slate roofs, and one west tower with a copper spire. "
                f"The square is empty. The night is {a['word'].lower()}, about {a['temp']}\u00b0C. "
                "This is the town church, not the harbour warehouses."
            ),
            "alt_text": "AI-generated artistic interpretation of Nakskov Church at night, a brick nave and a copper spire",
            "viewpoint": "The public square beside Sankt Nikolaj Kirke. Approximate researched point 54.83099, 11.13500, not a surveyed camera. Nominatim places the church in Nakskov, postal 4900.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nakskov_Church",
                "https://www.nakskovkirke.dk/sankt-nikolai-kirke/om-sankt-nikolai-kirke/sankt-nikolai-kirkes-historie-og-indretning",
            ],
            "anchors": [
                "A high light-red-brick nave with lower side aisles.",
                "Dark slate roofs, and a copper spire only on the west tower.",
                "An empty square. No harbour and no warehouse.",
            ],
            "solar": clock("DK-01-177") + "A few street lamps. No readable shop name.",
            "independent": (
                "Nakskov Church, Sankt Nikolaj, is the large town church. The parish history page says the present copper spire was built in 1906 by H. Glahn and that the height from the ground to the tip is 70 m. "
                "Wikipedia describes light red brick, Gothic aisles around an older core, and a west tower. "
                "The harbour warehouses are already DK-01-105. This frame is the church square."
            ),
            "ip": "No readable shop name and no logo. Internal review only, not a legal certification.",
            "visual": "Pass. Light-red brick, high nave, lower aisles, slate, copper spire, empty square, overcast night. No harbour.",
            "swap": (
                "Swapped from Nakskov Harbour. That harbour is already DK-01-105, Nakskov Harbour, Nakskov. "
                "The caption is Nakskov Church. City remains Nakskov."
            ),
        },
        {
            "entry_id": "DK-01-178",
            "region": "Lolland-Falster",
            "city": "Maribo",
            "caption": "Maribo Lake, Maribo",
            "description": (
                "From the northwest shore of S\u00f8nders\u00f8, reeds and a short wooden jetty face dark open water and a far wooded bank. "
                f"The path is empty. The night is {b['word'].lower()}, about {b['temp']}\u00b0C. "
                "The cathedral is behind the camera, and Knuthenborg is not in the frame."
            ),
            **b,
            "composition": "Reeds and a jetty on S\u00f8nders\u00f8 \u00b7 AI-generated artistic interpretation",
            "alt_text": "AI-generated artistic interpretation of Maribo Lake at night, reeds and open water under cloud",
            "viewpoint": "The public northwest shore of S\u00f8nders\u00f8, near the lakeside ground west of the cathedral, looking south across the water. Approximate researched point 54.77045, 11.49463, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Maribo_Lakes",
                "https://en.wikipedia.org/wiki/Maribo",
            ],
            "anchors": [
                "Reeds and a low wooden jetty in the foreground.",
                "Open dark water and a far wooded shore.",
                "No cathedral facade and no safari-park animals.",
            ],
            "solar": clock("DK-01-178") + "A few distant shore lights. No floodlit church.",
            "independent": (
                "Wikipedia lists the Maribo Lakes as Hejrede S\u00f8, N\u00f8rres\u00f8, R\u00f8gb\u00f8lle S\u00f8 and S\u00f8nders\u00f8, around the town of Maribo. "
                "The town and the cathedral sit on the north side of S\u00f8nders\u00f8. The cathedral close view is already DK-01-033, and Knuthenborg is DK-01-034. "
                "This frame looks south from the northwest shore, so the cathedral is not the subject."
            ),
            "ip": "No park logo and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Reeds, jetty, open lake, far trees, overcast night. No cathedral and no animals.",
            "swap": (
                "No site swap. Maribo Lake is distinct from Maribo Cathedral, DK-01-033, and from Knuthenborg, DK-01-034. "
                "City remains Maribo."
            ),
        },
        {
            "entry_id": "DK-01-179",
            "region": "Lolland-Falster",
            "city": "Nysted",
            "caption": "Aalholm Castle, Nysted",
            **c,
            "composition": "A pale castle on an islet across dark water \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the public shore, Aalholm stands on its islet: pale walls, red tile roofs, and several wings, with fjord water in front. "
                f"The shore is empty. The night is {c['word'].lower()}, about {c['temp']}\u00b0C. "
                "The castle grounds are not entered, and the town harbour houses are not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Aalholm Castle at night, seen across the water near Nysted",
            "viewpoint": "The public shore looking across the water at the castle islet. The castle point is approximately 54.66467, 11.72309, not a surveyed camera. Nominatim places the manor in Nysted, postal 4880.",
            "refs": [
                "https://www.visitlolland-falster.com/tourist/plan-your-holiday/aalholm-castle-gdk615714",
                "https://aalholmslot.dk/slot/",
            ],
            "anchors": [
                "A pale multi-wing castle on a small islet.",
                "Red tile roofs and dark water in the foreground.",
                "No town-harbour street and no visitors on the grounds.",
            ],
            "solar": clock("DK-01-179") + "A few warm windows. No facade floodlight show.",
            "independent": (
                "Visit Lolland-Falster says Aalholm can be seen from the dam and from routes around Nysted, and that the castle is not open to the public. "
                "The estate page states the same: not open to the public. The address given there is Aalholm Parkvej, 4880 Nysted. "
                "Nysted Harbour is already DK-01-107 and deliberately left the castle out of that frame. This card is the exterior across the water."
            ),
            "ip": "Private house, exterior only, no crest treated as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. Pale walls, red roofs, islet, water foreground, overcast night. No harbour street.",
            "swap": (
                "Swapped from Nysted Harbour. That harbour is already DK-01-107, Nysted Harbour, Nysted. "
                "The caption is Aalholm Castle. City remains Nysted."
            ),
        },
        {
            "entry_id": "DK-01-180",
            "region": "Lolland-Falster",
            "city": "R\u00f8dbyhavn",
            "caption": "R\u00f8dbyhavn Harbour, R\u00f8dbyhavn",
            **d,
            "composition": "Concrete ferry berths on a flat coast \u00b7 AI-generated artistic interpretation",
            "description": (
                "The ferry harbour exterior is concrete breakwaters and empty berths on the flat south Lolland coast, with dark wind-chopped water. "
                f"The quay is empty. The night is {d['word'].lower()}, about {d['temp']}\u00b0C. "
                "No ship name and no company mark are in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of R\u00f8dbyhavn harbour at night, concrete berths and dark water",
            "viewpoint": "The public side of R\u00f8dby F\u00e6rgehavn, looking at the moles. Approximate researched point 54.65378, 11.35291, not a surveyed camera. Nominatim places the ferry terminal in R\u00f8dbyhavn, postal 4970.",
            "refs": [
                "https://en.wikipedia.org/wiki/R%C3%B8dbyhavn",
                "https://da.wikipedia.org/wiki/R%C3%B8dbyhavn",
            ],
            "anchors": [
                "Long concrete breakwaters and ferry berths.",
                "Dark choppy water and a flat coast.",
                "No readable ship name and no funnel mark.",
            ],
            "solar": clock("DK-01-180") + "Harbour lamps. No lit wordmark.",
            "independent": (
                "R\u00f8dbyhavn is the ferry port on the south coast of Lolland, distinct from inland R\u00f8dby. Nominatim tags the village R\u00f8dbyhavn, postal 4970, and the ferry terminal R\u00f8dby F\u00e6rgehavn. "
                "The frame is the public harbour exterior. A first generation included a liveried ship and was replaced so no brand mark is the subject."
            ),
            "ip": "No ferry wordmark, no funnel logo, and no readable ship name. Internal review only, not a legal certification.",
            "visual": "Pass. Concrete moles, empty berths, choppy water, overcast night. No branded ferry.",
            "swap": "No site swap. City is R\u00f8dbyhavn, the port village, not inland R\u00f8dby. A branded ferry was removed from the frame before baking.",
        },
        {
            "entry_id": "DK-01-181",
            "region": "Lolland-Falster",
            "city": "Hesn\u00e6s",
            "caption": "Hesn\u00e6s Harbour, Hesn\u00e6s",
            **e,
            "composition": "A small mole, boats, and reed-thatched houses \u00b7 AI-generated artistic interpretation",
            "description": (
                "Hesn\u00e6s harbour is a short concrete mole with a few small boats, a low shed, and reed-thatched village houses behind, opening onto the Baltic. "
                f"The quay is empty. The night is {e['word'].lower()}, about {e['temp']}\u00b0C. "
                "No place name is written on the shed."
            ),
            "alt_text": "AI-generated artistic interpretation of Hesn\u00e6s harbour at night, boats and reed-thatched houses",
            "viewpoint": "The public quay at Hesn\u00e6s Havn. Approximate researched point 54.82315, 12.13802, not a surveyed camera. Nominatim places the marina in Hesn\u00e6s.",
            "refs": [
                "https://www.visitlolland-falster.dk/turist/planlaeg-din-ferie/hesnaes-havn-gdk885481",
                "https://falsterskyst.com/spisesteder/hesnaes-havn/",
            ],
            "anchors": [
                "A short concrete mole and a few small boats.",
                "Reed-thatched houses in the village behind the quay.",
                "Dark Baltic water. No readable name on the shed.",
            ],
            "solar": clock("DK-01-181") + "A few quay lamps. No sign lighting.",
            "independent": (
                "Visit Lolland-Falster describes Hesn\u00e6s Havn on northeast Falster, reopened on 1 July 2026, with the reed-clad houses the area is known for. The page gives B\u00f8nnedvej 65, 4850 Stubbek\u00f8bing. "
                "OpenStreetMap places Hesn\u00e6s Havn on B\u00f8nnetvej in the village Hesn\u00e6s. "
                "The caption city is Hesn\u00e6s, the village, not Stubbek\u00f8bing, which is a separate harbour card. Saksk\u00f8bing's waterfront is already DK-01-106. A first frame with lettering on a building was replaced."
            ),
            "ip": "No readable place name and no caf\u00e9 logo. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, small boats, reed roofs, Baltic, overcast night. No lettering.",
            "swap": (
                "Swapped from Saksk\u00f8bing harbour. Saksk\u00f8bing's canal, bridge, and church spire are already DK-01-106. "
                "The caption is Hesn\u00e6s Harbour. City is Hesn\u00e6s."
            ),
        },
        {
            "entry_id": "DK-01-182",
            "region": "Lolland-Falster",
            "city": "Nyk\u00f8bing Falster",
            "caption": "Klosterkirken, Nyk\u00f8bing Falster",
            **f,
            "composition": "A long brick church, stepped gable, and an onion spire \u00b7 AI-generated artistic interpretation",
            "description": (
                "Klosterkirken is a long red-brick Gothic church with buttresses, pointed windows, a stepped gable, and a north-side tower with an onion spire, beside a lower west wing. "
                f"The street is empty. The night is {f['word'].lower()}, about {f['temp']}\u00b0C. "
                "The harbour is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Klosterkirken in Nyk\u00f8bing Falster at night, a long brick church and an onion spire",
            "viewpoint": "The public street beside Klosterkirken. Approximate researched point 54.76570, 11.86928, not a surveyed camera. Nominatim places the church in Nyk\u00f8bing Falster, postal 4800.",
            "refs": [
                "https://en.wikipedia.org/wiki/Abbey_Church,_Nyk%C3%B8bing_Falster",
                "https://lex.dk/Klosterkirken_-_Nyk%C3%B8bing_Falster_Kirke",
            ],
            "anchors": [
                "A long red-brick nave with buttresses and pointed windows.",
                "A stepped gable and a north-side tower with an onion spire.",
                "A lower preserved west wing. No harbour.",
            ],
            "solar": clock("DK-01-182") + "Street lamps. No readable inscription.",
            "independent": (
                "The abbey church is the former Franciscan church in Nyk\u00f8bing Falster. Wikipedia describes a red-brick late Gothic nave, a tower on the north side, and the onion spire added when the tower was heightened in 1766. "
                "Lex describes the stepped gables and the surviving west wing. "
                "The harbour is already DK-01-091. This frame is the church exterior, and it is not Nyk\u00f8bing Sj\u00e6lland."
            ),
            "ip": "No readable inscription treated as a sign. Internal review only, not a legal certification.",
            "visual": "Pass. Long brick church, stepped gable, onion spire, west wing, empty street, overcast night.",
            "swap": (
                "Swapped from Nyk\u00f8bing Falster Harbour. That harbour is already DK-01-091. "
                "The caption is Klosterkirken. City remains Nyk\u00f8bing Falster, distinct from Nyk\u00f8bing Sj\u00e6lland, DK-01-174."
            ),
        },
        {
            "entry_id": "DK-01-183",
            "region": "Lolland-Falster",
            "city": "Gedser",
            "caption": "Gedser Harbour, Gedser",
            **g,
            "composition": "A short fishing quay on a flat Baltic coast \u00b7 AI-generated artistic interpretation",
            "description": (
                "Gedser's fishing harbour is a short concrete quay, a few small boats, and low sheds on a flat coast, with dark wind-chopped water. "
                f"The quay is empty. The night is {g['word'].lower()}, about {g['temp']}\u00b0C. "
                "There is no lighthouse and no clay cliff."
            ),
            "alt_text": "AI-generated artistic interpretation of Gedser harbour at night, a short quay and small boats",
            "viewpoint": "The public quay at Gedser Fiskerihavn, Havnegade. Approximate researched point 54.57222, 11.92320, not a surveyed camera.",
            "refs": [
                "https://www.guldborgsundhavne.dk/oversigt-over-havne/gedser-fiskerihavn",
                "https://en.wikipedia.org/wiki/Gedser",
            ],
            "anchors": [
                "A short concrete fishing quay and a few small boats.",
                "Low sheds and a flat coast.",
                "No hexagonal lighthouse and no cliff.",
            ],
            "solar": clock("DK-01-183") + "Quay lamps. Wind chop. No ferry name.",
            "independent": (
                "Guldborgsund Havne describes Gedser Fiskerihavn as Denmark's southernmost harbour, directly on the Baltic, at Havnegade 19, 4874 Gedser, with a quay of about 187 m. "
                "Gedser Odde, the low cliff and white hexagonal lighthouse, is already DK-01-035 and lies south of the town. "
                "This frame is the fishing harbour in town. A portrait that invented the Odde lighthouse was replaced. The ferry terminal wordmark is not the subject."
            ),
            "ip": "No ferry brand and no readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Short quay, small boats, flat coast, choppy water, overcast night. No lighthouse and no cliff.",
            "swap": (
                "The suggested cliff approach is already Gedser Odde, DK-01-035. "
                "This card is Gedser Harbour, the fishing quay in town. City remains Gedser."
            ),
        },
        {
            "entry_id": "DK-01-184",
            "region": "Lolland-Falster",
            "city": "Stubbek\u00f8bing",
            "caption": "Stubbek\u00f8bing Harbour, Stubbek\u00f8bing",
            **h,
            "composition": "A town basin and the distant Far\u00f8 bridges \u00b7 AI-generated artistic interpretation",
            "description": (
                "Stubbek\u00f8bing harbour holds a few boats beside low tiled houses, with a church spire in the town and the Far\u00f8 bridges small across Gr\u00f8nsund. "
                f"The quay is empty. The night is {h['word'].lower()}, about {h['temp']}\u00b0C. "
                "The bridges read as distant concrete motorway spans, not a close subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Stubbek\u00f8bing harbour at night, boats and the distant Far\u00f8 bridges",
            "viewpoint": "The public harbour at Stubbek\u00f8bing, looking across Gr\u00f8nsund. Approximate researched point 54.89073, 12.04712, not a surveyed camera. Nominatim places the harbour in Stubbek\u00f8bing, postal 4850.",
            "refs": [
                "https://www.sailbuddy.com/da/harbour/stubbekobing-havn",
                "https://en.wikipedia.org/wiki/Stubbek%C3%B8bing",
            ],
            "anchors": [
                "A small basin with boats and low town houses.",
                "A church spire in the town.",
                "The Far\u00f8 bridges small across the sound.",
            ],
            "solar": clock("DK-01-184") + "Quay lamps and distant bridge lights. No readable name.",
            "independent": (
                "Sailbuddy describes Stubbek\u00f8bing Havn on Gr\u00f8nsund between Bog\u00f8, Falster and M\u00f8n, with a view toward the Far\u00f8 bridges and Bog\u00f8. "
                "Nominatim places the harbour in Stubbek\u00f8bing. The bridges in the frame stay distant."
            ),
            "ip": "No ferry brand and no readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, boats, town roofs, distant bridges, overcast night. No logo.",
            "swap": "No site swap. City is Stubbek\u00f8bing.",
        },
        {
            "entry_id": "DK-01-185",
            "region": "Zealand",
            "city": "Vordingborg",
            "caption": "Vordingborg Harbour, Vordingborg",
            **i,
            "composition": "Marina boats and a tiny distant tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Vordingborg Nordhavn is a marina of pontoons and sailboats on dark water, with grass along the shore. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, and the quay is empty. "
                "The Goose Tower is only a small shape on the far horizon, not a close view."
            ),
            "alt_text": "AI-generated artistic interpretation of Vordingborg harbour at night, sailboats and a distant tower",
            "viewpoint": "The public pontoons at Vordingborg Nordhavn, Nordhavnsvej 34. Approximate researched point 55.00333, 11.91833, not a surveyed camera.",
            "refs": [
                "https://www.havne.vordingborg.dk/havne/vordingborg-nordhavn",
                "https://www.havneguide.dk/havn/vordingborg-nordhavn",
            ],
            "anchors": [
                "Sailboats and pontoons filling the foreground.",
                "A grass shore and dark water.",
                "The Goose Tower only as a tiny distant shape.",
            ],
            "solar": clock("DK-01-185") + "A few marina lamps. The distant tower is not floodlit as a show.",
            "independent": (
                "Vordingborg Nordhavn's own page calls it a natural harbour with a view toward the Far\u00f8 bridges and Danmarks Borgcenter with the Goose Tower. The address is Nordhavnsvej 34, 4760 Vordingborg. Havneguide gives 55.00333, 11.91833. "
                "The close view of the Goose Tower is already DK-01-090. This frame keeps the tower small so the harbour is the subject. An earlier frame that enlarged the tower was replaced."
            ),
            "ip": "No museum sign and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Marina boats in front, tower tiny on the horizon, overcast night. Not a second close view of the Goose Tower.",
            "swap": (
                "No site swap. The harbour is distinct from the Goose Tower close view, DK-01-090. "
                "City remains Vordingborg. The tower stays distant."
            ),
        },
        {
            "entry_id": "DK-01-186",
            "region": "Zealand",
            "city": "N\u00e6stved",
            "caption": "Sus\u00e5 Harbour, N\u00e6stved",
            **j,
            "composition": "Boats on the narrow Sus\u00e5 and brick quay buildings \u00b7 AI-generated artistic interpretation",
            "description": (
                "Sus\u00e5 Harbour is a narrow dark river in the town, with a few moored boats, a low quay, brick warehouses, and a low bridge farther along. "
                f"The quay is empty. The night is {j['word'].lower()}, about {j['temp']}\u00b0C. "
                "The old-town church is not the subject, and the planned new harbour district is not built here."
            ),
            "alt_text": "AI-generated artistic interpretation of Sus\u00e5 harbour in N\u00e6stved at night, boats and brick warehouses",
            "viewpoint": "The public quay at Sus\u00e5 Havn in central N\u00e6stved. Approximate researched point 55.22604, 11.75618, not a surveyed camera.",
            "refs": [
                "https://www.havneguide.dk/havn/susaa-havn",
                "https://www.susaahavn.com/",
            ],
            "anchors": [
                "A narrow river with moored boats.",
                "Brick warehouses along a low quay.",
                "A low bridge farther down the water. No close church.",
            ],
            "solar": clock("DK-01-186") + "Quay lamps. No shop name.",
            "independent": (
                "Havneguide places Sus\u00e5 Havn in central N\u00e6stved at 55.22604, 11.75618, a small town harbour on the Sus\u00e5. The association site describes the same small public harbour near the centre. "
                "N\u00e6stved Old Town, the church, is already DK-01-089. "
                "The municipality has decided to phase commercial inner-harbour use out toward 2034. In September 2026 that new district is not the existing quay, so the frame shows the present small-boat harbour."
            ),
            "ip": "No readable warehouse name. Internal review only, not a legal certification.",
            "visual": "Pass. Narrow river, boats, brick buildings, low bridge, overcast night. Not the church and not a new glass district.",
            "swap": (
                "No site swap. The Sus\u00e5 waterfront is distinct from N\u00e6stved Old Town, DK-01-089. "
                "City remains N\u00e6stved."
            ),
        },
        {
            "entry_id": "DK-01-187",
            "region": "Zealand",
            "city": "Sor\u00f8",
            "caption": "Sor\u00f8 Lake, Sor\u00f8",
            **k,
            "composition": "An empty jetty on Sor\u00f8 S\u00f8 \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the public bathing shore on the southwest side of Sor\u00f8 S\u00f8, a simple jetty meets dark open water and a far tree-lined bank. "
                f"The grass is empty. The night is {k['word'].lower()}, about {k['temp']}\u00b0C. "
                "The abbey church is not a close subject, and there are no swimmers."
            ),
            "alt_text": "AI-generated artistic interpretation of Sor\u00f8 Lake at night, an empty jetty and open water",
            "viewpoint": "S\u00f8badet ved Parnas, the public bathing shore on the southwest side of Sor\u00f8 S\u00f8, looking across the lake. Approximate researched point 55.42507, 11.53767, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Sor%C3%B8_S%C3%B8",
                "https://en.wikipedia.org/wiki/Sor%C3%B8_Academy",
            ],
            "anchors": [
                "A simple wooden jetty and empty grass.",
                "Wide dark water.",
                "A far tree line. No close abbey church.",
            ],
            "solar": clock("DK-01-187") + "Little shore light. No swimmers and no festival lamps.",
            "independent": (
                "Sor\u00f8 S\u00f8 is the lake beside Sor\u00f8 Academy. OpenStreetMap names a public bathing place, S\u00f8badet ved Parnas, on the southwest shore at about 55.42507, 11.53767. "
                "The academy buildings sit on the east shore, about a kilometre away, so they stay small. "
                "The close view of Sor\u00f8 Abbey Church is already DK-01-101. Late September night is outside bathing use, so the shore is empty."
            ),
            "ip": "No academy sign and no logo. Internal review only, not a legal certification.",
            "visual": "Pass. Empty jetty, open lake, far trees, overcast night. The church is not the subject.",
            "swap": (
                "No site swap. Sor\u00f8 Lake from the public shore is distinct from Sor\u00f8 Abbey Church, DK-01-101. "
                "City remains Sor\u00f8."
            ),
        },
        {
            "entry_id": "DK-01-188",
            "region": "Zealand",
            "city": "Fjenneslev",
            "caption": "Fjenneslev Church, Fjenneslev",
            **m,
            "composition": "A fieldstone nave and two equal brick towers \u00b7 AI-generated artistic interpretation",
            "description": (
                "Fjenneslev Church has a grey fieldstone nave and apse and two matching red-brick west towers with low pyramidal tile roofs. "
                f"The churchyard lane is empty. The night is {m['word'].lower()}, about {m['temp']}\u00b0C. "
                "There is one pair of towers, not a single central spire."
            ),
            "alt_text": "AI-generated artistic interpretation of Fjenneslev Church at night, twin brick towers on a fieldstone nave",
            "viewpoint": "The public lane by Fjenneslev Kirke in Kirke Fjenneslev. Approximate researched point 55.43354, 11.68759, not a surveyed camera. The postal address is Langtoftevej 3A, 4173 Fjenneslev.",
            "refs": [
                "https://da.wikipedia.org/wiki/Fjenneslev_Kirke",
                "https://slaglille-bjernede-alsted-fjenneslev.dk/kirkerne/fjenneslev",
            ],
            "anchors": [
                "A Romanesque fieldstone nave and apse.",
                "Two equal red-brick west towers with low pyramidal roofs.",
                "A small south porch and an empty churchyard.",
            ],
            "solar": clock("DK-01-188") + "A couple of lamps. No readable sign.",
            "independent": (
                "Fjenneslev Church stands in the village Kirke Fjenneslev. The parish page and the Danish article describe a fieldstone Romanesque church and later twin brick towers. The postal address is 4173 Fjenneslev. "
                "The twin-tower story about Absalon and Esbern is a legend; the towers were added later and the present roofs follow the 19th-century restoration. "
                "Sankt Bendts Kirke in Ringsted is already DK-01-102, a single central tower. This card is the twin-tower village church."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Fieldstone nave, two equal brick towers, apse, empty lane, overcast night.",
            "swap": (
                "Swapped from Ringsted town square and Sankt Bendts Church. That church is already DK-01-102, Sankt Bendts Kirke, Ringsted. "
                "The caption is Fjenneslev Church. City is Fjenneslev."
            ),
        },
        {
            "entry_id": "DK-01-189",
            "region": "Zealand",
            "city": "Slagelse",
            "caption": "Trelleborg, Slagelse",
            **n,
            "composition": "A grass ring rampart and one timber longhouse \u00b7 AI-generated artistic interpretation",
            "description": (
                "Trelleborg at night is a circular grass rampart, a wooden gate, and one reconstructed timber longhouse inside the ring. "
                f"The grounds are empty and the museum is closed. The night is {n['word'].lower()}, about {n['temp']}\u00b0C. "
                "There is no festival fire and no crowd."
            ),
            "alt_text": "AI-generated artistic interpretation of Trelleborg at night, a grass rampart and a timber longhouse",
            "viewpoint": "The public approach to the ring fortress exterior. Approximate researched point 55.39409, 11.26527, not a surveyed camera.",
            "refs": [
                "https://en.natmus.dk/museums-and-palaces/trelleborg/practical-information/",
                "https://da.wikipedia.org/wiki/Vikingeborgen_Trelleborg",
            ],
            "anchors": [
                "A circular grass-covered earth rampart.",
                "One reconstructed timber longhouse with a steep roof.",
                "A wooden gate. No fire and no visitors.",
            ],
            "solar": clock("DK-01-189") + "Very little light, one path lamp at most. No festival lighting.",
            "independent": (
                "The National Museum gives the address as Trelleborg All\u00e9 4, Hejninge, 4200 Slagelse. Wikipedia uses the same address. "
                "The postal city is Slagelse. The locality is Hejninge. OpenStreetMap's 4241 tag was not used. "
                "The site is a Viking ring fortress with a reconstructed rampart and longhouses. Slagelse Old Town is already DK-01-103. At this night hour the museum is closed, so the frame is the empty exterior."
            ),
            "ip": "No museum wordmark and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Grass ring, timber longhouse, dark empty grounds, overcast night. No crowd and no fire.",
            "swap": (
                "Swapped from Slagelse old town and the G\u00e5gade. That street is already DK-01-103, Slagelse Old Town, Slagelse. "
                "The caption is Trelleborg. City is Slagelse, the postal city on the museum address. The site is in Hejninge."
            ),
        },
        {
            "entry_id": "DK-01-190",
            "region": "Zealand",
            "city": "Kors\u00f8r",
            "caption": "Kors\u00f8r Fortress, Kors\u00f8r",
            **o,
            "composition": "A square brick tower, grass bastions, and a moat \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the cobbled dam, Kors\u00f8r Fortress is a square red-brick tower with a saddle roof, grass bastions, a water moat, and a long brick magazine. "
                f"The grounds are empty. The night is {o['word'].lower()}, about {o['temp']}\u00b0C. "
                "The Great Belt bridge is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Kors\u00f8r Fortress at night, a square brick tower and grass bastions",
            "viewpoint": "The public cobbled dam on the west side of Kors\u00f8r F\u00e6stning. Approximate researched point 55.33389, 11.13684, not a surveyed camera. Nominatim places the fortress in Kors\u00f8r.",
            "refs": [
                "https://byogoverfartsmuseet.dk/historie/korsoer-faestning/",
                "https://minkultur.slagelse.dk/da/kulturhistorien/korsoer-faestning/faestningstaarnet/",
            ],
            "anchors": [
                "A square red-brick tower with a saddle roof, not a spire.",
                "Grass bastions and a water-filled moat.",
                "A long brick magazine. No suspension bridge.",
            ],
            "solar": clock("DK-01-190") + "A little lamp light on the brick. The museum interior is closed.",
            "independent": (
                "Kors\u00f8r Museum describes the fortress tower as about 23 to 25 m, roughly 9 by 9 m in plan, with a saddle roof, one of the two surviving medieval fortress towers in Denmark together with the Goose Tower. "
                "The grounds, bastions and moat are the public exterior. The museum's 2026 hours close the interior on a weekday night, and after 18 October until Easter. "
                "Kors\u00f8r Harbour, including the Great Belt bridge, is already DK-01-104. This frame leaves the bridge out."
            ),
            "ip": "No museum wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Square saddle-roof tower, bastions, moat, empty grounds, overcast night. No suspension bridge.",
            "swap": (
                "Swapped from Kors\u00f8r Harbour and the Storeb\u00e6lt view. That harbour, with the bridge in the distance, is already DK-01-104, Kors\u00f8r Harbour, Kors\u00f8r. "
                "The caption is Kors\u00f8r Fortress. City remains Kors\u00f8r."
            ),
        },
        {
            "entry_id": "DK-01-191",
            "region": "Zealand",
            "city": "Sk\u00e6lsk\u00f8r",
            "caption": "Sk\u00e6lsk\u00f8r Harbour, Sk\u00e6lsk\u00f8r",
            **p,
            "composition": "Boats in a narrow inlet and low town houses \u00b7 AI-generated artistic interpretation",
            "description": (
                "Sk\u00e6lsk\u00f8r harbour is a narrow inlet with moored boats, low houses, and a plain brick warehouse. "
                f"The quay is empty. The night is {p['word'].lower()}, about {p['temp']}\u00b0C. "
                "No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Sk\u00e6lsk\u00f8r harbour at night, boats in a narrow inlet",
            "viewpoint": "The public quay at Sk\u00e6lsk\u00f8r Lystb\u00e5dehavn. Approximate researched point 55.25222, 11.28766, not a surveyed camera. Nominatim places the marina in Sk\u00e6lsk\u00f8r, postal 4230.",
            "refs": [
                "https://en.wikipedia.org/wiki/Sk%C3%A6lsk%C3%B8r",
                "https://da.wikipedia.org/wiki/Sk%C3%A6lsk%C3%B8r_Nor",
            ],
            "anchors": [
                "A narrow inlet with moored boats.",
                "Low houses and a brick warehouse.",
                "Town roofs behind the quay. No readable name.",
            ],
            "solar": clock("DK-01-191") + "Quay lamps. No shop name.",
            "independent": (
                "Sk\u00e6lsk\u00f8r sits on Sk\u00e6lsk\u00f8r Nor, a narrow inlet. Nominatim places Sk\u00e6lsk\u00f8r Lystb\u00e5dehavn on Kajgade in Sk\u00e6lsk\u00f8r, postal 4230. "
                "The English town article and the Danish article on the nor are the sources for the place. The frame is the harbour, not a church close-up."
            ),
            "ip": "No readable boat name and no shop sign. Internal review only, not a legal certification.",
            "visual": "Pass. Narrow inlet, boats, low houses, brick warehouse, overcast night. No logo.",
            "swap": "No site swap. City is Sk\u00e6lsk\u00f8r.",
        },
        {
            "entry_id": "DK-01-192",
            "region": "Zealand",
            "city": "Faxe Ladeplads",
            "caption": "Faxe Ladeplads Harbour, Faxe Ladeplads",
            **q,
            "composition": "A marina in front of a pale chalk pier \u00b7 AI-generated artistic interpretation",
            "description": (
                "Faxe Ladeplads harbour is a marina of boats and a concrete mole, with a pale chalk-loading pier and white limestone piles behind it. "
                f"The quay is empty. The night is {q['word'].lower()}, about {q['temp']}\u00b0C. "
                "No company name is readable on the chalk works."
            ),
            "alt_text": "AI-generated artistic interpretation of Faxe Ladeplads harbour at night, a marina and a pale chalk pier",
            "viewpoint": "The public marina at Faxe Ladeplads, in the lee of the chalk shipping harbour. Approximate researched point 55.21343, 12.15997, not a surveyed camera. Nominatim places the marina in Faxe Ladeplads, postal 4654.",
            "refs": [
                "https://havnelods.dk/havne/faxe-ladeplads-lystbaadehavn",
                "https://en.wikipedia.org/wiki/Faxe_Ladeplads",
            ],
            "anchors": [
                "Pleasure boats and a concrete mole.",
                "A pale chalk-loading pier and white limestone behind.",
                "Dark sea. No readable company name.",
            ],
            "solar": clock("DK-01-192") + "Harbour lamps. No lit wordmark.",
            "independent": (
                "Havnelods describes Faxe Ladeplads Lystb\u00e5dehavn as a combined fishing and pleasure harbour lying in the lee of the Faxe chalk-pit shipping harbour. "
                "Nominatim places it in Faxe Ladeplads, postal 4654, which is the harbour town, not inland Faxe. "
                "The chalk pier is the landmark. No company name is readable."
            ),
            "ip": "No chalk-works wordmark and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, pale chalk pier, white limestone, overcast night. No readable company name.",
            "swap": "No site swap. City is Faxe Ladeplads, the harbour town, not inland Faxe.",
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
    if len(all_scenes) != 192:
        raise SystemExit(f"expected 192 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 193)]
    if ids != expected:
        raise SystemExit(f"id sequence {ids[:3]} ... {ids[-3:]}")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-177-192.txt"
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

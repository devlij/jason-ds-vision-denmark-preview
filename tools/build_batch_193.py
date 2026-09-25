#!/usr/bin/env python3
"""Bake DK-01-193 through DK-01-208 and rebuild the gallery from every manifest."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.parse
import urllib.request
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

COORDS = {
    "DK-01-193": (55.05811, 10.63984),
    "DK-01-194": (55.10616, 10.17417),
    "DK-01-195": (55.26926, 9.89400),
    "DK-01-196": (55.50522, 9.68970),
    "DK-01-197": (55.31424, 10.78887),
    "DK-01-198": (55.44335, 10.61688),
    "DK-01-199": (55.41178, 10.38370),
    "DK-01-200": (54.94205, 10.25632),
    "DK-01-201": (54.89353, 10.41027),
    "DK-01-202": (55.02354, 10.61024),
    "DK-01-203": (54.92568, 9.59475),
    "DK-01-204": (55.03961, 9.41413),
    "DK-01-205": (55.24932, 9.48072),
    "DK-01-206": (55.49520, 9.49966),
    "DK-01-207": (56.27459, 10.46680),
    "DK-01-208": (55.56104, 9.75763),
}

GEN_BUCKET = {
    "DK-01-193": "partly",
    "DK-01-194": "partly",
    "DK-01-195": "clear",
    "DK-01-196": "clear",
    "DK-01-197": "overcast",
    "DK-01-198": "overcast",
    "DK-01-199": "partly",
    "DK-01-200": "partly",
    "DK-01-201": "overcast",
    "DK-01-202": "overcast",
    "DK-01-203": "mainly",
    "DK-01-204": "mainly",
    "DK-01-205": "clear",
    "DK-01-206": "clear",
    "DK-01-207": "mainly",
    "DK-01-208": "clear",
}

# Depicted from the 04:14 Europe/Copenhagen retrieval, valid 04:00
# (Haderslev Damparken valid 04:15). Kept if a later hour changes the sky bucket.
_BASE = {
    "is_day": 0,
    "valid": "2026-09-25T04:00",
    "retrieved_stamp": "25 September 2026 04:14",
    "offset": 7200,
    "precip": 0.0,
}
SNAPSHOT = {
    "DK-01-193": {**_BASE, "temp": 11.0, "cloud": 78, "wind": 13.3, "code": 2, "word": "Partly cloudy", "sunset_yesterday": "2026-09-24T19:11", "sunrise_today": "2026-09-25T07:08"},
    "DK-01-194": {**_BASE, "temp": 12.1, "cloud": 50, "wind": 16.9, "code": 2, "word": "Partly cloudy", "sunset_yesterday": "2026-09-24T19:13", "sunrise_today": "2026-09-25T07:10"},
    "DK-01-195": {**_BASE, "temp": 12.0, "cloud": 16, "wind": 16.6, "code": 0, "word": "Clear", "sunset_yesterday": "2026-09-24T19:14", "sunrise_today": "2026-09-25T07:11"},
    "DK-01-196": {**_BASE, "temp": 10.8, "cloud": 6, "wind": 11.9, "code": 0, "word": "Clear", "sunset_yesterday": "2026-09-24T19:15", "sunrise_today": "2026-09-25T07:12"},
    "DK-01-197": {**_BASE, "temp": 10.9, "cloud": 83, "wind": 16.6, "code": 3, "word": "Overcast", "sunset_yesterday": "2026-09-24T19:10", "sunrise_today": "2026-09-25T07:07"},
    "DK-01-198": {**_BASE, "temp": 11.5, "cloud": 82, "wind": 13.0, "code": 3, "word": "Overcast", "sunset_yesterday": "2026-09-24T19:11", "sunrise_today": "2026-09-25T07:08"},
    "DK-01-199": {**_BASE, "temp": 12.0, "cloud": 56, "wind": 10.1, "code": 2, "word": "Partly cloudy", "sunset_yesterday": "2026-09-24T19:12", "sunrise_today": "2026-09-25T07:09"},
    "DK-01-200": {**_BASE, "temp": 12.9, "cloud": 64, "wind": 23.8, "code": 2, "word": "Partly cloudy", "sunset_yesterday": "2026-09-24T19:13", "sunrise_today": "2026-09-25T07:09"},
    "DK-01-201": {**_BASE, "temp": 12.5, "cloud": 90, "wind": 21.7, "code": 3, "word": "Overcast", "sunset_yesterday": "2026-09-24T19:12", "sunrise_today": "2026-09-25T07:09"},
    "DK-01-202": {**_BASE, "temp": 10.7, "cloud": 81, "wind": 13.0, "code": 3, "word": "Overcast", "sunset_yesterday": "2026-09-24T19:11", "sunrise_today": "2026-09-25T07:08"},
    "DK-01-203": {**_BASE, "temp": 10.5, "cloud": 35, "wind": 6.5, "code": 1, "word": "Mainly clear", "sunset_yesterday": "2026-09-24T19:15", "sunrise_today": "2026-09-25T07:12"},
    "DK-01-204": {**_BASE, "temp": 9.9, "cloud": 28, "wind": 6.8, "code": 1, "word": "Mainly clear", "sunset_yesterday": "2026-09-24T19:16", "sunrise_today": "2026-09-25T07:13"},
    "DK-01-205": {**_BASE, "temp": 9.9, "cloud": 12, "wind": 6.8, "code": 0, "word": "Clear", "valid": "2026-09-25T04:15", "sunset_yesterday": "2026-09-24T19:16", "sunrise_today": "2026-09-25T07:12"},
    "DK-01-206": {**_BASE, "temp": 10.0, "cloud": 7, "wind": 9.4, "code": 0, "word": "Clear", "sunset_yesterday": "2026-09-24T19:16", "sunrise_today": "2026-09-25T07:12"},
    "DK-01-207": {**_BASE, "temp": 11.5, "cloud": 27, "wind": 14.0, "code": 1, "word": "Mainly clear", "sunset_yesterday": "2026-09-24T19:12", "sunrise_today": "2026-09-25T07:09"},
    "DK-01-208": {**_BASE, "temp": 10.9, "cloud": 3, "wind": 13.0, "code": 0, "word": "Clear", "sunset_yesterday": "2026-09-24T19:14", "sunrise_today": "2026-09-25T07:11"},
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
    for n in range(193, 209):
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

    def light(row: dict) -> str:
        if row["cloud"] >= 80:
            return "The cloud deck hides the moon, and a few lamps carry the light."
        if row["cloud"] >= 45:
            return "Broken cloud hides much of the moon."
        return "Moonlight reaches the ground under a thin cloud cover."

    rows = {entry: pack(entry) for entry in COORDS}

    def R(entry: str) -> dict:
        return rows[entry]

    a = R("DK-01-193")
    b = R("DK-01-194")
    c = R("DK-01-195")
    d = R("DK-01-196")
    e = R("DK-01-197")
    f = R("DK-01-198")
    g = R("DK-01-199")
    h = R("DK-01-200")
    i = R("DK-01-201")
    j = R("DK-01-202")
    k = R("DK-01-203")
    m = R("DK-01-204")
    n = R("DK-01-205")
    o = R("DK-01-206")
    p = R("DK-01-207")
    q = R("DK-01-208")

    return [
        {
            "entry_id": "DK-01-193",
            "region": "Funen",
            "city": "Svendborg",
            "caption": "Christiansminde, Svendborg",
            **a,
            "composition": "A wooden bathing pier and a wooded sound shore \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the shore path, Christiansminde is a wooden bathing pier with railings and small plain changing huts, with dark sound water and a beech slope still in leaf. "
                f"The pier is empty. The night is {a['word'].lower()}, about {a['temp']}\u00b0C. "
                f"{light(a)} The harbour warehouses and the sound bridge are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Christiansminde in Svendborg at night, a wooden pier and a wooded shore",
            "viewpoint": "The public shore at Christiansminde Badestrand, east of Svendborg harbour. Approximate researched point 55.05811, 10.63984, not a surveyed camera. Nominatim places the beach in Christiansminde, Svendborg.",
            "refs": [
                "https://www.visitsvendborg.dk/svendborg/svendborg/christiansminde-strand-gdk742975",
                "https://byensvendborg.dk/guide/christiansminde",
            ],
            "anchors": [
                "A wooden bathing pier with railings and a ramp.",
                "Small plain changing huts, with no lettering.",
                "A beech slope and dark sound water. No harbour bridge.",
            ],
            "solar": clock("DK-01-193") + "A few path lamps. No swimmers.",
            "independent": (
                "VisitSvendborg describes Christiansminde Strand as a sand beach on Svendborg Sound, with a bathing pier, east of the town centre, looking toward Thur\u00f8 and Troense. "
                "The old turreted bathing house was demolished in 1993, so it is not shown. "
                "Svendborg Harbour and the sound bridge are already DK-01-037. Vor Frue is DK-01-113. Late September night is outside ordinary bathing use, so the pier is empty."
            ),
            "ip": "No caf\u00e9 logo and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Wooden pier, plain huts, wooded slope, dark sound, partly cloudy night. No harbour bridge and no readable name.",
            "swap": (
                "Swapped from Svendborg Harbour. That quay and the sound bridge are already DK-01-037, Svendborg Harbour, Svendborg. "
                "Vor Frue on Torvet is DK-01-113. The caption is Christiansminde. City remains Svendborg."
            ),
        },
        {
            "entry_id": "DK-01-194",
            "region": "Funen",
            "city": "Horne",
            "caption": "Horne Church, Horne",
            **b,
            "composition": "A white round nave, a red-tiled choir, and a Renaissance tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Horne Church shows a whitewashed round nave under a steep pointed lead roof, a long choir with a red tile roof, and a square west tower with curved Renaissance gables and a shingled spire. "
                f"The churchyard is empty. The night is {b['word'].lower()}, about {b['temp']}\u00b0C. "
                f"{light(b)} This is Funen's round church, not a harbour."
            ),
            "alt_text": "AI-generated artistic interpretation of Horne Church at night, a white round nave and a Renaissance tower",
            "viewpoint": "The public churchyard at Horne Kirke. Approximate researched point 55.10616, 10.17417, not a surveyed camera. Nominatim places the church in Horne, postal 5642.",
            "refs": [
                "https://en.wikipedia.org/wiki/Horne_Church",
                "https://lex.dk/Horne_Kirke_-_Faaborg-Midtfyn_Kommune",
            ],
            "anchors": [
                "A whitewashed round nave with a steep pointed lead roof.",
                "A long choir under red tile, and a square west tower.",
                "Curved Renaissance gables and a shingled spire. No harbour.",
            ],
            "solar": clock("DK-01-194") + "A couple of churchyard lamps. No readable plaque.",
            "independent": (
                "Horne Church is the only round church on Funen. Lex describes a Romanesque round nave about 17 m across, later a long choir, a north porch, a west extension, and a tower, all whitewashed, with a lead roof on the round nave and red tile on the other ranges. "
                "The English article describes the pointed lead roof and the curved Renaissance gables of the west tower. The address on the Danish article is S\u00f8ren Lundsvej 42, Horne, 5600 Faaborg; Nominatim gives postal 5642 and the village Horne. "
                "Faaborg Harbour is already DK-01-039 and Klokket\u00e5rnet is DK-01-116. \u00d8sterlars on Bornholm is a different round church, DK-01-067."
            ),
            "ip": "No readable plaque and no film title. Internal review only, not a legal certification.",
            "visual": "Pass. White round nave, pointed lead roof, red-tiled choir, curved gables, empty churchyard, partly cloudy night. No harbour.",
            "swap": (
                "Swapped from Faaborg Harbour. That quay is already DK-01-039, Faaborg Harbour, Faaborg, and the freestanding bell tower is DK-01-116. "
                "The caption is Horne Church. City is Horne, the village. The postal town on one address line is Faaborg."
            ),
        },
        {
            "entry_id": "DK-01-195",
            "region": "Funen",
            "city": "Assens",
            "caption": "Vor Frue, Assens",
            **c,
            "composition": "A red-brick basilica and an octagonal copper spire \u00b7 AI-generated artistic interpretation",
            "description": (
                "Vor Frue in Assens is a red-brick Gothic basilica in bare brick, with dark slate roofs and a west tower that is square below and octagonal above, finished with a copper spire. "
                f"The square is empty. The night is {c['word'].lower()}, about {c['temp']}\u00b0C. "
                f"{light(c)} The harbour basin is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Vor Frue in Assens at night, a red-brick church with an octagonal tower",
            "viewpoint": "The public square beside Vor Frue Kirke, Lille Kirkestr\u00e6de. Approximate researched point 55.26926, 9.89400, not a surveyed camera. Nominatim places the church in Assens, postal 5610.",
            "refs": [
                "https://lex.dk/Vor_Frue_Kirke_-_Assens_Kommune",
                "https://www.assenskirke.dk/kirker/vor-frue-kirke/kirkens-historie",
            ],
            "anchors": [
                "Red brick in blank mur, not whitewash, and dark slate roofs.",
                "A west tower, square below and octagonal above.",
                "A copper spire. No harbour and no boats.",
            ],
            "solar": clock("DK-01-195") + "A few street lamps. No shop name.",
            "independent": (
                "Lex describes the late Gothic basilica, the west tower built in two stages with an octagonal upper part from about 1470, and slate roofs on bare brick. "
                "The parish history page calls it Funen's second-largest church and gives the octagonal tower a height of 48 m, finished in its present Gothic form in 1488. "
                "The National Museum notes the copper plates on the medieval spire. Assens Harbour is already DK-01-093. Vor Frue in Svendborg, DK-01-113, is a different church with a lantern spire."
            ),
            "ip": "No readable inscription treated as a sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, slate, octagonal upper tower, copper spire, empty square, clear night. No harbour.",
            "swap": (
                "Swapped from Assens Harbour. That mole and basin are already DK-01-093, Assens Harbour, Assens. "
                "The caption is Vor Frue. City remains Assens."
            ),
        },
        {
            "entry_id": "DK-01-196",
            "region": "Funen",
            "city": "Middelfart",
            "caption": "Hindsgavl Castle, Middelfart",
            **d,
            "composition": "A red-brick neoclassical manor and the strait beyond the park \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the garden side, Hindsgavl is a two-storey red-brick manor with a high hipped tile roof, sandstone-coloured pilasters, and a triangular pediment, with park trees and a glimpse of the Little Belt. "
                f"The lawn is empty. The night is {d['word'].lower()}, about {d['temp']}\u00b0C. "
                f"{light(d)} Neither Little Belt bridge is in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Hindsgavl Castle at night, a red-brick manor above the Little Belt",
            "viewpoint": "The public garden side of Hindsgavl Slot, Hindsgavl All\u00e9 7. Approximate researched point 55.50522, 9.68970, not a surveyed camera. Nominatim places the manor in Middelfart, postal 5500.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hindsgavl_Castle",
                "https://www.kulturarv.dk/fbb/sagvis.pub?sag=11505037",
            ],
            "anchors": [
                "A two-storey red-brick manor, not a white palace.",
                "A high hipped red-tile roof, pilasters, and a triangular pediment.",
                "Park trees and a glimpse of the strait. No bridge.",
            ],
            "solar": clock("DK-01-196") + "A few warm windows. No facade floodlight show and no bridge lights.",
            "independent": (
                "The heritage listing describes Hindsgavl on the peninsula west of Middelfart: a two-storey red-brick main house under a high hipped tile roof, with sandstone-coloured pilasters and a pediment, built in 1784. "
                "The English article places it at Middelfart on Funen. The address used by the house is Hindsgavl All\u00e9 7, 5500 Middelfart. "
                "The Little Belt Bridges are already DK-01-092, so this frame leaves both bridges out. The medieval bank is a low earthwork and is not the house."
            ),
            "ip": "No hotel wordmark and no crest treated as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, hipped roof, pediment, park, strait, clear night. No bridge.",
            "swap": (
                "Swapped from a Middelfart harbour and Little Belt bridge view. The two bridges are already DK-01-092, Little Belt Bridges, Middelfart. "
                "The caption is Hindsgavl Castle. City remains Middelfart."
            ),
        },
        {
            "entry_id": "DK-01-197",
            "region": "Funen",
            "city": "Nyborg",
            "caption": "Landporten, Nyborg",
            **e,
            "composition": "A yellow gatehouse in the grass ramparts \u00b7 AI-generated artistic interpretation",
            "description": (
                "Landporten is a long yellow-washed gatehouse with one large brick arch, set between grass ramparts, with dark moat water and a linden path. "
                f"The path is empty. The night is {e['word'].lower()}, about {e['temp']}\u00b0C. "
                f"{light(e)} The castle and the marina are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Landporten in Nyborg at night, a yellow gatehouse in the ramparts",
            "viewpoint": "The public path at Landporten, Lindealleen 1. Approximate researched point 55.31424, 10.78887, not a surveyed camera. Nominatim places the gate in Nyborg, postal 5800.",
            "refs": [
                "https://www.visitnyborg.dk/nyborg/planlaeg-din-tur/landporten-i-nyborg-gdk807063",
                "https://da.wikipedia.org/wiki/Landporten",
            ],
            "anchors": [
                "A long yellow gatehouse with one large arch.",
                "Grass ramparts and dark moat water.",
                "A tree-lined path. No castle and no marina.",
            ],
            "solar": clock("DK-01-197") + "A few path lamps. No readable sign.",
            "independent": (
                "VisitNyborg says Landporten took its present form in 1666 and that the vault, about 40 m, is Denmark's longest barrel vault, with the upper storey from 1750. The address is Lindealleen 1, 5800 Nyborg. "
                "The Danish article is the second source for the same gate. "
                "Nyborg Castle, including the conservation tents, is already DK-01-040. Nyborg Harbour is DK-01-111. A Great Belt pylon view would repeat Kors\u00f8r Harbour, DK-01-104, so the bridge is not the subject."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow gatehouse, one arch, grass ramparts, moat, overcast night. No castle and no marina.",
            "swap": (
                "Swapped from Nyborg Harbour. That marina is already DK-01-111, Nyborg Harbour, Nyborg, and the castle is DK-01-040. "
                "The caption is Landporten. City remains Nyborg."
            ),
        },
        {
            "entry_id": "DK-01-198",
            "region": "Funen",
            "city": "Ladby",
            "caption": "Ladby Ship, Ladby",
            **f,
            "composition": "A grass burial mound above a dark fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                "The Ladby ship site at night is a low grass mound with a plain doorway, a gravel path, and the dark fjord below. "
                f"The path is empty and the museum is closed. The night is {f['word'].lower()}, about {f['temp']}\u00b0C. "
                f"{light(f)} No reconstructed ship is shown on the water."
            ),
            "alt_text": "AI-generated artistic interpretation of the Ladby ship mound at night, grass above a dark fjord",
            "viewpoint": "The public path outside the rebuilt burial mound at Vikingemuseet Ladby, Vikingevej 123. Approximate researched point 55.44335, 10.61688, not a surveyed camera. The postal address is 5300 Kerteminde. The village is Ladby.",
            "refs": [
                "https://www.visitkerteminde.com/kerteminde/plan-your-holiday/vikingmuseum-ladby-gdk613576",
                "https://vikingemuseetladby.dk/practical-information/?lang=en",
            ],
            "anchors": [
                "A low grass-covered mound with a plain entrance.",
                "A gravel path and an empty bench.",
                "Dark fjord water below. No ship and no dragon head.",
            ],
            "solar": clock("DK-01-198") + "One path lamp at most. The interior is closed.",
            "independent": (
                "VisitKerteminde says the Ladby ship is shown inside a rebuilt burial mound on the spot where it was found in 1935, on the south side of Kerteminde Fjord. The address is Vikingevej 123, 5300 Kerteminde. "
                "The museum practical page describes the outdoor path between the building and the mound. "
                "The reconstructed ship Ladbydragen is a summer-season boat in the fjord. This is a late September night, so that boat is not asserted and is not in the frame. Kerteminde Harbour is already DK-01-110. The caption city is Ladby, the village, not the town of Kerteminde."
            ),
            "ip": "No museum wordmark and no ship name. Internal review only, not a legal certification.",
            "visual": "Pass. Grass mound, plain door, fjord, empty path, overcast night. No Viking ship on the water.",
            "swap": (
                "Swapped from Kerteminde Harbour. That narrow harbour of coloured houses is already DK-01-110, Kerteminde Harbour, Kerteminde. "
                "The caption is Ladby Ship. City is Ladby. The postal town on the museum address is Kerteminde."
            ),
        },
        {
            "entry_id": "DK-01-199",
            "region": "Funen",
            "city": "Odense",
            "caption": "Odense Canal, Odense",
            **g,
            "composition": "A narrow canal, moored boats, and brick quay buildings \u00b7 AI-generated artistic interpretation",
            "description": (
                "From Havnegade, the Odense Canal is a narrow dark channel with a few small boats, brick quay buildings, and a low bridge farther along. "
                f"The quay is empty. The night is {g['word'].lower()}, about {g['temp']}\u00b0C. "
                f"{light(g)} The cathedral, the ochre lane, and the park lawns are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of the Odense canal at night, boats and brick warehouses",
            "viewpoint": "The public quay on Havnegade along the inner canal. Approximate researched point 55.41178, 10.38370, not a surveyed camera. Nominatim places Havnegade in Odense, postal 5000.",
            "refs": [
                "https://da.wikipedia.org/wiki/Odense_Kanal",
                "https://en.wikipedia.org/wiki/Port_of_Odense",
            ],
            "anchors": [
                "A narrow canal with a few small boats.",
                "Brick quay buildings.",
                "A low bridge farther along. No cathedral and no park lawn.",
            ],
            "solar": clock("DK-01-199") + "Quay lamps. No readable boat name.",
            "independent": (
                "The Danish article describes Odense Kanal as the canal from Odense Fjord into the city. The English port article is the second source for the same waterway. "
                "This frame is the inner canal at Havnegade, in central Odense. The commercial terminal at Lind\u00f8, near Munkebo, is not this view. "
                "H.C. Andersen Quarter is DK-01-008, Odense Cathedral is DK-01-036, and Munke Mose is DK-01-112. No company name is readable."
            ),
            "ip": "No readable warehouse name and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Narrow canal, small boats, brick buildings, low bridge, partly cloudy night. No cathedral and no park.",
            "swap": (
                "No site swap. The canal is distinct from the H.C. Andersen quarter, DK-01-008, Odense Cathedral, DK-01-036, and Munke Mose, DK-01-112. "
                "City remains Odense."
            ),
        },
        {
            "entry_id": "DK-01-200",
            "region": "Funen",
            "city": "S\u00f8by",
            "caption": "S\u00f8by Harbour, S\u00f8by",
            **h,
            "composition": "A stone mole, fishing boats, and low red roofs \u00b7 AI-generated artistic interpretation",
            "description": (
                "S\u00f8by harbour is a stone mole with a few small fishing boats and low red-tiled houses, opening onto a wind-chopped sea. "
                f"The quay is empty. The night is {h['word'].lower()}, about {h['temp']}\u00b0C. "
                f"{light(h)} No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of S\u00f8by harbour at night, a mole and low red roofs on \u00c6r\u00f8",
            "viewpoint": "The public quay at S\u00f8by Havn on north \u00c6r\u00f8. Approximate researched point 54.94205, 10.25632, not a surveyed camera. Nominatim places S\u00f8by Havn in S\u00f8by, postal 5985.",
            "refs": [
                "https://da.wikipedia.org/wiki/S%C3%B8by_(%C3%86r%C3%B8)",
                "https://en.wikipedia.org/wiki/%C3%86r%C3%B8",
            ],
            "anchors": [
                "A stone mole and a few small fishing boats.",
                "Low red-tiled houses.",
                "Wind-chopped dark sea. No ferry funnel mark.",
            ],
            "solar": clock("DK-01-200") + "Quay lamps. Wind chop. No lit wordmark.",
            "independent": (
                "S\u00f8by is the port village at the north end of \u00c6r\u00f8. The Danish village article and the English island article are the sources. Nominatim places S\u00f8by Havn in S\u00f8by, postal 5985. "
                "The ferry berth is part of the harbour, but no ferry name or funnel mark is in the frame. "
                "Bogense Harbour is already DK-01-117. Marstal Harbour, on the east of the same island, is DK-01-114."
            ),
            "ip": "No ferry wordmark and no readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, small boats, red roofs, choppy water, partly cloudy night. No ferry brand.",
            "swap": (
                "Swapped from Bogense Harbour. That inner basin is already DK-01-117, Bogense Harbour, Bogense. "
                "The caption is S\u00f8by Harbour. City is S\u00f8by."
            ),
        },
        {
            "entry_id": "DK-01-201",
            "region": "Funen",
            "city": "\u00c6r\u00f8sk\u00f8bing",
            "caption": "\u00c6r\u00f8sk\u00f8bing Harbour, \u00c6r\u00f8sk\u00f8bing",
            **i,
            "composition": "Coloured houses along a small harbour basin \u00b7 AI-generated artistic interpretation",
            "description": (
                "\u00c6r\u00f8sk\u00f8bing harbour is a small basin in front of a cobbled quay, with tiny houses in yellow, pink, and white under red tile roofs and a few wooden boats. "
                f"The quay is empty. The night is {i['word'].lower()}, about {i['temp']}\u00b0C. "
                f"{light(i)} This is the waterfront, not an inland lane."
            ),
            "alt_text": "AI-generated artistic interpretation of \u00c6r\u00f8sk\u00f8bing harbour at night, coloured houses along the basin",
            "viewpoint": "The public quay at \u00c6r\u00f8sk\u00f8bing Lystb\u00e5dehavn. Approximate researched point 54.89353, 10.41027, not a surveyed camera. Nominatim places the marina in \u00c6r\u00f8sk\u00f8bing, postal 5970.",
            "refs": [
                "https://en.wikipedia.org/wiki/%C3%86r%C3%B8sk%C3%B8bing",
                "https://da.wikipedia.org/wiki/%C3%86r%C3%B8sk%C3%B8bing",
            ],
            "anchors": [
                "A small harbour basin in the foreground.",
                "Tiny houses in several colours under red tile roofs.",
                "A cobbled quay and a few wooden boats. No inland lane as the subject.",
            ],
            "solar": clock("DK-01-201") + "Quay lamps. No readable house name.",
            "independent": (
                "\u00c6r\u00f8sk\u00f8bing is the old town on \u00c6r\u00f8, with small painted houses. Nominatim places \u00c6r\u00f8sk\u00f8bing Lystb\u00e5dehavn on Strandvejen in \u00c6r\u00f8sk\u00f8bing, postal 5970. "
                "The English and Danish town articles are the sources for the place. "
                "DK-01-038 is the cobbled inland lane and has no harbour water. This frame puts the basin in front of the houses."
            ),
            "ip": "No readable house name and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, cobbled quay, coloured houses, small boats, overcast night. Not a second inland lane.",
            "swap": (
                "No site swap. The harbour is distinct from \u00c6r\u00f8sk\u00f8bing, \u00c6r\u00f8sk\u00f8bing, DK-01-038, which is the cobbled lane. "
                "City remains \u00c6r\u00f8sk\u00f8bing."
            ),
        },
        {
            "entry_id": "DK-01-202",
            "region": "Funen",
            "city": "Bregninge",
            "caption": "Bregninge Church, Bregninge",
            **j,
            "composition": "A red-brick hill church and a lantern spire \u00b7 AI-generated artistic interpretation",
            "description": (
                "Bregninge Church stands on the rounded hill: red brick, dark slate roofs, and a west tower with a low octagonal roof and a tall lantern spire. "
                f"The lane is empty. The night is {j['word'].lower()}, about {j['temp']}\u00b0C. "
                f"{light(j)} The sea is not the close subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Bregninge Church at night, a red-brick tower and lantern on a hill",
            "viewpoint": "The public lane by Bregninge Kirke on T\u00e5singe. Approximate researched point 55.02354, 10.61024, not a surveyed camera. Nominatim places the church in Bregninge, postal 5700.",
            "refs": [
                "https://lex.dk/Bregninge_Kirke_-_T%C3%A5singe",
                "https://www.visitsvendborg.dk/svendborg/svendborg/bregninge-kirkebakke-gdk1137682",
            ],
            "anchors": [
                "Red brick walls, not whitewash, and dark slate roofs.",
                "A west tower with a low octagonal roof and a tall lantern.",
                "A rounded grassy hill. No harbour.",
            ],
            "solar": clock("DK-01-202") + "A couple of lamps. The tower is not a floodlit show.",
            "independent": (
                "Lex says the church on T\u00e5singe's highest point has stood in visible brick with slate roofs since the 1882\u201383 restoration, and that the tower has a low octagonal roof with a tall lantern. "
                "VisitSvendborg places Bregninge Kirkebakke at 74 m, with the church on top, address context Kirkebakken, postal 5700 Svendborg. Nominatim names the village Bregninge. "
                "Marstal Harbour is already DK-01-114. Valdemars Slot at Troense is DK-01-155. This is the hill church, not the palace."
            ),
            "ip": "No museum sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, slate, lantern on an octagonal tower roof, hill, overcast night. No harbour.",
            "swap": (
                "Swapped from Marstal Harbour. That quay, pier, and lime kiln are already DK-01-114, Marstal Harbour, Marstal. "
                "The caption is Bregninge Church. City is Bregninge, the village on T\u00e5singe. The postal town is Svendborg."
            ),
        },
        {
            "entry_id": "DK-01-203",
            "region": "South Jutland",
            "city": "Gr\u00e5sten",
            "caption": "Gr\u00e5sten Palace, Gr\u00e5sten",
            **k,
            "composition": "A long white palace wing and a dark lawn \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the lawn, Gr\u00e5sten Palace is a long white wing with a dark roof and tall doors opening onto grass and a gravel path. "
                f"The grounds are empty. The night is {k['word'].lower()}, about {k['temp']}\u00b0C. "
                f"{light(k)} No flag is shown, and the yellow town house is not this building."
            ),
            "alt_text": "AI-generated artistic interpretation of Gr\u00e5sten Palace at night, a white wing above a dark lawn",
            "viewpoint": "The public lawn approach to Gr\u00e5sten Slot. Approximate researched point 54.92568, 9.59475, not a surveyed camera. Nominatim places the palace in Gr\u00e5sten, postal 6300.",
            "refs": [
                "https://en.wikipedia.org/wiki/Gr%C3%A5sten_Palace",
                "https://www.visitsonderjylland.com/tourist/plan-your-holiday/graasten-palace-gdk611078",
            ],
            "anchors": [
                "A long white palace wing, not a yellow house.",
                "A dark roof and tall doors onto a lawn.",
                "A gravel path. No flag and no guards.",
            ],
            "solar": clock("DK-01-203") + "A few warm windows. No royal-standard lighting was verified, so none is shown.",
            "independent": (
                "The English article describes Gr\u00e5sten Palace as a white main house with doors opening onto lawns. VisitS\u00f8nderjylland gives the address Gr\u00e5sten Slot 1A, 6300 Gr\u00e5sten, and says the gardens close when the royal family is in residence. "
                "Whether anyone was in residence on this September night was not verified, so the frame shows an empty exterior and no flag. The separate yellow house in the town is not the palace. "
                "S\u00f8nderborg Castle standing in Als Sound is already DK-01-041, so a S\u00f8nderborg harbour frame would repeat that waterfront. Dybb\u00f8l Mill is DK-01-042."
            ),
            "ip": "No royal standard and no crest treated as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. White wing, dark roof, lawn, gravel, mainly clear night. No flag and no yellow facade.",
            "swap": (
                "Swapped from S\u00f8nderborg Harbour. The castle-in-the-sound view is already DK-01-041, S\u00f8nderborg Castle, S\u00f8nderborg, and Dybb\u00f8l Mill is DK-01-042. "
                "The caption is Gr\u00e5sten Palace. City is Gr\u00e5sten."
            ),
        },
        {
            "entry_id": "DK-01-204",
            "region": "South Jutland",
            "city": "Aabenraa",
            "caption": "Brundlund Castle, Aabenraa",
            **m,
            "composition": "A white moated castle with two octagonal towers \u00b7 AI-generated artistic interpretation",
            "description": (
                "Across the moat, Brundlund is a whitewashed three-storey block with two octagonal corner towers, low copper tower roofs, red tile, dark blue windows, and a columned loggia. "
                f"The dam is empty. The night is {m['word'].lower()}, about {m['temp']}\u00b0C. "
                f"{light(m)} The fjord quay is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Brundlund Castle at night, a white moated castle in Aabenraa",
            "viewpoint": "The public side of the moat at Brundlund Slot. Approximate researched point 55.03961, 9.41413, not a surveyed camera. Nominatim places the castle in Aabenraa, postal 6200.",
            "refs": [
                "https://da.wikipedia.org/wiki/Brundlund_Slot",
                "https://trap.lex.dk/Brundlund_Slot,_Amtmandsboligen,_Aabenraa",
            ],
            "anchors": [
                "A whitewashed nearly square block on an island in a moat.",
                "Two large octagonal corner towers with low copper roofs.",
                "Red tile, dark blue windows, and a columned loggia. No fjord quay.",
            ],
            "solar": clock("DK-01-204") + "Moonlight on the white walls. No museum sign.",
            "independent": (
                "Trap Danmark describes Brundlund south of Aabenraa: a nearly square three-storey wing, two large octagonal corner towers, a smaller stair tower, a south loggia, whitewash, red tile roofs, and nearly flat copper roofs on the towers, with dark blue windows, standing in a moat. "
                "The Danish article is the second source for the same castle, now an art museum. The frame is the exterior only. No artwork is shown. "
                "Aabenraa Harbour is already DK-01-047. The city spelling in this gallery is Aabenraa."
            ),
            "ip": "No museum wordmark. Interior artworks are not depicted. Internal review only, not a legal certification.",
            "visual": "Pass. White walls, two octagonal towers, moat, red tile, mainly clear night. No harbour.",
            "swap": (
                "Swapped from Aabenraa Harbour. That fjord quay is already DK-01-047, Aabenraa Harbour, Aabenraa. "
                "The caption is Brundlund Castle. City remains Aabenraa."
            ),
        },
        {
            "entry_id": "DK-01-205",
            "region": "South Jutland",
            "city": "Haderslev",
            "caption": "Haderslev Dam, Haderslev",
            **n,
            "composition": "A long dark lake, reeds, and a shore path \u00b7 AI-generated artistic interpretation",
            "description": (
                "From Damparken, Haderslev Dam is a long dark lake with a reed edge and a shore path, and only small town roofs far along the water. "
                f"The path is empty. The night is {n['word'].lower()}, about {n['temp']}\u00b0C. "
                f"{light(n)} The towerless cathedral is not a close subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Haderslev Dam at night, a long lake and a shore path",
            "viewpoint": "The public park shore at Damparken, on Haderslev Dam. Approximate researched point 55.24932, 9.48072, not a surveyed camera. Nominatim places Damparken in Haderslev.",
            "refs": [
                "https://da.wikipedia.org/wiki/Haderslev_Dam",
                "https://en.wikipedia.org/wiki/Haderslev",
            ],
            "anchors": [
                "A long dark lake.",
                "Reeds and a shore path.",
                "Distant town roofs only. No close cathedral.",
            ],
            "solar": clock("DK-01-205") + "Little shore light. No floodlit church.",
            "independent": (
                "Haderslev Dam is the long lake on the south side of Haderslev. The Danish lake article and the English town article are the sources. Nominatim places Damparken in Haderslev, which is the park shore used here. "
                "Haderslev Cathedral, a brick church with no tower, is already the street close-up DK-01-046. From this shore the cathedral is not the subject."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Long lake, reeds, path, distant roofs, clear night. No close cathedral.",
            "swap": (
                "No site swap. The dam shore is distinct from Haderslev Cathedral, DK-01-046, which is the street view of the towerless church. "
                "City remains Haderslev."
            ),
        },
        {
            "entry_id": "DK-01-206",
            "region": "South Jutland",
            "city": "Kolding",
            "caption": "Kolding Fjord, Kolding",
            **o,
            "composition": "Marina masts and a wooded fjord shore \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the marina promenade, Kolding Fjord is dark water with sailboat masts at a plain quay and a low wooded shore opposite. "
                f"The promenade is empty. The night is {o['word'].lower()}, about {o['temp']}\u00b0C. "
                f"{light(o)} The castle and its timber tower are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Kolding Fjord at night, marina masts and a wooded shore",
            "viewpoint": "The public promenade at Kolding Marina Nord, Jens Holms Vej. Approximate researched point 55.49520, 9.49966, not a surveyed camera. Nominatim places the marina in Kolding, postal 6000.",
            "refs": [
                "https://en.wikipedia.org/wiki/Kolding_Fjord",
                "https://da.wikipedia.org/wiki/Kolding_Fjord",
            ],
            "anchors": [
                "Sailboat masts at a plain quay.",
                "Dark fjord water.",
                "A low wooded opposite shore. No castle and no timber tower.",
            ],
            "solar": clock("DK-01-206") + "A few marina lamps. No boat name.",
            "independent": (
                "Kolding Fjord is the inlet east of Kolding. The English and Danish articles describe that fjord. Nominatim places Kolding Marina Nord on Jens Holms Vej in Kolding, postal 6000, east of the town centre. "
                "Koldinghus, the brick castle and the modern timber tower, stands on the castle lake inland and is already DK-01-045. This frame is the fjord, and the castle is not in it."
            ),
            "ip": "No readable boat name and no marina logo. Internal review only, not a legal certification.",
            "visual": "Pass. Masts, quay, dark fjord, wooded shore, clear night. No castle.",
            "swap": (
                "No site swap. The fjord marina is distinct from Koldinghus, DK-01-045, which is the castle across the inland lake. "
                "City remains Kolding."
            ),
        },
        {
            "entry_id": "DK-01-207",
            "region": "Central Jutland",
            "city": "R\u00f8nde",
            "caption": "Kal\u00f8 Castle, R\u00f8nde",
            **p,
            "composition": "A roofless brick tower and a stone causeway \u00b7 AI-generated artistic interpretation",
            "description": (
                "Kal\u00f8 is a roofless medieval brick tower on a low islet, reached by a long stone causeway across dark bay water. "
                f"The causeway is empty. The night is {p['word'].lower()}, about {p['temp']}\u00b0C. "
                f"{light(p)} The tower is a ruin, with no intact roof."
            ),
            "alt_text": "AI-generated artistic interpretation of Kal\u00f8 Castle ruin at night, a brick tower and a causeway",
            "viewpoint": "The public causeway looking toward the ruin. Approximate researched point 56.27459, 10.46680, not a surveyed camera. Nominatim places Kal\u00f8 Slotsruin at R\u00f8nde, postal 8410.",
            "refs": [
                "https://en.wikipedia.org/wiki/Kal%C3%B8_Castle",
                "https://www.visitaarhus.com/aarhus-region/plan-your-trip/short-trip-kaloe-castle-ruin-gdk1112579",
            ],
            "anchors": [
                "A broken red-brick tower with no roof.",
                "A long low stone causeway.",
                "Dark bay water. No complete castle.",
            ],
            "solar": clock("DK-01-207") + "Moonlight on the brick. No visitors and no interior stair as the subject.",
            "independent": (
                "Wikipedia places Kal\u00f8 Castle ruin on an islet in Kal\u00f8 Vig, built about 1313 and linked to the mainland by a causeway of about 500 m. VisitAarhus describes the same ruin and the stone path. "
                "Nominatim places it at R\u00f8nde, postal 8410, in Region Midtjylland. A stair was added inside the tower in 2016; the exterior at night is still the ruined brick shell. "
                "Vejle Fjord, seen from the inner-harbour promenade, is already DK-01-119, so this card does not repeat that harbour."
            ),
            "ip": "No sign and no architect credit treated as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. Roofless brick tower, causeway, bay, mainly clear night. Not a complete castle.",
            "swap": (
                "Swapped from Vejle Harbour. That inner-harbour fjord view is already DK-01-119, Vejle Fjord, Vejle. "
                "The caption is Kal\u00f8 Castle. City is R\u00f8nde."
            ),
        },
        {
            "entry_id": "DK-01-208",
            "region": "South Jutland",
            "city": "Fredericia",
            "caption": "Fredericia Harbour, Fredericia",
            **q,
            "composition": "An inner harbour basin and low brick warehouses \u00b7 AI-generated artistic interpretation",
            "description": (
                "Fredericia's old inner harbour is a basin of moored boats and low brick warehouses on dark water. "
                f"The quay is empty. The night is {q['word'].lower()}, about {q['temp']}\u00b0C. "
                f"{light(q)} The rampart gate is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Fredericia harbour at night, boats and brick warehouses",
            "viewpoint": "The public quay at Gammel Havn. Approximate researched point 55.56104, 9.75763, not a surveyed camera. Nominatim places Gammel Havn in Fredericia, postal 7000.",
            "refs": [
                "https://da.wikipedia.org/wiki/Fredericia_Havn",
                "https://en.wikipedia.org/wiki/Fredericia",
            ],
            "anchors": [
                "A harbour basin with moored boats.",
                "Low brick warehouses.",
                "Dark water and quay lamps. No red gatehouse arch.",
            ],
            "solar": clock("DK-01-208") + "Quay lamps and moonlight. No readable name.",
            "independent": (
                "The Danish harbour article and the English town article describe Fredericia's harbour on the Little Belt. Nominatim places Gammel Havn in Fredericia, postal 7000, which is the old inner basin used here. "
                "Prinsens Port, the red-brick gate in the grass ramparts, is already DK-01-120. This frame leaves that gate out."
            ),
            "ip": "No readable boat name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, boats, brick warehouses, clear night. No rampart gate.",
            "swap": (
                "No site swap of the harbour. The rampart gate is already DK-01-120, Prinsens Port, Fredericia, so this frame is the old harbour and leaves the gate out. "
                "City remains Fredericia."
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
    raise SystemExit(
        "Refusing to run: this baker reused two Open-Meteo retrievals across DK-01-193–208. "
        "Per-scene fetches from 25 September 2026 14:32–14:33 Europe/Copenhagen are recorded in "
        "tools/wx-dk-01-193-208.json. Do not rebuild from the shared snapshot."
    )
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
    if len(all_scenes) != 208:
        raise SystemExit(f"expected 208 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 209)]
    if ids != expected:
        raise SystemExit(f"id sequence {ids[:3]} ... {ids[-3:]}")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-193-208.txt"
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

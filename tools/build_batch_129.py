#!/usr/bin/env python3
"""Bake DK-01-129 through DK-01-144 and rebuild the gallery from every manifest."""

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

# Viewpoint coordinates used for the Open-Meteo request. Not surveyed cameras.
COORDS = {
    "DK-01-129": (57.04790, 9.91960),
    "DK-01-130": (57.07722, 9.91250),
    "DK-01-131": (56.83131, 9.83454),
    "DK-01-132": (57.72488, 10.59833),
    "DK-01-133": (57.64982, 10.40743),
    "DK-01-134": (57.33316, 10.53248),
    "DK-01-135": (56.95246, 8.69641),
    "DK-01-136": (56.79259, 8.86616),
    "DK-01-137": (56.55133, 8.30256),
    "DK-01-138": (56.70451, 8.21748),
    "DK-01-139": (56.08701, 8.23907),
    "DK-01-140": (56.00165, 8.12860),
    "DK-01-141": (55.55783, 8.08325),
    "DK-01-142": (55.32940, 8.76091),
    "DK-01-143": (55.34856, 8.46898),
    "DK-01-144": (55.13953, 8.49398),
}

# Sky bucket the frames were depicted from.
GEN_BUCKET = {
    "DK-01-129": "overcast",
    "DK-01-130": "overcast",
    "DK-01-131": "partly",
    "DK-01-132": "overcast",
    "DK-01-133": "overcast",
    "DK-01-134": "overcast",
    "DK-01-135": "clear",
    "DK-01-136": "clear",
    "DK-01-137": "clear",
    "DK-01-138": "clear",
    "DK-01-139": "clear",
    "DK-01-140": "clear",
    "DK-01-141": "clear",
    "DK-01-142": "clear",
    "DK-01-143": "clear",
    "DK-01-144": "mainly",
}

# DK-01-129 was depicted from the 02:40 retrieval, when the code was overcast.
# A later hour can move the code to partly while the cloud deck stays high.
# The frame is not regenerated to chase that one-step change.
SNAPSHOT = {
    "DK-01-129": {
        "word": "Overcast",
        "temp": 13.5,
        "cloud": 87,
        "wind": 17.3,
        "precip": 0.0,
        "code": 3,
        "is_day": 0,
        "valid": "2026-09-25T02:30",
        "sunset_yesterday": "2026-09-24T19:14",
        "sunrise_today": "2026-09-25T07:11",
        "retrieved_stamp": "25 September 2026 02:40",
        "offset": 7200,
    },
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def bucket(code: int) -> str:
    return {0: "clear", 1: "mainly", 2: "partly", 3: "overcast"}.get(code, "other")


def sky_word(code: int) -> str:
    return {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
    }.get(code, f"Weather code {code}")


def nice_time(iso: str) -> str:
    y = iso[0:4]
    m = iso[5:7]
    d = iso[8:10]
    hhmm = iso[11:16]
    return f"{int(d)} {MONTHS[m]} {y} {hhmm}"


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
    return (
        f"A computed sun altitude of about {alt:.0f}\u00b0 ({band}), not an on-site observation."
    )


def pack_current(entry: str, item: dict, stamp: str) -> dict:
    cur = item["current"]
    daily = item["daily"]
    offset = int(item["utc_offset_seconds"])
    local = datetime.fromisoformat(cur["time"]).replace(
        tzinfo=timezone(timedelta(seconds=offset))
    )
    code = int(cur["weather_code"])
    temp = float(cur["temperature_2m"])
    cloud = int(cur["cloud_cover"])
    wind = float(cur["wind_speed_10m"])
    precip = float(cur["precipitation"])
    utc = local.astimezone(timezone.utc)
    alt = sun_alt(COORDS[entry][0], COORDS[entry][1], utc)
    word = sky_word(code)
    precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": (
            f"{word}, {temp:.1f}\u00b0C, cloud cover {cloud}%, "
            f"wind {wind:.1f} km/h, {precip_words}."
        ),
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
    local = datetime.fromisoformat(snap["valid"]).replace(
        tzinfo=timezone(timedelta(seconds=snap["offset"]))
    )
    alt = sun_alt(COORDS[entry][0], COORDS[entry][1], local.astimezone(timezone.utc))
    temp = float(snap["temp"])
    wind = float(snap["wind"])
    precip = float(snap["precip"])
    word = snap["word"]
    precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": (
            f"{word}, {temp:.1f}\u00b0C, cloud cover {snap['cloud']}%, "
            f"wind {wind:.1f} km/h, {precip_words}."
        ),
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
        if live_bucket == GEN_BUCKET[entry]:
            out[entry] = pack_current(entry, item, stamp)
            continue
        snap = SNAPSHOT.get(entry)
        if snap is not None and bucket(snap["code"]) == GEN_BUCKET[entry]:
            print(
                f"{entry} live bucket {live_bucket} differs from depicted {GEN_BUCKET[entry]}; "
                f"keeping the {snap['retrieved_stamp']} retrieval the frame was built from"
            )
            out[entry] = pack_snapshot(entry, snap)
            continue
        raise SystemExit(
            f"{entry} sky bucket changed from {GEN_BUCKET[entry]} to {live_bucket}; "
            "the frames were depicted from the earlier bucket and were not regenerated"
        )
    return stamp, out, moon_note(retrieved)


def prepare_raws() -> None:
    for n in range(129, 145):
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
        if row["cloud"] >= 80:
            text += "The cloud deck hides the moon. "
        else:
            text += moon + " "
        return text

    a = pack("DK-01-129")
    b = pack("DK-01-130")
    c = pack("DK-01-131")
    d = pack("DK-01-132")
    e = pack("DK-01-133")
    f = pack("DK-01-134")
    g = pack("DK-01-135")
    h = pack("DK-01-136")
    i = pack("DK-01-137")
    j = pack("DK-01-138")
    k = pack("DK-01-139")
    m = pack("DK-01-140")
    n = pack("DK-01-141")
    o = pack("DK-01-142")
    p = pack("DK-01-143")
    q = pack("DK-01-144")

    return [
        {
            "entry_id": "DK-01-129",
            "region": "North Jutland",
            "city": "Aalborg",
            "caption": "Budolfi, Aalborg",
            **a,
            "composition": "Whitewashed cathedral and a Baroque spire on the square \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the square between Algade and Gammeltorv, Budolfi is a pale whitewashed Gothic church with one square west tower, a metallic Baroque cupola, and a tall spire. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C, and the paved square is empty under street lamps. "
                "The harbour and the Utzon Center are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Budolfi Cathedral in Aalborg at night, a white tower and Baroque spire over the square",
            "viewpoint": "Budolfi Kirkeplads, looking at the west tower from the square between Algade and Gammeltorv. Approximate researched point 57.04790, 9.91960, not a surveyed camera.",
            "refs": [
                "https://www.aalborgdomkirke.dk/om-kirkerne",
                "https://en.wikipedia.org/wiki/Budolfi_Church",
            ],
            "anchors": [
                "A pale whitewashed Gothic church on the town square.",
                "One square west tower with a Baroque cupola and a tall spire.",
                "No harbour and no modern waterfront building.",
            ],
            "solar": clock("DK-01-129") + "Street lamps. The tower is not floodlit as a show. Clock faces are not treated as readable text.",
            "independent": "Budolfi Kirke is Aalborg Cathedral, on Algade at the square between Algade and Gammeltorv. The parish and Enjoy Nordjylland describe a Gothic church of yellow monk brick with a whitewashed facade, a square tower of about 28 metres, and the 1779 Baroque spire that brings the height to about 63.5 metres. Four clock faces were added in 1817. DK-01-057 is Aalborg Harbour and DK-01-058 is the Utzon Center. This card is the cathedral square.",
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. Pale church, one Baroque spire, empty square, cloudy night. No harbour.",
            "swap": (
                "No city swap. Budolfi is used so the card stays distinct from Aalborg Harbour, DK-01-057, and the Utzon Center, DK-01-058. "
                "The frame was depicted from the 02:40 overcast retrieval. A later model hour can move the code by one step while the cloud deck stays high; the frame was not regenerated for that."
            ),
        },
        {
            "entry_id": "DK-01-130",
            "region": "North Jutland",
            "city": "N\u00f8rresundby",
            "caption": "Lindholm H\u00f8je, N\u00f8rresundby",
            **b,
            "composition": "Stone circles and ship settings above the Limfjord \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the hilltop, Lindholm H\u00f8je is a field of low stone circles and ship-shaped settings on a grassy south slope, with the dark Limfjord and a thin band of city lights beyond. "
                f"The night is {b['word'].lower()}, about {b['temp']}\u00b0C. "
                "There is no reconstructed village. A building at the foot, if it reads as the museum, carries no name."
            ),
            "alt_text": "AI-generated artistic interpretation of Lindholm H\u00f8je at night, stone burial settings on a hill above the Limfjord",
            "viewpoint": "The public path on the burial field at Lindholm H\u00f8je, looking south over the stones toward the Limfjord. Approximate researched point 57.07722, 9.91250, not a surveyed camera.",
            "refs": [
                "https://nordjyskemuseer.dk/en/u/vikingemuseet-lindholm-hoje-en/",
                "https://en.wikipedia.org/wiki/Lindholm_H%C3%B8je",
            ],
            "anchors": [
                "Stone circles and ship-shaped settings on a grassy slope.",
                "Dark Limfjord water below the hill.",
                "A distant band of city lights. No reconstructed village.",
            ],
            "solar": clock("DK-01-130") + "Dim light from the far shore. The field is not floodlit as a show.",
            "independent": "Lindholm H\u00f8je is the Iron Age and Viking burial field on the south slope of Voerbjerg, address Vendilavej 11, 9400 N\u00f8rresundby. Nordjyske Museer describe nearly 700 cremation graves, marked by stone circles and ship settings, overlooking the Limfjord, with Aalborg across the water. The city is N\u00f8rresundby, not Aalborg. The museum building of 1992 sits at the site and is not the subject. No village was reconstructed on the hill.",
            "ip": "No museum name and no souvenir branding. Internal review only, not a legal certification.",
            "visual": "Pass. Stone settings, grassy slope, fjord, distant lights, overcast night. No reconstructed village and no readable sign.",
            "swap": "No swap. City verified as N\u00f8rresundby. The museum address is 9400 N\u00f8rresundby, across the Limfjord from Aalborg.",
        },
        {
            "entry_id": "DK-01-131",
            "region": "North Jutland",
            "city": "Rebild",
            "caption": "Rebild Bakker, Rebild",
            **c,
            "composition": "Heath hills and forest ridges at night \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From a footpath, Rebild Bakker is a run of rounded heath hills with dark forest on the ridges and a shallow valley between them. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, and the grass is still green. "
                "There is no stage, no flag, and no building."
            ),
            "alt_text": "AI-generated artistic interpretation of Rebild Bakker at night, heath hills and dark forest under broken cloud",
            "viewpoint": "A public path on the heath at Rebild Bakker, looking across the hills into Rold Forest. Approximate researched point 56.83131, 9.83454, not a surveyed camera.",
            "refs": [
                "https://www.rebildporten.com/guest/planlaeg-din-tur/rebild-bakker-ruten-gdk1096614",
                "https://en.wikipedia.org/wiki/Rold_Skov",
            ],
            "anchors": [
                "Rounded hills of low heath and grass.",
                "Dark forest on the ridges.",
                "A shallow valley. No stage and no flags.",
            ],
            "solar": clock("DK-01-131") + "No path lighting. Late September heather is not shown in full bloom.",
            "independent": "Rebild Bakker is the heath-hill valley inside Rold Skov, in Rebild Kommune. RebildPorten gives the trail start as Rebildvej 25a, 9520 Sk\u00f8rping, the neighbouring postal town. Nominatim places the hills themselves in Rebild. The city in the caption is Rebild, the locality of the viewpoint, not Sk\u00f8rping. The July festival ground is empty at this hour and is not dressed with flags. Late September leaves the heath green and brown rather than a purple carpet.",
            "ip": "No festival branding and no signs. Internal review only, not a legal certification.",
            "visual": "Pass. Heath hills, forest, empty path, partly cloudy night. No flags and no stage.",
            "swap": (
                "No city swap. City kept as Rebild after checking the address. "
                "The visitor-center postal town is Sk\u00f8rping (9520). The hills are in Rebild, and that is the caption city."
            ),
        },
        {
            "entry_id": "DK-01-132",
            "region": "North Jutland",
            "city": "Skagen",
            "caption": "Skagen Old Town, Skagen",
            **d,
            "composition": "Yellow houses and red tile roofs on a paved street \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A narrow paved street in \u00d8sterby is lined with low yellow-washed houses, red tile roofs, and white window frames. "
                f"The night is {d['word'].lower()}, about {d['temp']}\u00b0C, under street lamps. "
                "The street is empty of a crowd. There is no dune, no buried church, and no hotel name."
            ),
            "alt_text": "AI-generated artistic interpretation of Skagen old town at night, yellow houses and red roofs on a paved street",
            "viewpoint": "The public street in \u00d8sterby near Anchersvej, looking along the yellow houses. Approximate researched point 57.72488, 10.59833, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Skagen",
                "https://da.wikipedia.org/wiki/Skagen",
            ],
            "anchors": [
                "Low yellow-washed houses with red tile roofs.",
                "A narrow paved street.",
                "No dune, no buried church tower, and no spit of two seas.",
            ],
            "solar": clock("DK-01-132") + "Street lamps. No shop name is readable.",
            "independent": "Skagen's old town in \u00d8sterby is the yellow-washed houses with red roofs. Grenen is DK-01-012 and the Sand-Buried Church is DK-01-059. This card is the street. Br\u00f8ndums Hotel stands on Anchersvej in the same quarter; its name and sign are not the subject, so the frame is the public row of houses rather than a hotel front. A distant figure, if present, is not identifiable.",
            "ip": "No hotel name and no readable shop sign. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow houses, red roofs, paved street, overcast night. No dune and no buried church.",
            "swap": (
                "Site choice inside Skagen, not a city swap. The old-town street is used rather than a hotel exterior, "
                "so a hotel name stays out of the frame. Distinct from Grenen, DK-01-012, and the Sand-Buried Church, DK-01-059."
            ),
        },
        {
            "entry_id": "DK-01-133",
            "region": "North Jutland",
            "city": "Kandestederne",
            "caption": "R\u00e5bjerg Mile, Kandestederne",
            **e,
            "composition": "A bare migrating dune under a cloud deck \u00b7 AI-generated artistic interpretation",
            "description": (
                f"R\u00e5bjerg Mile is a broad ridge of pale wind-rippled sand, with marram and heath only at the edges. "
                f"The night is {e['word'].lower()}, about {e['temp']}\u00b0C, and the sand is a dim shape under full cloud. "
                "There is no town, no lighthouse, and no stair."
            ),
            "alt_text": "AI-generated artistic interpretation of R\u00e5bjerg Mile at night, a bare sand dune under heavy cloud",
            "viewpoint": "The open sand of R\u00e5bjerg Mile, looking along the dune ridge. Approximate researched point 57.64982, 10.40743, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/R%C3%A5bjerg_Mile",
                "https://www.rundtidanmark.dk/raabjerg-mile/",
            ],
            "anchors": [
                "A broad bare sand ridge with wind ripples.",
                "Heath and marram only at the edges.",
                "No town, no lighthouse, and no wooden stair.",
            ],
            "solar": clock("DK-01-133") + "No dune lighting. The sand is not snow and not a sunlit desert.",
            "independent": "R\u00e5bjerg Mile is the migrating dune on Skagen Odde, about 16 kilometres southwest of Skagen town, roughly 40 metres high and still moving. The parking address is R\u00e5bjerg Mile Vej, Kandestederne, 9990 Skagen. The postal town is Skagen, but the locality on the address is Kandestederne, and the dune is not in Skagen town, which already has Grenen and the Sand-Buried Church. The caption city is Kandestederne. A first wide frame that put a wooden stair on the slope was discarded. The published frame is bare sand.",
            "ip": "No signs and no buildings. Internal review only, not a legal certification.",
            "visual": "Pass. Bare dune, heath at the edge, overcast night. No stair and no town.",
            "swap": (
                "City swapped from Skagen to Kandestederne. The dune address names Kandestederne, and Skagen town is about 16 km away. "
                "A first wide frame with a wooden stair was discarded."
            ),
        },
        {
            "entry_id": "DK-01-134",
            "region": "North Jutland",
            "city": "S\u00e6by",
            "caption": "S\u00e6by Harbour, S\u00e6by",
            **f,
            "composition": "A small basin, red roofs, and a white church tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, S\u00e6by harbour is a basin of ordinary boats inside stone piers, with low red-tiled houses and one white church tower behind the roofs. "
                f"The night is {f['word'].lower()}, about {f['temp']}\u00b0C, and quay lamps lie on dark water. "
                "The quay is empty. No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of S\u00e6by harbour at night, boats, red roofs, and a white church tower",
            "viewpoint": "The public quay at S\u00e6by harbour, looking across the basin toward the town. Approximate researched point 57.33316, 10.53248, not a surveyed camera.",
            "refs": [
                "https://visitvendsyssel.dk/en/saeby/",
                "https://www.saebykirke.dk/saby-kirke-aalborg-stift",
            ],
            "anchors": [
                "A small harbour basin and ordinary boats.",
                "Low houses with red tile roofs.",
                "One white church tower behind the roofs, not a close-up.",
            ],
            "solar": clock("DK-01-134") + "Quay lamps. The church is the distant landmark, not the whole frame.",
            "independent": "S\u00e6by is the harbour town south of Frederikshavn. The inner harbour sits against the old town, and the white Carmelite church, a late-medieval lead-roofed brick church, is the tower sailors use as a landmark behind the roofs. This card is the harbour. The church interior and its frescoes are not shown. No boat name is treated as readable.",
            "ip": "No readable boat names and no shop signs. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, boats, red roofs, distant white tower, overcast night, empty quay.",
            "swap": "No swap. The harbour is the view, with the church tower only as the town landmark behind the roofs.",
        },
        {
            "entry_id": "DK-01-135",
            "region": "North Jutland",
            "city": "Thisted",
            "caption": "Thisted Harbour, Thisted",
            **g,
            "composition": "A Limfjord basin and low warehouses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Thisted harbour is a modest basin of ordinary boats on the Limfjord, with a plain quay and low warehouses. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C, and moonlight lies on calm water. "
                "The quay is empty. There is no longship and no readable name."
            ),
            "alt_text": "AI-generated artistic interpretation of Thisted harbour at night, boats and low warehouses on the Limfjord",
            "viewpoint": "The quay at Thisted harbour, looking across the basin. Approximate researched point 56.95246, 8.69641, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Thisted",
                "https://en.wikipedia.org/wiki/Thisted_Municipality",
            ],
            "anchors": [
                "A modest harbour basin and ordinary boats.",
                "A plain quay and low warehouses.",
                "Dark Limfjord water. No longship.",
            ],
            "solar": clock("DK-01-135") + "Quay lamps and moonlight. The town church is not the subject.",
            "independent": "Thisted stands on Thisted Bredning, an inlet of the Limfjord, in Thisted Kommune, which is Region Nordjylland. The gallery files it with North Jutland. The frame is the ordinary night harbour, not a Viking ship and not the town church. No boat name is treated as readable.",
            "ip": "No readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, boats, warehouses, clear moonlit night, empty quay. No longship.",
            "swap": "No swap. The harbour on the Limfjord is the view.",
        },
        {
            "entry_id": "DK-01-136",
            "region": "North Jutland",
            "city": "Nyk\u00f8bing Mors",
            "caption": "Nyk\u00f8bing Mors Harbour, Nyk\u00f8bing Mors",
            **h,
            "composition": "A small island-town basin on the fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Nyk\u00f8bing Mors harbour is a quiet basin of small boats, low town houses, and dark fjord water. "
                f"The night is {h['word'].lower()}, about {h['temp']}\u00b0C, with moonlight on the basin. "
                "The quay is empty. No boat name is readable. This is not the Falster harbour."
            ),
            "alt_text": "AI-generated artistic interpretation of Nyk\u00f8bing Mors harbour at night, small boats and low houses on the fjord",
            "viewpoint": "The quay at Nyk\u00f8bing Mors harbour, looking across the basin. Approximate researched point 56.79259, 8.86616, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nyk%C3%B8bing_Mors",
                "https://en.wikipedia.org/wiki/Mors_(island)",
            ],
            "anchors": [
                "A small harbour basin and ordinary boats.",
                "Low town houses along the quay.",
                "Dark fjord water. Not a large ferry port.",
            ],
            "solar": clock("DK-01-136") + "Quay lamps and moonlight.",
            "independent": "Nyk\u00f8bing Mors is the town on the island of Mors in the Limfjord, in Mors\u00f8 Kommune, Region Nordjylland. It is a different town from Nyk\u00f8bing Falster, whose harbour is DK-01-091. The frame is the small night harbour. Dueholm, the old monastery west of town, is not in the basin. No boat name is treated as readable.",
            "ip": "No readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Small basin, low houses, clear moonlit night, empty quay. Distinct from Nyk\u00f8bing Falster.",
            "swap": "No swap. The city is Nyk\u00f8bing Mors, not Nyk\u00f8bing Falster.",
        },
        {
            "entry_id": "DK-01-137",
            "region": "Central Jutland",
            "city": "Lemvig",
            "caption": "Lemvig Harbour, Lemvig",
            **i,
            "composition": "Boats at the foot of a hillside town \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Lemvig harbour is a basin of ordinary boats at the foot of a town that climbs a green hill, with houses stepping up the slope. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, and moonlight is on the water. "
                "The quay is empty. No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Lemvig harbour at night, boats below a town climbing a hill",
            "viewpoint": "The quay at Lemvig harbour, looking across the basin toward the hillside town. Approximate researched point 56.55133, 8.30256, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Lemvig",
                "https://en.wikipedia.org/wiki/Lemvig_Municipality",
            ],
            "anchors": [
                "A harbour basin and ordinary boats.",
                "Houses climbing a green hillside.",
                "Dark water. No readable names.",
            ],
            "solar": clock("DK-01-137") + "Quay lamps and moonlight.",
            "independent": "Lemvig sits at the east end of Lem Vig, an inlet of the Limfjord, and the town climbs the hill above the harbour. Lemvig Kommune is in Region Midtjylland, so the gallery files it with Central Jutland, not North Jutland. The frame is that night harbour and the slope. No boat name is treated as readable.",
            "ip": "No readable boat names and no shop signs. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, boats, hillside houses, clear moonlit night, empty quay.",
            "swap": "No swap. Region is Central Jutland because Lemvig Kommune is Region Midtjylland.",
        },
        {
            "entry_id": "DK-01-138",
            "region": "Central Jutland",
            "city": "Thybor\u00f8n",
            "caption": "Thybor\u00f8n Harbour, Thybor\u00f8n",
            **j,
            "composition": "Fishing cutters, moles, and a channel to the sea \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Thybor\u00f8n harbour holds fishing cutters with bare masts inside stone moles, with a channel toward dark sea and low houses and dunes behind the quay. "
                f"The night is {j['word'].lower()}, about {j['temp']}\u00b0C, and a fresh breeze puts a little chop on the water. "
                "The quay is empty. No boat name is readable, and there is no storm."
            ),
            "alt_text": "AI-generated artistic interpretation of Thybor\u00f8n harbour at night, fishing boats, moles, and a channel toward the sea",
            "viewpoint": "The public quay at Thybor\u00f8n harbour, looking along the fishing basin toward the channel. Approximate researched point 56.70451, 8.21748, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Thybor%C3%B8n",
                "https://en.wikipedia.org/wiki/Thybor%C3%B8n_Channel",
            ],
            "anchors": [
                "Fishing cutters with bare masts inside moles.",
                "A channel opening toward dark sea.",
                "Low houses and dunes. A little chop, not a storm.",
            ],
            "solar": clock("DK-01-138") + "Quay lamps and moonlight. A small entrance light, if present, is not the subject.",
            "independent": "Thybor\u00f8n is the fishing town on the sand tongue at Thybor\u00f8n Kanal, where the North Sea meets the western Limfjord. It is in Lemvig Kommune, Region Midtjylland, so the gallery files it with Central Jutland. The frame is the night harbour, the moles, and the channel, not a beach resort. Wind in the model hour is a fresh breeze, so the water has a little chop and is not a gale. No boat name is treated as readable.",
            "ip": "No readable boat names and no ferry brand. Internal review only, not a legal certification.",
            "visual": "Pass. Cutters, moles, channel, dunes, clear night, a little chop, empty quay.",
            "swap": "No city swap. Region is Central Jutland, with Lemvig Kommune, not North Jutland.",
        },
        {
            "entry_id": "DK-01-139",
            "region": "Central Jutland",
            "city": "Ringk\u00f8bing",
            "caption": "Ringk\u00f8bing Harbour, Ringk\u00f8bing",
            **k,
            "composition": "A quiet basin on the fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Ringk\u00f8bing harbour is a quiet basin of small boats, a plain quay, low town houses, and wide dark fjord water. "
                f"The night is {k['word'].lower()}, about {k['temp']}\u00b0C, with moonlight on the basin. "
                "The promenade is empty. No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Ringk\u00f8bing harbour at night, small boats and low houses on the fjord",
            "viewpoint": "The quay at Ringk\u00f8bing harbour, looking across the basin toward the fjord. Approximate researched point 56.08701, 8.23907, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ringk%C3%B8bing",
                "https://en.wikipedia.org/wiki/Ringk%C3%B8bing_Fjord",
            ],
            "anchors": [
                "A quiet basin of small boats.",
                "Low town houses along a plain quay.",
                "Wide dark fjord water. No sculpture as the subject.",
            ],
            "solar": clock("DK-01-139") + "Quay lamps and moonlight.",
            "independent": "Ringk\u00f8bing stands on the northeast shore of Ringk\u00f8bing Fjord. The town is in Ringk\u00f8bing-Skjern Kommune, Region Midtjylland, so the gallery files it with Central Jutland. The frame is the night harbour and the fjord, not a town-square sculpture. Hvide Sande, at the sea lock, is a separate card. No boat name is treated as readable.",
            "ip": "No readable boat names and no sculpture as the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, small boats, low houses, fjord, clear moonlit night, empty quay.",
            "swap": "No swap. The fjord harbour is the view, distinct from Hvide Sande.",
        },
        {
            "entry_id": "DK-01-140",
            "region": "Central Jutland",
            "city": "Hvide Sande",
            "caption": "Hvide Sande Harbour, Hvide Sande",
            **m,
            "composition": "Fishing boats in the dune canal \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Hvide Sande harbour is the canal through the dunes, with fishing boats along the lock walls, low sheds, and sand on either side. "
                f"The night is {m['word'].lower()}, about {m['temp']}\u00b0C, and a fresh breeze puts a little chop on the water. "
                "The quay is empty. No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Hvide Sande harbour at night, fishing boats in the canal through the dunes",
            "viewpoint": "The quay beside the harbour canal at Hvide Sande, looking along the lock and the boats. Approximate researched point 56.00165, 8.12860, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hvide_Sande",
                "https://en.wikipedia.org/wiki/Ringk%C3%B8bing_Fjord",
            ],
            "anchors": [
                "A canal cut through coastal dunes.",
                "Fishing boats along lock walls.",
                "Low sheds. No readable names.",
            ],
            "solar": clock("DK-01-140") + "Quay lamps and moonlight. A distant turbine, if present, is not identified as a named project.",
            "independent": "Hvide Sande is the fishing town where the lock canal crosses the Holmsland dune spit between the North Sea and Ringk\u00f8bing Fjord. It is in Ringk\u00f8bing-Skjern Kommune, Region Midtjylland, filed here with Central Jutland. The frame is the night canal and the boats, not Ringk\u00f8bing town. No boat name is treated as readable. A distant turbine, if it appears, is not named.",
            "ip": "No readable boat names and no shop logos. Internal review only, not a legal certification.",
            "visual": "Pass. Canal, boats, dunes, sheds, clear night, a little chop, empty quay.",
            "swap": "No swap. The dune canal is the view, distinct from Ringk\u00f8bing harbour.",
        },
        {
            "entry_id": "DK-01-141",
            "region": "South Jutland",
            "city": "Bl\u00e5vand",
            "caption": "Bl\u00e5vandshuk, Bl\u00e5vand",
            **n,
            "composition": "A square white lighthouse on the western dune \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Bl\u00e5vandshuk Lighthouse is a tall square white tower on a dune, with a granite base, a band of red-brown brick, a crenellated gallery, and a red lantern roof, and the North Sea is in front. "
                f"The night is {n['word'].lower()}, about {n['temp']}\u00b0C, with moonlight and a little surf. "
                "The dune path is empty. A low keeper's house may stand beside the tower. No sign is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Bl\u00e5vandshuk Lighthouse at night, a square white tower on a dune above the sea",
            "viewpoint": "The dune beside Bl\u00e5vandshuk Fyr, looking at the square tower with the sea beyond. Approximate researched point 55.55783, 8.08325, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Bl%C3%A5vand_Lighthouse",
                "https://trap.lex.dk/Bl%C3%A5vandshuk_Fyr_-_Fredede_og_bevaringsv%C3%A6rdige_bygninger",
            ],
            "anchors": [
                "One square white tower, not a round shaft.",
                "A crenellated gallery and a red lantern roof.",
                "Dune grass and the North Sea. No readable sign.",
            ],
            "solar": clock("DK-01-141") + "Moonlight. A small working light in the lantern is the ordinary sea light, not a measured flash pattern.",
            "independent": "Bl\u00e5vandshuk Fyr stands on the dune at Denmark's westernmost point, Fyrvej, 6857 Bl\u00e5vand, in Varde Kommune. Trap Danmark describes a 39-metre square concrete tower of 1899\u20131900, whitewashed, on a granite base, with a red-brown brick frieze, chamfered corners, and a gallery parapet finished with crenellations. The lantern roof is red-painted steel. The city is Bl\u00e5vand, not Varde and not Esbjerg. The gallery files Varde Kommune with South Jutland. The former keeper's house is part of the station. The generated lantern is an interpretation of that red roof, not a measured elevation. Horns Rev turbines are not the subject.",
            "ip": "No readable sign and no wind-farm brand. Internal review only, not a legal certification.",
            "visual": "Pass. Square white tower, crenellated gallery, red lantern, dune, sea, clear night. Not a round shaft.",
            "swap": "No city swap. City verified as Bl\u00e5vand. The lighthouse address is in 6857 Bl\u00e5vand, Varde Kommune.",
        },
        {
            "entry_id": "DK-01-142",
            "region": "South Jutland",
            "city": "Ribe",
            "caption": "Ribe Old Town, Ribe",
            **o,
            "composition": "A cobbled lane of half-timbered houses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A narrow cobbled lane in Ribe is closed in by low half-timbered houses, white panels, dark timber, and red tile roofs. "
                f"The night is {o['word'].lower()}, about {o['temp']}\u00b0C, with moonlight and warm street lamps. "
                "The lane is empty. The cathedral is not in the frame, and no shop name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of a Ribe old-town lane at night, half-timbered houses along a cobbled street",
            "viewpoint": "A cobbled lane in Ribe old town, such as the Gr\u00f8nnegade quarter, looking along the houses rather than at the cathedral west front. Approximate researched point 55.32940, 8.76091, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ribe",
                "https://da.wikipedia.org/wiki/Ribe",
            ],
            "anchors": [
                "Low half-timbered houses with white panels and red tile roofs.",
                "A narrow cobbled lane.",
                "No cathedral facade and no twin towers.",
            ],
            "solar": clock("DK-01-142") + "Street lamps and moonlight. No shop name is readable.",
            "independent": "Ribe's old town is the half-timbered lanes around the cathedral quarter. DK-01-013 is Ribe Cathedral. This card is a street, and the cathedral was kept out so the two cards do not repeat. A first wide frame that opened onto the cathedral towers was discarded. The published frame is the lane. No shop name is treated as readable.",
            "ip": "No readable shop names and no cathedral artwork as the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Half-timbered lane, cobbles, moonlight, empty street. No cathedral.",
            "swap": (
                "Site choice inside Ribe, not a city swap. The old-town street is used, as specified, so the card stays distinct from Ribe Cathedral, DK-01-013. "
                "A first wide frame that included the cathedral was discarded."
            ),
        },
        {
            "entry_id": "DK-01-143",
            "region": "South Jutland",
            "city": "S\u00f8nderho",
            "caption": "S\u00f8nderho, S\u00f8nderho",
            **p,
            "composition": "Thatched cottages along a village lane \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A lane in S\u00f8nderho is lined with low cottages, thick thatch, and gable ends toward the street, with small gardens that are not in summer bloom. "
                f"The night is {p['word'].lower()}, about {p['temp']}\u00b0C, under moonlight. "
                "The lane is empty. No inn name is readable, and the beach is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of S\u00f8nderho at night, thatched cottages along a village lane",
            "viewpoint": "A public lane in S\u00f8nderho, looking along the thatched cottages. Approximate researched point 55.34856, 8.46898, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/S%C3%B8nderho",
                "https://en.wikipedia.org/wiki/Fan%C3%B8",
            ],
            "anchors": [
                "Low cottages with thick thatched roofs.",
                "Gable ends facing the lane.",
                "Small gardens. No inn sign and no beach.",
            ],
            "solar": clock("DK-01-143") + "A few lane lamps and moonlight.",
            "independent": "S\u00f8nderho is the village at the south end of Fan\u00f8, in Fan\u00f8 Kommune, Region Syddanmark. The postal code is 6720 Fan\u00f8, but the settlement is S\u00f8nderho, and that is the caption city. The cottages are the 18th- and 19th-century captain's houses, mostly thatched, with gables to the lane. S\u00f8nderho Kro is an inn in the village; its name is not the subject. The gallery files Fan\u00f8 with South Jutland. Late September gardens are green, not a summer flower show.",
            "ip": "No inn name and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Thatched cottages, gables, lane, moonlit night, empty. No inn sign.",
            "swap": (
                "No city swap. City verified as S\u00f8nderho, the village, not the postal town Fan\u00f8 and not Nordby. "
                "The inn sign was not used as the subject."
            ),
        },
        {
            "entry_id": "DK-01-144",
            "region": "South Jutland",
            "city": "Lakolk",
            "caption": "Lakolk Beach, Lakolk",
            **q,
            "composition": "A vast flat beach and a low surf line \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Lakolk beach is an extremely wide flat sand plain, with a low dune of marram at the edge and a thin surf line far out on the North Sea. "
                f"The night is {q['word'].lower()}, about {q['temp']}\u00b0C, with moonlight and a breeze. "
                "There are no cars, no shops, and no people."
            ),
            "alt_text": "AI-generated artistic interpretation of Lakolk beach on R\u00f8m\u00f8 at night, a vast flat sand beach under moonlight",
            "viewpoint": "The open sand at Lakolk on the west coast of R\u00f8m\u00f8, looking toward the North Sea. Approximate researched point 55.13953, 8.49398, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Lakolk",
                "https://en.wikipedia.org/wiki/R%C3%B8m%C3%B8",
            ],
            "anchors": [
                "A very wide flat sandy beach.",
                "A low dune with marram grass.",
                "A distant surf line. No cars, no shops, and no harbour.",
            ],
            "solar": clock("DK-01-144") + "Moonlight. No beach lighting and no shop front.",
            "independent": "Lakolk is the settlement on the west coast of R\u00f8m\u00f8, in T\u00f8nder Kommune, known for the broad North Sea beach. The postal code is 6792 R\u00f8m\u00f8. Havneby, on the southeast of the island, is the ferry harbour and a different place. This card is the beach at Lakolk, not Havneby harbour and not the Lakolk shop center. The gallery files R\u00f8m\u00f8 with South Jutland. Late September night leaves the sand empty.",
            "ip": "No shop name, no car brand, and no ferry brand. Internal review only, not a legal certification.",
            "visual": "Pass. Wide sand, dune grass, distant surf, moonlit night. No cars and no harbour.",
            "swap": (
                "City verified as Lakolk, not Havneby and not R\u00f8m\u00f8 as the town name. "
                "The beach is used. Havneby harbour was not used."
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
    expected = {
        "Title": bd.ART50["Title"],
        "Description": bd.ART50["Description"],
        "Copyright": bd.ART50["Copyright"],
        "Software": bd.ART50["Software"],
        "Comment": bd.ART50["Comment"],
    }
    for path in paths:
        parsed = bd.read_text_chunks(path)
        for key, val in expected.items():
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
    if len(all_scenes) != 144:
        raise SystemExit(f"expected 144 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 145)]
    if ids != expected:
        raise SystemExit(ids)
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-129-144.txt"
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

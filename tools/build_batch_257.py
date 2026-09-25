#!/usr/bin/env python3
"""Bake DK-01-257 through DK-01-272 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-257-272.json.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-257-272.json").read_text(encoding="utf-8"))

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def sky_word(code: int) -> str:
    table = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 51: "Light drizzle"}
    if code not in table:
        raise SystemExit(f"unhandled weather code {code}")
    return table[code]


def nice_time(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[iso[5:7]]} {iso[0:4]} {iso[11:16]}"


def stamp_words(raw: str) -> str:
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


def temp_s(temp: float) -> str:
    if abs(temp) < 0.05:
        return "0.0"
    return f"{temp:.1f}"


def pack(entry: str) -> dict:
    row = WX[entry]
    when = datetime.fromisoformat(row["retrieved"])
    local_valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=timezone(timedelta(seconds=7200)))
    alt = sun_alt(row["lat"], row["lon"], local_valid.astimezone(timezone.utc))
    code = int(row["code"])
    word = sky_word(code)
    temp = float(row["temp"])
    wind = float(row["wind"])
    precip = float(row["precip"])
    snow = float(row["snow"])
    if int(row["is_day"]) != 0:
        raise SystemExit(f"{entry} is_day")
    if not str(row["valid"]).startswith("2026-09-25T06:45"):
        raise SystemExit(f"{entry} valid {row['valid']}")
    if not str(row["retrieved"]).startswith("2026-09-25T06:"):
        raise SystemExit(f"{entry} retrieval {row['retrieved']}")
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
        "valid": row["valid"],
        "sunset": row["sunset_yesterday"],
        "sunrise": row["sunrise_today"],
        "sun_alt": alt,
        "retrieved_stamp": stamp_words(row["retrieved"]),
        "retrieved_iso": row["retrieved"],
        "moon": moon_note(when),
        "prefix": (
            "Model data from Open-Meteo, retrieved "
            f"{stamp_words(row['retrieved'])} Europe/Copenhagen, valid "
            f"{nice_time(row['valid'])} Europe/Copenhagen "
            "\u2014 not a verified on-site observation. "
            f"Separate request for {row['lat']:.5f}, {row['lon']:.5f}. "
            "The model-valid hour is 06:00\u201306:59 Europe/Copenhagen. "
            "The cited model time is the 06:45 step (interval 900 seconds)."
        ),
    }


def light(row: dict) -> str:
    if row["code"] == 51:
        return "Light drizzle is falling. The cloud deck hides the moon."
    if row["cloud"] >= 80:
        return "The cloud deck hides the moon."
    return "Moonlight reaches the ground under a thin cloud cover."


def wind_clause(row: dict) -> str:
    w = row["wind_f"]
    if w >= 40:
        return f"The wind is strong, about {row['wind']} km/h."
    if w >= 20:
        return f"The wind is fresh, about {row['wind']} km/h."
    return f"The wind is light, about {row['wind']} km/h."


def clock(row: dict) -> str:
    sunset = nice_time(row["sunset"])
    sunrise = nice_time(row["sunrise"])
    text = (
        "Before today's sunrise. "
        f"Sunset on {sunset} Europe/Copenhagen and sunrise on {sunrise} Europe/Copenhagen. "
    )
    text += twilight_phrase(row["sun_alt"]) + " "
    text += f"Cloud cover {row['cloud']}%. "
    if row["code"] == 51:
        text += "Light drizzle is in the model. The cloud hides the moon. "
    elif row["cloud"] >= 80:
        text += "The cloud deck hides the moon. "
    else:
        text += row["moon"] + " "
    text += (
        "The scenario minute has to fall inside this scene's own model-valid hour, "
        "06:00\u201306:59 Europe/Copenhagen, and after the cited 06:45 model step, "
        "and before today's sunrise."
    )
    return text


def scenario_label(entry_id: str) -> str:
    """Use the generated JPEG mtimes. This filesystem ignores utime, so the decoded PNG mtime is not the generation time."""
    times = []
    for kind in ("16x9", "4x5"):
        path = bd.RAW / f"{entry_id.lower()}-{kind}.png"
        times.append(os.path.getmtime(path))
    dt = datetime.fromtimestamp(max(times), bd.CPH)
    month = dt.strftime("%B")
    return f"{dt.day} {month} {dt.year} \u00b7 {dt.strftime('%H:%M')} Europe/Copenhagen"


bd.scenario_label = scenario_label


def prepare_raws() -> None:
    for n in range(257, 273):
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
    stamps = [WX[e]["retrieved"] for e in WX]
    if len(stamps) != len(set(stamps)):
        raise SystemExit("reused retrieval timestamp")
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

    rows = {f"DK-01-{n}": base(f"DK-01-{n}") for n in range(257, 273)}

    def sky(entry: str) -> str:
        row = rows[entry]
        return (
            f"It is {row['word'].lower()}, about {row['temp']}\u00b0C. "
            f"{wind_clause(row['_row'])} {light(row['_row'])}"
        )

    return [
        {
            "entry_id": "DK-01-257",
            "region": "Capital Region",
            "city": "Helsing\u00f8r",
            "caption": "Helsing\u00f8r Harbour, Helsing\u00f8r",
            **rows["DK-01-257"],
            "composition": "Working harbour basin with Kronborg small on the point \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the south quay, Helsing\u00f8r harbour is a working basin of fishing boats and one plain ferry, and Kronborg's sandstone walls and copper roofs sit small on the point to the north. "
                f"The quay is empty. {sky('DK-01-257')} "
                "Quay lamps light the damp concrete. This is not the close seaward view of the castle."
            ),
            "alt_text": "AI-generated artistic interpretation of Helsing\u00f8r harbour before sunrise, with Kronborg small in the distance",
            "viewpoint": "South quay of Helsing\u00f8r Havn, looking north so Kronborg is distant. Approximate researched point 56.03147, 12.61301, not a surveyed camera. Nominatim returns the English exonym Elsinore. Postcode 3000 is Helsing\u00f8r.",
            "refs": [
                "https://en.wikipedia.org/wiki/Helsing%C3%B8r",
                "https://en.wikipedia.org/wiki/Kronborg",
            ],
            "anchors": [
                "A harbour basin with fishing boats and one plain ferry.",
                "Kronborg small on the northern point, not filling the frame.",
                "Dark \u00d8resund water and a faint far shore.",
            ],
            "solar": clock(rows["DK-01-257"]["_row"]) + " Quay lamps. No readable ferry name.",
            "independent": (
                "Helsing\u00f8r's harbour lies south of Kronborg on the \u00d8resund. "
                "The close seaward castle view is already DK-01-004, Kronborg Castle, Helsing\u00f8r. This frame stays on the harbour and keeps the castle distant."
            ),
            "ip": "No readable ferry name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, boats, plain ferry, damp quay, and a small distant castle with copper roofs. Not the close rampart view.",
            "swap": "No site swap. Kronborg Castle, Helsing\u00f8r is already DK-01-004. This caption is the harbour, with the castle only distant. City is Helsing\u00f8r.",
        },
        {
            "entry_id": "DK-01-258",
            "region": "Capital Region",
            "city": "Tisvildeleje",
            "caption": "Tisvildeleje Beach, Tisvildeleje",
            **rows["DK-01-258"],
            "composition": "Empty sand, marram dunes, and the Kattegat \u00b7 AI-generated artistic interpretation",
            "description": (
                "Tisvildeleje beach is a wide empty strand, low marram dunes, and a dark Kattegat with a light chop. "
                f"{sky('DK-01-258')} "
                "A few town lamps sit behind the dunes. There are no umbrellas and no summer bars."
            ),
            "alt_text": "AI-generated artistic interpretation of Tisvildeleje beach before sunrise, empty sand and dunes under cloud",
            "viewpoint": "The public beach at Tisvildeleje Strand, looking toward the Kattegat. Approximate researched point 56.05323, 12.05251, not a surveyed camera. Nominatim places the beach in Tisvildeleje.",
            "refs": [
                "https://en.wikipedia.org/wiki/Tisvildeleje",
                "https://en.wikipedia.org/wiki/Gribskov_Municipality",
            ],
            "anchors": [
                "A broad sandy beach.",
                "Low dunes with marram grass.",
                "Dark sea and no beach-bar row.",
            ],
            "solar": clock(rows["DK-01-258"]["_row"]) + " No readable sign.",
            "independent": (
                "Tisvildeleje is the north-coast resort at the edge of Tisvilde Hegn, with a long Kattegat beach. "
                "Late September has no summer beach furniture. Gilleleje Harbour is already DK-01-098, so this batch uses the beach at Tisvildeleje instead."
            ),
            "ip": "No sign and no flag. Internal review only, not a legal certification.",
            "visual": "Pass. Empty sand, dunes, dark sea, overcast. No umbrellas and no lettering.",
            "swap": "Swapped from Gilleleje Harbour. That basin is already DK-01-098, Gilleleje Harbour, Gilleleje. The caption is Tisvildeleje Beach. City is Tisvildeleje.",
        },
        {
            "entry_id": "DK-01-259",
            "region": "Capital Region",
            "city": "Hornb\u00e6k",
            "caption": "Hornb\u00e6k Harbour, Hornb\u00e6k",
            **rows["DK-01-259"],
            "composition": "Wooden piers and small boats inside the breakwater \u00b7 AI-generated artistic interpretation",
            "description": (
                "Hornb\u00e6k harbour is wooden piers, small boats, and low sheds inside a breakwater, not the open beach east of the mole. "
                f"The quay is empty. {sky('DK-01-259')} "
                "Lamps glisten on the wet planks."
            ),
            "alt_text": "AI-generated artistic interpretation of Hornb\u00e6k harbour before sunrise, wooden piers and boats in light drizzle",
            "viewpoint": "The public quay at Hornb\u00e6k Havn. Approximate researched point 56.09440, 12.45845, not a surveyed camera. Nominatim places the marina in Hornb\u00e6k, postcode 3100.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hornb%C3%A6k",
                "https://da.wikipedia.org/wiki/Hornb%C3%A6k",
            ],
            "anchors": [
                "Wooden piers and small moored boats.",
                "Low sheds and a breakwater.",
                "No open-beach panorama.",
            ],
            "solar": clock(rows["DK-01-259"]["_row"]) + " Quay lamps. No readable boat name.",
            "independent": (
                "Hornb\u00e6k has a small harbour beside the better-known beach. "
                "Hornb\u00e6k Beach is already DK-01-099. This frame stays inside the harbour."
            ),
            "ip": "No readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Piers, boats, sheds, wet wood, overcast lamps. Not the beach card.",
            "swap": "No site swap of the harbour. Hornb\u00e6k Beach is already DK-01-099, Hornb\u00e6k Beach, Hornb\u00e6k. This caption is the harbour. City is Hornb\u00e6k.",
        },
        {
            "entry_id": "DK-01-260",
            "region": "Capital Region",
            "city": "Hundested",
            "caption": "Hundested Harbour, Hundested",
            **rows["DK-01-260"],
            "composition": "Stone moles and fishing boats in the old basins \u00b7 AI-generated artistic interpretation",
            "description": (
                "Hundested's old fishing harbour is stone moles and inner basins of fishing boats, with a chop on the dark water. "
                f"The quay is empty. {sky('DK-01-260')} "
                "No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Hundested harbour before sunrise, fishing boats and stone moles under cloud",
            "viewpoint": "The old harbour basins at Hundested. The port publishes 55\u00b057.9\u2032N 11\u00b050.7\u2032E, used here as 55.96500, 11.84500. Not a surveyed camera. Nominatim's nearby pin is the harbour station, city Hundested, postcode 3390.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hundested",
                "https://hundestedhavn.dk/en/arrival/",
            ],
            "anchors": [
                "Stone moles around inner basins.",
                "Fishing boats.",
                "Choppy dark water and low harbour buildings.",
            ],
            "solar": clock(rows["DK-01-260"]["_row"]) + " Quay lamps. No readable boat name.",
            "independent": (
                "Hundested harbour sits on the east side of the entrance to the Isefjord. The port's own page describes the old harbour, the fishing basins, and the moles. "
                "The frame uses the old fishing basins, not a cruise-ship portrait."
            ),
            "ip": "No readable boat name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Moles, fishing boats, chop, overcast lamps. No readable name.",
            "swap": "No site swap. Hundested Harbour was not used in DK-01-001 through DK-01-256. City is Hundested.",
        },
        {
            "entry_id": "DK-01-261",
            "region": "Capital Region",
            "city": "Frederiksv\u00e6rk",
            "caption": "Frederiksv\u00e6rk Canal, Frederiksv\u00e6rk",
            **rows["DK-01-261"],
            "composition": "The canal and the long yellow foundry \u00b7 AI-generated artistic interpretation",
            "description": (
                "The canal through Frederiksv\u00e6rk runs past the long yellow foundry, Gjethuset, with a simple bridge and the brick edges of the old works. "
                f"The bank is empty. {sky('DK-01-261')} "
                "Lamps reflect in the still water."
            ),
            "alt_text": "AI-generated artistic interpretation of the Frederiksv\u00e6rk canal before sunrise, the yellow foundry beside dark water",
            "viewpoint": "The canal bank in the town centre, toward Gjethuset. Approximate researched point 55.96667, 12.01667, the town coordinate published on the English Wikipedia page, not a surveyed camera. Nominatim places the town as Frederiksv\u00e6rk, postcode 3300.",
            "refs": [
                "https://en.wikipedia.org/wiki/Frederiksv%C3%A6rk",
                "https://da.wikipedia.org/wiki/Frederiksv%C3%A6rk",
            ],
            "anchors": [
                "A canal through the town.",
                "The long yellow foundry beside the water.",
                "A simple bridge and brick works buildings.",
            ],
            "solar": clock(rows["DK-01-261"]["_row"]) + " Lamps on the water. No readable sign.",
            "independent": (
                "The English article describes Frederiksv\u00e6rk as the canal town founded around Classen's cannon foundry, and names Gjethuset, built 1761\u20131767, as the foundry building. "
                "The frame is that canal view, not Arres\u00f8 and not the gunpowder mill in the woods."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Canal, long yellow foundry, bridge, lamp reflections, overcast. No lettering.",
            "swap": "No site swap. Frederiksv\u00e6rk Canal was not used in DK-01-001 through DK-01-256. City is Frederiksv\u00e6rk.",
        },
        {
            "entry_id": "DK-01-262",
            "region": "Capital Region",
            "city": "Esrum",
            "caption": "Esrum Abbey, Esrum",
            **rows["DK-01-262"],
            "composition": "The long brick convent range and the mill pond \u00b7 AI-generated artistic interpretation",
            "description": (
                "Esrum Abbey is the long red-brick convent range that remains, with a steep dark roof and a mill pond in front. "
                f"The grounds are empty. {sky('DK-01-262')} "
                "It is not a palace, and the church is gone."
            ),
            "alt_text": "AI-generated artistic interpretation of Esrum Abbey before sunrise, a long brick range and a mill pond",
            "viewpoint": "The public side of Esrum Abbey across the mill pond. Approximate researched point 56.04756, 12.37791, not a surveyed camera. Nominatim places Esrum Abbey in Esrum, postcode 3080.",
            "refs": [
                "https://en.wikipedia.org/wiki/Esrum_Abbey",
                "https://da.wikipedia.org/wiki/Esrum_Kloster",
            ],
            "anchors": [
                "A long two-storey red-brick range.",
                "A steep dark roof.",
                "A mill pond, and no standing abbey church.",
            ],
            "solar": clock(rows["DK-01-262"]["_row"]) + " A few path lamps. No readable sign.",
            "independent": (
                "Esrum Abbey is the former Cistercian house at Esrum. What a visitor sees now is the surviving brick convent building and the pond, not a complete church. "
                "Fredensborg Palace is already DK-01-028, so this batch uses the abbey."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Long brick range, dark roof, pond, damp grounds, overcast. Not a palace and not a cathedral.",
            "swap": "Swapped from Fredensborg Palace. That exterior is already DK-01-028, Fredensborg Palace, Fredensborg. The caption is Esrum Abbey. City is Esrum.",
        },
        {
            "entry_id": "DK-01-263",
            "region": "Capital Region",
            "city": "Bagsv\u00e6rd",
            "caption": "Bagsv\u00e6rd Lake, Bagsv\u00e6rd",
            **rows["DK-01-263"],
            "composition": "Reeds, autumn trees, and the public lake shore \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the Aldershvile shore, Bagsv\u00e6rd Lake is dark water, reeds, and trees just turning, with a path lamp or two. "
                f"The shore is empty. {sky('DK-01-263')} "
                "No palace stands in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Bagsv\u00e6rd Lake before sunrise, reeds and autumn trees on the shore",
            "viewpoint": "The public shore at Aldershvile Slotspark, on the Bagsv\u00e6rd side of the lake. Approximate researched point 55.77108, 12.45280, not a surveyed camera. Nominatim's suburb is Bagsv\u00e6rd, in Gladsaxe Municipality. Postcode 2880 is Bagsv\u00e6rd.",
            "refs": [
                "https://en.wikipedia.org/wiki/Bagsv%C3%A6rd",
                "https://da.wikipedia.org/wiki/Bagsv%C3%A6rd_S%C3%B8",
            ],
            "anchors": [
                "A lake shore with reeds.",
                "Autumn trees.",
                "No intact palace in the frame.",
            ],
            "solar": clock(rows["DK-01-263"]["_row"]) + " Path lamps. No readable sign.",
            "independent": (
                "Bagsv\u00e6rd S\u00f8 lies between Bagsv\u00e6rd and Kongens Lyngby. Aldershvile is the public park on the Bagsv\u00e6rd shore. "
                "The requested view is that public shore, not Sorgenfri Palace."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Reeds, dark water, autumn trees, path lamps, overcast. No palace.",
            "swap": "No site swap. Bagsv\u00e6rd Lake was not used in DK-01-001 through DK-01-256. City is Bagsv\u00e6rd.",
        },
        {
            "entry_id": "DK-01-264",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Emil Holms Kanal, Copenhagen",
            **rows["DK-01-264"],
            "composition": "A straight \u00d8restad canal and the round brick residence \u00b7 AI-generated artistic interpretation",
            "description": (
                "Emil Holms Kanal is a straight modern canal in \u00d8restad, with the round brick Tietgenkollegiet, glass university blocks, and a footbridge. "
                f"The quay is empty. {sky('DK-01-264')} "
                "No broadcast logo is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Emil Holms Kanal in Copenhagen before sunrise, a canal and a round brick building",
            "viewpoint": "The quay along Emil Holms Kanal in \u00d8restad, toward the round student residence. Approximate researched point 55.65903, 12.59008, from a published camera position on the canal, not a new survey. Nominatim places the street in Copenhagen.",
            "refs": [
                "https://en.wikipedia.org/wiki/%C3%98restad",
                "https://en.wikipedia.org/wiki/Tietgenkollegiet",
            ],
            "anchors": [
                "A straight urban canal.",
                "The circular brick Tietgenkollegiet.",
                "A footbridge and contemporary blocks, with no broadcast logo.",
            ],
            "solar": clock(rows["DK-01-264"]["_row"]) + " Quay lamps. No readable sign.",
            "independent": (
                "Emil Holms Kanal is the canal through \u00d8restad Nord, with the circular Tietgenkollegiet and the university buildings beside it. "
                "Amager Strandpark's lagoon is already DK-01-081, and the \u00d8resund Bridge is already DK-01-149. This frame is the canal."
            ),
            "ip": "No broadcast logo and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Straight canal, round brick residence, footbridge, glass blocks, overcast lamps. No readable logo.",
            "swap": (
                "Swapped from a second Amager Strandpark view. That lagoon and footbridge are already DK-01-081, Amager Strandpark, Copenhagen, "
                "and the \u00d8resund Bridge is already DK-01-149. The unused alternative is the \u00d8restad canal. "
                "The caption is Emil Holms Kanal. City is Copenhagen."
            ),
        },
        {
            "entry_id": "DK-01-265",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Wilders Kanal, Copenhagen",
            **rows["DK-01-265"],
            "composition": "A narrow canal, warehouses, and gabled houses \u00b7 AI-generated artistic interpretation",
            "description": (
                "Wilders Kanal is a narrow Christianshavn canal with moored boats, brick warehouses, and gabled houses, and a bridge farther along. "
                f"The cobbles are empty. {sky('DK-01-265')} "
                "The spiral church is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Wilders Kanal in Copenhagen before sunrise, boats and gabled warehouses",
            "viewpoint": "The quay on Wilders Kanal beside Wilders Plads. Approximate researched point 55.67390, 12.59550, not a surveyed camera. Nominatim did not return a water polygon under that name; Wilders Plads is the adjacent square in Christianshavn, Copenhagen.",
            "refs": [
                "https://en.wikipedia.org/wiki/Christianshavn",
                "https://en.wikipedia.org/wiki/Wilders_Plads",
            ],
            "anchors": [
                "A narrow canal with moored boats.",
                "Brick warehouses and gabled houses.",
                "A bridge farther down the water, and no spiral church as the subject.",
            ],
            "solar": clock(rows["DK-01-265"]["_row"]) + " Quay lamps. No readable sign.",
            "independent": (
                "Wilders Kanal is the narrower canal east of Christianshavns Kanal, alongside Wilders Plads. "
                "The wider warehouse-and-houseboat view is already DK-01-022, Christianshavn, Copenhagen. The Church of Our Saviour is already DK-01-025 and is not this subject."
            ),
            "ip": "No readable sign and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Narrow canal, boats, gables, warehouses, lamps, overcast. The spiral church is not the subject.",
            "swap": (
                "The broader Christianshavn canal is already DK-01-022, Christianshavn, Copenhagen. "
                "This caption is Wilders Kanal. City is Copenhagen."
            ),
        },
        {
            "entry_id": "DK-01-266",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Sluseholmen, Copenhagen",
            **rows["DK-01-266"],
            "composition": "Modern brick blocks along a canal \u00b7 AI-generated artistic interpretation",
            "description": (
                "Sluseholmen is a canal quarter of modern brick blocks in red, ochre, and dark brick, with small bridges and moored boats. "
                f"The quay is empty. {sky('DK-01-266')} "
                "No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Sluseholmen in Copenhagen before sunrise, brick blocks along a canal",
            "viewpoint": "A public quay in the Sluseholmen neighbourhood, looking along a canal. Approximate researched point 55.64627, 12.54898, not a surveyed camera. Nominatim places the neighbourhood in Copenhagen, postcode 2450.",
            "refs": [
                "https://en.wikipedia.org/wiki/Sluseholmen",
                "https://da.wikipedia.org/wiki/Sluseholmen",
            ],
            "anchors": [
                "Canals between modern brick apartment blocks.",
                "Red, ochre, and dark brick.",
                "Small bridges and boats without readable names.",
            ],
            "solar": clock(rows["DK-01-266"]["_row"]) + " Quay lamps. No readable boat name.",
            "independent": (
                "Sluseholmen is the canal island quarter in Copenhagen's South Harbour, built with varied brick blocks along the water. "
                "The Islands Brygge harbour bath is already DK-01-026, so this frame moves south to Sluseholmen."
            ),
            "ip": "No readable boat name and no developer logo. Internal review only, not a legal certification.",
            "visual": "Pass. Canal, coloured brick blocks, bridges, boats, overcast lamps. No lettering.",
            "swap": "Swapped from Islands Brygge. That harbour-bath exterior is already DK-01-026, Islands Brygge, Copenhagen. The caption is Sluseholmen. City is Copenhagen.",
        },
        {
            "entry_id": "DK-01-267",
            "region": "Capital Region",
            "city": "Charlottenlund",
            "caption": "Charlottenlund Fort, Charlottenlund",
            **rows["DK-01-267"],
            "composition": "Grass ramparts and a low brick battery by the beach \u00b7 AI-generated artistic interpretation",
            "description": (
                "Charlottenlund Fort is a low grass-covered coastal battery and brick rampart beside a narrow beach, with the \u00d8resund in front. "
                f"The beach is empty. {sky('DK-01-267')} "
                "This is not the yellow palace inland."
            ),
            "alt_text": "AI-generated artistic interpretation of Charlottenlund Fort before sunrise, grass ramparts beside the \u00d8resund",
            "viewpoint": "The seaward side of Charlottenlund Fort, looking across the beach to the \u00d8resund. Approximate researched point 55.74582, 12.58708, not a surveyed camera. Nominatim's locality is Skovshoved, suburb Charlottenlund, postcode 2920. The caption city is Charlottenlund, the same postal town as the palace card.",
            "refs": [
                "https://da.wikipedia.org/wiki/Charlottenlund_Fort",
                "https://en.wikipedia.org/wiki/Charlottenlund",
            ],
            "anchors": [
                "Low grass-covered ramparts.",
                "A brick coastal battery.",
                "A narrow beach and the \u00d8resund, and no yellow palace.",
            ],
            "solar": clock(rows["DK-01-267"]["_row"]) + " A few lamps. No flag and no readable sign.",
            "independent": (
                "Charlottenlund Fort is the late-19th-century coastal battery on the \u00d8resund, north of Copenhagen. The grass-covered ramparts and the beach are the visitor view. "
                "Charlottenlund Palace is already DK-01-085 and stands inland."
            ),
            "ip": "No flag treated as a logo and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Grass ramparts, low brick battery, beach, dark water, overcast. Not the palace.",
            "swap": "Charlottenlund Palace is already DK-01-085, Charlottenlund Palace, Charlottenlund. This caption is the coastal fort. City is Charlottenlund.",
        },
        {
            "entry_id": "DK-01-268",
            "region": "Capital Region",
            "city": "Vedb\u00e6k",
            "caption": "Vedb\u00e6k Harbour, Vedb\u00e6k",
            **rows["DK-01-268"],
            "composition": "A small marina, covered boats, and the \u00d8resund \u00b7 AI-generated artistic interpretation",
            "description": (
                "Vedb\u00e6k harbour is a small marina of wooden piers and covered sailboats, with low pale houses and the \u00d8resund beyond the mole. "
                f"The quay is empty. {sky('DK-01-268')} "
                "No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Vedb\u00e6k harbour before sunrise, a marina and pale houses under cloud",
            "viewpoint": "The public quay at Vedb\u00e6k Havn. Approximate researched point 55.84964, 12.57247, not a surveyed camera. Nominatim places the marina in Vedb\u00e6k, postcode 2942.",
            "refs": [
                "https://en.wikipedia.org/wiki/Vedb%C3%A6k",
                "https://da.wikipedia.org/wiki/Vedb%C3%A6k",
            ],
            "anchors": [
                "Wooden marina piers.",
                "Sailboats under covers.",
                "Low pale houses and open water beyond the mole.",
            ],
            "solar": clock(rows["DK-01-268"]["_row"]) + " Quay lamps. No readable boat name.",
            "independent": (
                "Vedb\u00e6k is the coastal town on the \u00d8resund between Skodsborg and Rungsted, with a small yacht harbour. "
                "Rungsted Harbour is already DK-01-151. This frame is Vedb\u00e6k."
            ),
            "ip": "No readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Piers, covered boats, pale houses, mole, overcast lamps. No lettering.",
            "swap": "No site swap. Vedb\u00e6k Harbour was not used in DK-01-001 through DK-01-256. City is Vedb\u00e6k.",
        },
        {
            "entry_id": "DK-01-269",
            "region": "Capital Region",
            "city": "Raadvad",
            "caption": "Raadvad Mill, Raadvad",
            **rows["DK-01-269"],
            "composition": "Brick and timber mill buildings along the river \u00b7 AI-generated artistic interpretation",
            "description": (
                "Raadvad Mill is red-brick and white-timber buildings with tiled roofs along the M\u00f8lle\u00e5en and a mill race, under autumn trees. "
                f"The lane is empty. {sky('DK-01-269')} "
                "No brand lettering is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Raadvad Mill before sunrise, brick and timber buildings along a river",
            "viewpoint": "The lane through the Raadvad mill yard, looking along the river. Approximate researched point 55.80528, 12.55944, the coordinate published for the village, not a surveyed camera. Nominatim's administrative city is Kongens Lyngby. The settlement name is Raadvad, and that is the caption city.",
            "refs": [
                "https://en.wikipedia.org/wiki/Raadvad",
                "https://da.wikipedia.org/wiki/Raadvad_M%C3%B8lle",
            ],
            "anchors": [
                "Red-brick and white-timber mill buildings.",
                "A narrow river and mill race.",
                "Tiled roofs and autumn trees, with no brand lettering.",
            ],
            "solar": clock(rows["DK-01-269"]["_row"]) + " A few warm windows. No readable sign.",
            "independent": (
                "The English article describes Raadvad as the former mill village on the M\u00f8lle\u00e5en, built around a watermill, with listed brick and timber buildings. "
                "The Danish article is specifically the mill. A knife brand shares the name; no wordmark is the subject."
            ),
            "ip": "No brand wordmark and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Mill buildings, river, tiled roofs, autumn trees, overcast. No lettering.",
            "swap": "No site swap. Raadvad Mill was not used in DK-01-001 through DK-01-256. City is Raadvad, the settlement name.",
        },
        {
            "entry_id": "DK-01-270",
            "region": "Zealand",
            "city": "Roskilde",
            "caption": "Boserup Forest, Roskilde",
            **rows["DK-01-270"],
            "composition": "Beeches and a path along the fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                "Boserup forest meets Roskilde Fjord as a dirt path, tall beeches with the first autumn colour, and dark water. "
                f"Nobody is on the path. {sky('DK-01-270')} "
                "There is no harbour and no town."
            ),
            "alt_text": "AI-generated artistic interpretation of Boserup forest on Roskilde Fjord before sunrise, beeches along dark water",
            "viewpoint": "The public shore path where Boserup Skov meets Roskilde Fjord. The weather pin is the forest centroid, 55.66266, 12.03980, from Nominatim, which places the forest in Roskilde. The exact camera point on the shore was not surveyed.",
            "refs": [
                "https://en.wikipedia.org/wiki/Roskilde_Fjord",
                "https://da.wikipedia.org/wiki/Boserup_Skov",
            ],
            "anchors": [
                "Tall beeches with early autumn colour.",
                "A dirt path.",
                "Dark fjord water and no harbour.",
            ],
            "solar": clock(rows["DK-01-270"]["_row"]) + " No lamps and no sign.",
            "independent": (
                "Boserup Skov is the beech forest on the western shore of Roskilde Fjord, northwest of the town. "
                "Roskilde Harbour is already DK-01-167, and the cathedral and the Viking Ship Museum are earlier cards. This frame stays on the forest shore."
            ),
            "ip": "No sign. Internal review only, not a legal certification.",
            "visual": "Pass. Beeches, path, dark fjord, overcast, empty. No harbour.",
            "swap": "Roskilde Harbour is already DK-01-167, Roskilde Harbour, Roskilde. This caption is Boserup Forest. City is Roskilde.",
        },
        {
            "entry_id": "DK-01-271",
            "region": "Zealand",
            "city": "Lejre",
            "caption": "Ledreborg Palace, Lejre",
            **rows["DK-01-271"],
            "composition": "A pale yellow baroque manor and an autumn court \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ledreborg is a pale yellow baroque manor with a central block and lower wings, a gravel court, and autumn lawns. "
                f"The court is empty. {sky('DK-01-271')} "
                "These are not the iron-age houses at Sagnlandet."
            ),
            "alt_text": "AI-generated artistic interpretation of Ledreborg Palace near Lejre before sunrise, a yellow baroque manor",
            "viewpoint": "The public court in front of Ledreborg, looking at the garden facade. Approximate researched point 55.60546, 11.95037, not a surveyed camera. One Nominatim hit on the manor said Allerslev. Ledreborg All\u00e9 returned city Lejre, postcode 4320. The caption city is Lejre.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ledreborg",
                "https://da.wikipedia.org/wiki/Ledreborg",
            ],
            "anchors": [
                "A pale yellow central block and lower wings.",
                "A gravel court and autumn lawns.",
                "No iron-age reconstructions.",
            ],
            "solar": clock(rows["DK-01-271"]["_row"]) + " A few facade lamps. No readable sign.",
            "independent": (
                "Ledreborg is the baroque country house west of Lejre, with a formal garden axis. "
                "Sagnlandet Lejre, the open-air ancient-house landscape, is already DK-01-168. This frame is the palace exterior."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow baroque manor, wings, gravel court, autumn lawn, overcast. Not iron-age huts.",
            "swap": "Sagnlandet Lejre is already DK-01-168, Sagnlandet Lejre, Lejre. This caption is Ledreborg Palace. City is Lejre.",
        },
        {
            "entry_id": "DK-01-272",
            "region": "Zealand",
            "city": "Or\u00f8",
            "caption": "Or\u00f8 Harbour, Or\u00f8",
            **rows["DK-01-272"],
            "composition": "A short mole, a few boats, and a plain ferry \u00b7 AI-generated artistic interpretation",
            "description": (
                "Or\u00f8 harbour is a short mole, a few boats, low houses, and one plain ferry on the dark fjord. "
                f"The quay is empty. {sky('DK-01-272')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Or\u00f8 harbour before sunrise, a small mole and a plain ferry",
            "viewpoint": "The ferry quay at Or\u00f8 Havn. Approximate researched point 55.75586, 11.80087, not a surveyed camera. Nominatim's hamlet at the quay is Br\u00f8nde, postcode 4305. That postcode is Or\u00f8, and the caption city is Or\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Or%C3%B8",
                "https://da.wikipedia.org/wiki/Or%C3%B8",
            ],
            "anchors": [
                "A short mole and a small basin.",
                "A few boats and one plain ferry.",
                "Low houses and dark fjord water.",
            ],
            "solar": clock(rows["DK-01-272"]["_row"]) + " Quay lamps. No readable ferry name.",
            "independent": (
                "Or\u00f8 is the island in Holb\u00e6k Fjord. The harbour at Br\u00f8nde is the ferry quay on the island. "
                "Holb\u00e6k Harbour is already DK-01-088, and Ahlgade is DK-01-169. This frame is the island quay. Postcode 4305 is Or\u00f8."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, boats, plain ferry, low houses, dark water, overcast lamps. No lettering.",
            "swap": "Holb\u00e6k Harbour is already DK-01-088 and Ahlgade, Holb\u00e6k is DK-01-169. This caption is Or\u00f8 Harbour. City is Or\u00f8. The quay hamlet is Br\u00f8nde; the postal town is Or\u00f8.",
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


def verify_baked_text(scene: dict, label: str) -> None:
    caption = scene["caption"]
    for kind, path in scene["_files"].items():
        txt = subprocess.check_output(
            ["tesseract", str(path), "stdout", "--psm", "6"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        if "Jason" not in txt or "Vision" not in txt:
            raise SystemExit(f"signature OCR {path}\n{txt}")
        if kind == "16x9":
            if "Scenario" not in txt:
                raise SystemExit(f"scenario OCR {path}\n{txt}")
            if "artistic" not in txt and "photograph" not in txt:
                raise SystemExit(f"disclosure OCR {path}\n{txt}")
        # Tesseract misreads ø/æ/å, so match a 4-letter ASCII stem from the caption.
        stems = []
        for word in caption.replace(",", " ").split():
            ascii_word = "".join(ch for ch in word if ch.isascii() and ch.isalpha())
            if len(ascii_word) >= 4:
                stems.append(ascii_word[:4])
        if stems and not any(stem in txt for stem in stems):
            raise SystemExit(f"caption OCR {path} missing {stems!r}\n{txt}")
        if "\u2019" not in bd.SIG:
            raise SystemExit("signature constant lost the curly apostrophe")
        _ = kind, label


def main() -> None:
    prepare_raws()
    batch = scenes()
    if len(batch) != 16:
        raise SystemExit(len(batch))
    lines = []
    masters: list[Path] = []
    for scene in batch:
        label = bd.scenario_label(scene["entry_id"])
        hour = label.split("\u00b7")[1].strip().split(" ")[0]
        if not hour.startswith("06:"):
            raise SystemExit(f"{scene['entry_id']} scenario {label} outside valid hour 06")
        minute = int(hour.split(":")[1])
        if minute < 45 or minute > 59:
            raise SystemExit(f"{scene['entry_id']} scenario {label} outside 06:45 step")
        sunrise = scene["_row"]["sunrise"]
        if hour >= sunrise[11:16]:
            raise SystemExit(f"{scene['entry_id']} scenario {hour} not before sunrise {sunrise}")
        if "25 September 2026" not in label:
            raise SystemExit(label)
        retrieved = datetime.fromisoformat(scene["_row"]["retrieved_iso"])
        # The later JPEG mtime is the scenario clock. It must be after this scene's own retrieval.
        jpeg_times = []
        for kind in ("16x9", "4x5"):
            jpeg_times.append(os.path.getmtime(bd.RAW / f"{scene['entry_id'].lower()}-{kind}.png"))
        scenario_dt = datetime.fromtimestamp(max(jpeg_times), bd.CPH)
        if scenario_dt <= retrieved:
            raise SystemExit(f"{scene['entry_id']} scenario {scenario_dt} not after retrieval {retrieved}")
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
    if len(all_scenes) != 272:
        raise SystemExit(f"expected 272 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 273)]
    if ids != expected:
        raise SystemExit("id sequence mismatch")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    descriptions = [item["_manifest"]["description"] for item in all_scenes]
    if len(descriptions) != len(set(descriptions)):
        raise SystemExit("duplicate description")
    for item in all_scenes:
        if item["_manifest"].get("approval_status") not in (None, "Candidate"):
            raise SystemExit(f"status {item['_manifest']['entry_id']}")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-257-272.txt"
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

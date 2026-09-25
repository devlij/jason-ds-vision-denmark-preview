#!/usr/bin/env python3
"""Bake DK-01-273 through DK-01-288 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-273-288.json.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-273-288.json").read_text(encoding="utf-8"))

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def sky_word(code: int) -> str:
    table = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}
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
    hm = valid[11:16]
    return (
        "The model-valid hour is 07:00\u201307:59 Europe/Copenhagen. "
        f"The cited model time is the {hm} step (interval 900 seconds)."
    )


def pack(entry: str) -> dict:
    row = WX[entry]
    local_valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=timezone(timedelta(seconds=7200)))
    alt_step = sun_alt(row["lat"], row["lon"], local_valid.astimezone(timezone.utc))
    code = int(row["code"])
    word = sky_word(code)
    temp = float(row["temp"])
    wind = float(row["wind"])
    precip = float(row["precip"])
    snow = float(row["snow"])
    if not str(row["valid"]).startswith("2026-09-25T07:"):
        raise SystemExit(f"{entry} valid {row['valid']}")
    if not str(row["retrieved"]).startswith("2026-09-25T07:"):
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


def light(row: dict) -> str:
    if row["cloud"] >= 80:
        return "The cloud deck softens the morning light."
    if row["code"] == 0:
        return "Low morning sun, long shadows."
    if row["code"] == 1:
        return "The morning sun is low under a mainly clear sky."
    return "Broken cloud partly veils the low morning sun."


def wind_clause(row: dict) -> str:
    w = row["wind_f"]
    if w >= 40:
        return f"The wind is strong, about {row['wind']} km/h."
    if w >= 20:
        return f"The wind is fresh, about {row['wind']} km/h."
    return f"The wind is light, about {row['wind']} km/h."


def solar_text(row: dict, scenario_dt: datetime) -> str:
    alt = sun_alt(row["lat"], row["lon"], scenario_dt.astimezone(timezone.utc))
    sunset = nice_time(row["sunset"])
    sunrise = nice_time(row["sunrise"])
    text = (
        "After today's sunrise. "
        f"Sunset on {sunset} Europe/Copenhagen and sunrise on {sunrise} Europe/Copenhagen. "
        f"A computed sun altitude of about {alt:.1f}\u00b0 at the scenario minute "
        "(low morning sun), not an on-site observation. "
    )
    if row["is_day"] == 0:
        text += (
            "The cited 07:00 model step is flagged is_day 0 because that step is before sunrise. "
            "The scenario minute is after sunrise, so the frame is first daylight, not lamplight. "
        )
    else:
        text += "The cited model step is flagged is_day 1. "
    text += f"Cloud cover {row['cloud']}%. "
    text += (
        "The scenario minute has to fall inside this scene's own model-valid hour, "
        "07:00\u201307:59 Europe/Copenhagen, and at or after the cited model step."
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


def scenario_dt(entry_id: str) -> datetime:
    times = []
    for kind in ("16x9", "4x5"):
        times.append(os.path.getmtime(bd.RAW / f"{entry_id.lower()}-{kind}.png"))
    return datetime.fromtimestamp(max(times), bd.CPH)


bd.scenario_label = scenario_label


def prepare_raws() -> None:
    for n in range(273, 289):
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

    rows = {f"DK-01-{n}": base(f"DK-01-{n}") for n in range(273, 289)}

    def sky(entry: str) -> str:
        row = rows[entry]
        return (
            f"It is {row['word'].lower()}, about {row['temp']}\u00b0C. "
            f"{wind_clause(row['_row'])} {light(row['_row'])}"
        )

    return [
        {
            "entry_id": "DK-01-273",
            "region": "Funen",
            "city": "Spodsbjerg",
            "caption": "Spodsbjerg Harbour, Spodsbjerg",
            **rows["DK-01-273"],
            "composition": "The east-coast ferry berth and a plain white ferry \u00b7 AI-generated artistic interpretation",
            "description": (
                "Spodsbjerg harbour is the ferry berth on the east coast of Langeland, with one plain white vehicle ferry, a stone quay, and low red-tiled houses. "
                f"The quay is empty. {sky('DK-01-273')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Spodsbjerg ferry harbour just after sunrise, a plain white ferry and red roofs",
            "viewpoint": "The ferry quay at Spodsbjerg F\u00e6rgehavn, looking across the berth. Approximate researched point 54.93502, 10.83312, not a surveyed camera. Open-Meteo ran this request on grid 54.94004, 10.83264. Nominatim places the terminal in Spodsbjerg.",
            "refs": [
                "https://en.wikipedia.org/wiki/Spodsbjerg",
                "https://da.wikipedia.org/wiki/Spodsbjerg",
            ],
            "anchors": [
                "A stone ferry berth on the east coast.",
                "One plain white vehicle ferry without a readable name.",
                "Low red-tiled houses behind the quay.",
            ],
            "independent": (
                "Spodsbjerg is the Langeland village with the ferry across the Langelandsb\u00e6lt toward T\u00e5rs. "
                "Rudk\u00f8bing Harbour is already DK-01-108, so this frame uses the east-coast ferry harbour instead."
            ),
            "ip": "No readable ferry name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Ferry berth, plain white ferry, red roofs, clear low morning light. No lettering.",
            "swap": "Swapped from Rudk\u00f8bing Harbour. That basin is already DK-01-108, Rudk\u00f8bing Harbour, Rudk\u00f8bing. The unused Langeland alternative is the east-coast ferry harbour. The caption is Spodsbjerg Harbour. City is Spodsbjerg.",
        },
        {
            "entry_id": "DK-01-274",
            "region": "Funen",
            "city": "Ristinge",
            "caption": "Ristinge Klint, Ristinge",
            **rows["DK-01-274"],
            "composition": "A layered coastal cliff, grass crown, and a stony beach \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ristinge Klint is the coastal cliff on south Langeland, seen from the stony beach: a grass crown, a pale layered face, and open sea beside the shore. "
                f"The beach is empty. {sky('DK-01-274')} "
                "There is no building in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Ristinge Klint just after sunrise, a layered cliff above a stony beach",
            "viewpoint": "The beach below Ristinge Klint, looking along the cliff. Approximate researched point 54.82883, 10.60764, not a surveyed camera. Open-Meteo ran this request on grid 54.82000, 10.60000. Nominatim places the cliff in Ristinge.",
            "refs": [
                "https://da.wikipedia.org/wiki/Ristinge_Klint",
                "https://en.wikipedia.org/wiki/Langeland",
            ],
            "anchors": [
                "A grass-topped coastal cliff.",
                "A pale layered sand-and-clay face.",
                "A stony beach and open sea, with no building.",
            ],
            "independent": (
                "Ristinge Klint is the ice-age cliff on the Ristinge peninsula, south Langeland. "
                "Tranek\u00e6r Castle is already DK-01-109, so this frame uses the cliff instead of the castle."
            ),
            "ip": "No sign and no flag. Internal review only, not a legal certification.",
            "visual": "Pass. Layered cliff, grass, beach, broken cloud, empty shore. No lettering.",
            "swap": "Swapped from Tranek\u00e6r Castle. That exterior is already DK-01-109, Tranek\u00e6r Castle, Tranek\u00e6r. The unused south-Langeland alternative is the cliff. The caption is Ristinge Klint. City is Ristinge.",
        },
        {
            "entry_id": "DK-01-275",
            "region": "Funen",
            "city": "Lohals",
            "caption": "Lohals Harbour, Lohals",
            **rows["DK-01-275"],
            "composition": "Stone moles, small boats, and a white lighthouse \u00b7 AI-generated artistic interpretation",
            "description": (
                "Lohals harbour is the small basin at the north end of Langeland, with stone moles, a few boats, a modest white lighthouse, and red-tiled houses by the open sea. "
                f"The quay is empty. {sky('DK-01-275')} "
                "No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Lohals harbour just after sunrise, moles and a white lighthouse",
            "viewpoint": "The public quay at Lohals Havn, with Lohals Fyr at the entrance. Approximate researched point 55.13555, 10.90285, not a surveyed camera. Open-Meteo ran this request on grid 55.13916, 10.90381. Nominatim places the harbour and the lighthouse in Lohals.",
            "refs": [
                "https://da.wikipedia.org/wiki/Lohals",
                "https://en.wikipedia.org/wiki/Langeland",
            ],
            "anchors": [
                "Stone moles around a small basin.",
                "A modest white lighthouse at the entrance.",
                "A few boats, red-tiled houses, and open sea.",
            ],
            "independent": (
                "Lohals is the harbour village at the north end of Langeland. Lohals Fyr stands at the harbour. "
                "This is not Rudk\u00f8bing and not the east-coast ferry at Spodsbjerg."
            ),
            "ip": "No readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Moles, boats, white lighthouse, red roofs, clear morning light. No lettering.",
            "swap": "No site swap. Lohals Harbour was not used in DK-01-001 through DK-01-272. City is Lohals.",
        },
        {
            "entry_id": "DK-01-276",
            "region": "Funen",
            "city": "Thur\u00f8",
            "caption": "Thur\u00f8 Harbour, Thur\u00f8",
            **rows["DK-01-276"],
            "composition": "Wooden marina piers in sheltered Thur\u00f8 Bund \u00b7 AI-generated artistic interpretation",
            "description": (
                "Thur\u00f8 harbour is the marina in sheltered Thur\u00f8 Bund: wooden piers, sailboats, calm water, and low red-roofed houses with trees behind. "
                f"The quay is empty. {sky('DK-01-276')} "
                "There is no car ferry. The island is joined to Funen by a causeway."
            ),
            "alt_text": "AI-generated artistic interpretation of Thur\u00f8 harbour just after sunrise, wooden piers and sailboats in a sheltered bay",
            "viewpoint": "The quay at Gamb\u00f8t Lystb\u00e5dehavn in Thur\u00f8 Bund. Approximate researched point 55.04182, 10.66842, not a surveyed camera. Open-Meteo ran this request on grid 55.04087, 10.66533. Nominatim's locality is Thur\u00f8 By, postcode 5881. The caption city is Thur\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Thur%C3%B8",
                "https://thuroebundmarina.dk/",
            ],
            "anchors": [
                "Wooden marina piers and sailboats.",
                "Sheltered water, not an open ferry berth.",
                "Low houses and trees, and no car ferry.",
            ],
            "independent": (
                "Thur\u00f8 is linked to Funen by a causeway. Thur\u00f8bund Marina describes Gamb\u00f8t as a recreational harbour in Thur\u00f8 Bund, not a scheduled ferry quay. "
                "Svendborg Harbour is already DK-01-037. This frame stays on Thur\u00f8."
            ),
            "ip": "No club logo and no readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Wooden piers, sailboats, sheltered water, red roofs, clear morning light. No ferry and no lettering.",
            "swap": "The suggested ferry quay is not an operating ferry. Thur\u00f8 is joined to Funen by a causeway, and the harbour is the Gamb\u00f8t marina in Thur\u00f8 Bund. The caption is Thur\u00f8 Harbour. City is Thur\u00f8.",
        },
        {
            "entry_id": "DK-01-277",
            "region": "Funen",
            "city": "Vindeby",
            "caption": "Vindeby Harbour, Vindeby",
            **rows["DK-01-277"],
            "composition": "A small marina on the narrow sound \u00b7 AI-generated artistic interpretation",
            "description": (
                "Vindeby harbour is a small marina on the T\u00e5singe side of Svendborgsund, with a stone mole, wooden piers, a few sailboats, and low houses. "
                f"The quay is empty. {sky('DK-01-277')} "
                "There is no vehicle ferry. The car ferry ended in 1966."
            ),
            "alt_text": "AI-generated artistic interpretation of Vindeby harbour just after sunrise, a marina on the narrow sound",
            "viewpoint": "The public quay at Vindeby Havn. Approximate researched point 55.04948, 10.61509, not a surveyed camera. Open-Meteo ran this request on grid 55.04795, 10.61771. Nominatim's city field is Svendborg and the postcode is 5700; the address locality is Vindeby. The caption city is Vindeby.",
            "refs": [
                "https://www.svendborghistorie.dk/faerger-og-faergeruter/504-vindeby-overfarten",
                "http://vindebyhavn.dk/gaestesejler/",
            ],
            "anchors": [
                "A stone mole and wooden piers.",
                "A few sailboats on a narrow sound.",
                "Low houses, and no vehicle ferry.",
            ],
            "independent": (
                "The Vindeby\u2013Svendborg car ferry ended when Svendborgsundbroen opened on 18 November 1966. The harbour is now a marina. "
                "Valdemars Slot is already DK-01-155, and Bregninge Church is already DK-01-202. This frame is the present harbour, not an operating ferry."
            ),
            "ip": "No readable boat name and no ferry company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, mole, sailboats, low houses, clear morning light. No vehicle ferry and no lettering.",
            "swap": "Valdemars Slot, Troense is already DK-01-155, and Bregninge Church is already DK-01-202. The preferred site is Vindeby. The car ferry ended in 1966, so the caption is Vindeby Harbour, the present marina, not an operating ferry quay. City is Vindeby.",
        },
        {
            "entry_id": "DK-01-278",
            "region": "Funen",
            "city": "Voderup",
            "caption": "Voderup Klint, Voderup",
            **rows["DK-01-278"],
            "composition": "Stepped grassy terraces above a stony beach \u00b7 AI-generated artistic interpretation",
            "description": (
                "Voderup Klint is the stepped grassy landslide on the west coast of \u00c6r\u00f8, dropping toward a stony beach and the sea, with no town in the frame. "
                f"The terraces are empty. {sky('DK-01-278')} "
                "This is not the white village church at Rise."
            ),
            "alt_text": "AI-generated artistic interpretation of Voderup Klint just after sunrise, stepped grassy terraces above the sea",
            "viewpoint": "The public viewpoint at Voderup Klint, looking over the terraces toward the sea. Approximate researched point 54.86600, 10.33474, not a surveyed camera. Open-Meteo ran this request on grid 54.88000, 10.34000. Nominatim lists the hamlet Voderup and the village Vindeballe, postcode 5970. The caption city is Voderup.",
            "refs": [
                "https://da.wikipedia.org/wiki/Voderup_Klint",
                "https://en.wikipedia.org/wiki/%C3%86r%C3%B8",
            ],
            "anchors": [
                "Stepped grassy terraces.",
                "A stony beach and the sea below.",
                "No town and no church.",
            ],
            "independent": (
                "Voderup Klint is the grassy landslide terraces on the west coast of \u00c6r\u00f8. "
                "S\u00f8by Harbour is already DK-01-200. Rise Church was the other unused option; this frame uses the cliff."
            ),
            "ip": "No sign. Internal review only, not a legal certification.",
            "visual": "Pass. Stepped grass terraces, beach, sea, broken cloud, empty. No church and no lettering.",
            "swap": "S\u00f8by Harbour is already DK-01-200, S\u00f8by Harbour, S\u00f8by. The unused alternatives were Rise Church and Voderup Klint. This caption is Voderup Klint. City is Voderup. The parish village is Vindeballe.",
        },
        {
            "entry_id": "DK-01-279",
            "region": "Funen",
            "city": "Ly\u00f8",
            "caption": "Ly\u00f8 Harbour, Ly\u00f8",
            **rows["DK-01-279"],
            "composition": "A short mole and a plain island ferry \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ly\u00f8 harbour is a short stone mole and a small basin, with one plain white ferry, a few boats, and low cottages behind the quay. "
                f"The quay is empty. {sky('DK-01-279')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Ly\u00f8 harbour just after sunrise, a short mole and a plain ferry",
            "viewpoint": "The ferry quay at Ly\u00f8 Havn. Approximate researched point 55.05227, 10.15863, not a surveyed camera. Open-Meteo ran this request on grid 55.04723, 10.16545. Nominatim's hamlet at the quay is B\u00e5dsted, postcode 5601. The caption city is Ly\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ly%C3%B8",
                "https://da.wikipedia.org/wiki/Ly%C3%B8",
            ],
            "anchors": [
                "A short stone mole and a small basin.",
                "One plain white ferry without a readable name.",
                "Low cottages behind the quay.",
            ],
            "independent": (
                "Ly\u00f8 is the island south of Faaborg. The harbour at B\u00e5dsted is the ferry quay. "
                "Faaborg Harbour is already DK-01-039. This frame is the island quay."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Short mole, plain ferry, cottages, mainly clear morning light. No lettering.",
            "swap": "No site swap. Ly\u00f8 Harbour was not used in DK-01-001 through DK-01-272. City is Ly\u00f8. The quay hamlet is B\u00e5dsted.",
        },
        {
            "entry_id": "DK-01-280",
            "region": "Funen",
            "city": "Avernak\u00f8",
            "caption": "Avernak\u00f8 Harbour, Avernak\u00f8",
            **rows["DK-01-280"],
            "composition": "A marina and a plain ferry on the northwest tip \u00b7 AI-generated artistic interpretation",
            "description": (
                "Avernak\u00f8 harbour is the marina on the northwest tip, with wooden piers, a few sailboats, and one plain white ferry beside a low green shore. "
                f"The quay is empty. {sky('DK-01-280')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Avernak\u00f8 harbour just after sunrise, a marina and a plain ferry",
            "viewpoint": "The quay at Avernak\u00f8 B\u00e5dehavn. Havneguide publishes 55.03977, 10.25314, used as the researched point, not a surveyed camera. Open-Meteo ran this request on grid 55.03342, 10.26083. The postal address is often given as Faaborg, postcode 5600. The caption city is Avernak\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Avernak%C3%B8",
                "https://www.havneguide.dk/en/havn/avernako-badehavn",
            ],
            "anchors": [
                "A small marina with wooden piers.",
                "One plain white ferry without a readable name.",
                "A low green shore, not a town skyline.",
            ],
            "independent": (
                "Avernak\u00f8 lies south of Faaborg. The harbour on the northwest tip is beside the ferry to Faaborg and Ly\u00f8. "
                "The island was once two islands, joined in 1937 by the Drejet causeway. That causeway is not the subject of this harbour frame."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, plain ferry, low shore, mainly clear morning light. No lettering.",
            "swap": "No site swap. Avernak\u00f8 Harbour was not used in DK-01-001 through DK-01-272. City is Avernak\u00f8.",
        },
        {
            "entry_id": "DK-01-281",
            "region": "Funen",
            "city": "Drej\u00f8",
            "caption": "Drej\u00f8 Harbour, Drej\u00f8",
            **rows["DK-01-281"],
            "composition": "A small mole, a plain ferry, and a flat green island \u00b7 AI-generated artistic interpretation",
            "description": (
                "Drej\u00f8 harbour is a small stone mole on a flat green island, with one plain white ferry, a few boats, and a handful of low houses. "
                f"The quay is empty. {sky('DK-01-281')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Drej\u00f8 harbour just after sunrise, a small mole and a plain ferry",
            "viewpoint": "The ferry quay at Drej\u00f8 Havn. Approximate researched point 54.96578, 10.43651, not a surveyed camera. Open-Meteo ran this request on grid 54.96876, 10.42480. Nominatim's hamlet is Drej\u00f8 By. The caption city is Drej\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Drej%C3%B8",
                "https://da.wikipedia.org/wiki/Drej%C3%B8",
            ],
            "anchors": [
                "A small stone mole.",
                "One plain white ferry without a readable name.",
                "Flat green fields and a few low houses.",
            ],
            "independent": (
                "Drej\u00f8 is the island west of Skar\u00f8, with the ferry from Svendborg. "
                "Svendborg Harbour is already DK-01-037. This frame is the island harbour."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Small mole, plain ferry, flat island, mainly clear morning light. No lettering.",
            "swap": "No site swap. Drej\u00f8 Harbour was not used in DK-01-001 through DK-01-272. City is Drej\u00f8.",
        },
        {
            "entry_id": "DK-01-282",
            "region": "Funen",
            "city": "Stryn\u00f8",
            "caption": "Stryn\u00f8 Harbour, Stryn\u00f8",
            **rows["DK-01-282"],
            "composition": "A harbour at the end of a long causeway \u00b7 AI-generated artistic interpretation",
            "description": (
                "Stryn\u00f8 harbour sits at the end of a long low causeway, with a small marina, one plain white ferry, and a few boats in open water. "
                f"The quay is empty. {sky('DK-01-282')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Stryn\u00f8 harbour just after sunrise, a causeway and a plain ferry",
            "viewpoint": "The harbour head at the end of the Stryn\u00f8 causeway. Havnelods and marina listings place it near 54.90330, 10.62993, used as the researched point, not a surveyed camera. Open-Meteo ran this request on grid 54.90508, 10.61914. The village is Stryn\u00f8 By, postcode 5943. The caption city is Stryn\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Stryn%C3%B8",
                "https://havnelods.dk/havne/strynoe-havn",
            ],
            "anchors": [
                "A long low causeway out to the harbour.",
                "A small marina and one plain white ferry.",
                "Open water around the pier head.",
            ],
            "independent": (
                "Stryn\u00f8 is the island between T\u00e5singe and Langeland. Havnelods describes the marina at the end of a 315 m causeway, with a ferry berth leisure boats must not use. "
                "Rudk\u00f8bing Harbour is already DK-01-108. This frame is the island harbour."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Causeway, marina, plain ferry, mainly clear morning light. No lettering.",
            "swap": "No site swap. Stryn\u00f8 Harbour was not used in DK-01-001 through DK-01-272. City is Stryn\u00f8.",
        },
        {
            "entry_id": "DK-01-283",
            "region": "Zealand",
            "city": "Om\u00f8",
            "caption": "Om\u00f8 Harbour, Om\u00f8",
            **rows["DK-01-283"],
            "composition": "The Kirkehavn quay, a plain ferry, and a white church \u00b7 AI-generated artistic interpretation",
            "description": (
                "Om\u00f8 harbour at Kirkehavn is a small quay with one plain white ferry, fishing boats, and a simple white church among low houses. "
                f"The quay is empty. {sky('DK-01-283')} "
                "The water is choppy. No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Om\u00f8 harbour just after sunrise, a quay, a plain ferry, and a white church",
            "viewpoint": "The quay at Om\u00f8 Havn in Kirkehavn. Approximate researched point 55.17104, 11.16105, not a surveyed camera. Open-Meteo ran this request on grid 55.16631, 11.16663. Nominatim's hamlet is Kirkehavn, in Om\u00f8 By, postcode 4245. The caption city is Om\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Om%C3%B8",
                "https://da.wikipedia.org/wiki/Om%C3%B8",
            ],
            "anchors": [
                "A small ferry quay and marina.",
                "One plain white ferry without a readable name.",
                "A white church set among low houses.",
            ],
            "independent": (
                "Om\u00f8 is the island in Sm\u00e5landsfarvandet, in Slagelse Municipality. Kirkehavn is the harbour village, with the church near the quay. "
                "The ferry runs toward Stigsn\u00e6s. This is Zealand, not Funen."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Quay, plain ferry, white church, chop, mainly clear morning light. No lettering.",
            "swap": "No site swap. Om\u00f8 Harbour was not used in DK-01-001 through DK-01-272. City is Om\u00f8. Region is Zealand.",
        },
        {
            "entry_id": "DK-01-284",
            "region": "Zealand",
            "city": "Agers\u00f8",
            "caption": "Agers\u00f8 Harbour, Agers\u00f8",
            **rows["DK-01-284"],
            "composition": "A long quay, fishing boats, and a plain ferry \u00b7 AI-generated artistic interpretation",
            "description": (
                "Agers\u00f8 harbour is a longer stone quay with wooden piers, fishing boats, one plain white ferry, and low brick houses along the shore. "
                f"The quay is empty. {sky('DK-01-284')} "
                "The water is choppy. The church is not the subject, and no ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Agers\u00f8 harbour just after sunrise, a long quay and a plain ferry",
            "viewpoint": "The ferry quay at Agers\u00f8 Havn. Approximate researched point 55.21177, 11.19797, not a surveyed camera. Open-Meteo ran this request on grid 55.21187, 11.19316. Nominatim places the terminal in Agers\u00f8, postcode 4244.",
            "refs": [
                "https://en.wikipedia.org/wiki/Agers%C3%B8",
                "https://da.wikipedia.org/wiki/Agers%C3%B8",
            ],
            "anchors": [
                "A longer stone quay and wooden piers.",
                "Fishing boats and one plain white ferry.",
                "Low brick houses, and no church as the subject.",
            ],
            "independent": (
                "Agers\u00f8 is the island next to Om\u00f8, also in Slagelse Municipality, with its own harbour. "
                "The Om\u00f8 frame includes the church at Kirkehavn. This frame stays on the Agers\u00f8 quay."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Long quay, fishing boats, plain ferry, chop, mainly clear morning light. No lettering.",
            "swap": "No site swap. Agers\u00f8 Harbour was not used in DK-01-001 through DK-01-272. City is Agers\u00f8. Region is Zealand.",
        },
        {
            "entry_id": "DK-01-285",
            "region": "Central Jutland",
            "city": "Ballen",
            "caption": "Ballen Harbour, Ballen",
            **rows["DK-01-285"],
            "composition": "Ferry moles, boats, and red roofs under broken cloud \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ballen harbour is the east-coast ferry harbour on Sams\u00f8, with stone moles, sailboats and fishing boats, one plain white ferry, and low red-roofed houses. "
                f"The quay is empty. {sky('DK-01-285')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Ballen harbour on Sams\u00f8 just after sunrise, moles and a plain ferry under broken cloud",
            "viewpoint": "The public quay at Ballen Havn. Approximate researched point 55.81608, 10.64006, not a surveyed camera. Open-Meteo ran this request on grid 55.81760, 10.63562. Nominatim places the marina in Ballen, postcode 8305.",
            "refs": [
                "https://en.wikipedia.org/wiki/Sams%C3%B8",
                "https://da.wikipedia.org/wiki/Sams%C3%B8",
            ],
            "anchors": [
                "Stone ferry moles and a marina.",
                "One plain white ferry without a readable name.",
                "Low red-roofed houses under broken cloud.",
            ],
            "independent": (
                "Ballen is the village and ferry harbour on the east coast of Sams\u00f8, with the crossing toward Kalundborg. "
                "The Sams\u00f8 articles are the sources used here. No separate English village article was found."
            ),
            "ip": "No readable ferry name and no operator mark. Internal review only, not a legal certification.",
            "visual": "Pass. Moles, boats, plain ferry, red roofs, broken cloud, morning light. No lettering.",
            "swap": "No site swap. Ballen Harbour was not used in DK-01-001 through DK-01-272. City is Ballen. Region is Central Jutland.",
        },
        {
            "entry_id": "DK-01-286",
            "region": "Central Jutland",
            "city": "Nordby",
            "caption": "Nordby village street, Nordby",
            **rows["DK-01-286"],
            "composition": "An inland lane of brick and thatched houses \u00b7 AI-generated artistic interpretation",
            "description": (
                "This is the village street in Nordby on Sams\u00f8, an inland lane of low brick and plastered houses, a few thatched roofs, and small gardens. "
                f"The lane is empty. {sky('DK-01-286')} "
                "There is no sea and no harbour. This is not the Fan\u00f8 quay."
            ),
            "alt_text": "AI-generated artistic interpretation of the village street in Nordby on Sams\u00f8 just after sunrise, thatched houses and no sea",
            "viewpoint": "Nordby Hovedgade in Nordby on Sams\u00f8, looking along the lane. Approximate researched point 55.96410, 10.55206, not a surveyed camera. Open-Meteo ran this request on grid 55.96658, 10.55354. Nominatim places the street in Nordby, Sams\u00f8 Kommune.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nordby_(Sams%C3%B8)",
                "https://da.wikipedia.org/wiki/Nordby_(Sams%C3%B8)",
            ],
            "anchors": [
                "An inland village lane.",
                "Low brick and plastered houses, some with thatch.",
                "No sea, no dune, and no harbour.",
            ],
            "independent": (
                "Nordby is the old village at the north end of Sams\u00f8. The street is inland. "
                "Nordby Harbour, Nordby, DK-01-221, is the Fan\u00f8 harbour in South Jutland. The city string matches; the place does not."
            ),
            "ip": "No shop sign and no readable plate. Internal review only, not a legal certification.",
            "visual": "Pass. Inland lane, brick and thatch, broken cloud, no sea. Not the Fan\u00f8 harbour. No lettering.",
            "swap": "No site swap of the Sams\u00f8 village. Fan\u00f8's Nordby Harbour is already DK-01-221, Nordby Harbour, Nordby, in South Jutland. This caption is Nordby village street. City is Nordby. Region is Central Jutland.",
        },
        {
            "entry_id": "DK-01-287",
            "region": "Central Jutland",
            "city": "Tun\u00f8",
            "caption": "Tun\u00f8 Harbour, Tun\u00f8",
            **rows["DK-01-287"],
            "composition": "A short mole, a plain ferry, and a white church set back \u00b7 AI-generated artistic interpretation",
            "description": (
                "Tun\u00f8 harbour is a short stone mole and a small basin, with one plain white ferry, a few boats, low houses, and a simple white church set back from the quay. "
                f"The quay is empty. {sky('DK-01-287')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Tun\u00f8 harbour just after sunrise, a short mole, a plain ferry, and a white church",
            "viewpoint": "The quay at Tun\u00f8 Havn. Approximate researched point 55.94830, 10.45513, not a surveyed camera. Open-Meteo ran this request on grid 55.94441, 10.44440. Nominatim places the marina in Tun\u00f8 By, postcode 8799. The caption city is Tun\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Tun%C3%B8",
                "https://da.wikipedia.org/wiki/Tun%C3%B8",
            ],
            "anchors": [
                "A short stone mole and a small basin.",
                "One plain white ferry without a readable name.",
                "Low houses and a white church set back from the water.",
            ],
            "independent": (
                "Tun\u00f8 is the small island between Sams\u00f8 and the Jutland coast, in Odder Municipality, with the ferry toward Hou. "
                "This is not Ballen and not Endelave."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Short mole, plain ferry, white church set back, broken cloud. No lettering.",
            "swap": "No site swap. Tun\u00f8 Harbour was not used in DK-01-001 through DK-01-272. City is Tun\u00f8. Region is Central Jutland.",
        },
        {
            "entry_id": "DK-01-288",
            "region": "Central Jutland",
            "city": "Endelave",
            "caption": "Endelave Harbour, Endelave",
            **rows["DK-01-288"],
            "composition": "A compact basin, a plain ferry, and green fields \u00b7 AI-generated artistic interpretation",
            "description": (
                "Endelave harbour is a compact basin inside stone moles, with one plain white ferry, a few fishing boats, scattered low houses, and green fields. "
                f"The quay is empty. {sky('DK-01-288')} "
                "No ferry name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Endelave harbour just after sunrise, a basin, a plain ferry, and green fields",
            "viewpoint": "The quay at Endelave Havn. Approximate researched point 55.76214, 10.27154, not a surveyed camera. Open-Meteo ran this request on grid 55.75858, 10.27696. Nominatim places the harbour in Endelave By, postcode 8789. The caption city is Endelave.",
            "refs": [
                "https://en.wikipedia.org/wiki/Endelave",
                "https://da.wikipedia.org/wiki/Endelave",
            ],
            "anchors": [
                "A compact basin inside stone moles.",
                "One plain white ferry and a few fishing boats.",
                "Scattered low houses and green fields.",
            ],
            "independent": (
                "Endelave is the island east of Horsens, with the ferry toward Snaptun. "
                "The harbour is a small basin, not the longer quay at Agers\u00f8 and not the Ballen ferry port."
            ),
            "ip": "No readable ferry name. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, moles, plain ferry, fields, broken cloud. No lettering.",
            "swap": "No site swap. Endelave Harbour was not used in DK-01-001 through DK-01-272. City is Endelave. Region is Central Jutland.",
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
    prefixes = [scene["weather_prefix"] for scene in batch]
    if len(prefixes) != len(set(prefixes)):
        raise SystemExit("reused weather prefix")
    lines = []
    masters: list[Path] = []
    for scene in batch:
        label = bd.scenario_label(scene["entry_id"])
        hour = label.split("\u00b7")[1].strip().split(" ")[0]
        valid_hm = scene["_row"]["valid"][11:16]
        if not hour.startswith("07:"):
            raise SystemExit(f"{scene['entry_id']} scenario {label} outside valid hour 07")
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
        scene["solar"] = solar_text(scene["_row"], when)
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
    if len(all_scenes) != 288:
        raise SystemExit(f"expected 288 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 289)]
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
    report = bd.ROOT / "approvals" / "BATCH-DK-01-273-288.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pngs = list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-16x9.png"))
    pngs += list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-4x5.png"))
    if len(pngs) != 576:
        raise SystemExit(f"expected 576 masters, got {len(pngs)}")
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

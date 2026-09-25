#!/usr/bin/env python3
"""Bake DK-01-241 through DK-01-256 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-241-256.json.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-241-256.json").read_text(encoding="utf-8"))

# Local civil zone and the hour offset from Europe/Copenhagen on this September date.
ZONE = {
    "DK-01-241": ("Europe/Copenhagen", 0),
    "DK-01-242": ("Europe/Copenhagen", 0),
    "DK-01-243": ("Europe/Copenhagen", 0),
    "DK-01-244": ("Europe/Copenhagen", 0),
    "DK-01-245": ("Europe/Copenhagen", 0),
    "DK-01-246": ("Europe/Copenhagen", 0),
    "DK-01-247": ("Atlantic/Faroe", -1),
    "DK-01-248": ("Atlantic/Faroe", -1),
    "DK-01-249": ("Atlantic/Faroe", -1),
    "DK-01-250": ("Atlantic/Faroe", -1),
    "DK-01-251": ("America/Nuuk", -3),
    "DK-01-252": ("America/Nuuk", -3),
    "DK-01-253": ("America/Nuuk", -3),
    "DK-01-254": ("America/Nuuk", -3),
    "DK-01-255": ("America/Nuuk", -3),
    "DK-01-256": ("America/Scoresbysund", -3),
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def sky_word(code: int) -> str:
    table = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 71: "Light snow"}
    if code not in table:
        raise SystemExit(f"unhandled weather code {code}")
    return table[code]


def nice_time(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[iso[5:7]]} {iso[0:4]} {iso[11:16]}"


def stamp_words(raw: str) -> str:
    return f"{int(raw[8:10])} {MONTHS[raw[5:7]]} {raw[0:4]} {raw[11:19]}"


def shift_iso(iso: str, hours: int) -> str:
    dt = datetime.fromisoformat(iso) + timedelta(hours=hours)
    return dt.strftime("%Y-%m-%dT%H:%M")


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
    if not str(row["valid"]).startswith("2026-09-25T06:30"):
        raise SystemExit(f"{entry} valid {row['valid']}")
    if not str(row["retrieved"]).startswith("2026-09-25T06:"):
        raise SystemExit(f"{entry} retrieval {row['retrieved']}")
    if int(row["interval"]) != 900:
        raise SystemExit(f"{entry} interval")
    if precip == 0 and snow == 0:
        precip_words = "no precipitation"
    else:
        precip_words = f"precipitation {precip:.1f} mm, snowfall {snow:.2f} cm"
    zone, offset = ZONE[entry]
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
        "moon": moon_note(when),
        "zone": zone,
        "offset": offset,
        "prefix": (
            "Model data from Open-Meteo, retrieved "
            f"{stamp_words(row['retrieved'])} Europe/Copenhagen, valid "
            f"{nice_time(row['valid'])} Europe/Copenhagen "
            "\u2014 not a verified on-site observation. "
            f"Separate request for {row['lat']:.5f}, {row['lon']:.5f}. "
            "The model-valid hour is 06:00\u201306:59 Europe/Copenhagen. "
            "The cited model time is the 06:30 step (interval 900 seconds)."
        ),
    }


def light(row: dict) -> str:
    if row["code"] == 71:
        return "Light snow is falling in the gale, and the cloud hides the moon."
    if row["cloud"] >= 80:
        return "The cloud deck hides the moon, and only a few lamps carry the light."
    if row["cloud"] >= 45:
        return "Broken cloud hides much of the moon."
    return "Moonlight reaches the ground under a thin cloud cover."


def wind_clause(row: dict) -> str:
    w = row["wind_f"]
    if w >= 60:
        return f"The wind is a gale, about {row['wind']} km/h."
    if w >= 40:
        return f"The wind is strong, about {row['wind']} km/h."
    if w >= 20:
        return f"The wind is fresh, about {row['wind']} km/h."
    return f"The wind is light, about {row['wind']} km/h."


def clock(row: dict) -> str:
    sunset = nice_time(row["sunset"])
    sunrise = nice_time(row["sunrise"])
    text = "Night, still before today's sunrise. "
    if row["offset"] == 0:
        text += f"Sunset on {sunset} Europe/Copenhagen and sunrise on {sunrise} Europe/Copenhagen. "
    else:
        behind = abs(row["offset"])
        unit = "hour" if behind == 1 else "hours"
        text += (
            f"Sunset on {sunset} Europe/Copenhagen ({nice_time(shift_iso(row['sunset'], row['offset']))} {row['zone']}) "
            f"and sunrise on {sunrise} Europe/Copenhagen ({nice_time(shift_iso(row['sunrise'], row['offset']))} {row['zone']}). "
            f"The clock printed on the image is Europe/Copenhagen. Local civil time is {behind} {unit} behind that clock. "
        )
    text += twilight_phrase(row["sun_alt"]) + " "
    text += f"Cloud cover {row['cloud']}%. "
    if row["code"] == 71:
        text += "Light snow is in the model. The cloud hides the moon. "
    elif row["cloud"] >= 80:
        text += "The cloud deck hides the moon. "
    else:
        text += row["moon"] + " "
    text += (
        "The scenario minute has to fall inside this scene's own model-valid hour, "
        "06:00\u201306:59 Europe/Copenhagen, and after the cited 06:30 model step."
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
    for n in range(241, 257):
        for kind, src_name, expect in (
            ("16x9", "16x9", (1280, 720)),
            ("4x5", "4x5", (864, 1152)),
        ):
            src = bd.RAW / f"dk-01-{n:03d}-{src_name}.png"
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

    rows = {f"DK-01-{n}": base(f"DK-01-{n}") for n in range(241, 257)}

    def sky(entry: str) -> str:
        row = rows[entry]
        return (
            f"It is {row['word'].lower()}, about {row['temp']}\u00b0C. "
            f"{wind_clause(row['_row'])} {light(row['_row'])}"
        )

    a = rows["DK-01-241"]
    return [
        {
            "entry_id": "DK-01-241",
            "region": "Bornholm",
            "city": "R\u00f8nne",
            "caption": "R\u00f8nne Harbour, R\u00f8nne",
            **a,
            "composition": "Fishing boats and red warehouses in the basin \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the public quay, R\u00f8nne harbour is a working basin with fishing boats, one plain ferry, and low red warehouses, and the town roofs sit behind them. "
                f"The quay is empty. {sky('DK-01-241')} "
                "This is not the cobbled old-town lanes."
            ),
            "alt_text": "AI-generated artistic interpretation of R\u00f8nne harbour at night, red warehouses and fishing boats under cloud",
            "viewpoint": "The public quay at R\u00f8nne Havn, looking across the basin toward the low warehouses. Approximate researched point 55.09388, 14.69272, not a surveyed camera. Nominatim places R\u00f8nne Havn in R\u00f8nne.",
            "refs": [
                "https://en.wikipedia.org/wiki/R%C3%B8nne",
                "https://da.wikipedia.org/wiki/R%C3%B8nne",
            ],
            "anchors": [
                "A harbour basin with fishing boats and one plain ferry.",
                "Low red and ochre warehouses.",
                "Town roofs behind the sheds. No cobbled half-timber lane.",
            ],
            "solar": clock(a["_row"]) + " Quay lamps. No readable ferry name.",
            "independent": (
                "R\u00f8nne is the main town and port on the west side of Bornholm. "
                "The old merchant lanes around Store Torv are already DK-01-065, R\u00f8nne Old Town, R\u00f8nne. This frame stays on the water."
            ),
            "ip": "No readable ferry name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, boats, plain ferry, red warehouses, overcast lamps. Not the old-town square.",
            "swap": "No site swap. R\u00f8nne Old Town is already DK-01-065. This caption is the harbour. City remains R\u00f8nne.",
        },
        {
            "entry_id": "DK-01-242",
            "region": "Bornholm",
            "city": "Nex\u00f8",
            "caption": "Nex\u00f8 Harbour, Nex\u00f8",
            **rows["DK-01-242"],
            "composition": "A concrete mole and a fishing basin \u00b7 AI-generated artistic interpretation",
            "description": (
                "Nex\u00f8 harbour is a concrete mole, fishing boats, and low sheds on the east-coast basin. "
                f"The quay is empty. {sky('DK-01-242')} "
                "The beach south of town is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Nex\u00f8 harbour at night, a mole and fishing boats",
            "viewpoint": "The public quay at Nex\u00f8 Havn. Approximate researched point 55.06181, 15.13598, not a surveyed camera. Nominatim places the harbour in Nex\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nex%C3%B8",
                "https://da.wikipedia.org/wiki/Nex%C3%B8",
            ],
            "anchors": [
                "A concrete breakwater mole.",
                "Fishing boats and low sheds.",
                "Dark water. No beach and no dunes.",
            ],
            "solar": clock(rows["DK-01-242"]["_row"]) + " Harbour lamps. No readable boat name.",
            "independent": (
                "Nex\u00f8 is the east-coast fishing town of Bornholm. The English article describes the harbour and the ferry link. "
                "Dueodde beach, south of town, is already DK-01-068 and is not this frame."
            ),
            "ip": "No readable boat name and no factory mark. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, fishing boats, sheds, overcast water. No beach.",
            "swap": "No site swap. Nex\u00f8 Harbour was not used in DK-01-001 through DK-01-240. City is Nex\u00f8.",
        },
        {
            "entry_id": "DK-01-243",
            "region": "Bornholm",
            "city": "\u00c5kirkeby",
            "caption": "Aa Church, \u00c5kirkeby",
            **rows["DK-01-243"],
            "composition": "Greenish and rust-brown Romanesque stone and a limestone tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Aa Church has a Romanesque choir of greenish sandstone and rust-brown shale, a paler limestone west tower, and a dark roof, standing in an empty churchyard. "
                f"{sky('DK-01-243')} "
                "It is not a round church and it is not whitewashed over."
            ),
            "alt_text": "AI-generated artistic interpretation of Aa Church in \u00c5kirkeby at night, coloured stone and a limestone tower",
            "viewpoint": "The public churchyard at Aa Kirke, Storegade, \u00c5kirkeby. Approximate researched point 55.07068, 14.91946, not a surveyed camera. Nominatim spells the town Aakirkeby and gives postal 3720. The caption uses the \u00c5 spelling.",
            "refs": [
                "https://en.wikipedia.org/wiki/Aa_Church",
                "https://da.wikipedia.org/wiki/Aa_Kirke",
            ],
            "anchors": [
                "Greenish sandstone and rust-brown shale on the choir and apse.",
                "A paler limestone west tower.",
                "A dark roof and an empty churchyard. Not a round church.",
            ],
            "solar": clock(rows["DK-01-243"]["_row"]) + " Two path lamps. No readable gravestone.",
            "independent": (
                "The English article says Aa Church, in Aakirkeby, is a 12th-century Romanesque church. The choir, apse, and lower nave use greenish sandstone and rust-brown shale from Gr\u00f8dby Stream, and the west end and the tower are limestone. "
                "Svaneke Harbour is already DK-01-069, so this batch uses the inland church instead of another Svaneke waterfront."
            ),
            "ip": "No readable sign and no gravestone treated as lettering. Internal review only, not a legal certification.",
            "visual": "Pass. Two-tone stone choir, limestone tower, dark roof, empty churchyard, overcast. Not whitewashed and not round.",
            "swap": (
                "Swapped from Svaneke Harbour. That basin is already DK-01-069, Svaneke Harbour, Svaneke. "
                "The caption is Aa Church. City is \u00c5kirkeby."
            ),
        },
        {
            "entry_id": "DK-01-244",
            "region": "Bornholm",
            "city": "R\u00f8",
            "caption": "Helligdomsklipperne, R\u00f8",
            **rows["DK-01-244"],
            "composition": "Jagged granite sea cliffs and a cave \u00b7 AI-generated artistic interpretation",
            "description": (
                "Helligdomsklipperne are jagged grey granite cliffs and pillars at the water, with a dark cave at the base and a path along the top. "
                f"Nobody is on the path. {sky('DK-01-244')} "
                "There is no building in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Helligdomsklipperne at night, granite cliffs above dark water",
            "viewpoint": "The coastal rocks at Helligdomsklipperne. Approximate researched point 55.22511, 14.89738, not a surveyed camera. Nominatim places the cliffs in R\u00f8, postal 3760. That postcode is the Gudhjem postal town. The city in the caption is R\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Helligdomsklipperne",
                "https://da.wikipedia.org/wiki/Helligdomsklipperne",
            ],
            "anchors": [
                "Steep jagged granite cliffs and pillars.",
                "A cave at the waterline.",
                "Dark water and no building.",
            ],
            "solar": clock(rows["DK-01-244"]["_row"]) + " No museum and no staircase as the subject.",
            "independent": (
                "The English article describes moderately high granite coastal cliffs, about 22 metres, with caves and pillars, between Gudhjem and Tejn. The 22 metre figure is the published height, not a new measurement. "
                "Gudhjem Harbour is already DK-01-066. The art museum above the cliffs is not the subject."
            ),
            "ip": "No sign and no museum wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Granite pillars, cave, dark water, overcast, empty. No building.",
            "swap": (
                "Swapped from Gudhjem Harbour. That basin is already DK-01-066, Gudhjem Harbour, Gudhjem. "
                "The caption is Helligdomsklipperne. City is R\u00f8."
            ),
        },
        {
            "entry_id": "DK-01-245",
            "region": "Bornholm",
            "city": "Vang",
            "caption": "Jons Kapel, Vang",
            **rows["DK-01-245"],
            "composition": "A tall granite bluff and a cave, with no building \u00b7 AI-generated artistic interpretation",
            "description": (
                "Jons Kapel is one tall granite bluff with a cave overhang, seen from the boulder shore. "
                f"The shore is empty. {sky('DK-01-245')} "
                "There is no chapel building."
            ),
            "alt_text": "AI-generated artistic interpretation of Jons Kapel at night, a granite cliff and cave above the shore",
            "viewpoint": "The rocky shore below Jons Kapel, looking up at the bluff. Approximate researched point 55.23306, 14.72036, not a surveyed camera. The nearest hamlet is Vang. One OSM label on the same search said Ringe with postal 3790. The caption city is Vang.",
            "refs": [
                "https://en.wikipedia.org/wiki/Jons_Kapel",
                "https://da.wikipedia.org/wiki/Jons_Kapel",
            ],
            "anchors": [
                "One tall grey granite cliff.",
                "A cave-like overhang.",
                "Boulder shore and dark water. No church.",
            ],
            "solar": clock(rows["DK-01-245"]["_row"]) + " No building lights, because there is no building.",
            "independent": (
                "The English article calls Jons Kapel a rock bluff on Bornholm's west coast, about 7 kilometres north of Hasle, with the cave visible from the beach. It gives the cliff as 135 feet, a published figure, not a new measurement. The name is the rock, not a chapel that was built there. "
                "Dueodde Beach is already DK-01-068. Hasle Harbour is DK-01-157 and is not this cliff."
            ),
            "ip": "No sign. Internal review only, not a legal certification.",
            "visual": "Pass. Single bluff, cave, boulder shore, overcast water. No chapel building.",
            "swap": (
                "Swapped from Dueodde Beach. That shore is already DK-01-068, Dueodde Beach, Dueodde. "
                "The caption is Jons Kapel. City is Vang."
            ),
        },
        {
            "entry_id": "DK-01-246",
            "region": "Bornholm",
            "city": "Olsker",
            "caption": "Olsker Round Church, Olsker",
            **rows["DK-01-246"],
            "composition": "A white round church and a dark conical roof \u00b7 AI-generated artistic interpretation",
            "description": (
                "Olsker Round Church is a white round stone church with a dark conical roof, small openings, and a short apse, alone on a grassy hill. "
                f"The hill is empty. {sky('DK-01-246')} "
                "It is not a long rectangular church."
            ),
            "alt_text": "AI-generated artistic interpretation of Olsker round church at night, a white cone-roofed tower on a hill",
            "viewpoint": "The public ground at Sankt Ols Kirke, Olsker. Approximate researched point 55.23601, 14.80037, not a surveyed camera. Nominatim's town field says Tejn and the postcode is 3770. The English article places the church in the village of Olsker. The caption city is Olsker.",
            "refs": [
                "https://en.wikipedia.org/wiki/Olsker_Church",
                "https://da.wikipedia.org/wiki/Sankt_Ols_Kirke",
            ],
            "anchors": [
                "A white round nave, not a rectangle.",
                "A dark conical roof and a small apse.",
                "Open grass on a hill. No buttressed rectangular church.",
            ],
            "solar": clock(rows["DK-01-246"]["_row"]) + " Two lamps. No readable sign.",
            "independent": (
                "The English article describes a 12th-century round church of granite fieldstone, with a round nave, choir, and apse, on a hill. It gives 13 metres to the top of the conical roof and 112 metres above sea level. Those are published figures, not a new measurement, and they are not lettered on the image. "
                "\u00d8sterlars Round Church is already DK-01-067."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. White round church, conical roof, apse, empty hill, overcast. Not a rectangular church.",
            "swap": (
                "Swapped from \u00d8sterlars Round Church. That church is already DK-01-067, \u00d8sterlars Round Church, \u00d8sterlars. "
                "The caption is Olsker Round Church. City is Olsker."
            ),
        },
        {
            "entry_id": "DK-01-247",
            "region": "Faroe Islands",
            "city": "Kirkjub\u00f8ur",
            "caption": "Kirkjub\u00f8ur, Kirkjub\u00f8ur",
            **rows["DK-01-247"],
            "composition": "A roofless stone ruin, a white church, and a black turf-roof farm \u00b7 AI-generated artistic interpretation",
            "description": (
                "Kirkjub\u00f8ur shows an unroofed medieval stone ruin, a small white church, and a black turf-roof farmhouse on the grass above a choppy sound. "
                f"The shore is empty. {sky('DK-01-247')} "
                "The ruin has no roof."
            ),
            "alt_text": "AI-generated artistic interpretation of Kirkjub\u00f8ur at night, a roofless ruin and a turf-roof farmhouse",
            "viewpoint": "The public grass in front of the ruin and the farm at Kirkjub\u00f8ur, looking toward the sound. Approximate researched point 61.95371, -6.79341, not a surveyed camera. Nominatim places the village in Kirkjub\u00f8ur.",
            "refs": [
                "https://en.wikipedia.org/wiki/Kirkjub%C3%B8ur",
                "https://en.wikipedia.org/wiki/Magnus_Cathedral",
            ],
            "anchors": [
                "Roofless stone cathedral walls, open to the sky.",
                "A small white church beside the ruin.",
                "A black wooden farmhouse with a grass roof, and dark choppy water.",
            ],
            "solar": clock(rows["DK-01-247"]["_row"]) + " A few lamps. No ferry terminal.",
            "independent": (
                "The English village article names the ruins of Magnus Cathedral, Saint Olav's Church, and the old farmhouse Kirkjub\u00f8argar\u00f0ur, with a view west toward Hestur and Koltur. The ruin is shown without a roof. "
                "The ferry port at Gamlar\u00e6tt is a different place and is not in the frame. Klaksv\u00edk Harbour is already DK-01-075."
            ),
            "ip": "No readable sign and no ferry mark. Internal review only, not a legal certification.",
            "visual": "Pass. Roofless ruin, white church, black turf-roof house, choppy water, full cloud. No terminal.",
            "swap": (
                "Swapped from Klaksv\u00edk Harbour. That port is already DK-01-075, Klaksv\u00edk Harbour, Klaksv\u00edk. "
                "The caption is Kirkjub\u00f8ur. City is Kirkjub\u00f8ur."
            ),
        },
        {
            "entry_id": "DK-01-248",
            "region": "Faroe Islands",
            "city": "Tv\u00f8royri",
            "caption": "Tv\u00f8royri Harbour, Tv\u00f8royri",
            **rows["DK-01-248"],
            "composition": "Houses above a small fjord harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                "Tv\u00f8royri harbour is a small basin on the fjord, with fishing boats and colourful wooden houses stepping up the steep hillside. "
                f"The quay is empty. {sky('DK-01-248')} "
                "The water is choppy."
            ),
            "alt_text": "AI-generated artistic interpretation of Tv\u00f8royri harbour at night, houses above a choppy fjord",
            "viewpoint": "The public harbour front at Tv\u00f8royri, on the north side of Trongisv\u00e1gsfj\u00f8r\u00f0ur. Approximate researched point 61.55533, -6.80468, not a surveyed camera. Nominatim places the town in Tv\u00f8royri, postal 800.",
            "refs": [
                "https://en.wikipedia.org/wiki/Tv%C3%B8royri",
                "https://en.wikipedia.org/wiki/Su%C3%B0uroy",
            ],
            "anchors": [
                "A small harbour basin and fishing boats with blank hulls.",
                "Colourful wooden houses on a steep slope.",
                "Choppy fjord water under broken cloud.",
            ],
            "solar": clock(rows["DK-01-248"]["_row"]) + " Quay lamps. No readable boat name.",
            "independent": (
                "Tv\u00f8royri is the village on the north side of Trongisv\u00e1gsfj\u00f8r\u00f0ur, on the east coast of Su\u00f0uroy. "
                "The scene was not used in DK-01-001 through DK-01-240."
            ),
            "ip": "No readable boat name and no shop sign. Internal review only, not a legal certification.",
            "visual": "Pass. Hillside houses, small basin, choppy water, broken cloud. No readable name.",
            "swap": "No site swap. Tv\u00f8royri Harbour was not used in DK-01-001 through DK-01-240. City is Tv\u00f8royri.",
        },
        {
            "entry_id": "DK-01-249",
            "region": "Faroe Islands",
            "city": "Tj\u00f8rnuv\u00edk",
            "caption": "Tj\u00f8rnuv\u00edk, Tj\u00f8rnuv\u00edk",
            **rows["DK-01-249"],
            "composition": "Turf-roof houses, a dark beach, and two sea stacks \u00b7 AI-generated artistic interpretation",
            "description": (
                "Tj\u00f8rnuv\u00edk is a few turf-roof houses at the foot of a steep valley, a dark sand beach, and two sea stacks across the water, one taller and blockier and one pointed. "
                f"The beach is empty. {sky('DK-01-249')} "
                "There is no boat in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Tj\u00f8rnuv\u00edk at night, turf-roof houses and two sea stacks",
            "viewpoint": "The beach at Tj\u00f8rnuv\u00edk, looking north across the sound toward the stacks off Eysturoy. Approximate researched point 62.28951, -7.14917, not a surveyed camera. Nominatim places the village in Tj\u00f8rnuv\u00edk, postal 445.",
            "refs": [
                "https://en.wikipedia.org/wiki/Tj%C3%B8rnuv%C3%ADk",
                "https://en.wikipedia.org/wiki/Risin_og_Kellingin",
            ],
            "anchors": [
                "A few turf-roof houses in a steep valley.",
                "Dark sand in the foreground and no boat.",
                "Two sea stacks on the far water, one blocky and one pointed.",
            ],
            "solar": clock(rows["DK-01-249"]["_row"]) + " A little light from the houses. No road sign.",
            "independent": (
                "The village article places Tj\u00f8rnuv\u00edk at the north end of Streymoy and says Risin og Kellingin are visible across the sound. "
                "The stack article describes Risin as the 71 metre stack farther out and Kellingin as the pointed 68 metre stack nearer land. Those heights are published figures, not a new measurement. "
                "Gj\u00f3gv is already DK-01-072."
            ),
            "ip": "No boat and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Turf roofs, dark beach, two stacks, broken cloud, empty. No boat.",
            "swap": (
                "Swapped from Gj\u00f3gv. That gorge village is already DK-01-072, Gj\u00f3gv, Gj\u00f3gv. "
                "The caption is Tj\u00f8rnuv\u00edk. City is Tj\u00f8rnuv\u00edk."
            ),
        },
        {
            "entry_id": "DK-01-250",
            "region": "Faroe Islands",
            "city": "B\u00f8ur",
            "caption": "B\u00f8ur, B\u00f8ur",
            **rows["DK-01-250"],
            "composition": "Turf-roof houses and the jagged islet across the water \u00b7 AI-generated artistic interpretation",
            "description": (
                "B\u00f8ur is a cluster of turf-roof houses on a green slope, with the jagged islet Tindh\u00f3lmur across choppy water. "
                f"The lanes are empty. {sky('DK-01-250')} "
                "No separate second island is invented beyond that western view."
            ),
            "alt_text": "AI-generated artistic interpretation of B\u00f8ur at night, turf-roof houses and a jagged islet",
            "viewpoint": "The village slope at B\u00f8ur, looking west over S\u00f8rv\u00e1gsfj\u00f8r\u00f0ur. Approximate researched point 62.08798, -7.37145, not a surveyed camera. Nominatim places the village in B\u00f8ur, postal 386.",
            "refs": [
                "https://en.wikipedia.org/wiki/B%C3%B8ur",
                "https://en.wikipedia.org/wiki/Tindh%C3%B3lmur",
            ],
            "anchors": [
                "Turf-roof houses bunched on a slope.",
                "Dark choppy water.",
                "The jagged multi-peaked islet across the water.",
            ],
            "solar": clock(rows["DK-01-250"]["_row"]) + " A few windows. No readable house name.",
            "independent": (
                "The English article places B\u00f8ur on the west side of V\u00e1gar and describes the view to Tindh\u00f3lmur and the tall rocks in that same water. The frame keeps the islet as one jagged shape rather than inventing extra islands. "
                "Saksun Lagoon is already DK-01-071. The church of 1865 is not the subject and carries no readable sign."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Turf-roof houses, choppy water, jagged islet, full cloud. Empty lanes.",
            "swap": (
                "Swapped from Saksun Lagoon. That lagoon is already DK-01-071, Saksun Lagoon, Saksun. "
                "The caption is B\u00f8ur. City is B\u00f8ur."
            ),
        },
        {
            "entry_id": "DK-01-251",
            "region": "Greenland",
            "city": "Uummannaq",
            "caption": "Uummannaq, Uummannaq",
            **rows["DK-01-251"],
            "composition": "Painted houses and the heart-shaped mountain \u00b7 AI-generated artistic interpretation",
            "description": (
                "Uummannaq's painted wooden houses stand on dark rock, and the heart-shaped mountain rises behind them with two summits and snow on the upper slopes. "
                f"The lanes are empty. {sky('DK-01-251')} "
                "The water in front is open. No iceberg is in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Uummannaq at night, colourful houses and a heart-shaped mountain",
            "viewpoint": "The town shore on Uummannaq Island, looking toward the mountain. Approximate researched point 70.67462, -52.12676, not a surveyed camera. Nominatim places the town in Uummannaq, postal 3061.",
            "refs": [
                "https://en.wikipedia.org/wiki/Uummannaq",
                "https://en.wikipedia.org/wiki/Uummannaq_(mountain)",
            ],
            "anchors": [
                "Brightly painted wooden houses on rock.",
                "A twin-summit mountain, heart-shaped, with snow high up.",
                "Open dark water. No icebergs.",
            ],
            "solar": clock(rows["DK-01-251"]["_row"]) + " Warm windows. No falling snow in this scene's model.",
            "independent": (
                "The mountain article describes a 1,170 metre twin-summit mountain, the eastern summit the higher, which is why the Greenlandic name means heart-shaped. The 1,170 metre figure is published, not a new measurement. "
                "The model for this hour is clear, about 0.4\u00b0C, with no snowfall, so the frame does not invent bergs or a snow cover on the streets. Snow on the high rock is the mountain's usual upper slopes. "
                "Ilulissat Icefjord is already DK-01-016. Disko Bay is DK-01-078. Eqi Glacier is DK-01-079."
            ),
            "ip": "No readable sign and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Painted houses, heart-shaped twin summit, moonlight, open water. No bergs.",
            "swap": (
                "Swapped from Ilulissat Icefjord. That shore is already DK-01-016, Ilulissat Icefjord, Ilulissat. "
                "The caption is Uummannaq. City is Uummannaq."
            ),
        },
        {
            "entry_id": "DK-01-252",
            "region": "Greenland",
            "city": "Nuuk",
            "caption": "Nuuk Cathedral, Nuuk",
            **rows["DK-01-252"],
            "composition": "A small red wooden church and a white steeple \u00b7 AI-generated artistic interpretation",
            "description": (
                "Nuuk Cathedral is a small red wooden church with white window frames and a white steeple, among low wooden houses. "
                f"The lane is empty. {sky('DK-01-252')} "
                "The mountain across the fjord is not the subject, and no statue is in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Nuuk Cathedral at night, a red wooden church with a white steeple",
            "viewpoint": "The lane beside Annaassisitta Oqaluffia in Old Nuuk. Approximate researched point 64.17976, -51.74413, not a surveyed camera. Nominatim places the church in Nuuk, postal 3900.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nuuk_Cathedral",
                "https://en.wikipedia.org/wiki/Nuuk",
            ],
            "anchors": [
                "A small red wooden church.",
                "A plain white steeple and white window frames.",
                "Low wooden houses. No mountain as the subject and no statue.",
            ],
            "solar": clock(rows["DK-01-252"]["_row"]) + " A few warm windows. No inscription on the steeple.",
            "independent": (
                "The cathedral article describes the red wooden Church of Our Saviour in Old Nuuk, consecrated in 1849, with a spire. "
                "The old-harbour view toward Sermitsiaq is already DK-01-076, so this frame stays on the church and leaves the mountain out."
            ),
            "ip": "No inscription and no statue. Internal review only, not a legal certification.",
            "visual": "Pass. Red wooden church, white steeple, moonlight, low houses. No mountain subject and no lettering.",
            "swap": (
                "Swapped from a Nuuk colonial-harbour view. That old harbour, with Sermitsiaq across the water, is already DK-01-076, Sermitsiaq, Nuuk. "
                "The caption is Nuuk Cathedral. City remains Nuuk."
            ),
        },
        {
            "entry_id": "DK-01-253",
            "region": "Greenland",
            "city": "Nanortalik",
            "caption": "Nanortalik Harbour, Nanortalik",
            **rows["DK-01-253"],
            "composition": "Painted houses on a rocky point above a small basin \u00b7 AI-generated artistic interpretation",
            "description": (
                "Nanortalik harbour is a small basin under colourful wooden houses on a rocky point, with a few blank boats and low mountains beyond. "
                f"The quay is empty. {sky('DK-01-253')} "
                "There is no ice in the water and no animal on the shore."
            ),
            "alt_text": "AI-generated artistic interpretation of Nanortalik harbour at night, colourful houses on rock",
            "viewpoint": "The public harbour at Nanortalik, looking toward the houses on the rock. Approximate researched point 60.14002, -45.24285, not a surveyed camera. Nominatim places the town in Nanortalik.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nanortalik",
                "https://da.wikipedia.org/wiki/Nanortalik",
            ],
            "anchors": [
                "Colourful wooden houses on rock.",
                "A small harbour and boats with blank hulls.",
                "Dark water and low mountains. No ice and no animals.",
            ],
            "solar": clock(rows["DK-01-253"]["_row"]) + " Quay lamps. No readable boat name.",
            "independent": (
                "Nanortalik is the southern town on its island in Kujalleq. The public face is the coloured wooden houses and the small harbour. "
                "The Greenlandic name is not treated as a wildlife claim, and no animal is shown. "
                "The Qaqortoq harbour-and-houses view is already DK-01-077."
            ),
            "ip": "No readable boat name and no shop sign. Internal review only, not a legal certification.",
            "visual": "Pass. Rocky point, painted houses, small basin, overcast lamps. No ice and no lettering.",
            "swap": (
                "Swapped from Qaqortoq harbour. That town-above-the-basin view is already DK-01-077, Qaqortoq, Qaqortoq. "
                "The caption is Nanortalik Harbour. City is Nanortalik."
            ),
        },
        {
            "entry_id": "DK-01-254",
            "region": "Greenland",
            "city": "Sisimiut",
            "caption": "Bethel Church, Sisimiut",
            **rows["DK-01-254"],
            "composition": "A blue wooden church and a small tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Bethel Church is a blue wooden church with white trim and a modest tower, standing among low houses. "
                f"The lane is empty. {sky('DK-01-254')} "
                "The harbour is not in this frame, and no snow is falling."
            ),
            "alt_text": "AI-generated artistic interpretation of Bethel Church in Sisimiut at night, a blue wooden church",
            "viewpoint": "The lane at Bethel Kirke, Jukkorsuup Aqquserna, Sisimiut. Approximate researched point 66.93852, -53.67138, not a surveyed camera. Nominatim names the building Bethel Kirke in Sisimiut, postal 3911.",
            "refs": [
                "https://en.wikipedia.org/wiki/Sisimiut",
                "https://da.wikipedia.org/wiki/Sisimiut",
            ],
            "anchors": [
                "A blue wooden church, not a red one.",
                "White trim and a small tower.",
                "Low houses and an empty lane. No harbour.",
            ],
            "solar": clock(rows["DK-01-254"]["_row"]) + " Two lamps. No signpost and no readable plaque.",
            "independent": (
                "Nominatim names Bethel Kirke in central Sisimiut. Published exterior captions call it a blue wooden church dated 1775. The 1775 date is that published caption, not a new measurement, and it is not painted on the image. "
                "Sisimiut Harbour is already DK-01-080. This frame leaves the port out. A claim that the building is the oldest church still standing is not repeated."
            ),
            "ip": "No readable sign and no plaque. Internal review only, not a legal certification.",
            "visual": "Pass. Blue wooden church, white trim, small tower, overcast lane. No harbour and no lettering.",
            "swap": (
                "Swapped from Sisimiut Harbour. That basin is already DK-01-080, Sisimiut Harbour, Sisimiut. "
                "The caption is Bethel Church. City remains Sisimiut."
            ),
        },
        {
            "entry_id": "DK-01-255",
            "region": "Greenland",
            "city": "Kangerlussuaq",
            "caption": "Kangerlussuaq Fjord, Kangerlussuaq",
            **rows["DK-01-255"],
            "composition": "Brown tundra and a wide dark fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                "The Kangerlussuaq shore is brown late-September tundra and a gravel bank along a wide dark fjord, with low barren mountains. "
                f"The bank is empty. {sky('DK-01-255')} "
                "No terminal, runway, or aircraft is in the frame, and no snow is falling."
            ),
            "alt_text": "AI-generated artistic interpretation of Kangerlussuaq Fjord at night, tundra and dark water",
            "viewpoint": "A gravel shore of the fjord west of the settlement, looking along the water, not at the airport apron. Approximate researched point 67.00200, -50.72000, not a surveyed camera. Nominatim's town point is 67.00868, -50.69134. The research gap is the exact standing spot on the bank. The terminal is intentionally outside the frame.",
            "refs": [
                "https://en.wikipedia.org/wiki/Kangerlussuaq",
                "https://en.wikipedia.org/wiki/Kangerlussuaq_Fjord",
            ],
            "anchors": [
                "Brown low tundra and a gravel shore.",
                "A wide dark fjord and low mountains.",
                "No terminal, no runway, and no aircraft.",
            ],
            "solar": clock(rows["DK-01-255"]["_row"]) + " Only a few tiny distant lights. No snow cover.",
            "independent": (
                "The settlement article places Kangerlussuaq at the head of the long fjord, on the alluvial flat of the river estuary. The airport is the reason the settlement exists, and it is left out of this frame on purpose. "
                "The model is overcast and about 0\u00b0C with no snowfall, so the tundra is bare rather than under a snow blanket. Late September colour is brown, not summer green."
            ),
            "ip": "No airport mark and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Tundra, gravel, wide fjord, overcast. No terminal and no aircraft.",
            "swap": (
                "No site swap from the brief. The airport-approach idea was already set aside. "
                "The caption is Kangerlussuaq Fjord. City is Kangerlussuaq."
            ),
        },
        {
            "entry_id": "DK-01-256",
            "region": "Greenland",
            "city": "Ittoqqortoormiit",
            "caption": "Ittoqqortoormiit Harbour, Ittoqqortoormiit",
            **rows["DK-01-256"],
            "composition": "Painted houses on a steep slope above a rough harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ittoqqortoormiit is a steep rocky slope of painted wooden houses above a small harbour, with light snow blowing and rough dark water. "
                f"The quay is empty. {sky('DK-01-256')} "
                "The houses stay visible. There is no iceberg field."
            ),
            "alt_text": "AI-generated artistic interpretation of Ittoqqortoormiit harbour at night, houses in light snow above dark water",
            "viewpoint": "The harbour slope at Ittoqqortoormiit, on the Scoresby Sound shore. Approximate researched point 70.48562, -21.96173, not a surveyed camera. Nominatim places the settlement in Ittoqqortoormiit, postal 3980.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ittoqqortoormiit",
                "https://en.wikipedia.org/wiki/Scoresby_Sound",
            ],
            "anchors": [
                "Brightly painted wooden houses on a steep rock slope.",
                "A small harbour and rough dark water.",
                "Light blowing snow. No iceberg field.",
            ],
            "solar": clock(rows["DK-01-256"]["_row"]) + " A few windows through the snow. No readable boat name.",
            "independent": (
                "Ittoqqortoormiit stands on Liverpool Land by the mouth of Kangertittivaq, the fjord also called Scoresby Sound. The former Danish name is Scoresbysund. "
                "This scene's own model fetch is weather code 71, light snow, full cloud, about 0.2\u00b0C, and a gale near 70 km/h. The frame follows that: light snow, not a whiteout, and open rough water rather than an invented field of bergs. "
                "Zoneinfo on this date gives America/Scoresbysund the same UTC\u22121 offset as America/Nuuk."
            ),
            "ip": "No readable boat name and no sign. Internal review only, not a legal certification.",
            "visual": "Pass. Steep painted houses, small harbour, light snow, rough open water, full cloud. No berg field and no lettering.",
            "swap": "No site swap. Ittoqqortoormiit Harbour was not used in DK-01-001 through DK-01-240. City is Ittoqqortoormiit.",
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
        if minute < 30 or minute > 44:
            raise SystemExit(f"{scene['entry_id']} scenario {label} outside 06:30 step")
        sunrise = scene["_row"]["sunrise"]
        if hour >= sunrise[11:16] and sunrise.startswith("2026-09-25T06:"):
            raise SystemExit(f"{scene['entry_id']} scenario {hour} not before sunrise {sunrise}")
        if "25 September 2026" not in label:
            raise SystemExit(label)
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
    if len(all_scenes) != 256:
        raise SystemExit(f"expected 256 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 257)]
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
    report = bd.ROOT / "approvals" / "BATCH-DK-01-241-256.txt"
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

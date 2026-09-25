#!/usr/bin/env python3
"""Bake DK-01-289 through DK-01-304 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-289-304.json.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-289-304.json").read_text(encoding="utf-8"))

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
    for n in range(289, 305):
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

    rows = {f"DK-01-{n}": base(f"DK-01-{n}") for n in range(289, 305)}

    def sky(entry: str) -> str:
        row = rows[entry]
        return (
            f"It is {row['word'].lower()}, about {row['temp']}\u00b0C. "
            f"{wind_clause(row['_row'])} {light(row['_row'])}"
        )

    return [
        {
            "entry_id": "DK-01-289",
            "region": "North Jutland",
            "city": "Hobro",
            "caption": "Fyrkat, Hobro",
            **rows["DK-01-289"],
            "composition": "A grass ring rampart and a thatched longhouse outside it \u00b7 AI-generated artistic interpretation",
            "description": (
                "From outside the ring at Fyrkat, a thatched oak longhouse with curved walls stands in the foreground, and the circular grass rampart sits behind it with a gate opening onto an empty grassy interior. "
                f"The site is empty. {sky('DK-01-289')} "
                "This is the fortress meadow, not the harbour basin in Hobro."
            ),
            "alt_text": "AI-generated artistic interpretation of Fyrkat near Hobro on an overcast morning, a grass rampart and a thatched longhouse",
            "viewpoint": "Outside the west side of the rampart, with the reconstructed longhouse in front of the ring. Approximate researched point 56.62497, 9.77246, not a surveyed camera. Open-Meteo ran this request on grid 56.62384, 9.76988. Nominatim places Fyrkat in Hobro.",
            "refs": [
                "https://nordjyskemuseer.dk/en/ringborgen-the-viking-fortress/",
                "https://en.wikipedia.org/wiki/Fyrkat",
            ],
            "anchors": [
                "A circular grass-covered earth rampart.",
                "One reconstructed thatched longhouse standing outside the ring.",
                "An open grassy interior, not a harbour.",
            ],
            "independent": (
                "Fyrkat is the Viking-age ring fortress by Hobro. The rampart visible today marks the ring, and one longhouse has been reconstructed just outside it. "
                "Hobro Harbour is already DK-01-128, so this frame uses the fortress."
            ),
            "ip": "No readable sign and no museum logo. Internal review only, not a legal certification.",
            "visual": "Pass. Grass rampart, thatched longhouse outside the ring, overcast morning, empty. No lettering.",
            "swap": "Swapped from Hobro Harbour. That basin is already DK-01-128, Hobro Harbour, Hobro. The unused Hobro landmark is the ring fortress. The caption is Fyrkat. City is Hobro.",
        },
        {
            "entry_id": "DK-01-290",
            "region": "North Jutland",
            "city": "Mariager",
            "caption": "Mariager Harbour, Mariager",
            **rows["DK-01-290"],
            "composition": "A small marina of wooden piers on the fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                "Mariager harbour is a small marina on Mariager Fjord: wooden piers, a few sailboats with blank hulls, calm grey water, and low red-tiled houses set back from the quay. "
                f"The quay is empty. {sky('DK-01-290')} "
                "The half-timbered street and the abbey church are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Mariager harbour on an overcast morning, wooden piers and small boats on the fjord",
            "viewpoint": "The quay at Mariager Lystb\u00e5dehavn. Approximate researched point 56.65407, 9.98309, not a surveyed camera. Open-Meteo ran this request on grid 56.65092, 9.97798. Nominatim places the marina in Mariager.",
            "refs": [
                "https://en.wikipedia.org/wiki/Mariager",
                "https://da.wikipedia.org/wiki/Mariager",
            ],
            "anchors": [
                "Wooden marina piers and small boats.",
                "Calm fjord water.",
                "Low red-tiled houses, and no half-timbered street.",
            ],
            "independent": (
                "Mariager sits at the east end of Mariager Fjord. The marina is at the harbour, separate from the old-town street. "
                "Mariager Old Town is already DK-01-127."
            ),
            "ip": "No readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, blank hulls, red roofs, heavy overcast, empty quay. No lettering.",
            "swap": "Swapped from Mariager Old Town. That street is already DK-01-127, Mariager Old Town, Mariager. The suggested unused alternative is the harbour. The caption is Mariager Harbour. City is Mariager.",
        },
        {
            "entry_id": "DK-01-291",
            "region": "North Jutland",
            "city": "Hadsund",
            "caption": "Hadsund Bridge, Hadsund",
            **rows["DK-01-291"],
            "composition": "A low concrete bascule bridge, closed, across the fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                "Hadsund Bridge is the low concrete bascule bridge of 1976, shown closed and nearly horizontal, with short piers in Mariager Fjord and a few small boats by one shore. "
                f"The near quay is empty. {sky('DK-01-291')} "
                "This is not the demolished 1904 steel swing bridge, and it is not an arch or a suspension bridge."
            ),
            "alt_text": "AI-generated artistic interpretation of the closed concrete bascule bridge at Hadsund on an overcast morning",
            "viewpoint": "The fjord shore beside Hadsundbroen, looking along the closed deck. Approximate researched point 56.71333, 10.11815, not a surveyed camera. Open-Meteo ran this request on grid 56.71061, 10.11655. Nominatim places the bridge in Hadsund.",
            "refs": [
                "https://da.wikipedia.org/wiki/Hadsundbroen",
                "https://en.wikipedia.org/wiki/Hadsund",
            ],
            "anchors": [
                "A low concrete bascule bridge lying closed.",
                "Short piers in the fjord.",
                "A few boats, and no steel arch.",
            ],
            "independent": (
                "The present Hadsund Bridge is a concrete klapbro opened in 1976, about 252 metres long, replacing the steel swing bridge of 1904. "
                "The frame keeps the deck down. Danish Wikipedia describes two bascule leaves."
            ),
            "ip": "No readable road sign and no plate. Internal review only, not a legal certification.",
            "visual": "Pass. Closed low concrete bridge, grey sky, small boats, no arch and no lettering.",
            "swap": "No site swap. Hadsund Bridge was not used in DK-01-001 through DK-01-288. City is Hadsund.",
        },
        {
            "entry_id": "DK-01-292",
            "region": "North Jutland",
            "city": "L\u00f8gst\u00f8r",
            "caption": "L\u00f8gst\u00f8r Canal, L\u00f8gst\u00f8r",
            **rows["DK-01-292"],
            "composition": "A straight canal, white keeper houses, and a low swing bridge \u00b7 AI-generated artistic interpretation",
            "description": (
                "Frederik VII's Canal at L\u00f8gst\u00f8r is a straight cut of still water with grass banks, a pair of whitewashed keeper houses under red tile roofs, and a low swing bridge lying flat across the canal. "
                f"The towpath is empty. {sky('DK-01-292')} "
                "The bridge is closed. No house name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Frederik VII's Canal in L\u00f8gst\u00f8r on a partly cloudy morning, white houses and a low bridge",
            "viewpoint": "The towpath by Kanalvejen at the L\u00f8gst\u00f8r end of the canal. Approximate researched point 56.96667, 9.24394, not a surveyed camera. Open-Meteo ran this request on grid 56.95816, 9.24231. Nominatim places Kanalvejen in L\u00f8gst\u00f8r.",
            "refs": [
                "https://da.wikipedia.org/wiki/Frederik_den_VII%27s_kanal",
                "https://da.wikipedia.org/wiki/L%C3%B8gst%C3%B8r",
            ],
            "anchors": [
                "A straight canal with grass banks.",
                "Whitewashed keeper houses with red tile roofs.",
                "A low swing bridge lying closed.",
            ],
            "independent": (
                "Danish Wikipedia describes Frederik VII's Canal as the cut built in 1856\u20131861 around L\u00f8gst\u00f8r Grunde, with whitewashed canal-keeper houses at the ends and a swing bridge by the Limfjord museum. "
                "The frame uses that canal, not a ferry quay at Hvalpsund."
            ),
            "ip": "No museum name and no sign. Internal review only, not a legal certification.",
            "visual": "Pass. Straight canal, white red-roofed houses, low closed bridge, broken cloud. No lettering.",
            "swap": "No site swap. The preferred site was L\u00f8gst\u00f8r Canal. It was not used in DK-01-001 through DK-01-288. City is L\u00f8gst\u00f8r.",
        },
        {
            "entry_id": "DK-01-293",
            "region": "North Jutland",
            "city": "Aars",
            "caption": "Aars Church, Aars",
            **rows["DK-01-293"],
            "composition": "The parish church beside a small paved square \u00b7 AI-generated artistic interpretation",
            "description": (
                "Aars Church stands beside a small paved square: pale walls, a red tile roof, and one west tower, with a few early-autumn trees. "
                f"The square is empty. {sky('DK-01-293')} "
                "Shop fronts are out of the frame. The town spells its name Aars."
            ),
            "alt_text": "AI-generated artistic interpretation of Aars Church on a partly cloudy morning, a pale church and tower by an empty square",
            "viewpoint": "Kirkeplads in front of Aars Kirke. Approximate researched point 56.80501, 9.51398, not a surveyed camera. Open-Meteo ran this request on grid 56.80055, 9.51410. Nominatim places the church in Aars.",
            "refs": [
                "https://da.wikipedia.org/wiki/Aars_Kirke",
                "https://en.wikipedia.org/wiki/Aars",
            ],
            "anchors": [
                "A parish church with one west tower.",
                "A small paved square.",
                "Pale walls and a red tile roof.",
            ],
            "independent": (
                "Aars Kirke is the town church on Kirkeplads. Danish Wikipedia identifies it as the church in Aars in Himmerland and does not support a detailed elevation survey here. "
                "The caption uses the town's own spelling, Aars."
            ),
            "ip": "No shop sign. Internal review only, not a legal certification.",
            "visual": "Pass. Pale church, one tower, red roof, empty square, broken cloud. No shop lettering.",
            "swap": "No site swap. Aars Church was not used in DK-01-001 through DK-01-288. City is Aars.",
        },
        {
            "entry_id": "DK-01-294",
            "region": "Central Jutland",
            "city": "Skive",
            "caption": "Skive Harbour, Skive",
            **rows["DK-01-294"],
            "composition": "A stone quay and fishing boats on Skive Fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                "Skive harbour is a stone quay on Skive Fjord, with fishing boats and a few yachts whose hulls carry no readable names, and low red-roofed warehouses behind. "
                f"The quay is empty. {sky('DK-01-294')} "
                "The water is part of the Limfjord. There is no city skyline."
            ),
            "alt_text": "AI-generated artistic interpretation of Skive harbour on a partly cloudy morning, fishing boats and red roofs on the fjord",
            "viewpoint": "The public quay at Skive Havn. Approximate researched point 56.57067, 9.05314, not a surveyed camera. Open-Meteo ran this request on grid 56.56218, 9.04614. Nominatim places the harbour in Skive.",
            "refs": [
                "https://en.wikipedia.org/wiki/Skive,_Denmark",
                "https://da.wikipedia.org/wiki/Skive",
            ],
            "anchors": [
                "A stone quay.",
                "Fishing boats with blank hulls.",
                "Low red-roofed buildings on the fjord.",
            ],
            "independent": (
                "Skive Havn lies on Skive Fjord, an arm of the Limfjord, in Skive Municipality in Central Jutland. "
                "This is not the harbour at Nyk\u00f8bing Mors."
            ),
            "ip": "No readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Quay, blank fishing boats, red roofs, broken cloud, empty. No lettering.",
            "swap": "No site swap. Skive Harbour was not used in DK-01-001 through DK-01-288. City is Skive. Region is Central Jutland.",
        },
        {
            "entry_id": "DK-01-295",
            "region": "Central Jutland",
            "city": "Dollerup",
            "caption": "Hald Hovedg\u00e5rd, Dollerup",
            **rows["DK-01-295"],
            "composition": "A long red-brick manor and its central pavilion above Hald S\u00f8 \u00b7 AI-generated artistic interpretation",
            "description": (
                "Hald Hovedg\u00e5rd is a long single-storey red-brick manor with a half-hipped roof and a taller central pavilion, seen across the lawn with Hald S\u00f8 in the foreground. "
                f"The grounds are empty. {sky('DK-01-295')} "
                "This is the manor by the lake south of Viborg, not N\u00f8rres\u00f8 and not the medieval ruin."
            ),
            "alt_text": "AI-generated artistic interpretation of Hald Hovedg\u00e5rd at Dollerup on a partly cloudy morning, a red-brick manor above the lake",
            "viewpoint": "The park slope between Hald S\u00f8 and the manor front. Wikipedia gives 56.39292, 9.34385, used as the researched point, not a surveyed camera. Open-Meteo ran this request on grid 56.38891, 9.35078. Nominatim's nearest name at the building is B\u00e6kkelund. The published address is Dollerup. The caption city is Dollerup.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hald_Manor",
                "https://da.wikipedia.org/wiki/Hald_Hovedg%C3%A5rd",
            ],
            "anchors": [
                "A long red-brick manor of one storey.",
                "A taller central pavilion.",
                "Hald S\u00f8 in the foreground, not a town lake.",
            ],
            "independent": (
                "English Wikipedia describes Hald Manor as a single-storey building with a three-storey central section, completed in the 1790s, about 7 km south-west of Viborg on Hald S\u00f8. "
                "N\u00f8rres\u00f8 in the town is already DK-01-214. The medieval bank at the lakeside is not this house."
            ),
            "ip": "No sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick manor, central pavilion, lake, broken cloud, empty grounds. No ruin and no lettering.",
            "swap": "No site swap. Hald Hovedg\u00e5rd was not used in DK-01-001 through DK-01-288. It is distinct from N\u00f8rres\u00f8, Viborg, DK-01-214. City is Dollerup.",
        },
        {
            "entry_id": "DK-01-296",
            "region": "Central Jutland",
            "city": "Ikast",
            "caption": "Ikast Church, Ikast",
            **rows["DK-01-296"],
            "composition": "A red-brick cross church and its west tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Ikast Church is a red-brick church with one west tower, a red tile roof, and lower side wings, seen from the churchyard. "
                f"The yard is empty. {sky('DK-01-296')} "
                "No sculpture is the subject, and no shop sign is in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Ikast Church on a mainly clear morning, a red-brick church with a west tower",
            "viewpoint": "The churchyard at Ikast Kirke, Kirkegade. Approximate researched point 56.13840, 9.15508, not a surveyed camera. Open-Meteo ran this request on grid 56.13666, 9.14923. Nominatim places the church in Ikast.",
            "refs": [
                "https://lex.dk/Ikast_Kirke",
                "https://en.wikipedia.org/wiki/Ikast",
            ],
            "anchors": [
                "Red-brick walls and a red tile roof.",
                "One west tower.",
                "Lower side wings and a churchyard.",
            ],
            "independent": (
                "Lex describes Ikast Kirke as built in red brick, originally with nave, chancel, apse and tower, later extended as a cross church. The present church was consecrated in 1907. "
                "A search for a square named Torvet in Ikast returned Brande's square instead, so the frame uses the church rather than an unverified square name."
            ),
            "ip": "No readable sign and no sculpture as a focal artwork. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, west tower, side wings, mainly clear low sun, empty churchyard. No lettering.",
            "swap": "The suggested town square could not be pinned without colliding with Brande's Torvet in the gazetteer. The verified landmark is Ikast Church. City is Ikast.",
        },
        {
            "entry_id": "DK-01-297",
            "region": "Central Jutland",
            "city": "Herning",
            "caption": "S\u00f8ndre Anl\u00e6g, Herning",
            **rows["DK-01-297"],
            "composition": "A park lake, lawns, and large trees \u00b7 AI-generated artistic interpretation",
            "description": (
                "S\u00f8ndre Anl\u00e6g is the city park south of Herning station: a calm lake, open lawns, and large trees with a little early yellow, and gravel paths. "
                f"The paths are empty. {sky('DK-01-297')} "
                "There is no sculpture and no commercial sign."
            ),
            "alt_text": "AI-generated artistic interpretation of S\u00f8ndre Anl\u00e6g in Herning on a partly cloudy morning, a park lake and trees",
            "viewpoint": "The shore path inside S\u00f8ndre Anl\u00e6g. Approximate researched point 56.13027, 8.97884, not a surveyed camera. Open-Meteo ran this request on grid 56.12759, 8.97365. Nominatim places the park in Herning.",
            "refs": [
                "https://trap.lex.dk/Hernings_parker_og_anl%C3%A6g",
                "https://en.wikipedia.org/wiki/Herning",
            ],
            "anchors": [
                "A calm park lake.",
                "Lawns and large trees.",
                "No sculpture and no logo.",
            ],
            "independent": (
                "Trap Danmark says the Heath Society laid out S\u00f8ndre Anl\u00e6g in 1896 and that the park now has a lake, large trees and lawns. "
                "There is no park named Byparken in the same account. Fuglsang S\u00f8, opened in the 2000s north of town, is a different lake. Birk Centerpark is the sculpture district and is not this frame."
            ),
            "ip": "No brand logo and no artwork as the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Lake, lawns, trees, broken cloud, empty paths. No logo and no sculpture.",
            "swap": "The suggested name City Park is S\u00f8ndre Anl\u00e6g, the town park with a lake. City is Herning.",
        },
        {
            "entry_id": "DK-01-298",
            "region": "Central Jutland",
            "city": "Brande",
            "caption": "Brande Church, Brande",
            **rows["DK-01-298"],
            "composition": "A red-brick parish church and its west tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Brande Church, the one in the town of Brande, is a red-brick church with one west tower and a red tile roof, set in a churchyard with early-autumn trees and low town roofs nearby. "
                f"The yard is empty. {sky('DK-01-298')} "
                "This is not the other Brande Kirke near Silkeborg."
            ),
            "alt_text": "AI-generated artistic interpretation of Brande Church in Brande town on a mainly clear morning",
            "viewpoint": "The churchyard at Brande Kirke on Storegade in Brande. Approximate researched point 55.94532, 9.12506, not a surveyed camera. Open-Meteo ran this request on grid 55.94743, 9.13200. Nominatim places this church in Brande, Ikast-Brande Kommune. A different Brande Kirke near Gjess\u00f8 was rejected.",
            "refs": [
                "https://da.wikipedia.org/wiki/Brande",
                "https://en.wikipedia.org/wiki/Brande",
            ],
            "anchors": [
                "A red-brick church in the town.",
                "One west tower.",
                "A churchyard, not open country near Silkeborg.",
            ],
            "independent": (
                "Danish Wikipedia lists two churches named Brande Kirke. This frame uses the one in Brande Sogn, Ikast-Brande Kommune, at the Storegade coordinates. "
                "The church in Them Sogn near Silkeborg is a different building."
            ),
            "ip": "No sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick church, one tower, churchyard, mainly clear morning light. No lettering.",
            "swap": "No site swap. Brande Church in Brande town was not used in DK-01-001 through DK-01-288. City is Brande.",
        },
        {
            "entry_id": "DK-01-299",
            "region": "South Jutland",
            "city": "Give",
            "caption": "Give Church, Give",
            **rows["DK-01-299"],
            "composition": "A pale stone nave and a later west tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Give Church has a pale stone nave and chancel, a red tile roof, and a west tower, standing in a churchyard with trees that are still mostly green. "
                f"The yard is empty. {sky('DK-01-299')} "
                "Gravestone lettering is not readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Give Church on a mainly clear morning, pale stone walls and a west tower",
            "viewpoint": "The churchyard south of Give Kirke. Approximate researched point 55.84478, 9.24050, not a surveyed camera. Open-Meteo ran this request on grid 55.84556, 9.24442. Nominatim places the church in Give, Vejle Kommune.",
            "refs": [
                "https://da.wikipedia.org/wiki/Give_Kirke",
                "https://en.wikipedia.org/wiki/Give,_Denmark",
            ],
            "anchors": [
                "A pale stone nave and chancel.",
                "A west tower.",
                "A red tile roof and a churchyard.",
            ],
            "independent": (
                "Danish Wikipedia says Give Kirke was built about 1200\u20131225, with a Romanesque chancel and nave of tufa, and that the tower and porch were added in 1905. "
                "Give is in Vejle Municipality. This gallery files Vejle under South Jutland, and Give follows that region label."
            ),
            "ip": "No readable gravestone. Internal review only, not a legal certification.",
            "visual": "Pass. Pale stone church, west tower, red roof, mainly clear morning light. No readable lettering.",
            "swap": "No site swap. Give Church was not used in DK-01-001 through DK-01-288. City is Give. Region is South Jutland.",
        },
        {
            "entry_id": "DK-01-300",
            "region": "South Jutland",
            "city": "Vejen",
            "caption": "Vejen Anl\u00e6g, Vejen",
            **rows["DK-01-300"],
            "composition": "Lawns, mature trees, and a gravel path \u00b7 AI-generated artistic interpretation",
            "description": (
                "Vejen Anl\u00e6g is a small town park of lawns, mature trees with a little early yellow, and a gravel path with plain benches. "
                f"The path is empty. {sky('DK-01-300')} "
                "There is no lake in this frame and no statue."
            ),
            "alt_text": "AI-generated artistic interpretation of Vejen Anl\u00e6g on a mainly clear morning, lawns and mature trees",
            "viewpoint": "A path inside Vejen Anl\u00e6g. Approximate researched point 55.47502, 9.14684, not a surveyed camera. Open-Meteo ran this request on grid 55.47306, 9.14533. Nominatim places the park in Vejen. Vejen Kirke is a separate point about 800 metres north and is not in this frame.",
            "refs": [
                "https://en.wikipedia.org/wiki/Vejen",
                "https://da.wikipedia.org/wiki/Vejen",
            ],
            "anchors": [
                "Lawns and mature trees.",
                "A gravel path.",
                "No lake and no church.",
            ],
            "independent": (
                "Nominatim lists Vejen Anl\u00e6g as a park in Vejen, separate from Vejen Kirke. "
                "The frame is the park. The church was the other option and is not shown."
            ),
            "ip": "No sign. Internal review only, not a legal certification.",
            "visual": "Pass. Park lawns, trees, path, mainly clear low sun, empty. No lake and no lettering.",
            "swap": "No site swap. The suggested pair was the town park or the church. This caption is the park, Vejen Anl\u00e6g. City is Vejen. Region is South Jutland.",
        },
        {
            "entry_id": "DK-01-301",
            "region": "South Jutland",
            "city": "Vamdrup",
            "caption": "Vamdrup Church, Vamdrup",
            **rows["DK-01-301"],
            "composition": "A pale parish church and tower in a churchyard \u00b7 AI-generated artistic interpretation",
            "description": (
                "Vamdrup Church stands at the west end of the town in a green churchyard: pale walls, a red tile roof, and one west tower, with low houses beyond the trees. "
                f"The yard is empty. {sky('DK-01-301')} "
                "This is not the yellow-brick square at Christiansfeld."
            ),
            "alt_text": "AI-generated artistic interpretation of Vamdrup Church on a clear morning, a pale church and tower in a churchyard",
            "viewpoint": "The churchyard at Vamdrup Kirke on Vestergade. Approximate researched point 55.42818, 9.27294, not a surveyed camera. Open-Meteo ran this request on grid 55.42618, 9.27914. Nominatim places the church in Vamdrup.",
            "refs": [
                "https://da.wikipedia.org/wiki/Vamdrup_Kirke",
                "https://en.wikipedia.org/wiki/Vamdrup",
            ],
            "anchors": [
                "A pale church with one west tower.",
                "A red tile roof.",
                "A churchyard at the edge of town.",
            ],
            "independent": (
                "Danish Wikipedia places Vamdrup Kirke at the western end of Vamdrup and says it is thought to have been built between 1200 and 1300 and later rebuilt. "
                "Christiansfeld's church square is already DK-01-044, so this frame does not repeat that yellow-brick street."
            ),
            "ip": "No readable gravestone. Internal review only, not a legal certification.",
            "visual": "Pass. Pale church, red roof, tower, clear low sun, empty churchyard. No lettering.",
            "swap": "Swapped from Christiansfeld. The Moravian square is already DK-01-044, Christiansfeld, Christiansfeld. The unused town between Kolding and Christiansfeld is Vamdrup. The caption is Vamdrup Church. City is Vamdrup.",
        },
        {
            "entry_id": "DK-01-302",
            "region": "South Jutland",
            "city": "Gram",
            "caption": "Gram Castle, Gram",
            **rows["DK-01-302"],
            "composition": "A red-brick manor across its moat \u00b7 AI-generated artistic interpretation",
            "description": (
                "Gram Castle is a red-brick manor with half-hipped red tile roofs and white cornices, seen from outside across the moat, with the wings enclosing a court. "
                f"The near bank is empty. {sky('DK-01-302')} "
                "The view is the exterior only. There is no round tower and no readable sign."
            ),
            "alt_text": "AI-generated artistic interpretation of Gram Castle on a mainly clear morning, a red-brick manor across a moat",
            "viewpoint": "The outer bank of the moat, looking at the manor. Approximate researched point 55.29504, 9.05636, not a surveyed camera. Open-Meteo ran this request on grid 55.29860, 9.06319. Nominatim places Gram Slot in Gram.",
            "refs": [
                "https://trap.lex.dk/Gram_Slot",
                "https://www.visitsonderjylland.com/tourist/information/gram-slot-gdk1116574",
            ],
            "anchors": [
                "Red brick and half-hipped red roofs.",
                "White cornices.",
                "Moat water, and no round towers.",
            ],
            "independent": (
                "Trap Danmark and the South Jutland visitor page describe Gram Slot as a three-wing red-brick manor with red roofs and white cornices, on a moated site. "
                "The frame stays outside. Vamdrup was the other option and is used for the church scene."
            ),
            "ip": "No cafe logo and no flag device. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick manor, moat, white cornices, mainly clear morning light, exterior only. No lettering.",
            "swap": "No site swap. Gram Castle was the preferred site and was not used in DK-01-001 through DK-01-288. City is Gram.",
        },
        {
            "entry_id": "DK-01-303",
            "region": "South Jutland",
            "city": "Vester Vedsted",
            "caption": "Wadden Sea Centre, Vester Vedsted",
            **rows["DK-01-303"],
            "composition": "A low thatched building in the flat marsh \u00b7 AI-generated artistic interpretation",
            "description": (
                "The Wadden Sea Centre is a low building in the flat marsh at Vester Vedsted, with reed thatch running over the roof and down the walls to the ground, and a stretch of pale timber slats. "
                f"The grass in front is empty. {sky('DK-01-303')} "
                "The frame is the exterior. Ribe's cathedral and old town are not in view."
            ),
            "alt_text": "AI-generated artistic interpretation of the Wadden Sea Centre at Vester Vedsted on a partly cloudy morning, a thatched building in the marsh",
            "viewpoint": "The marsh approach to Vadehavscentret, Okholmvej. Approximate researched point 55.29563, 8.66908, not a surveyed camera. Open-Meteo ran this request on grid 55.29511, 8.67038. Nominatim places the museum in Vester Vedsted.",
            "refs": [
                "https://dac.dk/magazine/steder/vadehavscentret-i-ribe-389",
                "https://www.vadehavscentret.dk/udstilling/arkitektur/",
            ],
            "anchors": [
                "Thatch on the roof and down the walls.",
                "A low building on flat marsh.",
                "No cathedral and no readable sign.",
            ],
            "independent": (
                "The centre at Vester Vedsted was extended to a thatched exterior by Dorte Mandrup; the Danish Architecture Center describes reed continuing to the ground. "
                "Ribe Cathedral is DK-01-013, Ribe Old Town is DK-01-142, and Kammerslusen is DK-01-220. The caption city is Vester Vedsted, where the building stands."
            ),
            "ip": "No logo and no exhibition graphic. Internal review only, not a legal certification.",
            "visual": "Pass. Thatched walls and roof, flat marsh, broken cloud, exterior, empty. No lettering.",
            "swap": "No site swap. The Wadden Sea Centre was not used in DK-01-001 through DK-01-288. City is Vester Vedsted, not Ribe.",
        },
        {
            "entry_id": "DK-01-304",
            "region": "South Jutland",
            "city": "H\u00f8jer",
            "caption": "H\u00f8jer Mill, H\u00f8jer",
            **rows["DK-01-304"],
            "composition": "A tall smock mill, a gallery, and a brick warehouse \u00b7 AI-generated artistic interpretation",
            "description": (
                "H\u00f8jer Mill is a tall Dutch smock mill with a whitewashed base, a dark shingled octagonal body, a gallery, a boat-shaped cap and four sails, with a plain brick warehouse beside it and the flat marsh beyond the roofs. "
                f"The yard is empty. {sky('DK-01-304')} "
                "No cafe sign is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of H\u00f8jer Mill on a mainly clear morning, a tall smock mill and a brick warehouse",
            "viewpoint": "The mill yard at M\u00f8llegade. Approximate researched point 54.96420, 8.69304, not a surveyed camera. Open-Meteo ran this request on grid 54.96510, 8.69594. Nominatim places the mill in H\u00f8jer.",
            "refs": [
                "https://msj.dk/en/hoejer-windmill/",
                "https://www.kulturarv.dk/fbb/sagvis.pub?sag=12957365",
            ],
            "anchors": [
                "A whitewashed base and a dark shingled body.",
                "A gallery, a boat-shaped cap, and sails.",
                "A brick warehouse and flat marsh.",
            ],
            "independent": (
                "Museum S\u00f8nderjylland describes H\u00f8jer Mill as a Dutch mill of 1857 with a gallery, on the edge of the marsh. The heritage note describes a whitewashed masonry base, a shingled timber body, and a boat-shaped cap. "
                "T\u00f8nder Old Town is already DK-01-048, so this frame uses the mill in H\u00f8jer."
            ),
            "ip": "No cafe logo and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Smock mill, gallery, sails, brick warehouse, marsh, mainly clear morning light. No lettering.",
            "swap": "Swapped from T\u00f8nder Old Town. That street is already DK-01-048, T\u00f8nder Old Town, T\u00f8nder. The unused marsh-town landmark is H\u00f8jer Mill. City is H\u00f8jer.",
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

        left = ocr_box((0, top, int(w * 0.75), h), "l", "6")
        right = ocr_box((int(w * 0.73), int(h * 0.885), w - 2, int(h * 0.97)), "r", "7")
        txt = left + "\n" + right
        low = txt.lower()
        if "vision" not in low or ("jason" not in low and "ason" not in low):
            raise SystemExit(f"signature OCR {path}\n{txt}")
        if kind == "16x9":
            if "scenario" not in low:
                raise SystemExit(f"scenario OCR {path}\n{txt}")
            if "artistic" not in low and "photograph" not in low:
                raise SystemExit(f"disclosure OCR {path}\n{txt}")
        stems = []
        for word in caption.replace(",", " ").split():
            ascii_word = "".join(ch for ch in word if ch.isascii() and ch.isalpha())
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
        if int(scene["_row"]["is_day"]) != 1:
            raise SystemExit(f"{scene['entry_id']} is_day")
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
    if len(all_scenes) != 304:
        raise SystemExit(f"expected 304 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 305)]
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
    report = bd.ROOT / "approvals" / "BATCH-DK-01-289-304.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pngs = list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-16x9.png"))
    pngs += list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-4x5.png"))
    if len(pngs) != 608:
        raise SystemExit(f"expected 608 masters, got {len(pngs)}")
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

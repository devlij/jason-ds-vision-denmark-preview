#!/usr/bin/env python3
"""Bake DK-01-305 through DK-01-320 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-305-320.json.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-305-320.json").read_text(encoding="utf-8"))

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
        "The model-valid hour is 08:00\u201308:59 Europe/Copenhagen. "
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
    if not str(row["valid"]).startswith("2026-09-25T08:"):
        raise SystemExit(f"{entry} valid {row['valid']}")
    if not str(row["retrieved"]).startswith("2026-09-25T08:"):
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
    if row["code"] == 3 or row["cloud"] >= 80:
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
            "The cited model step is flagged is_day 0. "
            "The scenario minute is after sunrise, so the frame is daylight, not lamplight. "
        )
    else:
        text += "The cited model step is flagged is_day 1. "
    text += f"Cloud cover {row['cloud']}%. "
    text += (
        "The scenario minute has to fall inside this scene's own model-valid hour, "
        "08:00\u201308:59 Europe/Copenhagen, and at or after the cited model step."
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
    for n in range(305, 321):
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

    rows = {f"DK-01-{n}": base(f"DK-01-{n}") for n in range(305, 321)}

    def sky(entry: str) -> str:
        row = rows[entry]
        return (
            f"It is {row['word'].lower()}, about {row['temp']}\u00b0C. "
            f"{wind_clause(row['_row'])} {light(row['_row'])}"
        )

    return [
        {
            "entry_id": "DK-01-305",
            "region": "North Jutland",
            "city": "Hjørring",
            "caption": "Sankt Catharinæ Church, Hjørring",
            **rows["DK-01-305"],
            "composition": "Red-brick cross church and a tall west tower · AI-generated artistic interpretation",
            "description": (
                "From the churchyard by Store Kirkestræde, Sankt Catharinæ is a large red-brick cross church with a tall square west tower. "
                f"The yard is empty. {sky('DK-01-305')} "
                "This is the town church in Hjørring, not the dune tower at Skagen."
            ),
            "alt_text": "AI-generated artistic interpretation of Sankt Catharinæ Church in Hjørring on an overcast morning, a red-brick church with a tall west tower",
            "viewpoint": "The churchyard beside Store Kirkestræde. Approximate researched point 57.46180, 9.98247, not a surveyed camera. Open-Meteo ran this request on grid 57.45865, 9.97726. Nominatim places the church in Hjørring, postal 9800.",
            "refs": [
                "https://da.wikipedia.org/wiki/Sankt_Catharinæ_Kirke",
                "https://www.visitnordvestkysten.dk/nordvestkysten/planlaeg-din-tur/sct-catharinae-kirke-gdk595472",
            ],
            "anchors": [
                "A large red-brick church.",
                "A tall square west tower.",
                "A churchyard, with no dune and no sea.",
            ],
            "independent": (
                "The Danish article describes Sankt Catharinæ as Hjørring's large brick church near the old square, with a west tower raised in the middle of the 1400s. "
                "The Sand-Buried Church is already DK-01-059, so this frame uses the town church."
            ),
            "ip": "No readable name board. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick church, tall west tower, churchyard, overcast morning, empty. No lettering.",
            "swap": "Swapped from the Sand-Buried Church. That tower is already DK-01-059, Sand-Buried Church, Skagen. The unused town church is Sankt Catharinæ. City is Hjørring.",
        },
        {
            "entry_id": "DK-01-306",
            "region": "North Jutland",
            "city": "Frøstrup",
            "caption": "Bulbjerg, Frøstrup",
            **rows["DK-01-306"],
            "composition": "A limestone cliff above dunes and the Jammerbugt · AI-generated artistic interpretation",
            "description": (
                "Bulbjerg is a pale limestone cliff rising out of the dunes above the Jammerbugt, with a small concrete observation bunker on the top and open sea below. "
                f"The cliff top is empty. {sky('DK-01-306')} "
                "The sea stack Skarreklit fell in 1978 and is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Bulbjerg on an overcast morning, a limestone cliff above the Jammerbugt",
            "viewpoint": "The cliff top at Bulbjerg, looking along the face toward the sea. Approximate researched point 57.15841, 9.02492, not a surveyed camera. Open-Meteo ran this request on grid 57.15414, 9.02760. Nominatim names the cliff Bulbjerg in Thisted Kommune and gives it no village. The published approach is Bulbjergvej, postal 7741 Frøstrup.",
            "refs": [
                "https://en.wikipedia.org/wiki/Bulbjerg",
                "https://naturstyrelsen.dk/find-et-naturomraade/naturguider/thy-og-vendsyssel/bulbjerg/oplevelser",
            ],
            "anchors": [
                "A pale limestone cliff above sand dunes.",
                "The North Sea, with no standing sea stack.",
                "A small concrete bunker on the cliff top.",
            ],
            "independent": (
                "Naturstyrelsen describes Bulbjerg as a 47-metre limestone knoll on the Jammerbugt. Wikipedia records that Skarreklit, the sea stack offshore, fell in a storm in 1978, and that a wartime concrete lookout remains on the cliff. "
                "Råbjerg Mile is already DK-01-133, so this frame uses the cliff. The cliff is not itself a town. The caption city is the postal town Frøstrup."
            ),
            "ip": "No sign and no bunker lettering. Internal review only, not a legal certification.",
            "visual": "Pass. Limestone cliff, dunes, sea, small bunker, overcast, empty. No sea stack and no lettering.",
            "swap": "Swapped from Råbjerg Mile. That dune is already DK-01-133, Råbjerg Mile, Kandestederne. The unused cliff is Bulbjerg. City is Frøstrup, the postal town, because the cliff has no village of its own.",
        },
        {
            "entry_id": "DK-01-307",
            "region": "Central Jutland",
            "city": "Jelling",
            "caption": "Kongernes Jelling, Jelling",
            **rows["DK-01-307"],
            "composition": "White museum blocks on the forecourt, mounds beyond · AI-generated artistic interpretation",
            "description": (
                "The approach to Kongernes Jelling shows two parallel white-rendered brick blocks with dark timber sunshades, facing a paved forecourt. Across the square the two grassy mounds and the small white church sit in the distance. "
                f"The forecourt is empty. {sky('DK-01-307')} "
                "The rune stones are not the close subject."
            ),
            "alt_text": "AI-generated artistic interpretation of the Kongernes Jelling visitor centre on a partly cloudy morning, white museum blocks with the mounds beyond",
            "viewpoint": "The forecourt at Gormsgade 23, looking at the visitor centre with the monument area beyond. Approximate researched point 55.75671, 9.41824, not a surveyed camera. Open-Meteo ran this request on grid 55.75559, 9.41800. Nominatim files the address under Vejle Municipality, postal 7300. The town used in the caption is Jelling, as on the stones card.",
            "refs": [
                "https://kongernesjelling.dk/en",
                "https://www.arkitekturbilleder.dk/bygning/kongernes-jelling-besoegscenter",
            ],
            "anchors": [
                "Two parallel white brick museum blocks.",
                "A paved forecourt.",
                "Grassy mounds and a small church in the distance, not a close view of the rune stones.",
            ],
            "independent": (
                "The architecture note describes the visitor centre as two parallel white-rendered brick volumes with a covered gap between them, opposite the mounds and the church, at Gormsgade 23. "
                "The Jelling Stones are already DK-01-052. This frame is the museum approach. The gallery keeps Jelling with Central Jutland, matching that card and the kit row, although Vejle Municipality sits in the Region of Southern Denmark."
            ),
            "ip": "No readable museum name and no featured artwork. The modern painted stone by the entrance is not the subject. Internal review only, not a legal certification.",
            "visual": "Pass. White museum blocks, forecourt, distant mounds and church, broken cloud, empty. No close rune stones and no lettering.",
            "swap": "No site swap. The stones are already DK-01-052, Jelling Stones, Jelling. This card is the visitor-centre approach, which had not been used. City remains Jelling.",
        },
        {
            "entry_id": "DK-01-308",
            "region": "Central Jutland",
            "city": "Hammel",
            "caption": "Frijsenborg Castle, Hammel",
            **rows["DK-01-308"],
            "composition": "Red-brick manor, dark roofs, and a copper lantern across a moat · AI-generated artistic interpretation",
            "description": (
                "From the public road, Frijsenborg is a red-brick neo-renaissance manor of three wings, with dark glazed roofs and a copper lantern spire, standing across a moat. "
                f"The road is empty. {sky('DK-01-308')} "
                "The park behind the house is not entered."
            ),
            "alt_text": "AI-generated artistic interpretation of Frijsenborg Castle near Hammel on an overcast morning, a red-brick manor across a moat",
            "viewpoint": "The public road at Pøt Møllevej, looking across the moat. The building can be seen from the road and is not open as a general visit. Approximate researched point 56.26489, 9.89358, not a surveyed camera. Open-Meteo ran this request on grid 56.26142, 9.88760. Nominatim places the house in Hammel, postal 8450.",
            "refs": [
                "https://en.wikipedia.org/wiki/Frijsenborg",
                "https://www.kultunaut.dk/perl/sted/type-nynaut/UK/version-diverse/nr-151182",
            ],
            "anchors": [
                "A red-brick manor of three wings.",
                "Dark roofs and a copper lantern spire.",
                "A moat between the road and the house.",
            ],
            "independent": (
                "Wikipedia describes Frijsenborg as the manor near Hammel, expanded in the 1860s, visible from the road and not open to the public. KultuNaut gives Pøt Møllevej 15 and the same road-only view. "
                "Gammel Estrup is already DK-01-126, so this frame uses Frijsenborg."
            ),
            "ip": "Private house, exterior from the public road only. No name board. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, dark roofs, copper lantern, moat, overcast morning, empty road. No lettering.",
            "swap": "Swapped from Gammel Estrup. That manor is already DK-01-126, Gammel Estrup, Auning. The unused manor seen from the road is Frijsenborg. City is Hammel.",
        },
        {
            "entry_id": "DK-01-309",
            "region": "Central Jutland",
            "city": "Hornslet",
            "caption": "Rosenholm Castle, Hornslet",
            **rows["DK-01-309"],
            "composition": "Red-brick Renaissance wings and copper-capped towers across a moat · AI-generated artistic interpretation",
            "description": (
                "Rosenholm's red-brick wings, steep red roofs, stepped gables, and round towers with copper caps stand across the moat, with a gate tower and a copper spire in the silhouette. "
                f"The bank is empty. {sky('DK-01-309')} "
                "The courtyard and the private chapel are not the view."
            ),
            "alt_text": "AI-generated artistic interpretation of Rosenholm Castle at Hornslet on an overcast morning, red-brick wings and copper-capped towers across a moat",
            "viewpoint": "The outer bank of the moat on Rosenholmvej, looking at the castle. Approximate researched point 56.33327, 10.33125, not a surveyed camera. Open-Meteo ran this request on grid 56.33390, 10.32986. Nominatim places the castle in Hornslet. The castle's own page gives Rosenholmvej 119, 8543 Hornslet. Nominatim returned postal 8544.",
            "refs": [
                "https://www.rosenholm.dk/en/om-rosenholm-slot/",
                "https://en.wikipedia.org/wiki/Rosenholm_Castle",
            ],
            "anchors": [
                "Red-brick wings with steep red roofs and stepped gables.",
                "Round towers with copper caps and a gate tower.",
                "A moat in the foreground.",
            ],
            "independent": (
                "The castle's own page describes an early Renaissance house of 1559 to about 1610, the east wing flanked by two dome-capped towers, and a moat. "
                "Clausholm Castle is already DK-01-213, so this frame uses Rosenholm. City is Hornslet."
            ),
            "ip": "Exterior only. No interior paintings and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, copper caps, moat, overcast morning, empty. No lettering.",
            "swap": "No site swap. Clausholm is already DK-01-213, Clausholm Castle, Voldum. Rosenholm Castle had not been used. City is Hornslet.",
        },
        {
            "entry_id": "DK-01-310",
            "region": "North Jutland",
            "city": "Dronninglund",
            "caption": "Voergaard Castle, Dronninglund",
            **rows["DK-01-310"],
            "composition": "Red-brick manor, octagonal towers, and a broad moat · AI-generated artistic interpretation",
            "description": (
                "Voergaard is a red-brick Renaissance manor with octagonal corner towers and a sandstone portal, seen across a broad moat. "
                f"The bank is empty. {sky('DK-01-310')} "
                "The rooms and the collection are not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Voergaard Castle on an overcast morning, a red-brick manor with octagonal towers across a broad moat",
            "viewpoint": "The near bank of the moat, looking at the entrance front. Approximate researched point 57.24252, 10.33543, not a surveyed camera. Open-Meteo ran this request on grid 57.24002, 10.34062. Nominatim places the building in the hamlet Voer and returns postal 9352. The castle's published address is Voergaard 6, 9330 Dronninglund. The caption city is Dronninglund.",
            "refs": [
                "https://en.wikipedia.org/wiki/Voergaard_Castle",
                "https://www.enjoynordjylland.com/north-jutland/plan-your-trip/voergaard-slot-gdk600579",
            ],
            "anchors": [
                "A red-brick manor with octagonal corner towers.",
                "A sandstone portal on the entrance front.",
                "A broad moat in the foreground.",
            ],
            "independent": (
                "Wikipedia describes Voergaard as a two-winged red-brick Renaissance manor with octagonal corner towers and a sandstone portal, north of Dronninglund. The tourism note describes the moat and the portal on the approach. "
                "The frame does not repeat a ranking about the moat. City is Dronninglund, the published town. The hamlet on the map is Voer."
            ),
            "ip": "Exterior only. No collection and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, octagonal towers, broad moat, overcast morning, empty. No lettering.",
            "swap": "No site swap. Voergaard Castle was not used in DK-01-001 through DK-01-304. City is Dronninglund.",
        },
        {
            "entry_id": "DK-01-311",
            "region": "Central Jutland",
            "city": "Spøttrup",
            "caption": "Spøttrup Castle, Spøttrup",
            **rows["DK-01-311"],
            "composition": "A red-brick fortress rising from a double moat · AI-generated artistic interpretation",
            "description": (
                "From the west approach, Spøttrup is a red-brick medieval fortress of short wings and a projecting gate tower, rising from the inner moat, with a grass rampart and a second moat outside it. "
                f"The bridge is empty. {sky('DK-01-311')} "
                "The courtyard is not the view."
            ),
            "alt_text": "AI-generated artistic interpretation of Spøttrup Castle on an overcast morning, a red-brick fortress rising from its moat",
            "viewpoint": "The west approach across the outer moat. Approximate researched point 56.63964, 8.78283, not a surveyed camera. Open-Meteo ran this request on grid 56.63851, 8.78827. Nominatim places the castle in the hamlet Spøttrup, with the village Rødding also named, postal 7860. The caption city is Spøttrup.",
            "refs": [
                "https://www.en.spottrupborg.dk/the-history-of-the-castle/",
                "https://kulturarv.dk/fbb/sagvis.pub?sag=20039630",
            ],
            "anchors": [
                "Red-brick walls rising from the water.",
                "A projecting gate tower.",
                "A grass rampart and a second moat.",
            ],
            "independent": (
                "The castle history page describes ramparts and a double moat. The heritage record describes three short wings, a gate tower toward the west, and walls that rise from the moat. "
                "Ørslev Kloster was the other unused option and was not needed. City is Spøttrup."
            ),
            "ip": "No readable year anchors treated as signage. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick fortress, gate tower, moat and rampart, overcast morning, empty. No lettering.",
            "swap": "No site swap between the two options. Both Ørslev Kloster and Spøttrup Castle were unused. This card uses Spøttrup Castle. City is Spøttrup. Ørslev Kloster remains unused.",
        },
        {
            "entry_id": "DK-01-312",
            "region": "Central Jutland",
            "city": "Vemb",
            "caption": "Nørre Vosborg, Vemb",
            **rows["DK-01-312"],
            "composition": "A whitewashed manor and a gate tower behind a moat · AI-generated artistic interpretation",
            "description": (
                "The approach to Nørre Vosborg shows the gate tower in front of whitewashed wings and red roofs, with the moat and a grass rampart around the house. "
                f"The drive is empty. {sky('DK-01-312')} "
                "No hotel name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Nørre Vosborg near Vemb on an overcast morning, a whitewashed manor and a gate tower",
            "viewpoint": "The approach across the moat toward the gate tower. Approximate researched point 56.32666, 8.32944, not a surveyed camera. Open-Meteo ran this request on grid 56.32528, 8.32469. Nominatim places the manor in Vemb, postal 7570. The published address is Vembvej 35.",
            "refs": [
                "https://lex.dk/N%C3%B8rre_Vosborg",
                "https://www.visit-nordvestkysten.com/the-northwest-coast/whatson/norre-vosborg-manor-gdk606918",
            ],
            "anchors": [
                "Whitewashed wings and red roofs.",
                "A gate tower on the approach.",
                "A moat and a grass rampart.",
            ],
            "independent": (
                "Lex describes a whitewashed four-wing house on a moated site south of Vemb, and a gate tower from about 1790. The visit note says the tower is what the approach shows first. A hotel wing was added in the 2008 restoration, so the complex is shown as it stands, without a readable name."
            ),
            "ip": "No hotel logo and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. White manor, gate tower, moat, overcast morning, empty. No lettering.",
            "swap": "No site swap. Nørre Vosborg was not used in DK-01-001 through DK-01-304. City is Vemb.",
        },
        {
            "entry_id": "DK-01-313",
            "region": "North Jutland",
            "city": "Vrå",
            "caption": "Vrå Church, Vrå",
            **rows["DK-01-313"],
            "composition": "A granite and brick village church with a tall tower · AI-generated artistic interpretation",
            "description": (
                "Vrå Church has a granite-ashlar nave, a tower of reused granite below and brick above, a saddle roof with east and west gables rather than a spire, and a porch on the north side. "
                f"The yard is empty. {sky('DK-01-313')} "
                "The abbey at Børglum is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Vrå Church on an overcast morning, a granite and brick church with a tall tower",
            "viewpoint": "The churchyard on Østergade. Approximate researched point 57.35268, 9.94484, not a surveyed camera. Open-Meteo ran this request on grid 57.34945, 9.94318. Nominatim places the church in Vrå, postal 9760.",
            "refs": [
                "https://da.wikipedia.org/wiki/Vrå_Kirke",
                "https://lex.dk/Vr%C3%A5_Kirke",
            ],
            "anchors": [
                "A granite-block nave, partly whitewashed.",
                "A tower with a saddle roof and gables, not a spire.",
                "A porch on the north side and a churchyard.",
            ],
            "independent": (
                "Lex, written for the National Museum, describes granite nave and chancel, a brick tower on reused granite below, a north porch, and a saddle roof with gables. The Danish Wikipedia article also notes the year 1760 on the tower. The frame follows the Lex exterior and does not treat a year as readable lettering. "
                "Børglum Abbey is already DK-01-231. Its postal town is Vrå, but the abbey is a different place. This frame is the church in the town of Vrå."
            ),
            "ip": "No readable board. A mark on the tower, if present, is not treated as a sign. Internal review only, not a legal certification.",
            "visual": "Pass. Granite and brick church, saddle-roof tower, north porch, churchyard, overcast morning, empty. No readable sign.",
            "swap": "Swapped from Børglum Abbey. That abbey is already DK-01-231, Børglum Abbey, Børglum. The unused church in the postal town is Vrå Church. City is Vrå.",
        },
        {
            "entry_id": "DK-01-314",
            "region": "South Jutland",
            "city": "Sønderho",
            "caption": "Sønderho Church, Sønderho",
            **rows["DK-01-314"],
            "composition": "A whitewashed church with a red roof and no tower · AI-generated artistic interpretation",
            "description": (
                "Sønderho Church is a whitewashed, nearly square building with a red tile roof and no tower. The bell sits by openings in the east gable, and a low churchyard surrounds the walls. "
                f"The yard is empty. {sky('DK-01-314')} "
                "The thatched village lane is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Sønderho Church on an overcast morning, a whitewashed church with a red roof and no tower",
            "viewpoint": "The churchyard at Sønderho Strandvej. Approximate researched point 55.34969, 8.46668, not a surveyed camera. Open-Meteo ran this request on grid 55.34656, 8.47229. Nominatim places the church in Sønderho. The parish page gives Sønderho Strandvej 1A.",
            "refs": [
                "https://www.kirkernepaafano.dk/kirker/soenderho-kirke",
                "https://da.wikipedia.org/wiki/Sønderho_Kirke",
            ],
            "anchors": [
                "A whitewashed church with a red tile roof.",
                "No tower. Openings in the east gable.",
                "A churchyard, not a thatched street.",
            ],
            "independent": (
                "The parish page says the church was built in 1782 and that the bell hangs in a frame against the east gable, with two openings so the sound carries. The Danish article describes the nearly square plan. "
                "The village lane is already DK-01-143, Sønderho, Sønderho."
            ),
            "ip": "No readable name. Internal review only, not a legal certification.",
            "visual": "Pass. White church, red roof, no tower, churchyard, overcast morning, empty. No lettering.",
            "swap": "Swapped from the Sønderho village street. That lane is already DK-01-143, Sønderho, Sønderho. The unused building is Sønderho Church. City remains Sønderho.",
        },
        {
            "entry_id": "DK-01-315",
            "region": "South Jutland",
            "city": "Havneby",
            "caption": "Havneby Harbour, Havneby",
            **rows["DK-01-315"],
            "composition": "A concrete mole and small boats on the Wadden Sea · AI-generated artistic interpretation",
            "description": (
                "Havneby harbour is a concrete mole with a few small boats, flat island ground, and the Wadden Sea. "
                f"The quay is empty. {sky('DK-01-315')} "
                "No ferry name is readable, and the west-coast beach is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Havneby harbour on Rømø on a partly cloudy morning, a concrete mole and small boats",
            "viewpoint": "The quay at Rømø Havn, Nordre Mole. Approximate researched point 55.08728, 8.56875, not a surveyed camera. Open-Meteo ran this request on grid 55.08310, 8.56610. Nominatim places the marina in Havneby, postal 6792.",
            "refs": [
                "https://en.wikipedia.org/wiki/Rømø",
                "https://da.wikipedia.org/wiki/Havneby",
            ],
            "anchors": [
                "A concrete harbour mole.",
                "A few small boats.",
                "Flat island and open water. No beach as the subject.",
            ],
            "independent": (
                "Havneby is the port village on the southeast of Rømø. Nominatim names this basin Rømø Havn. "
                "Lakolk Beach is already DK-01-144. Odden Harbour, Havnebyen, DK-01-175, is a different town on Sjællands Odde. The branded ferry is not the subject."
            ),
            "ip": "No ferry name, no company mark, and no readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, small boats, flat island, broken cloud, empty quay. No readable name.",
            "swap": "No site swap. Lakolk Beach is already DK-01-144, Lakolk Beach, Lakolk. Havneby Harbour had not been used. City is Havneby, not Havnebyen.",
        },
        {
            "entry_id": "DK-01-316",
            "region": "South Jutland",
            "city": "Mandø",
            "caption": "Mandø Causeway, Mandø",
            **rows["DK-01-316"],
            "composition": "A raised tidal track and marker poles across the flats · AI-generated artistic interpretation",
            "description": (
                "Låningsvejen is a straight raised track with a line of plain wooden marker poles across the tidal flats toward Mandø. "
                f"The track is empty. {sky('DK-01-316')} "
                "The tide was not checked. The church on the island is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of the Mandø causeway on an overcast morning, a raised track and marker poles across the flats",
            "viewpoint": "On Låningsvejen, the tidal causeway, looking along the poles. Approximate researched point 55.29225, 8.57799, not a surveyed camera. Open-Meteo ran this request on grid 55.28982, 8.57687. Nominatim names the road Låningsvejen and does not give it a village at this point. The mainland end is Vester Vedsted. The caption city is Mandø, the island the road approaches.",
            "refs": [
                "https://en.wikipedia.org/wiki/Mandø",
                "https://da.wikipedia.org/wiki/Mandø",
            ],
            "anchors": [
                "A raised track across tidal flats.",
                "A line of wooden marker poles.",
                "No church and no cars.",
            ],
            "independent": (
                "Mandø is reached from Vester Vedsted by Låningsvejen, a tidal road marked by poles. "
                "The island church is already DK-01-096, Mandø, Mandø. The Wadden Sea Centre is DK-01-303 at Vester Vedsted. This frame is the causeway itself. The tide at the scenario minute was not checked, so the picture does not claim a passable or a flooded road as an observation."
            ),
            "ip": "No sign and no vehicle livery. Internal review only, not a legal certification.",
            "visual": "Pass. Raised track, marker poles, flats, overcast morning, empty. No church and no lettering.",
            "swap": "No site swap. The island church is already DK-01-096, Mandø, Mandø. This card is the causeway, which had not been used. City remains Mandø.",
        },
        {
            "entry_id": "DK-01-317",
            "region": "South Jutland",
            "city": "Nordborg",
            "caption": "Nordborg Castle, Nordborg",
            **rows["DK-01-317"],
            "composition": "A whitewashed castle on a holm in Nordborg Lake · AI-generated artistic interpretation",
            "description": (
                "From the lake shore, Nordborg Castle is a whitewashed building with plain facades and a simplified gate building, standing on a small holm in Nordborg Lake, with lime trees along the bank. "
                f"The shore is empty. {sky('DK-01-317')} "
                "Sønderborg Castle is a different building and is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Nordborg Castle on a mainly clear morning, a whitewashed castle on a holm in the lake",
            "viewpoint": "The public shore of Nordborg Lake, looking toward the castle holm. The park is the public approach. The buildings are used by a boarding school. Approximate researched point 55.05907, 9.74785, not a surveyed camera. Open-Meteo ran this request on grid 55.05502, 9.74298. Nominatim places the castle in Nordborg, postal 6430.",
            "refs": [
                "https://en.wikipedia.org/wiki/Nordborg_Castle",
                "https://trap.lex.dk/Nordborg_Slot",
            ],
            "anchors": [
                "A whitewashed castle with plain facades.",
                "A gate building toward the approach.",
                "Lake water and trees. Not Sønderborg Castle.",
            ],
            "independent": (
                "Trap Danmark describes the present buildings as Eugen Fink's plain neo-baroque rebuilding of 1909–10, on a holm at the west end of Nordborg Lake, reusing old foundations. Oplev Jylland calls the castle whitewashed. "
                "Sønderborg Castle is already DK-01-041. City is Nordborg."
            ),
            "ip": "No school name and no readable arms treated as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. White castle, lake, trees, mainly clear morning light, empty shore. No lettering.",
            "swap": "No site swap. Nordborg Castle was not used in DK-01-001 through DK-01-304. It is distinct from Sønderborg Castle, DK-01-041. City is Nordborg.",
        },
        {
            "entry_id": "DK-01-318",
            "region": "Funen",
            "city": "Store Rise",
            "caption": "Rise Church, Store Rise",
            **rows["DK-01-318"],
            "composition": "A whitewashed church and a copper spire · AI-generated artistic interpretation",
            "description": (
                "Rise Church is whitewashed, with red tile roofs and a west tower carrying an octagonal copper spire, inside a churchyard wall in the village. "
                f"The lane is empty. {sky('DK-01-318')} "
                "The cliff at Voderup is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Rise Church in Store Rise on an overcast morning, a whitewashed church with a copper spire",
            "viewpoint": "The churchyard lane at St. Rise Landevej. Approximate researched point 54.85403, 10.39971, not a surveyed camera. Open-Meteo ran this request on grid 54.86000, 10.40000. Nominatim places the church in Store Rise. The Danish article gives St. Rise Landevej 9, postal 5970 Ærøskøbing. The caption city is the village, Store Rise.",
            "refs": [
                "https://lex.dk/Rise_Kirke_-_%C3%86r%C3%B8_Kommune",
                "https://da.wikipedia.org/wiki/Rise_Kirke_(%C3%86r%C3%B8)",
            ],
            "anchors": [
                "A whitewashed church with a red tile roof.",
                "A west tower and an octagonal copper spire.",
                "A churchyard wall in a village, not a cliff.",
            ],
            "independent": (
                "Lex describes Rise Church as whitewashed with red tile roofs, and a large late-Gothic tower with an octagonal copper-covered spire. The Danish article places it in the village Store Rise. The spire has been copper-covered since 1957. "
                "Voderup Klint is already DK-01-278. The user name Rise is the parish. The village is Store Rise."
            ),
            "ip": "No readable board. Internal review only, not a legal certification.",
            "visual": "Pass. White church, red roof, copper spire, churchyard, overcast morning, empty. No lettering.",
            "swap": "No site swap away from Rise. Voderup Klint is already DK-01-278, Voderup Klint, Voderup. Rise Church had not been used. City is Store Rise, the village, not Rise as a town name and not Ærøskøbing.",
        },
        {
            "entry_id": "DK-01-319",
            "region": "North Jutland",
            "city": "Vesterø Havn",
            "caption": "Vesterø Harbour, Vesterø Havn",
            **rows["DK-01-319"],
            "composition": "A fishing mole and small boats on the north side of Læsø · AI-generated artistic interpretation",
            "description": (
                "Vesterø harbour is a mole with a few small fishing boats, low sheds, and open water on the flat north side of Læsø. "
                f"The quay is empty. {sky('DK-01-319')} "
                "The seaweed-roofed farmhouses are not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Vesterø harbour on a partly cloudy morning, a mole and small fishing boats",
            "viewpoint": "The quay at Vesterø Havn. Approximate researched point 57.29507, 10.92654, not a surveyed camera. Open-Meteo ran this request on grid 57.29760, 10.93071. Nominatim names the place Vesterø Havn in Læsø Kommune.",
            "refs": [
                "https://en.wikipedia.org/wiki/Læsø",
                "https://da.wikipedia.org/wiki/Vesterø_Havn",
            ],
            "anchors": [
                "A harbour mole.",
                "A few small boats and low sheds.",
                "Open water. No seaweed roof as the subject.",
            ],
            "independent": (
                "Vesterø Havn is the harbour settlement on the north of Læsø. "
                "The seaweed houses are already DK-01-062, Seaweed Houses, Læsø. This frame is the harbour, and the city is Vesterø Havn."
            ),
            "ip": "No readable boat name and no ferry mark. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, small boats, sheds, broken cloud, fresh wind on the water, empty quay. No lettering.",
            "swap": "No site swap. The seaweed houses are already DK-01-062, Seaweed Houses, Læsø. Vesterø Harbour had not been used. City is Vesterø Havn.",
        },
        {
            "entry_id": "DK-01-320",
            "region": "Central Jutland",
            "city": "Anholt",
            "caption": "Anholt Harbour, Anholt",
            **rows["DK-01-320"],
            "composition": "A small pier, a few boats, and dunes · AI-generated artistic interpretation",
            "description": (
                "Anholt harbour is a small concrete pier with a few boats, low houses, and dunes behind the quay. "
                f"The pier is empty. {sky('DK-01-320')} "
                "The tall lighthouse stands at the east end of the island and is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Anholt harbour on an overcast morning, a small pier and a few boats",
            "viewpoint": "The quay at Anholt havn. Approximate researched point 56.71489, 11.51260, not a surveyed camera. Open-Meteo ran this request on grid 56.71596, 11.52016. Nominatim places the harbour in Anholt, Norddjurs Kommune, postal 8592. The gallery region is Central Jutland.",
            "refs": [
                "https://en.wikipedia.org/wiki/Anholt_(Denmark)",
                "https://da.wikipedia.org/wiki/Anholt",
            ],
            "anchors": [
                "A small concrete harbour pier.",
                "A few boats and low houses.",
                "Dunes. No tall lighthouse.",
            ],
            "independent": (
                "Anholt is the Kattegat island in Norddjurs. The harbour used here is the west-side haven. Anholt Fyr, the tall lighthouse, stands at the eastern tip and is a different viewpoint, so it is not shown. "
                "The island had not been used in DK-01-001 through DK-01-304."
            ),
            "ip": "No readable boat name and no sign. Internal review only, not a legal certification.",
            "visual": "Pass. Small pier, boats, low houses, dunes, overcast morning, empty. No lighthouse and no lettering.",
            "swap": "No site swap. Anholt harbour was not used in DK-01-001 through DK-01-304. The east-end lighthouse was left out of this harbour frame. City is Anholt.",
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
        if not hour.startswith("08:"):
            raise SystemExit(f"{scene['entry_id']} scenario {label} outside valid hour 08")
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
    if len(all_scenes) != 320:
        raise SystemExit(f"expected 320 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 321)]
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
    report = bd.ROOT / "approvals" / "BATCH-DK-01-305-320.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pngs = list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-16x9.png"))
    pngs += list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-4x5.png"))
    if len(pngs) != 640:
        raise SystemExit(f"expected 640 masters, got {len(pngs)}")
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

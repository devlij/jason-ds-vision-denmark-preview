#!/usr/bin/env python3
"""Bake DK-01-321 through DK-01-336 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-321-336.json.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-321-336.json").read_text(encoding="utf-8"))
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
    if entry in {"DK-01-332", "DK-01-333"}:
        return FAROE
    if entry in {"DK-01-334", "DK-01-335", "DK-01-336"}:
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
    for n in range(321, 337):
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

    rows = {f"DK-01-{n}": base(f"DK-01-{n}") for n in range(321, 337)}

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
            "entry_id": "DK-01-321",
            "region": "Capital Region",
            "city": "Helsing\u00f8r",
            "caption": "Marienlyst Castle, Helsing\u00f8r",
            "composition": "A pale neoclassical palace with a flat roof and a balustrade \u00b7 AI-generated artistic interpretation",
            "lead": "From the formal garden, Marienlyst is a pale neoclassical palace, the center block set forward of the side wings, with a flat roof and a balustrade. The gravel court is empty.",
            "tail": "Kronborg and the dry-dock museum are not in this frame.",
            "alt_text": "AI-generated artistic interpretation of Marienlyst Castle in Helsing\u00f8r on a mainly clear afternoon, a pale palace with a balustrade",
            "viewpoint": "The gravel court in the formal garden, looking at the garden front. Approximate researched point 56.04201, 12.60198, not a surveyed camera. Open-Meteo ran this request on grid 56.04565, 12.60959. Nominatim places the castle in Helsing\u00f8r, postal 3000.",
            "refs": [
                "https://en.wikipedia.org/wiki/Marienlyst_Castle",
                "https://helsingorleksikon.dk/index.php/Marienlyst_Slot",
            ],
            "anchors": [
                "A pale neoclassical palace, center block forward of the side wings.",
                "A flat roof with a balustrade, not a dome and not fortress spires.",
                "A formal garden and gravel court.",
            ],
            "independent": "Nicolas-Henri Jardin's palace of 1759\u20131763 extended the older pavilion with side wings and a balustraded roofline. It stands in its own garden west of the town, apart from Kronborg and from the shipyard dry dock.",
            "ip": "No readable museum name. Interior paintings are not shown. Internal review only, not a legal certification.",
            "visual": "Pass. Pale palace, flat roof, balustrade, side wings, formal hedges, mainly clear afternoon, empty. No dome, no Kronborg, no lettering.",
            "swap": "Swapped from the M/S Maritime Museum exterior. That dry dock and its glass bridges are already DK-01-029, Maritime Museum, Helsing\u00f8r. Helsing\u00f8r Harbour is DK-01-257 and Kronborg is DK-01-004. The unused palace is Marienlyst. City remains Helsing\u00f8r.",
        },
        {
            "entry_id": "DK-01-322",
            "region": "Bornholm",
            "city": "Nyker",
            "caption": "Nyker Round Church, Nyker",
            "composition": "A low white round church under a conical roof \u00b7 AI-generated artistic interpretation",
            "lead": "From the churchyard, Nyker Round Church is a low white round nave under a dark conical roof, with a small apse and a porch. The yard is empty.",
            "tail": "It does not have the heavy buttresses of \u00d8sterlars, and there is no separate bell tower.",
            "alt_text": "AI-generated artistic interpretation of Nyker Round Church on an overcast afternoon, a low white round church with a conical roof",
            "viewpoint": "The churchyard at Ellebyvej 1A. Approximate researched point 55.13935, 14.76914, not a surveyed camera. Open-Meteo ran this request on grid 55.14216, 14.77458. Nominatim places the church in the village Nyker, postal 3700.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ny_Kirke",
                "https://bornholm.info/en/ny-kirke/",
            ],
            "anchors": [
                "A low whitewashed round nave.",
                "A dark conical roof, not a square tower.",
                "A small apse, a porch, and a churchyard.",
            ],
            "independent": "Ny Kirke is the round church in Nyker. The English Wikipedia article describes a round nave, apse, rectangular choir, and a later porch, built of fieldstone. Destination Bornholm describes the conical roof. \u00d8sterlars is DK-01-067 and Olsker is DK-01-246.",
            "ip": "No readable board. Interior frescos are not shown. Internal review only, not a legal certification.",
            "visual": "Pass. White round nave, conical roof, apse, porch, overcast, empty yard. No separate square tower and no lettering.",
            "swap": "Swapped from Kastellet ramparts. Kastellet, including the rampart windmill and the moat, is already DK-01-021, Kastellet, Copenhagen. The unused round church is Nyker. City is Nyker. The gallery region is Bornholm.",
        },
        {
            "entry_id": "DK-01-323",
            "region": "Lolland-Falster",
            "city": "Borre",
            "caption": "Liselund, Borre",
            "composition": "A small white thatched manor across a park pond \u00b7 AI-generated artistic interpretation",
            "lead": "Across the park pond, Liselund's old manor is a small white house with a thick thatched roof and a columned porch. The bank is empty.",
            "tail": "The later hotel building, Liselund Ny Slot, is not the subject, and the chalk cliffs are not in this frame.",
            "alt_text": "AI-generated artistic interpretation of Liselund old manor near Borre on a mainly clear afternoon, a small white thatched house",
            "viewpoint": "The near bank of the park pond, looking at Liselund Gammel Slot. Approximate researched point 54.99905, 12.52448, not a surveyed camera. Open-Meteo ran this request on grid 54.99912, 12.52188. Nominatim places Langebjergvej 4 in Borre, postal 4791. The manor's own page uses that address.",
            "refs": [
                "https://liselundpark.dk/en",
                "https://liselundpark.dk/en/knowledge/liselund-castle",
            ],
            "anchors": [
                "A small white house, not a large palace.",
                "A thick thatched roof and a columned porch.",
                "A pond and park trees in front.",
            ],
            "independent": "The manor page describes the 1792 house by Andreas Kirkerup at the end of the garden glade, with a classical portico. The park is open daily. Liselund Ny Slot, the later building, is a different house and is not this frame. The gallery keeps M\u00f8n with Lolland-Falster, as on the M\u00f8ns Klint card. Administratively the municipality is in Region Zealand.",
            "ip": "Exterior only. No interior furnishings. Internal review only, not a legal certification.",
            "visual": "Pass. Small white house, thatched roof, porch, pond, mainly clear afternoon, empty. No red-tile palace and no lettering.",
            "swap": "Swapped from the Amalienborg courtyard. Amalienborg square is already DK-01-003, Amalienborg, Copenhagen. The unused manor is Liselund's old thatched house. City is Borre, the postal village on the address.",
        },
        {
            "entry_id": "DK-01-324",
            "region": "Capital Region",
            "city": "J\u00e6gerspris",
            "caption": "J\u00e6gerspris Castle, J\u00e6gerspris",
            "composition": "An oxblood three-wing palace with three dark spires \u00b7 AI-generated artistic interpretation",
            "lead": "From the approach, J\u00e6gerspris is an oxblood-red three-wing palace with black roofs and three dark spires. The drive is empty.",
            "tail": "The long farm wings are not the subject.",
            "alt_text": "AI-generated artistic interpretation of J\u00e6gerspris Castle on a clear afternoon, an oxblood palace with three spires",
            "viewpoint": "The outer approach toward the courtyard. Approximate researched point 55.85644, 11.97453, not a surveyed camera. Open-Meteo ran this request on grid 55.86071, 11.96899. Nominatim places the castle in J\u00e6gerspris, Frederikssund Kommune, postal 3630.",
            "refs": [
                "https://kongfrederik.dk/slottets-historie/",
                "https://trap.lex.dk/J%C3%A6gerspris_Slot",
            ],
            "anchors": [
                "A three-wing palace plastered a deep oxblood red.",
                "Black roofs.",
                "Three towers with dark spires.",
            ],
            "independent": "The foundation history page describes the U-shaped plan finished under Frederik 5, with spires on the three towers. A castle note records the present oxblood colour under black tile roofs. The gallery region is Capital Region because Frederikssund Municipality is in Region Hovedstaden.",
            "ip": "Exterior only. No readable foundation name. Internal review only, not a legal certification.",
            "visual": "Pass. Oxblood wings, black roofs, three spires, clear afternoon, empty drive. No lettering.",
            "swap": "Swapped from the Viking Ship Museum quay. That harbour view is already DK-01-086, Viking Ship Museum, Roskilde. The unused palace is J\u00e6gerspris. City is J\u00e6gerspris.",
        },
        {
            "entry_id": "DK-01-325",
            "region": "Funen",
            "city": "Odense",
            "caption": "Brandts, Odense",
            "composition": "Red-brick factory buildings around a courtyard \u00b7 AI-generated artistic interpretation",
            "lead": "The Brandts courtyard is enclosed by red-brick factory buildings with tall industrial windows, and the city river shows at one side. The yard is empty.",
            "tail": "This is the old cloth mill in the centre, not the harbour canal.",
            "alt_text": "AI-generated artistic interpretation of the Brandts cloth-mill courtyard in Odense on an overcast afternoon",
            "viewpoint": "The courtyard of the old cloth mill. Approximate researched point 55.39593, 10.38043, not a surveyed camera. Open-Meteo ran this request on grid 55.39626, 10.38689. Nominatim places Brandts Kl\u00e6defabrik in Odense, postal 5000.",
            "refs": [
                "https://da.wikipedia.org/wiki/Brandts_Kl%C3%A6defabrik",
                "https://brandts.dk/en/",
            ],
            "anchors": [
                "Red-brick industrial buildings.",
                "Tall factory windows around a courtyard.",
                "A short stretch of the city river, not a harbour canal with a bridge.",
            ],
            "independent": "Brandts Kl\u00e6defabrik is the former textile mill in central Odense, now a cultural complex. It sits by the river in the city, which is a different stretch from the harbour canal already used as DK-01-199.",
            "ip": "No readable brand name and no poster treated as artwork. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick mill, tall windows, courtyard, overcast afternoon, empty. No logo and no harbour bridge.",
            "swap": "No site swap. The harbour canal is already DK-01-199, Odense Canal, Odense. Brandts, the old cloth mill, had not been used. City is Odense.",
        },
        {
            "entry_id": "DK-01-326",
            "region": "Central Jutland",
            "city": "Aarhus",
            "caption": "Aarhus Cathedral, Aarhus",
            "composition": "One tall brick tower and a single slender spire \u00b7 AI-generated artistic interpretation",
            "lead": "From the cathedral square, Aarhus Cathedral is a red-brick Gothic church with one tall west tower and a single slender spire. The square is empty.",
            "tail": "The rainbow museum is not in this frame.",
            "alt_text": "AI-generated artistic interpretation of Aarhus Cathedral on a partly cloudy afternoon, one brick tower and a slender spire",
            "viewpoint": "The square in front of the west tower. Approximate researched point 56.15685, 10.21065, not a surveyed camera. Open-Meteo ran this request on grid 56.15868, 10.20799. Nominatim places Aarhus Domkirke in Aarhus, postal 8000.",
            "refs": [
                "https://en.wikipedia.org/wiki/Aarhus_Cathedral",
                "https://aarhusdomkirke.dk/",
            ],
            "anchors": [
                "A red-brick Gothic church.",
                "One west tower, not a pair.",
                "A single slender spire.",
            ],
            "independent": "Aarhus Cathedral, Sankt Clemens, stands on the cathedral square. Its west front is known by the one tall tower. The ARoS rainbow exterior is already DK-01-011. The gallery keeps Aarhus with Central Jutland.",
            "ip": "No readable dedication board. Interior fittings are not shown. Internal review only, not a legal certification.",
            "visual": "Pass. One brick tower, one spire, open square, broken cloud, empty. No twin spires and no lettering.",
            "swap": "Swapped from the ARoS rainbow exterior. That street view of the brick cube and the roof ring is already DK-01-011, ARoS, Aarhus. The unused church is Aarhus Cathedral. City is Aarhus.",
        },
        {
            "entry_id": "DK-01-327",
            "region": "North Jutland",
            "city": "Aalborg",
            "caption": "Kunsten, Aalborg",
            "composition": "A low white museum building in a park \u00b7 AI-generated artistic interpretation",
            "lead": "From the park lawn, Kunsten is a low white modern building among trees. The grass is empty.",
            "tail": "The fjord and the curved waterfront roofs are not the subject.",
            "alt_text": "AI-generated artistic interpretation of Kunsten in Aalborg on a partly cloudy afternoon, a low white building in a park",
            "viewpoint": "The park lawn in front of the museum. Approximate researched point 57.04255, 9.90578, not a surveyed camera. Open-Meteo ran this request on grid 57.04256, 9.90512. Nominatim places Kunsten on Kong Christians All\u00e9 in Aalborg, postal 9000.",
            "refs": [
                "https://kunsten.dk/en",
                "https://en.wikipedia.org/wiki/Kunsten_Museum_of_Modern_Art",
            ],
            "anchors": [
                "A low white modern building.",
                "A park lawn and trees.",
                "No fjord and no curved concrete shells.",
            ],
            "independent": "Kunsten is the modern-art museum in the park at Kong Christians All\u00e9, the building associated with Alvar Aalto. It is inland from the Utzon Center, which is already DK-01-058. No name is readable on the building.",
            "ip": "No museum wordmark and no featured artwork. Internal review only, not a legal certification.",
            "visual": "Pass. Low white building, park trees, broken cloud, empty lawn. No logo and no waterfront.",
            "swap": "Swapped from the Utzon Center. That waterfront exterior is already DK-01-058, Utzon Center, Aalborg. The unused museum is Kunsten. City is Aalborg.",
        },
        {
            "entry_id": "DK-01-328",
            "region": "South Jutland",
            "city": "Esbjerg",
            "caption": "Fisheries Museum, Esbjerg",
            "composition": "A low brick building beside a small boat basin \u00b7 AI-generated artistic interpretation",
            "lead": "The fisheries museum at S\u00e6dding is a low brick building beside a small boat basin, with a few boats at the quay. The quay is empty.",
            "tail": "The four white figures on the beach are not in this frame, and the commercial port is not the subject.",
            "alt_text": "AI-generated artistic interpretation of the Fisheries Museum at Esbjerg on an overcast afternoon, a low brick building and a few boats",
            "viewpoint": "The museum basin at S\u00e6dding Strandvej. Approximate researched point 55.49012, 8.41073, not a surveyed camera. Open-Meteo ran this request on grid 55.48672, 8.41542. Nominatim places Fiskeri- og S\u00f8fartsmuseet in Esbjerg, postal 6710. The four figures stand a short way south and are outside this frame.",
            "refs": [
                "https://en.wikipedia.org/wiki/Fisheries_and_Maritime_Museum",
                "https://fimus.dk/",
            ],
            "anchors": [
                "A low brick building.",
                "A small boat basin and a few boats.",
                "No white seated figures and no container cranes.",
            ],
            "independent": "Fiskeri- og S\u00f8fartsmuseet stands at S\u00e6dding, north of the Men at Sea figures. Men at Sea is already DK-01-095. The commercial harbour is already DK-01-219. This frame is the museum building and its basin.",
            "ip": "No museum wordmark and no sculpture. Internal review only, not a legal certification.",
            "visual": "Pass. Low brick building, two boats, overcast, empty quay. No white figure and no lettering.",
            "swap": "No site swap. Men at Sea is already DK-01-095, Men at Sea, Esbjerg, and the commercial quay is DK-01-219, Esbjerg Harbour, Esbjerg. The fisheries museum exterior had not been used. City is Esbjerg.",
        },
        {
            "entry_id": "DK-01-329",
            "region": "North Jutland",
            "city": "Skagen",
            "caption": "Grey Lighthouse, Skagen",
            "composition": "A tall round grey tower with a white lantern in the dunes \u00b7 AI-generated artistic interpretation",
            "lead": "The Grey Lighthouse is a tall round grey tower with a white lantern, standing in the dunes. The heath is empty.",
            "tail": "The sand spit at Grenen is not the subject.",
            "alt_text": "AI-generated artistic interpretation of the Grey Lighthouse at Skagen on a partly cloudy afternoon, a tall grey tower in the dunes",
            "viewpoint": "The dune beside the tower at Fyrvej. Approximate researched point 57.73550, 10.63018, not a surveyed camera. Open-Meteo ran this request on grid 57.73555, 10.62646. Nominatim names both Skagen Fyr and Det Gr\u00e5 Fyr at this point, in Skagen, postal 9990.",
            "refs": [
                "https://en.wikipedia.org/wiki/Skagen_Lighthouse",
                "https://detgraafyr.dk/",
            ],
            "anchors": [
                "A tall round grey masonry tower.",
                "A white lantern room at the top.",
                "Dunes, not the Grenen spit.",
            ],
            "independent": "Det Gr\u00e5 Fyr is the working grey lighthouse at Skagen, the same tower Nominatim files as Skagen Fyr. Grenen is DK-01-012, the Sand-Buried Church is DK-01-059, the old town is DK-01-132, and the harbour is DK-01-227.",
            "ip": "No readable visitor-centre name. Internal review only, not a legal certification.",
            "visual": "Pass. Grey round tower, white lantern, dunes, broken cloud, empty. No lettering.",
            "swap": "No site swap. The Grey Lighthouse had not been used. City is Skagen.",
        },
        {
            "entry_id": "DK-01-330",
            "region": "Lolland-Falster",
            "city": "Klintholm Havn",
            "caption": "Klintholm Harbour, Klintholm Havn",
            "composition": "A concrete mole, fishing boats, and low red roofs \u00b7 AI-generated artistic interpretation",
            "lead": "Klintholm harbour is a concrete mole with a few fishing boats and low red-roofed houses on the Baltic. The quay is empty.",
            "tail": "The chalk cliffs are not in this frame.",
            "alt_text": "AI-generated artistic interpretation of Klintholm harbour on a mainly clear afternoon, a mole and fishing boats",
            "viewpoint": "The mole at Klintholm Havn. Approximate researched point 54.95402, 12.46909, not a surveyed camera. Open-Meteo ran this request on grid 54.95320, 12.46284. Nominatim names the village Klintholm Havn, postal 4791. The exact camera on the mole was not pinned beyond the village harbour.",
            "refs": [
                "https://en.wikipedia.org/wiki/Klintholm_Havn",
                "https://da.wikipedia.org/wiki/Klintholm_Havn",
            ],
            "anchors": [
                "A concrete harbour mole.",
                "A few fishing boats.",
                "Low houses with red roofs. No chalk cliff.",
            ],
            "independent": "Klintholm Havn is the fishing harbour on the east coast of M\u00f8n. M\u00f8ns Klint is DK-01-007 and Stege Harbour is DK-01-173. Nominatim's village name is Klintholm Havn, so that is the city. The gallery region follows the M\u00f8n cards in Lolland-Falster. Administratively the municipality is in Region Zealand.",
            "ip": "No readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, fishing boats, red roofs, mainly clear afternoon, empty. No cliffs and no lettering.",
            "swap": "No site swap. The user suggested the city Klintholm. Nominatim names the settlement Klintholm Havn, and the caption uses that city. The harbour had not been used.",
        },
        {
            "entry_id": "DK-01-331",
            "region": "Bornholm",
            "city": "Christians\u00f8",
            "caption": "Christians\u00f8 Harbour, Christians\u00f8",
            "composition": "Granite ramparts, a round tower, and a narrow harbour \u00b7 AI-generated artistic interpretation",
            "lead": "Christians\u00f8 harbour sits between rocky islets, with granite ramparts, a round stone tower, and red-roofed houses. The quay is empty.",
            "tail": "There are no cars.",
            "alt_text": "AI-generated artistic interpretation of Christians\u00f8 harbour on an overcast afternoon, a round tower and red roofs above the water",
            "viewpoint": "The harbour between the islets. Approximate researched point 55.31970, 15.18576, not a surveyed camera. Open-Meteo ran this request on grid 55.32059, 15.18102. Nominatim names the marina Christians\u00f8 Havn and the islet Christians\u00f8. It returns no town field. The city used here is Christians\u00f8.",
            "refs": [
                "https://en.wikipedia.org/wiki/Christians%C3%B8",
                "https://da.wikipedia.org/wiki/Christians%C3%B8",
            ],
            "anchors": [
                "A round stone tower.",
                "Granite ramparts and red-roofed houses.",
                "A narrow harbour between rocky islets.",
            ],
            "independent": "Christians\u00f8 is the inhabited islet of Ertholmene, with the harbour between it and Frederiks\u00f8 and the round tower inside the ramparts. Nominatim does not assign a municipality town. The gallery region is Bornholm because that is the island group used in this library. Ertholmene is administered apart from Bornholm Municipality, and that gap is labeled here rather than folded into a Bornholm town.",
            "ip": "No readable naval mark and no flag treated as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. Round tower, granite walls, red roofs, harbour, overcast, empty. No cars and no lettering.",
            "swap": "No site swap. Christians\u00f8 harbour had not been used. City is Christians\u00f8, the islet name, because Nominatim returns no town.",
        },
        {
            "entry_id": "DK-01-332",
            "region": "Faroe Islands",
            "city": "Ei\u00f0i",
            "caption": "Ei\u00f0i, Ei\u00f0i",
            "composition": "Two sea stacks off a grass headland \u00b7 AI-generated artistic interpretation",
            "lead": "From the grass headland at Ei\u00f0i, two sea stacks stand in the Atlantic, the nearer one smaller than the one farther out. The headland is empty.",
            "tail": "The Vestmanna cliffs are a different island and are not this view.",
            "alt_text": "AI-generated artistic interpretation of the Ei\u00f0i headland in the Faroe Islands on a clear windy afternoon, two sea stacks",
            "viewpoint": "The headland toward Ei\u00f0iskollur, looking north at the two stacks. Approximate researched point 62.31893, -7.10330, not a surveyed camera. Open-Meteo ran this request on grid 62.32677, -7.10687. Nominatim names the peak Ei\u00f0iskollur in the village Ei\u00f0i. The exact tripod point on the path was not pinned.",
            "refs": [
                "https://en.wikipedia.org/wiki/Ei%C3%B0i",
                "https://en.wikipedia.org/wiki/Risin_og_Kellingin",
            ],
            "anchors": [
                "A grass headland.",
                "Exactly two sea stacks.",
                "The nearer stack smaller than the farther one.",
            ],
            "independent": "Ei\u00f0i is the village on the north coast of Eysturoy. Risin og Kellingin are the two stacks off Ei\u00f0iskollur: Kellingin is the smaller stack nearer the cliff, and Risin is the larger one farther out. Vestmanna Cliffs are already DK-01-073.",
            "ip": "No sign and no boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Green headland, two stacks, the nearer one smaller, clear sky, whitecaps, empty. No lettering.",
            "swap": "Swapped from the Vestmanna bird-cliff overlook. Those cliffs, seen from the water, are already DK-01-073, Vestmanna Cliffs, Vestmanna. The unused view is the Ei\u00f0i headland. City is Ei\u00f0i.",
        },
        {
            "entry_id": "DK-01-333",
            "region": "Faroe Islands",
            "city": "Fuglafj\u00f8r\u00f0ur",
            "caption": "Fuglafj\u00f8r\u00f0ur Harbour, Fuglafj\u00f8r\u00f0ur",
            "composition": "A fishing mole and colourful houses against green mountains \u00b7 AI-generated artistic interpretation",
            "lead": "Fuglafj\u00f8r\u00f0ur harbour is a fishing mole and colourful houses against steep green mountains. The quay is wet and empty.",
            "tail": "The mountains stay visible.",
            "alt_text": "AI-generated artistic interpretation of Fuglafj\u00f8r\u00f0ur harbour under a bright sky with drizzle, colourful houses and a mole",
            "viewpoint": "The quay in the town harbour. Approximate researched point 62.24384, -6.81332, not a surveyed camera. Open-Meteo ran this request on grid 62.23537, -6.80275. Nominatim places the town Fuglafj\u00f8r\u00f0ur in Fuglafjar\u00f0ar kommuna. The exact mole camera was not pinned beyond the town harbour.",
            "refs": [
                "https://en.wikipedia.org/wiki/Fuglafj%C3%B8r%C3%B0ur",
                "https://da.wikipedia.org/wiki/Fuglafj%C3%B8r%C3%B0ur",
            ],
            "anchors": [
                "A fishing mole and a few boats.",
                "Colourful wooden houses.",
                "Steep green mountains around the fjord.",
            ],
            "independent": "Fuglafj\u00f8r\u00f0ur is the harbour town on Eysturoy, set in a steep fjord. It had not been used. The model step is moderate drizzle with cloud cover about 1 percent, so the frame keeps a bright sky and wet stones rather than a fog bank.",
            "ip": "No readable boat name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, colourful houses, green mountains, bright sky, light drizzle, choppy water, empty. No lettering.",
            "swap": "No site swap. Fuglafj\u00f8r\u00f0ur harbour had not been used. City is Fuglafj\u00f8r\u00f0ur.",
        },
        {
            "entry_id": "DK-01-334",
            "region": "Greenland",
            "city": "Qeqertarsuaq",
            "caption": "Qeqertarsuaq Harbour, Qeqertarsuaq",
            "composition": "Colourful wooden houses on dark rock by open water \u00b7 AI-generated artistic interpretation",
            "lead": "Qeqertarsuaq harbour is a row of colourful wooden houses on dark rock, with a few small boats and open water. The shore is empty.",
            "tail": "No snow is falling, and the frame does not add an ice field.",
            "alt_text": "AI-generated artistic interpretation of Qeqertarsuaq harbour on an overcast late morning, colourful wooden houses on dark rock",
            "viewpoint": "The town quay. Approximate researched point 69.24624, -53.53537, not a surveyed camera. Open-Meteo ran this request on grid 69.27943, -53.57861. Nominatim places the town Qeqertarsuaq in Qeqertalik, postal 3953. The exact camera on the mole was not pinned beyond the town.",
            "refs": [
                "https://en.wikipedia.org/wiki/Qeqertarsuaq",
                "https://da.wikipedia.org/wiki/Qeqertarsuaq",
            ],
            "anchors": [
                "Colourful wooden houses.",
                "Dark rock and a few small boats.",
                "Open water. No snow cover and no ice field.",
            ],
            "independent": "Qeqertarsuaq is the town on Disko Island. The model step is overcast, about \u22120.2\u00b0C, with no precipitation and no snowfall, so the frame stays bare rock and open water. Ice in the bay was not treated as a count for this hour.",
            "ip": "No readable house name. Internal review only, not a legal certification.",
            "visual": "Pass. Colourful houses, dark rock, open water, overcast, empty. No snow and no lettering.",
            "swap": "No site swap. Qeqertarsuaq harbour had not been used. City is Qeqertarsuaq.",
        },
        {
            "entry_id": "DK-01-335",
            "region": "Greenland",
            "city": "Paamiut",
            "caption": "Paamiut Harbour, Paamiut",
            "composition": "Colourful wooden houses on bare rock by a small pier \u00b7 AI-generated artistic interpretation",
            "lead": "Paamiut harbour is colourful wooden houses on bare rock, with a small pier and low mountains. The shore is empty.",
            "tail": "The sky is clear and the ground is not snow-covered.",
            "alt_text": "AI-generated artistic interpretation of Paamiut harbour under a clear late-morning sky, colourful houses on rock",
            "viewpoint": "The town waterfront. Approximate researched point 61.99462, -49.66595, not a surveyed camera. Open-Meteo ran this request on grid 61.96836, -49.57816. Nominatim places the town Paamiut in Sermersooq, postal 3940. The exact camera on the pier was not pinned beyond the town.",
            "refs": [
                "https://en.wikipedia.org/wiki/Paamiut",
                "https://da.wikipedia.org/wiki/Paamiut",
            ],
            "anchors": [
                "Colourful wooden houses on rock.",
                "A small pier and a few boats.",
                "Low mountains and a clear sky.",
            ],
            "independent": "Paamiut is the town on the southwest coast. The harbour is the town waterfront. It had not been used. The model step is clear and about 4.1\u00b0C, with no snowfall.",
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Colourful houses, rock, pier, clear sky, low sun, empty. No lettering.",
            "swap": "No site swap. Paamiut harbour had not been used. City is Paamiut.",
        },
        {
            "entry_id": "DK-01-336",
            "region": "Greenland",
            "city": "Narsaq",
            "caption": "Narsaq Harbour, Narsaq",
            "composition": "Colourful wooden houses along a quiet quay \u00b7 AI-generated artistic interpretation",
            "lead": "Narsaq harbour is colourful wooden houses along a quiet quay, with rocky mountains behind the town. The quay is empty.",
            "tail": "The water is calm under a clear sky.",
            "alt_text": "AI-generated artistic interpretation of Narsaq harbour under a clear late-morning sky, colourful houses and rocky mountains",
            "viewpoint": "The town quay. Approximate researched point 60.91275, -46.04527, not a surveyed camera. Open-Meteo ran this request on grid 60.91388, -46.07657. Nominatim places the town Narsaq in Kujalleq, postal 3921. The exact camera on the quay was not pinned beyond the town.",
            "refs": [
                "https://en.wikipedia.org/wiki/Narsaq",
                "https://da.wikipedia.org/wiki/Narsaq",
            ],
            "anchors": [
                "Colourful wooden houses.",
                "A quiet harbour and a few small boats.",
                "Rocky mountains behind the town.",
            ],
            "independent": "Narsaq is the town in Kujalleq, on a fjord in south Greenland. The harbour is the town quay. It had not been used. The model step is clear, about 5.0\u00b0C, with light wind and no snowfall.",
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Colourful houses, quay, mountains, clear sky, calm water, empty. No lettering.",
            "swap": "No site swap. Narsaq harbour had not been used. City is Narsaq.",
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
    if len(all_scenes) != 336:
        raise SystemExit(f"expected 336 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 337)]
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
    report = bd.ROOT / "approvals" / "BATCH-DK-01-321-336.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pngs = list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-16x9.png"))
    pngs += list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-4x5.png"))
    if len(pngs) != 672:
        raise SystemExit(f"expected 672 masters, got {len(pngs)}")
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

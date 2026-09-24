#!/usr/bin/env python3
"""Bake DK-01-065 through DK-01-080 and rebuild the gallery from every manifest."""

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
    "The generator returned a 1280\u00d7720 PNG for the wide frame and an 864\u00d71152 PNG for the portrait frame. "
    "Those frames were saved as PNG without resampling. "
    "The 16:9 master is a uniform Lanczos resample from 1280\u00d7720 to 1920\u00d71080. "
    "The 4:5 master is a centered crop of the 864\u00d71152 frame to 864\u00d71080, with no upscale."
)

# Viewpoint coordinates used for the Open-Meteo request. Not surveyed cameras.
COORDS = {
    "DK-01-065": (55.1008, 14.7019, "Europe/Copenhagen"),
    "DK-01-066": (55.2117, 14.9708, "Europe/Copenhagen"),
    "DK-01-067": (55.1714, 14.9611, "Europe/Copenhagen"),
    "DK-01-068": (54.9917, 15.0735, "Europe/Copenhagen"),
    "DK-01-069": (55.1365, 15.1425, "Europe/Copenhagen"),
    "DK-01-070": (62.0087, -6.7695, "Atlantic/Faroe"),
    "DK-01-071": (62.2489, -7.1758, "Atlantic/Faroe"),
    "DK-01-072": (62.3250, -6.9420, "Atlantic/Faroe"),
    "DK-01-073": (62.1480, -7.2800, "Atlantic/Faroe"),
    "DK-01-074": (62.3702, -6.8103, "Atlantic/Faroe"),
    "DK-01-075": (62.2265, -6.5860, "Atlantic/Faroe"),
    "DK-01-076": (64.1790, -51.7375, "America/Nuuk"),
    "DK-01-077": (60.7186, -46.0370, "America/Nuuk"),
    "DK-01-078": (69.2198, -51.1035, "America/Nuuk"),
    "DK-01-079": (69.7620, -50.2200, "America/Nuuk"),
    "DK-01-080": (66.9389, -53.6722, "America/Nuuk"),
}

# Sky bucket at the retrieval used to depict the frames. Later numbers may move;
# a changed bucket would no longer match the picture, so that row stays locked.
GEN_BUCKET = {
    "DK-01-065": "overcast",
    "DK-01-066": "overcast",
    "DK-01-067": "overcast",
    "DK-01-068": "overcast",
    "DK-01-069": "overcast",
    "DK-01-070": "overcast",
    "DK-01-071": "mainly",
    "DK-01-072": "clear",
    "DK-01-073": "overcast",
    "DK-01-074": "clear",
    "DK-01-075": "clear",
    "DK-01-076": "overcast",
    "DK-01-077": "overcast",
    "DK-01-078": "clear",
    "DK-01-079": "clear",
    "DK-01-080": "overcast",
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}
TZ_LABEL = {
    "Europe/Copenhagen": "Europe/Copenhagen",
    "Atlantic/Faroe": "Atlantic/Faroe",
    "America/Nuuk": "America/Nuuk",
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


def fetch_group(tz: str, ids: list[str]) -> list:
    lats = ",".join(str(COORDS[i][0]) for i in ids)
    lons = ",".join(str(COORDS[i][1]) for i in ids)
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lats}&longitude={lons}"
        "&current=temperature_2m,cloud_cover,wind_speed_10m,precipitation,weather_code,is_day"
        "&daily=sunrise,sunset&timezone=" + urllib.parse.quote(tz) +
        "&past_days=1&forecast_days=2"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "jason-ds-vision-denmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    if isinstance(data, dict):
        data = [data]
    if len(data) != len(ids):
        raise SystemExit(f"weather count {tz} {len(data)}")
    return data


def fetch_weather() -> tuple[str, dict, str]:
    retrieved = datetime.now(bd.CPH)
    out = {}
    groups: dict[str, list[str]] = {}
    for entry, (_lat, _lon, tz) in COORDS.items():
        groups.setdefault(tz, []).append(entry)
    for tz, ids in groups.items():
        data = fetch_group(tz, ids)
        for entry, item in zip(ids, data):
            cur = item["current"]
            daily = item["daily"]
            if len(daily["sunset"]) < 2:
                raise SystemExit(f"expected yesterday and today in daily for {entry}")
            offset = int(item["utc_offset_seconds"])
            local = datetime.fromisoformat(cur["time"]).replace(
                tzinfo=timezone(timedelta(seconds=offset))
            )
            cph = local.astimezone(bd.CPH)
            code = int(cur["weather_code"])
            if bucket(code) != GEN_BUCKET[entry]:
                raise SystemExit(
                    f"{entry} sky bucket changed from {GEN_BUCKET[entry]} to {bucket(code)}; "
                    "the frames were depicted from the earlier bucket and were not regenerated"
                )
            temp = float(cur["temperature_2m"])
            cloud = int(cur["cloud_cover"])
            wind = float(cur["wind_speed_10m"])
            precip = float(cur["precipitation"])
            precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
            word = sky_word(code)
            utc = local.astimezone(timezone.utc)
            alt = sun_alt(COORDS[entry][0], COORDS[entry][1], utc)
            out[entry] = {
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
                "valid_cph": cph.strftime("%Y-%m-%dT%H:%M"),
                "tz": tz,
                "tzlabel": TZ_LABEL[tz],
                "sunset_yesterday": daily["sunset"][0],
                "sunrise_today": daily["sunrise"][1],
                "sun_alt": alt,
                "precip_words": precip_words,
            }
    stamp = retrieved.strftime("%-d %B %Y %H:%M")
    return stamp, out, moon_note(retrieved)


def prepare_raws() -> None:
    for n in range(65, 81):
        wide = bd.RAW / f"dk-01-{n:03d}-16x9.png"
        port = bd.RAW / f"dk-01-{n:03d}-45.png"
        imw = Image.open(wide)
        imp = Image.open(port)
        if imw.size != (1280, 720):
            raise SystemExit(f"bad wide {wide} {imw.size}")
        if imp.size != (864, 1152):
            raise SystemExit(f"bad portrait {port} {imp.size}")
        imw.convert("RGB").save(bd.RAW / f"dk-01-{n:03d}-16x9-raw.png", "PNG")
        imp.convert("RGB").save(bd.RAW / f"dk-01-{n:03d}-4x5-raw.png", "PNG")


def scenes(weather_stamp: str, wx: dict, moon: str) -> list:
    def pref(entry: str) -> str:
        row = wx[entry]
        local = f"{nice_time(row['valid'])} {row['tzlabel']}"
        if row["tz"] == "Europe/Copenhagen":
            valid = local
        else:
            valid = (
                f"{local} (the same instant as {nice_time(row['valid_cph'])} Europe/Copenhagen)"
            )
        return (
            "Model data from Open-Meteo, retrieved "
            f"{weather_stamp} Europe/Copenhagen, valid {valid} "
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
            f"{nice_time(row['sunset_yesterday'])} {row['tzlabel']} and sunrise on "
            f"{nice_time(row['sunrise_today'])} {row['tzlabel']}. "
        )
        if row["tz"] != "Europe/Copenhagen":
            text += (
                "The clock printed on the image is Europe/Copenhagen. "
                f"Local valid time is {nice_time(row['valid'])} {row['tzlabel']}. "
            )
        if row["tz"] == "America/Nuuk":
            text += twilight_phrase(row["sun_alt"]) + " "
        text += f"Cloud cover {row['cloud']}%. "
        if row["cloud"] >= 80:
            text += "The cloud deck hides the moon. "
        else:
            text += moon + " "
        return text

    def local_phrase(entry: str) -> str:
        row = wx[entry]
        if row["tz"] == "Europe/Copenhagen":
            return ""
        return f" Local time is {row['valid'][11:16]} {row['tzlabel']}."

    a = pack("DK-01-065")
    b = pack("DK-01-066")
    c = pack("DK-01-067")
    d = pack("DK-01-068")
    e = pack("DK-01-069")
    f = pack("DK-01-070")
    g = pack("DK-01-071")
    h = pack("DK-01-072")
    i = pack("DK-01-073")
    j = pack("DK-01-074")
    k = pack("DK-01-075")
    m = pack("DK-01-076")
    n = pack("DK-01-077")
    o = pack("DK-01-078")
    p = pack("DK-01-079")
    q = pack("DK-01-080")

    return [
        {
            "entry_id": "DK-01-065",
            "region": "Bornholm",
            "city": "R\u00f8nne",
            "caption": "R\u00f8nne Old Town, R\u00f8nne",
            **a,
            "composition": "Half-timbered lanes behind the harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From a cobbled lane in R\u00f8nne's old town, low half-timbered houses with ochre and cream plaster and red tile roofs face the square. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C, with no rain, and the street is empty. "
                "A few lamps light the cobbles. This is the merchant quarter around Store Torv, not the ferry terminal."
            ),
            "alt_text": "AI-generated artistic interpretation of R\u00f8nne old town at night, half-timbered houses on a cobbled lane",
            "viewpoint": "A public lane in the old town, toward Store Torv, Storegade and Laksegade. Approximate researched point 55.1008, 14.7019, not a surveyed camera.",
            "refs": [
                "https://www.bornholm.de/en/ronne/",
                "https://en.wikipedia.org/wiki/R%C3%B8nne",
            ],
            "anchors": [
                "Low half-timbered houses with colored plaster and red tile roofs.",
                "Cobbled street and a small square.",
                "Night lamps. No ferry terminal and no modern port sheds.",
            ],
            "solar": clock("DK-01-065") + "Streetlamps carry the scene.",
            "independent": "R\u00f8nne's old town sits just inland of the harbour. Store Torv, Lille Torv, Storegade and Laksegade keep low half-timbered merchant houses. The Swedish timber houses from 1945 are a separate residential area and are not this view.",
            "ip": "No readable shop signs are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Cobbled lane, half-timbered houses, overcast night, empty street.",
            "swap": "No swap. The kit city is R\u00f8nne, and the old town is in R\u00f8nne.",
        },
        {
            "entry_id": "DK-01-066",
            "region": "Bornholm",
            "city": "Gudhjem",
            "caption": "Gudhjem Harbour, Gudhjem",
            **b,
            "composition": "Harbour below a hill of houses and smokehouse chimneys \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, small boats sit in Gudhjem's rocky harbour and the houses climb the hill behind them. "
                f"Tall smokehouse chimneys stand by the water and are not smoking. The night is {b['word'].lower()}, about {b['temp']}\u00b0C, with no rain, and the quay is empty. "
                "Harbour lamps mark the basin. This is the hillside harbour, not \u00d8sterlars church."
            ),
            "alt_text": "AI-generated artistic interpretation of Gudhjem harbour at night, with boats, a hillside town and smokehouse chimneys",
            "viewpoint": "Public quay at Gudhjem harbour, looking at the basin and the town on the hill. Approximate researched point 55.2117, 14.9708, not a surveyed camera.",
            "refs": [
                "https://bornholm.info/en/gudhjem/",
                "https://www.bornholm.de/en/places/",
            ],
            "anchors": [
                "A small rocky harbour and moored boats.",
                "Houses stepped up the hill.",
                "Smokehouse chimneys, cold at this hour. No round church.",
            ],
            "solar": clock("DK-01-066") + "Harbour lamps. The smokehouse is not working at this hour, so the chimneys are dark.",
            "independent": "Gudhjem is the harbour town on Bornholm's northeast coast, built in terraces up the rock. Gudhjem R\u00f8geri stands by the harbour. The first smokehouse in the town opened in 1866. At this hour the chimneys are part of the skyline and are not in use.",
            "ip": "No readable boat names or smokehouse wordmarks are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Harbour, hillside houses, chimneys, overcast night.",
            "swap": "No swap. The kit city is Gudhjem.",
        },
        {
            "entry_id": "DK-01-067",
            "region": "Bornholm",
            "city": "\u00d8sterlars",
            "caption": "\u00d8sterlars Round Church, \u00d8sterlars",
            **c,
            "composition": "White round church with a conical roof on a hill \u00b7 AI-generated artistic interpretation",
            "description": (
                f"\u00d8sterlars Round Church stands alone on a rise, a white circular medieval church with a dark conical roof, a smaller central turret and stone buttresses. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, with no rain, and the field around it is empty. "
                "The church is closed. Only a faint exterior lamp shows. This is not Gudhjem harbour."
            ),
            "alt_text": "AI-generated artistic interpretation of \u00d8sterlars Round Church at night, a white round church with a conical roof",
            "viewpoint": "The churchyard approach on Vietsvej, looking at the round church on its hill. Address Vietsvej 25, 3760 Gudhjem. Approximate researched point 55.1714, 14.9611, not a surveyed camera.",
            "refs": [
                "https://www.oesterlarskirke.dk/turistinformation/",
                "https://www.bornholmsfolkekirker.dk/kirkerne/oesterlars",
            ],
            "anchors": [
                "A circular whitewashed church, not a long nave.",
                "A large conical roof and a smaller central turret.",
                "Stone buttresses, open fields, no harbour.",
            ],
            "solar": clock("DK-01-067") + "The building is closed. No floodlighting.",
            "independent": "\u00d8sterlars Kirke is the largest of Bornholm's four round churches, dated to about 1150 and dedicated to St Lawrence. It stands on Vietsvej north of the village. The parish site gives tourist hours of 09:00\u201317:00 on ordinary days through the middle of October 2026, so the upper storeys are shut at this hour.",
            "ip": "Exterior of a parish church. No sign is the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Round white church, conical roof, buttresses, overcast night, closed.",
            "swap": (
                "City kept as \u00d8sterlars. The church stands on Vietsvej, about half a kilometre to a kilometre north of the village of \u00d8sterlars. "
                "The postal address is Vietsvej 25, 3760 Gudhjem, because Gudhjem is the postal town. "
                "Gudhjem itself is the harbour town about 6 km north and is DK-01-066, not this view."
            ),
        },
        {
            "entry_id": "DK-01-068",
            "region": "Bornholm",
            "city": "Dueodde",
            "caption": "Dueodde Beach, Dueodde",
            **d,
            "composition": "Fine pale sand, dunes and pines at the south tip \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Dueodde Beach is a wide stretch of very fine pale sand, with low dunes, marram and a dark pine wood behind, and the Baltic along the shore. "
                f"The night is {d['word'].lower()}, about {d['temp']}\u00b0C, wind near {d['wind']} km/h, and the beach is empty. "
                "No rain. A tall slender white lighthouse sits far back in the dunes and is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Dueodde beach at night, fine pale sand, dunes and pines",
            "viewpoint": "The public beach and boardwalk approach from the Fyrvejen car park, looking along the sand. Approximate researched point 54.9917, 15.0735, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Dueodde",
                "https://visit-bornholm.com/en/towns-villages/dueodde",
            ],
            "anchors": [
                "A broad beach of very fine pale sand.",
                "Dunes, marram grass and pine forest.",
                "The Baltic at the side. A distant lighthouse, not a harbour.",
            ],
            "solar": clock("DK-01-068") + "Dueodde Fyr is an active light, so a small lantern glow far inland is consistent. The beach is unlit.",
            "independent": "Dueodde is the beach and dune country at Bornholm's southern tip, known for very fine sand. Pines were planted to hold the dunes. Dueodde Fyr, lit in 1962, is the tall white lighthouse inland of the beach. Late September is outside the summer crowd.",
            "ip": "No signs or brands are the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Empty pale beach, dunes, pines, overcast night, lighthouse only in the distance.",
            "swap": (
                "City kept as Dueodde. Dueodde is the beach locality named on the signs and on the campsite address, which reads Dueodde, 3730 Nex\u00f8. "
                "It is not a statistical town. The postal town is Nex\u00f8, about 8 km north, and the nearest village with shops is Snogeb\u00e6k. "
                "The beach itself is not in Nex\u00f8's harbour."
            ),
        },
        {
            "entry_id": "DK-01-069",
            "region": "Bornholm",
            "city": "Svaneke",
            "caption": "Svaneke Harbour, Svaneke",
            **e,
            "composition": "Granite harbour, boats and a smokehouse skyline \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, Svaneke harbour is a small granite basin of moored boats, with painted houses close to the water and a smokehouse of tall chimneys. "
                f"The chimneys are not smoking. The night is {e['word'].lower()}, about {e['temp']}\u00b0C, and the quay is empty. "
                "There is no lighthouse beam. The old stone lighthouse southeast of the harbour was taken out of use in 2010."
            ),
            "alt_text": "AI-generated artistic interpretation of Svaneke harbour at night, with boats, houses and smokehouse chimneys",
            "viewpoint": "Public quay at Svaneke harbour, looking across the basin toward the town. Approximate researched point 55.1365, 15.1425, not a surveyed camera.",
            "refs": [
                "https://visitbornholm.com/en/cities-places/selected-places/smokehouses-on-bornholm",
                "https://en.wikipedia.org/wiki/Svaneke_Lighthouse",
            ],
            "anchors": [
                "A small granite harbour and fishing boats.",
                "Houses tight to the water.",
                "Smokehouse chimneys, cold. No working lighthouse beam.",
            ],
            "solar": clock("DK-01-069") + "Harbour lamps only. Svaneke Fyr has been dark since 2010.",
            "independent": "Svaneke is the market town on Bornholm's east coast. The harbour is the public view, with a smokehouse among the houses. Svaneke Lighthouse, a square stone tower southeast of the basin, was deactivated in 2010 and is not shown as a working light.",
            "ip": "No readable boat names or smokehouse brands are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Granite harbour, houses, cold chimneys, overcast night, no beam.",
            "swap": "No swap. The kit city is Svaneke. This is the surplus Bornholm harbour after the anchor list.",
        },
        {
            "entry_id": "DK-01-070",
            "region": "Faroe Islands",
            "city": "T\u00f3rshavn",
            "caption": "Tinganes, T\u00f3rshavn",
            **f,
            "composition": "Red turf-roofed government buildings on the harbour point \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From across the harbour, Tinganes is the narrow point that splits T\u00f3rshavn's water, with red timber government buildings and turf roofs, and black-tarred houses with white windows along the lane. "
                f"The local night is {f['word'].lower()}, about {f['temp']}\u00b0C, with wind near {f['wind']} km/h, so the harbour is chopped into whitecaps.{local_phrase('DK-01-070')} "
                "No rain. The point is empty."
            ),
            "alt_text": "AI-generated artistic interpretation of Tinganes in T\u00f3rshavn at night, red turf-roofed buildings on the harbour point in a strong wind",
            "viewpoint": "Public view from the harbour side toward the Tinganes peninsula. Approximate researched point 62.0087, -6.7695, not a surveyed camera.",
            "refs": [
                "https://www.faroeislands.fo/the-big-picture/torshavn",
                "https://en.wikipedia.org/wiki/T%C3%B3rshavn",
            ],
            "anchors": [
                "A narrow peninsula dividing the harbour.",
                "Red timber buildings with turf roofs at the point.",
                "Black houses with white window frames. Wind chop on the water.",
            ],
            "solar": clock("DK-01-070") + "A few windows. No moon disk.",
            "independent": "Tinganes is the old parliamentary point in T\u00f3rshavn, between Eystarav\u00e1g and Vesterav\u00e1g. The red buildings house the Faroese government. The black-tarred turf-roofed houses of the old quarter stand along the same peninsula. Havnar Kirkja, the white cathedral, is inland of the point and is not the subject.",
            "ip": "No government wordmark or readable sign is intended. Internal review only, not a legal certification.",
            "visual": "Pass. Red turf-roofed point, black houses, overcast night, wind on the harbour.",
            "swap": "No swap. The kit city is T\u00f3rshavn. The site is Tinganes, not the whole town.",
        },
        {
            "entry_id": "DK-01-071",
            "region": "Faroe Islands",
            "city": "Saksun",
            "caption": "Saksun Lagoon, Saksun",
            **g,
            "composition": "Turf-roofed church and farm above a tidal lagoon \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Saksun sits in a bowl of steep mountains above the tidal lagoon Pollurin, with a small white turf-roofed church and turf-roofed farmhouses. "
                f"The local night is {g['word'].lower()}, about {g['temp']}\u00b0C, and a gale near {g['wind']} km/h flattens the grass.{local_phrase('DK-01-071')} "
                "Broken cloud lets the moonlight through. No rain, and nobody is on the shore path."
            ),
            "alt_text": "AI-generated artistic interpretation of Saksun at night, a turf-roofed church above a tidal lagoon in moonlight and wind",
            "viewpoint": "The public view from the village and D\u00favugar\u00f0ar side, looking down to the lagoon. Approximate researched point 62.2489, -7.1758, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Saksun",
                "https://guidetofaroeislands.fo/travel-faroe-islands/drive/saksun/",
            ],
            "anchors": [
                "A tidal lagoon in a mountain bowl.",
                "A small white church with a turf roof.",
                "Turf-roofed farmhouses. Wind-flattened grass. No town street.",
            ],
            "solar": clock("DK-01-071") + "Moonlight on the water and the white church. No visitors on the tide path.",
            "independent": "Saksun is a small village on Streymoy. The old inlet was closed by sand in a storm and became the tidal lagoon Pollurin. The church was moved from Tj\u00f8rnuv\u00edk and rebuilt here in 1858. D\u00favugar\u00f0ar is the turf-roofed farm. A fee to visit the lagoon was introduced in 2023; the night frame has no visitors.",
            "ip": "The farm is private. The view is the landscape from the village side, with no house name readable. Internal review only, not a legal certification.",
            "visual": "Pass. Lagoon, mountains, white turf-roofed church, moonlight, wind.",
            "swap": "No swap. The kit city is Saksun.",
        },
        {
            "entry_id": "DK-01-072",
            "region": "Faroe Islands",
            "city": "Gj\u00f3gv",
            "caption": "Gj\u00f3gv, Gj\u00f3gv",
            **h,
            "composition": "Turf-roofed houses beside a sea-filled gorge harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                f"At Gj\u00f3gv, colorful wooden houses with turf roofs stand on either side of a long narrow gorge that runs out to the Atlantic and is the village harbour. "
                f"The local night is {h['word'].lower()}, about {h['temp']}\u00b0C, with wind near {h['wind']} km/h, so the gorge is rough and the grass is flat.{local_phrase('DK-01-072')} "
                "The sky is clear and the moon is up. No statue is in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Gj\u00f3gv at night, turf-roofed houses beside a rough sea gorge under a clear sky",
            "viewpoint": "The public view from the village edge, looking down the gorge toward the sea. Approximate researched point 62.3250, -6.9420, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Gj%C3%B3gv",
                "https://guidetofaroeislands.fo/travel-faroe-islands/drive/gjogv/",
            ],
            "anchors": [
                "A narrow sea-filled gorge used as the harbour.",
                "Colorful houses with turf roofs on the cliffs.",
                "Rough water and spray. No memorial statue.",
            ],
            "solar": clock("DK-01-072") + "Moonlight and stars. Wind in the gorge.",
            "independent": "Gj\u00f3gv, on northeast Eysturoy, is named for the gorge. The gorge is about 200 metres long and is the natural harbour, with boats pulled up clear of the surf. The village church dates from 1929. A memorial sculpture to lost fishermen stands in the village and is not depicted.",
            "ip": "The fishermen's memorial by Fritjof Joensen is a copyrighted sculpture and is not in the frame. No readable house names. Internal review only, not a legal certification.",
            "visual": "Pass. Gorge harbour, turf roofs, clear moonlit night, rough water. No statue.",
            "swap": "No city swap. The kit city is Gj\u00f3gv.",
        },
        {
            "entry_id": "DK-01-073",
            "region": "Faroe Islands",
            "city": "Vestmanna",
            "caption": "Vestmanna Cliffs, Vestmanna",
            **i,
            "composition": "Exterior sea cliffs and stacks in a gale \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the water, the Vestmanna bird cliffs are sheer dark sea walls and stacks rising out of the Atlantic, seen from outside, not from inside a cave. "
                f"The local night is {i['word'].lower()}, about {i['temp']}\u00b0C, with wind near {i['wind']} km/h and heavy whitecaps.{local_phrase('DK-01-073')} "
                "No boat and no people. Bird ledges are rock, not a close view of birds."
            ),
            "alt_text": "AI-generated artistic interpretation of the Vestmanna sea cliffs at night, exterior basalt walls and stacks in a gale",
            "viewpoint": "The boat-tour view of the exterior cliffs west of Vestmanna, with no boat left in the frame. Approximate researched point 62.1480, -7.2800, not a surveyed camera. Tours do not run at this hour.",
            "refs": [
                "https://guidetofaroeislands.fo/book-holiday-trips/vestmanna-sea-cliffs/",
                "https://eternalarrival.com/vestmanna-bird-cliffs/",
            ],
            "anchors": [
                "Sheer exterior basalt cliffs.",
                "Sea stacks standing in the water.",
                "Whitecaps. No cave interior and no tour boat.",
            ],
            "solar": clock("DK-01-073") + "No boat lights. The cliffs are unlit.",
            "independent": "Vestmannabj\u00f8rgini are the sea cliffs west of Vestmanna on Streymoy. The public view is from a boat that leaves the harbour in Vestmanna in the daytime. Heygadrangur, a sea stack on that coast, is described as rising about 144 metres. At this hour the boat is not out. The frame stays on the outside of the cliffs.",
            "ip": "No tour branding. Internal review only, not a legal certification.",
            "visual": "Pass. Exterior cliffs and stacks, overcast, gale, no cave and no boat.",
            "swap": "No swap. The kit city is Vestmanna. The cliffs are outside the village; the village is where the boats leave from.",
        },
        {
            "entry_id": "DK-01-074",
            "region": "Faroe Islands",
            "city": "Tr\u00f8llanes",
            "caption": "Kallur Lighthouse, Tr\u00f8llanes",
            **j,
            "composition": "A tiny lighthouse on a cliff edge above two seas \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Kallur lighthouse is a very small white-and-red tower, only a few metres tall, on the narrow grassy tip of Kalsoy, with the cliff falling to the sea on both sides. "
                f"The local night is {j['word'].lower()}, about {j['temp']}\u00b0C, and wind near {j['wind']} km/h presses the grass flat.{local_phrase('DK-01-074')} "
                "The sky is clear, the moon is up, and a small light shows in the lantern. Nobody is on the path."
            ),
            "alt_text": "AI-generated artistic interpretation of Kallur lighthouse at night, a small white-and-red tower on a cliff edge under a clear sky",
            "viewpoint": "The headland at Kallur, the end of the hike from Tr\u00f8llanes. Approximate point 62.3702, -6.8103 from an unofficial lighthouse list, not a surveyed camera.",
            "refs": [
                "https://guidetofaroeislands.fo/travel-faroe-islands/drive/kallur-lighthouse/",
                "https://visitnorth.fo/kallur-lighthouse/",
            ],
            "anchors": [
                "A very small lighthouse, not a tall coastal tower.",
                "White tower with red, on a knife-edge of grass.",
                "Sea cliffs on both sides. Clear night and flattened grass.",
            ],
            "solar": clock("DK-01-074") + "The lantern is lit. An unofficial light list says the light is shown from 15 July to 1 June.",
            "independent": "Kallur lighthouse was built in 1927 on the northern tip of Kalsoy. The public route is a hike of about an hour from Tr\u00f8llanes. The tower itself is short; the light sits high because the cliff is high. The sea stacks Risin and Kellingin lie toward Ei\u00f0i and are not required in this frame.",
            "ip": "No trail signs are readable. Internal review only, not a legal certification.",
            "visual": "Pass. Small white-and-red light, cliffs both sides, clear moonlit gale, empty path.",
            "swap": (
                "City corrected from the suggested Kalsoy to Tr\u00f8llanes. Kalsoy is the island, and there is no town of that name. "
                "The lighthouse stands on the northern headland, and the hike starts in Tr\u00f8llanes, the northernmost village. "
                "An unofficial list gives the tower as about 4 metres tall, coordinates 62.3702, -6.8103, and the light as shown from 15 July to 1 June."
            ),
        },
        {
            "entry_id": "DK-01-075",
            "region": "Faroe Islands",
            "city": "Klaksv\u00edk",
            "caption": "Klaksv\u00edk Harbour, Klaksv\u00edk",
            **k,
            "composition": "Fishing harbour in a mountain sound \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Klaksv\u00edk harbour lies in the sound under steep mountains, with fishing boats moored and colorful wooden houses climbing the slope. "
                f"The local night is {k['word'].lower()}, about {k['temp']}\u00b0C, with wind near {k['wind']} km/h and whitecaps in the harbour.{local_phrase('DK-01-075')} "
                "The moon is up. No rain, and the quay is empty. Boat names are not treated as real names."
            ),
            "alt_text": "AI-generated artistic interpretation of Klaksv\u00edk harbour at night, boats and wooden houses under a clear windy sky",
            "viewpoint": "Public quay in central Klaksv\u00edk, looking along the harbour toward the mountains. Approximate researched point 62.2265, -6.5860, not a surveyed camera.",
            "refs": [
                "https://guidetofaroeislands.fo/travel-faroe-islands/drive/klaksvik/",
                "https://visitfaroeislands.com/dk/whatson/places/place/klaksvik-by-the-harbour",
            ],
            "anchors": [
                "A working harbour and fishing boats.",
                "Colorful wooden houses on the slope.",
                "Steep mountains close behind. Whitecaps. No ferry wordmark.",
            ],
            "solar": clock("DK-01-075") + "Moonlight and quay lamps.",
            "independent": "Klaksv\u00edk, on Bor\u00f0oy, is the second-largest town in the Faroe Islands and a fishing port. The Kalsoy ferry leaves from the harbour. The town sits between steep mountains. This is the surplus Faroe harbour after the anchor list.",
            "ip": "No readable boat names or fish-company marks are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Harbour, houses, mountains, clear night, wind chop.",
            "swap": "No swap. Surplus scene. The kit did not name Klaksv\u00edk; the city is Klaksv\u00edk.",
        },
        {
            "entry_id": "DK-01-076",
            "region": "Greenland",
            "city": "Nuuk",
            "caption": "Sermitsiaq, Nuuk",
            **m,
            "composition": "Colorful houses and the saddle peak across the fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the old harbour in Nuuk, colorful wooden houses stand above the dark water and the steep saddle of Sermitsiaq rises across the fjord, with snow on the upper slopes only. "
                f"The local night is {m['word'].lower()}, about {m['temp']}\u00b0C, with no rain and no snow on the streets.{local_phrase('DK-01-076')} "
                "The cloud hides the moon. A few windows are lit. No statue is the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Nuuk at night, colorful houses and the mountain Sermitsiaq across the fjord",
            "viewpoint": "Public view from the colonial harbour district, looking east across the fjord to Sermitsiaq. Approximate researched point 64.1790, -51.7375, not a surveyed camera.",
            "refs": [
                "https://northtrotter.com/2019/02/18/colourful-nuuk-the-15-best-viewpoints-in-the-city/",
                "https://www.ollietaylorphotography.com/nuuk/",
            ],
            "anchors": [
                "Colorful wooden houses in the foreground.",
                "Dark fjord water.",
                "Sermitsiaq's steep peak across the water, snow only high up. No snow on the town.",
            ],
            "solar": clock("DK-01-076") + "Town lamps. The overcast hides any leftover twilight.",
            "independent": "Sermitsiaq is the steep mountain on the island across the fjord from Nuuk, and it is the usual backdrop of the old town. The colonial harbour and the colorful houses are the public foreground. The Hans Egede statue is not the subject. Late September at a few degrees above freezing is not a snow-covered town; the high peak can still carry snow.",
            "ip": "The Hans Egede monument is not depicted as the subject. No readable signs. Internal review only, not a legal certification.",
            "visual": "Pass. Houses, fjord, saddle peak, overcast night, no street snow.",
            "swap": "No swap. The kit city is Nuuk. The site is the Sermitsiaq view.",
        },
        {
            "entry_id": "DK-01-077",
            "region": "Greenland",
            "city": "Qaqortoq",
            "caption": "Qaqortoq, Qaqortoq",
            **n,
            "composition": "Colorful wooden houses above a small harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Qaqortoq's colourful wooden houses stand on dark rock above a small harbour and a few fishing boats. "
                f"The local night is {n['word'].lower()}, about {n['temp']}\u00b0C, with no rain and no snow covering the town.{local_phrase('DK-01-077')} "
                "The sky is clouded, the moon is hidden, and the quay is empty. No stone sculpture is the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Qaqortoq at night, colorful wooden houses above the harbour",
            "viewpoint": "Public view from the harbour, looking up at the houses on the rock. Approximate researched point 60.7186, -46.0370, near the town point 60.722, -46.040, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Qaqortoq",
                "https://en.wikipedia.org/api/rest_v1/page/summary/Qaqortoq",
            ],
            "anchors": [
                "Colorful wooden houses on rock.",
                "A small harbour and fishing boats.",
                "Overcast night, lamps, no snow blanket and no sculpture.",
            ],
            "solar": clock("DK-01-077") + "Harbour lamps. Full night under the cloud.",
            "independent": "Qaqortoq, also called Julianeh\u00e5b, is the main town of Kujalleq in southern Greenland, on the coast near Cape Thorvaldsen. The public face is the coloured wooden town around the harbour. Stone works in the town are not the subject.",
            "ip": "Town sculptures are not depicted. No readable signs or boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Rocky harbour town, colorful houses, overcast night.",
            "swap": "No swap. The kit city is Qaqortoq. The caption uses the town name for both site and city because the view is the town from its harbour.",
        },
        {
            "entry_id": "DK-01-078",
            "region": "Greenland",
            "city": "Ilulissat",
            "caption": "Disko Bay, Ilulissat",
            **o,
            "composition": "Church shore and icebergs out in the bay \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the rocky shore by Zion's Church, a long dark wooden church with white windows, icebergs float in Disko Bay with dark water between them. "
                f"The local night is {o['word'].lower()}, about {o['temp']}\u00b0C, and moonlight is on the ice.{local_phrase('DK-01-078')} "
                "This is the town edge, not the empty icefjord shore of DK-01-016, and the sky is night rather than the earlier amber twilight."
            ),
            "alt_text": "AI-generated artistic interpretation of Disko Bay at Ilulissat at night, icebergs beyond a dark wooden church",
            "viewpoint": "The public shore by Zion's Church, Oqaluffiup Aqq., looking out to ice that has left the icefjord into Disko Bay. Approximate researched point 69.2198, -51.1035, not a surveyed camera.",
            "refs": [
                "https://trap.gl/en/kultur/kirker/",
                "https://www.travelsinorbit.com/greenland-2012-blog-icebergs-in-ilulissat/",
            ],
            "anchors": [
                "A long dark wooden church with white windows and a roof turret on the near shore.",
                "Icebergs in the bay, with dark water still visible.",
                "No packed wilderness fjord and no amber sunset glow.",
            ],
            "solar": clock("DK-01-078") + "Moonlight on the ice. A faint horizon glow is plausible this close to the end of nautical twilight; the sky is otherwise night.",
            "independent": "Zion's Church in Ilulissat is the wooden church begun in 1779, moved about 50 metres inland in 1929\u201331, and still in use. From the shore in front of it, ice that has crossed the iceberg bank at the mouth of Kangia drifts in Disko Bay. DK-01-016 is the icefjord shore south of town, without the church, at an earlier local twilight.",
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. Wooden church, bay ice, moonlit clear night. Distinct from the icefjord card.",
            "swap": (
                "No city swap. Both this scene and DK-01-016 are Ilulissat. "
                "The viewpoint is the church shore on Disko Bay, not the icefjord boardwalk. "
                "The bay in front of the church holds many bergs; that is the reported view from this shore, and the church is what separates it from DK-01-016."
            ),
        },
        {
            "entry_id": "DK-01-079",
            "region": "Greenland",
            "city": "Ilulissat",
            "caption": "Eqi Glacier, Ilulissat",
            **p,
            "composition": "Tidewater glacier face meeting the sea \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Eqi Glacier is a wide wall of white and blue ice meeting the sea, seen from the water at a distance, with a little brash in front and dark rock at the sides. "
                f"The local night is {p['word'].lower()}, about {p['temp']}\u00b0C, with wind near {p['wind']} km/h and moonlight on the face.{local_phrase('DK-01-079')} "
                "There is no boat and no lit lodge. This is the calving front, not the iceberg-filled icefjord."
            ),
            "alt_text": "AI-generated artistic interpretation of Eqi Glacier at night, a tidewater ice wall under a clear sky",
            "viewpoint": "The daytime boat position in front of the calving face, about 80 km north of Ilulissat, with the boat itself left out because no boat is out at this hour. Approximate weather point 69.7620, -50.2200, not a surveyed camera.",
            "refs": [
                "https://www.worldofgreenland.com/en-gb/glacier-lodge-eqi/about-glacier-lodge-eqi",
                "https://www.greenland-travel.com/inspiration/travel-guides/eqi-the-calving-glacier/",
            ],
            "anchors": [
                "One glacier face across the frame, not a field of icebergs.",
                "Ice meeting dark water, with a little brash.",
                "No boat, no people and no lit cabins.",
            ],
            "solar": clock("DK-01-079") + "Moonlight on the ice. No boat lights.",
            "independent": "Eqip Sermia, called Eqi, is a tidewater glacier about 80 km north of Ilulissat, reached only by boat. Day boats stop in front of the face. Glacier Lodge Eqi, at Port Victor, is described as open from the middle of June through the middle of September, so it is not shown as an open resort on 25 September. The icefjord scene does not show this glacier face; Sermeq Kujalleq calves far up Kangia.",
            "ip": "No lodge branding and no boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Glacier wall, clear cold night, no boat and no lodge.",
            "swap": (
                "City kept as Ilulissat. Eqi is not a town. The only public approach is by boat from Ilulissat, about 80 km north. "
                "The lodge season published by the operator runs to the middle of September, so the cabins are not depicted as open. "
                "The frame is the exterior glacier, not the icefjord."
            ),
        },
        {
            "entry_id": "DK-01-080",
            "region": "Greenland",
            "city": "Sisimiut",
            "caption": "Sisimiut Harbour, Sisimiut",
            **q,
            "composition": "Colorful houses and fishing boats in the harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Sisimiut harbour is a working basin under dark hills, with colorful wooden houses on the rock and a few fishing boats. "
                f"The local night is {q['word'].lower()}, about {q['temp']}\u00b0C, with no rain and no snow on the streets.{local_phrase('DK-01-080')} "
                "The cloud hides the moon. Quay lamps light the water, and the quay is empty."
            ),
            "alt_text": "AI-generated artistic interpretation of Sisimiut harbour at night, colorful wooden houses and fishing boats",
            "viewpoint": "Public side of the harbour in Sisimiut, looking at the boats and the houses. Town point 66.9389, -53.6722, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Sisimiut",
                "https://www.cruiseweb.com/ports/sisimiut-greenland",
            ],
            "anchors": [
                "A harbour basin and fishing boats.",
                "Colorful wooden houses on rock.",
                "Dark hills. Overcast night. No snow blanket.",
            ],
            "solar": clock("DK-01-080") + "Harbour lamps. The overcast hides any leftover twilight.",
            "independent": "Sisimiut, also called Holsteinsborg, is the second-largest town in Greenland, on the Davis Strait coast about 320 km north of Nuuk, at 66.94\u00b0 N, just north of the Arctic Circle. It is a year-round port. The public night view is the harbour and the wooden houses, not the museum interior.",
            "ip": "No readable boat names or store brands are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Harbour, colorful houses, overcast night, no street snow.",
            "swap": "No swap. Surplus Greenland harbour. The city is Sisimiut.",
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
                raise SystemExit(f"art50 {path} {key}")
        if "\u2019" in parsed["Title"] or "\u2019" in parsed["Copyright"]:
            raise SystemExit(f"curly apostrophe in metadata {path}")
        if "\u2014" not in parsed["Title"] or "\u2014" not in parsed["Copyright"]:
            raise SystemExit(f"missing em dash {path}")
        if "Denmark" not in parsed["Description"]:
            raise SystemExit(f"country {path}")


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
    if len(all_scenes) != 80:
        raise SystemExit(f"expected 80 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 81)]
    if ids != expected:
        raise SystemExit(ids)
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-065-080.txt"
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

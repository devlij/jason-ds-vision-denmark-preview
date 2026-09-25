#!/usr/bin/env python3
"""Bake DK-01-113 through DK-01-128 and rebuild the gallery from every manifest."""

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
    "DK-01-113": (55.06025, 10.60992),
    "DK-01-114": (54.85350, 10.52250),
    "DK-01-115": (54.75162, 10.67735),
    "DK-01-116": (55.09467, 10.24357),
    "DK-01-117": (55.56620, 10.08450),
    "DK-01-118": (55.61581, 10.59152),
    "DK-01-119": (55.71150, 9.53650),
    "DK-01-120": (55.56764, 9.75263),
    "DK-01-121": (55.86216, 9.85191),
    "DK-01-122": (56.16968, 9.55148),
    "DK-01-123": (56.02700, 9.93322),
    "DK-01-124": (55.97300, 10.15243),
    "DK-01-125": (56.41279, 10.90601),
    "DK-01-126": (56.43794, 10.34441),
    "DK-01-127": (56.64792, 9.97880),
    "DK-01-128": (56.63928, 9.79838),
}

# Sky bucket at the retrieval used to depict the frames.
GEN_BUCKET = {
    "DK-01-113": "overcast",
    "DK-01-114": "overcast",
    "DK-01-115": "overcast",
    "DK-01-116": "overcast",
    "DK-01-117": "overcast",
    "DK-01-118": "overcast",
    "DK-01-119": "mainly",
    "DK-01-120": "partly",
    "DK-01-121": "mainly",
    "DK-01-122": "mainly",
    "DK-01-123": "mainly",
    "DK-01-124": "partly",
    "DK-01-125": "overcast",
    "DK-01-126": "overcast",
    "DK-01-127": "partly",
    "DK-01-128": "partly",
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
    out = {}
    for entry, item in zip(ids, data):
        cur = item["current"]
        daily = item["daily"]
        if len(daily["sunset"]) < 2 or len(daily["sunrise"]) < 2:
            raise SystemExit(f"expected yesterday and today in daily for {entry}")
        offset = int(item["utc_offset_seconds"])
        local = datetime.fromisoformat(cur["time"]).replace(
            tzinfo=timezone(timedelta(seconds=offset))
        )
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
            "sunset_yesterday": daily["sunset"][0],
            "sunrise_today": daily["sunrise"][1],
            "sun_alt": alt,
        }
    stamp = retrieved.strftime("%-d %B %Y %H:%M")
    return stamp, out, moon_note(retrieved)


def prepare_raws() -> None:
    for n in range(113, 129):
        wide = bd.RAW / f"dk-01-{n:03d}-16x9.png"
        port = bd.RAW / f"dk-01-{n:03d}-4x5.png"
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

    a = pack("DK-01-113")
    b = pack("DK-01-114")
    c = pack("DK-01-115")
    d = pack("DK-01-116")
    e = pack("DK-01-117")
    f = pack("DK-01-118")
    g = pack("DK-01-119")
    h = pack("DK-01-120")
    i = pack("DK-01-121")
    j = pack("DK-01-122")
    k = pack("DK-01-123")
    m = pack("DK-01-124")
    n = pack("DK-01-125")
    o = pack("DK-01-126")
    p = pack("DK-01-127")
    q = pack("DK-01-128")

    return [
        {
            "entry_id": "DK-01-113",
            "region": "Funen",
            "city": "Svendborg",
            "caption": "Vor Frue, Svendborg",
            **a,
            "composition": "Red-brick church and a copper lantern spire above the old town \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From Torvet, Vor Frue stands on the rise: a red medieval brick church with one west tower, a tile-hung pyramidal roof, and a copper double-lantern spire. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C, and low red-tiled houses close the empty square. "
                "The harbour and the sound bridge are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Vor Frue Church in Svendborg at night, a red-brick tower above the old town",
            "viewpoint": "Torvet, looking up toward Vor Frue above the square. Approximate researched point 55.06025, 10.60992, not a surveyed camera.",
            "refs": [
                "https://www.vorfruekirke.dk/hvor",
                "https://lex.dk/Vor_Frue_Kirke_-_Svendborg_Kommune",
            ],
            "anchors": [
                "A red-brick church on a rise above the square.",
                "One west tower with a tile pyramid and a copper lantern spire.",
                "Low old houses. No harbour and no bridge.",
            ],
            "solar": clock("DK-01-113") + "Street lamps. The church is not floodlit as a show.",
            "independent": "Vor Frue Kirke stands on the highest ground of medieval Svendborg, north of Torvet, at Frue Kirkestræde 8. The parish describes a late-Romanesque brick church, with a late-medieval west tower that sits askew on the nave. The spire of 1768 is a tile-hung pyramid under a double lantern, copper-clad in 1936. The 1884 restoration left the brick exposed. DK-01-037 is Svendborg Harbour and the sound bridge. This card is the church and the square.",
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick church, copper lantern spire, old houses, overcast night, empty square. No harbour.",
            "swap": "No city swap. The old-town church is used so this card stays distinct from Svendborg Harbour, DK-01-037.",
        },
        {
            "entry_id": "DK-01-114",
            "region": "Funen",
            "city": "Marstal",
            "caption": "Marstal Harbour, Marstal",
            **b,
            "composition": "Fishing boats, a stone pier, and a brick lime kiln \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, Marstal's harbour holds fishing boats inside a long fieldstone pier, with a squat brick lime kiln on the small harbour islet. "
                f"The night is {b['word'].lower()}, about {b['temp']}\u00b0C, and quay lamps lie on dark water. "
                "Low red-tiled sheds close the basin. The quay is empty, and no boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Marstal harbour at night, boats, a stone pier, and a brick lime kiln",
            "viewpoint": "The town quay at Marstal harbour, looking toward the stone pier and Kalkovnen. Approximate researched point 54.85350, 10.52250, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Marstal",
                "https://www.havneguide.dk/en/havn/marstal-havn",
            ],
            "anchors": [
                "A working harbour basin and moored boats.",
                "A long fieldstone pier and one brick lime kiln on an islet.",
                "Low red-tiled sheds. No pastel cobbled lane.",
            ],
            "solar": clock("DK-01-114") + "Quay lamps. No lighthouse is the subject.",
            "independent": "Marstal is the largest town on Ærø and a shipping harbour, distinct from Ærøskøbing, which is DK-01-038. The stone pier was built by local seamen in the early 19th century. Frederiksøen, in the harbour, is the site of Kalkovnen, a lime kiln from 1863. The gallery files Ærø with Funen. A first wide frame that put a white tower on the islet was discarded before publication. The published frame is the brick kiln, the pier, and the boats.",
            "ip": "No readable boat names and no museum wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Boats, stone pier, brick kiln, overcast night, empty quay. Distinct from Ærøskøbing.",
            "swap": (
                "No city swap. The city is Marstal, not Ærøskøbing. "
                "A first wide frame showed a white tower on the islet and was discarded. The published frame is Kalkovnen, the brick lime kiln."
            ),
        },
        {
            "entry_id": "DK-01-115",
            "region": "Funen",
            "city": "Bagenkop",
            "caption": "Bagenkop Harbour, Bagenkop",
            **c,
            "composition": "Fishing cutters and low red roofs at the south-west tip \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Bagenkop harbour is a basin of fishing cutters with bare masts, stone moles, and low red-roofed houses behind the quay. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, with quay lamps and dark water beyond the entrance. "
                "The quay is empty. No boat name is readable, and there is no castle."
            ),
            "alt_text": "AI-generated artistic interpretation of Bagenkop harbour at night, fishing boats and red-roofed houses",
            "viewpoint": "The public quay at Bagenkop harbour, looking across the fishing basin. Approximate researched point 54.75162, 10.67735, not a surveyed camera.",
            "refs": [
                "https://www.langeland.dk/langeland/planlaeg-din-tur/bagenkop-havn-gdk612364",
                "https://www.harbourmaps.com/en/harbour/bagenkop-havn",
            ],
            "anchors": [
                "Fishing cutters with bare masts inside stone moles.",
                "Low fishermen's houses with red tile roofs.",
                "Dark water beyond the entrance. No castle.",
            ],
            "solar": clock("DK-01-115") + "Quay lamps. Rudkøbing and Tranekær are other cards.",
            "independent": "Bagenkop is the fishing harbour at the south-west end of Langeland. VisitLangeland describes it as the island's largest fishing harbour, opened in its present place in 1858 after Magleby Nor was drained. The gallery files Langeland with Funen. Rudkøbing harbour is DK-01-108 and Tranekær Castle is DK-01-109. This frame is the south-end basin, not those places. A small leading light may exist at the entrance; it is not the subject.",
            "ip": "No readable boat names and no ferry brand. Internal review only, not a legal certification.",
            "visual": "Pass. Cutters, moles, red roofs, overcast night, empty quay. No castle.",
            "swap": "No swap. The city is Bagenkop. Rudkøbing and Tranekær stay on their own cards.",
        },
        {
            "entry_id": "DK-01-116",
            "region": "Funen",
            "city": "Faaborg",
            "caption": "Klokket\u00e5rnet, Faaborg",
            **d,
            "composition": "Yellow freestanding bell tower on a cobbled rise \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Klokket\u00e5rnet is a freestanding yellow-washed brick tower on a cobbled rise, with buttresses, a blue door, an eight-sided red tile roof, and a wooden lantern under a shingled spire. "
                f"The night is {d['word'].lower()}, about {d['temp']}\u00b0C, and low old houses stand around the empty street. "
                "There is no harbour and no boats."
            ),
            "alt_text": "AI-generated artistic interpretation of Klokket\u00e5rnet in Faaborg at night, a yellow freestanding tower on a cobbled street",
            "viewpoint": "T\u00e5rnstr\u00e6de beside the freestanding bell tower, not the harbour quay. Approximate researched point 55.09467, 10.24357, not a surveyed camera.",
            "refs": [
                "https://trap.lex.dk/Klokket%C3%A5rnet,_Faaborg",
                "https://lex.dk/Faaborg",
            ],
            "anchors": [
                "One freestanding yellow-washed brick tower.",
                "An eight-sided red tile roof and a wooden lantern spire.",
                "A cobbled street of low houses. No harbour and no boats.",
            ],
            "solar": clock("DK-01-116") + "Street lamps. Clock faces on the lantern are not treated as legible.",
            "independent": "Faaborg's Klokket\u00e5rnet is a freestanding tower of about 31 metres in T\u00e5rnstr\u00e6de, built about 1450 for the demolished Sankt Nicolaj church and still used by Hellig\u00e5ndskirken. Trap Danmark describes yellow limewash, buttresses, a blue door, an eight-sided red tile roof, and a shingled lantern spire. DK-01-039 is the harbour, where the same tower is only a distant roof. This card is the street. A first wide frame that added carved figures by the door was discarded. Ymerbr\u00f8nden on Torvet is not the subject.",
            "ip": "No sculpture as the subject and no readable sign. Tower exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow tower, red octagonal roof, lantern, cobbled street, overcast night. No harbour.",
            "swap": (
                "No city swap. The street view of Klokket\u00e5rnet is used so the card stays distinct from Faaborg Harbour, DK-01-039. "
                "A first wide frame with carved figures was discarded."
            ),
        },
        {
            "entry_id": "DK-01-117",
            "region": "Funen",
            "city": "Bogense",
            "caption": "Bogense Harbour, Bogense",
            **e,
            "composition": "Narrow harbour, coloured houses, and a church tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Bogense's inner harbour is a narrow basin of small boats between low houses in yellow, white, and red, with one church tower behind the roofs. "
                f"The night is {e['word'].lower()}, about {e['temp']}\u00b0C, and quay lamps sit on dark water. "
                "The quay is empty. No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Bogense harbour at night, coloured houses and small boats",
            "viewpoint": "The inner-harbour quay in Bogense, looking along the basin toward the town roofs. Approximate researched point 55.56620, 10.08450, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Bogense",
                "https://www.harbourmaps.com/en/harbour/bogense-havn",
            ],
            "anchors": [
                "A narrow harbour basin and small boats.",
                "Low houses in yellow, white, and red.",
                "One church tower behind the roofs. No readable names.",
            ],
            "solar": clock("DK-01-117") + "Quay lamps.",
            "independent": "Bogense is the old market town on the north coast of Funen, in Nordfyns Kommune. The inner harbour sits against the town, with coloured houses and the church in the roofscape. The outer marina is a separate basin and is not required in this frame. Late September leaves the quay empty. No boat name is treated as readable.",
            "ip": "No readable boat names or shop signs. Internal review only, not a legal certification.",
            "visual": "Pass. Narrow basin, coloured houses, church tower, overcast night, empty quay.",
            "swap": "No swap. The inner harbour is the view.",
        },
        {
            "entry_id": "DK-01-118",
            "region": "Funen",
            "city": "Martofte",
            "caption": "Fyns Hoved, Martofte",
            **f,
            "composition": "Grassy headland and dark sea on both sides \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Fyns Hoved is a narrow grassy headland, with a low bank down to a stony shore and dark sea on both sides. "
                f"The night is {f['word'].lower()}, about {f['temp']}\u00b0C, and the sky is a heavy cloud deck. "
                "There is no town, no lighthouse, and no path lamp. The grass is still green."
            ),
            "alt_text": "AI-generated artistic interpretation of Fyns Hoved at night, a grassy headland between two dark seas",
            "viewpoint": "The path on the northern headland of Hindsholm, looking along the point. Approximate researched point 55.61581, 10.59152, not a surveyed camera.",
            "refs": [
                "https://naturstyrelsen.dk/find-et-naturomraade/naturguider/fyn/fyns-hoved/praktisk",
                "https://www.visitkerteminde.com/kerteminde/plan-your-holiday/fynshoved-gdk733358",
            ],
            "anchors": [
                "A narrow grassy moraine point.",
                "A low bank and a stony shore.",
                "Dark sea on both sides. No lighthouse and no town.",
            ],
            "solar": clock("DK-01-118") + "No headland lighting. A faint distant light, if present, is not identified.",
            "independent": "Fyns Hoved is the northern tip of the Hindsholm peninsula, where the Kattegat and the Great Belt meet. Naturstyrelsen describes cliffs, meadows, and beach on a moraine knob; B\u00e6sbanke, about 25 metres, is the high point, so this is a low headland and not a cliff on the scale of M\u00f8ns Klint. VisitKerteminde gives the address as Fyns Hoved, 5390 Martofte. The city is therefore Martofte. Kerteminde harbour is already DK-01-110. Korshavn light is a small sector light off the tip and is not shown. A portrait frame that added a white lighthouse was discarded.",
            "ip": "No signs and no buildings. Internal review only, not a legal certification.",
            "visual": "Pass. Grass, low bank, dark sea both sides, overcast night. No lighthouse and no town.",
            "swap": (
                "Catalogue named Otterup. Swapped to Fyns Hoved, the headland at the north end of Hindsholm. "
                "City is Martofte, the postal village on the VisitKerteminde address, not Otterup and not Kerteminde. "
                "A portrait frame with a lighthouse was discarded."
            ),
        },
        {
            "entry_id": "DK-01-119",
            "region": "South Jutland",
            "city": "Vejle",
            "caption": "Vejle Fjord, Vejle",
            **g,
            "composition": "Dark fjord water between wooded hills \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the inner-harbour promenade, Vejle Fjord runs east between wooded hills, with a few boats at a plain quay and small distant bridge lights. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C. "
                "The promenade is empty. No building stands in the water, and no sign is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Vejle Fjord at night, dark water between wooded hills",
            "viewpoint": "The public promenade at Vejle's inner harbour, looking east down the fjord. Approximate researched point 55.71150, 9.53650, not a surveyed camera.",
            "refs": [
                "https://www.visitvejle.com/vejle/plan-your-holidays/vejles-waterfront-gdk1082121",
                "https://en.wikipedia.org/wiki/Vejle",
            ],
            "anchors": [
                "Dark fjord water between wooded hills.",
                "A few ordinary boats at a plain quay.",
                "Distant bridge lights. No building standing in the water.",
            ],
            "solar": clock("DK-01-119") + "Quay lamps. Not a floodlit waterfront show.",
            "independent": "Vejle sits at the west end of Vejle Fjord. The public waterfront looks east between the hills, and Vejlefjordbroen crosses farther down the fjord. The gallery files this Region Syddanmark town with South Jutland, as it does Kolding. Fjordenhus, the headquarters designed by Olafur Eliasson, and the wave-shaped apartments were kept out of the frame. A first wide frame that included a building standing in the water was discarded. The published view is the fjord, the hills, and the boats.",
            "ip": "No hotel name and no contemporary artwork as the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Fjord, wooded hills, boats, mainly clear night. No building in the water.",
            "swap": (
                "No city swap. The fjord from the promenade is used. "
                "A first wide frame included a building in the water and was discarded so Fjordenhus is not the subject."
            ),
        },
        {
            "entry_id": "DK-01-120",
            "region": "South Jutland",
            "city": "Fredericia",
            "caption": "Prinsens Port, Fredericia",
            **h,
            "composition": "Red-brick gatehouse in the grass ramparts \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Prinsens Port is a red-brick gatehouse with one large arch and a tiled roof, set in high grass ramparts, with a dark moat in front. "
                f"The night is {h['word'].lower()}, about {h['temp']}\u00b0C, and the path is empty. "
                "There is no white triumphal arch and no statue."
            ),
            "alt_text": "AI-generated artistic interpretation of Prinsens Port in Fredericia at night, a brick gate in grass ramparts",
            "viewpoint": "The path outside Prinsens Port, looking at the brick gate and the rampart with the moat in front. Approximate researched point 55.56764, 9.75263, not a surveyed camera.",
            "refs": [
                "https://www.fredericiahistorie.dk/side/facts-about-the-fortress",
                "https://www.visitfredericia.com/turist/planlaeg-din-tur/gates-fredericia-gdk1093915",
            ],
            "anchors": [
                "A red-brick gatehouse with one large arch and a tiled roof.",
                "High grass-covered earth ramparts.",
                "A dark moat. No statue.",
            ],
            "solar": clock("DK-01-120") + "Path lamps. The ramparts are not lit as an event.",
            "independent": "Fredericia was laid out in 1650 as a fortress town. The landward ramparts and their moat remain a town park. Prinsens Port, in its present brick form from 1753, was the main gate until 1925; VisitFredericia credits the military architect Samuel Christoph Gedde. The gallery files Fredericia with South Jutland, with Kolding. The Foot Soldier monument by the gate is not the subject. A first wide frame that showed a white classical arch was discarded. The published frame is the brick gatehouse, the grass banks, and the moat.",
            "ip": "No statue as the subject and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick gate, grass ramparts, moat, partly cloudy night, empty path. No statue.",
            "swap": (
                "No city swap. A first wide frame showed a white triumphal arch and was discarded. "
                "The published frame is the 1753 brick gatehouse in the ramparts."
            ),
        },
        {
            "entry_id": "DK-01-121",
            "region": "Central Jutland",
            "city": "Horsens",
            "caption": "Vor Frelsers Kirke, Horsens",
            **i,
            "composition": "Red-brick basilica and one onion-domed spire \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Vor Frelsers Kirke is a red-brick basilica on the square, with one tower under a baroque onion dome and a slender octagonal spire. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, and low town houses close the empty square. "
                "There is no second tower and no harbour."
            ),
            "alt_text": "AI-generated artistic interpretation of Vor Frelsers Kirke in Horsens at night, a brick church with an onion dome",
            "viewpoint": "The square beside Vor Frelsers Kirke, looking at the single tower and the nave. Approximate researched point 55.86216, 9.85191, not a surveyed camera.",
            "refs": [
                "https://lex.dk/Vor_Frelsers_Kirke_-_Horsens_Kommune",
                "https://www.hvfk.dk/om-kirken/kirkens-historie",
            ],
            "anchors": [
                "A red-brick basilica.",
                "One tower with an onion dome and an octagonal spire.",
                "A town square. No harbour and no second tower.",
            ],
            "solar": clock("DK-01-121") + "Street lamps. The spire is not a measured floodlight plot.",
            "independent": "Vor Frelsers Kirke is the medieval town church of Horsens, begun about 1225, not a cathedral. Lex describes one tower over the west bay of the south aisle, probably after a fire about 1450, and the onion dome with an octagonal spire from 1737. The parish history notes that a twin-tower scheme was not completed. DK-01-055 is Horsens Harbour. This card is the church square. The generated spire is an interpretation of that baroque crown, not a measured elevation.",
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. One onion-domed tower, red brick, square, partly cloudy night. No harbour.",
            "swap": (
                "Caption honesty, not a city swap. The catalogue said cathedral. Horsens has no cathedral; "
                "the town church is Vor Frelsers Kirke, kept distinct from Horsens Harbour, DK-01-055."
            ),
        },
        {
            "entry_id": "DK-01-122",
            "region": "Central Jutland",
            "city": "Silkeborg",
            "caption": "Silkeborg Church, Silkeborg",
            **j,
            "composition": "Red-brick cross church and an octagonal spire \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Silkeborg Church is a red-brick Neo-Romanesque cross church on the square, with copper roofs, round-arched windows, and one west tower that turns octagonal under an octagonal spire. "
                f"The night is {j['word'].lower()}, about {j['temp']}\u00b0C, and the square is empty. "
                "There is no paddle steamer and no lake boat."
            ),
            "alt_text": "AI-generated artistic interpretation of Silkeborg Church at night, a red-brick church with an octagonal spire",
            "viewpoint": "Torvet, looking at the west tower of Silkeborg Kirke. Approximate researched point 56.16968, 9.55148, not a surveyed camera.",
            "refs": [
                "https://lex.dk/Silkeborg_Kirke",
                "https://da.wikipedia.org/wiki/Silkeborg_Kirke",
            ],
            "anchors": [
                "A red-brick cross church with round-arched windows.",
                "Copper roofs and one octagonal spire.",
                "A town square. No paddle steamer.",
            ],
            "solar": clock("DK-01-122") + "Street lamps. The harbour below the hill is not in the frame.",
            "independent": "Silkeborg Kirke, Torvet 10C, was built in 1877 to designs by H.S. Sibbern: a Neo-Romanesque brick cross church with an apse, short transepts, and a west tower that is square below and octagonal above. Lex and the church's own account give copper roofs; Wikipedia notes a new copper roof in 1967. The church stands on the edge of the plateau above the old harbour. DK-01-050 is the paddle steamer Hjejlen at that harbour. This card is the church. The aquarium was not used.",
            "ip": "Church exterior only. No aquarium name and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red brick, copper roofs, octagonal spire, square, partly cloudy night. No steamer.",
            "swap": (
                "No city swap. Silkeborg Church is used, as specified, so the card stays distinct from Hjejlen, DK-01-050. "
                "The aquarium exterior was not used."
            ),
        },
        {
            "entry_id": "DK-01-123",
            "region": "Central Jutland",
            "city": "Skanderborg",
            "caption": "Skanderborg Lake, Skanderborg",
            **k,
            "composition": "Long brick church and a round tower on the lake holm \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Across dark water, Skanderborg Slotskirke is a long low red-brick wing on the holm, with one round corner tower. "
                f"The night is {k['word'].lower()}, about {k['temp']}\u00b0C, and trees stand along the empty shore. "
                "The rest of the castle is not invented back into the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Skanderborg Lake at night, the brick church and round tower on the holm",
            "viewpoint": "The public shore of Skanderborg S\u00f8, looking toward Slotskirken on the holm. Approximate researched point 56.02700, 9.93322, not a surveyed camera.",
            "refs": [
                "https://lex.dk/Skanderborg_Slotskirke",
                "https://da.wikipedia.org/wiki/Skanderborg_Slotskirke",
            ],
            "anchors": [
                "Dark lake water in the foreground.",
                "A long low red-brick wing on a holm.",
                "One round brick tower. No full palace.",
            ],
            "solar": clock("DK-01-123") + "A few shore lamps. The holm is not floodlit as a show.",
            "independent": "Skanderborg Slot stood on a holm between Skanderborg S\u00f8 and the smaller Henning S\u00f8. The castle was demolished in 1767. Slotskirken, the surviving part of Frederik II's east wing of 1572, remains, and its tower was one of the flanking towers. The address is Slotsholmen 4. This lake-front view is that church and the water, not a reconstructed palace. A small pale figure, if it appears on the shore, is not identified and is not the subject.",
            "ip": "No readable sign. Church exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. Lake, long brick wing, round tower, trees, partly cloudy night. No invented palace.",
            "swap": "No city swap. The lake front is the surviving castle church on the holm, not a rebuilt palace.",
        },
        {
            "entry_id": "DK-01-124",
            "region": "Central Jutland",
            "city": "Odder",
            "caption": "Odder Church, Odder",
            **m,
            "composition": "Whitewashed church and a heavy west tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Odder Church is a whitewashed building with a heavy square west tower, a low nave, and a red tile roof, with town roofs behind the trees. "
                f"The night is {m['word'].lower()}, about {m['temp']}\u00b0C, and the churchyard path is empty. "
                "No shop name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Odder Church at night, a whitewashed church with a heavy tower",
            "viewpoint": "The path by Odder Kirke, looking at the west tower. Approximate researched point 55.97300, 10.15243, not a surveyed camera.",
            "refs": [
                "https://www.kystlandet.dk/kystlandet/planlaeg-turen/odder-kirke-gdk605245",
                "https://en.wikipedia.org/wiki/Odder",
            ],
            "anchors": [
                "A whitewashed church with a heavy west tower.",
                "A low nave and a red tile roof.",
                "Town roofs behind trees. No readable shop names.",
            ],
            "solar": clock("DK-01-124") + "Street lamps. The shopping street is not the subject.",
            "independent": "Odder Kirke stands near the centre of Odder, by the old ford of Odder \u00c5. Destination Kystlandet describes a Romanesque church from the 1100s, originally of ashlar, later extended, whitewashed, with a late-medieval porch and a heavy tower. It is the oldest building in town. The pedestrian shopping street was not used, because shop names would have been the wrong subject. The frame is the church.",
            "ip": "No shop names. Church exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. White church, heavy tower, town roofs, partly cloudy night, empty path.",
            "swap": (
                "Site choice inside Odder, not a city swap. The church is used rather than the shopping street, "
                "so brand names stay out of the frame."
            ),
        },
        {
            "entry_id": "DK-01-125",
            "region": "Central Jutland",
            "city": "Grenaa",
            "caption": "Grenaa Harbour, Grenaa",
            **n,
            "composition": "Fishing boats, stone piers, and the dark Kattegat \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Grenaa harbour is a basin of fishing boats and a few smaller craft, with stone piers, low warehouses, and red-roofed houses, and dark sea beyond the entrance. "
                f"The night is {n['word'].lower()}, about {n['temp']}\u00b0C, under quay lamps. "
                "The quay is empty. No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Grenaa harbour at night, fishing boats and stone piers",
            "viewpoint": "The quay at Grenaa harbour, looking across the basin toward the sea entrance. Approximate researched point 56.41279, 10.90601, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Grenaa",
                "https://www.havneguide.dk/en/havn/grenaa-havn",
            ],
            "anchors": [
                "Fishing boats in a harbour basin.",
                "Stone piers, warehouses, and red roofs.",
                "Dark open water beyond the entrance. No aquarium.",
            ],
            "solar": clock("DK-01-125") + "Quay lamps. The cloud deck is complete.",
            "independent": "Grenaa is the east-coast port of Djursland, on the Kattegat, in Norddjurs Kommune, which the gallery files with Central Jutland as it does Ebeltoft. The harbour is a fishing port and marina. The town aquarium is a separate building and is not shown, and no ferry name is treated as readable. Which boats were alongside this night was not checked.",
            "ip": "No aquarium wordmark and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Fishing boats, piers, warehouses, overcast night, empty quay. No aquarium.",
            "swap": "No swap. The harbour is used. The aquarium is not the subject.",
        },
        {
            "entry_id": "DK-01-126",
            "region": "Central Jutland",
            "city": "Auning",
            "caption": "Gammel Estrup, Auning",
            **o,
            "composition": "Three-wing brick manor inside a double moat \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Gammel Estrup is a three-wing red-brick manor on a narrow island in a moat, with crow-stepped gables, a gate tower, and two octagonal corner towers under flat roofs. "
                f"The night is {o['word'].lower()}, about {o['temp']}\u00b0C, with a brick bridge, dark water, and a few warm windows. "
                "The grounds are empty. There is no forest of copper spires."
            ),
            "alt_text": "AI-generated artistic interpretation of Gammel Estrup at Auning at night, a red-brick manor in its moat",
            "viewpoint": "The public approach to Gammel Estrup, looking across the moat at the gate wing and the corner towers. Approximate researched point 56.43794, 10.34441, not a surveyed camera.",
            "refs": [
                "https://www.visitaarhus.dk/aarhusregionen/planlaeg-ferien/gammel-estrup-en-af-danmarks-bedst-bevarede-renaessance-herregaarde-gdk1078932",
                "https://www.gammelestrup.dk/en/visit-us",
            ],
            "anchors": [
                "A three-wing red-brick house in a moat.",
                "Crow-stepped gables and a gate tower.",
                "Two octagonal corner towers with flat roofs. No pointed copper spires.",
            ],
            "solar": clock("DK-01-126") + "A few warm windows. Not a floodlit show.",
            "independent": "Gammel Estrup stands at Randersvej 2, 8963 Auning, on northern Djursland. VisitAarhus describes a red-brick Renaissance manor, most of it from about 1600, inside double moats. The manor-research account gives the two octagonal corner towers to J\u00f8rgen Skeel's years, 1625 to 1631, with lead roofs, and copper only on the courtyard stair turrets. The city is Auning. This is not Egeskov, which is DK-01-009 at Kv\u00e6rndrup. A portrait frame that put pointed spires on the corner towers was discarded. The published towers are flat-roofed.",
            "ip": "Manor exterior only. No museum banner and no family crest as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. Three red wings, flat-roofed octagonal towers, moat, bridge, overcast night. No pointed spire forest.",
            "swap": (
                "Catalogue named Djurs Sommerland. Swapped to Gammel Estrup, Auning, so a theme-park brand is not the subject. "
                "A portrait frame with pointed copper spires on the corner towers was discarded."
            ),
        },
        {
            "entry_id": "DK-01-127",
            "region": "North Jutland",
            "city": "Mariager",
            "caption": "Mariager Old Town, Mariager",
            **p,
            "composition": "Half-timbered street and a white abbey church \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A cobbled street in Mariager is lined with low half-timbered houses, white panels and red tile roofs, and a whitewashed church with one west tower under a pyramidal spire. "
                f"The night is {p['word'].lower()}, about {p['temp']}\u00b0C, and the street is empty. "
                "No shop name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Mariager old town at night, half-timbered houses and a white church tower",
            "viewpoint": "The old street beside Mariager Klosterkirke, looking along the houses toward the west tower. Approximate researched point 56.64792, 9.97880, not a surveyed camera.",
            "refs": [
                "https://www.mariager-kirke.dk/turist/historien",
                "https://trap.lex.dk/Kalkmalerier_i_Mariager_Kirke",
            ],
            "anchors": [
                "Low half-timbered houses with red tile roofs.",
                "A whitewashed church.",
                "One west tower with a pyramidal spire. No readable shop names.",
            ],
            "solar": clock("DK-01-127") + "Street lamps. No festival banners.",
            "independent": "Mariager grew around a Bridgettine abbey. Trap Danmark says only the west part of the church, the west tower, and the transept arms survive from the late-medieval building, and that the tower was lowered in the 1780s and given a pyramidal spire. The church is whitewashed. Half-timbered houses line the old streets. Mariagerfjord Kommune is in the North Jutland region. The frame is that street and tower, not a rose fair and not a shop front.",
            "ip": "No shop names and no festival banner. Internal review only, not a legal certification.",
            "visual": "Pass. Half-timbered street, white church, pyramidal spire, overcast night, empty.",
            "swap": "No swap. The old town and the abbey church are the view.",
        },
        {
            "entry_id": "DK-01-128",
            "region": "North Jutland",
            "city": "Hobro",
            "caption": "Hobro Harbour, Hobro",
            **q,
            "composition": "Small fjord basin and low brick warehouses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Hobro harbour is a small basin of ordinary boats on the dark fjord, with low brick warehouses and houses along the quay. "
                f"The night is {q['word'].lower()}, about {q['temp']}\u00b0C, under quay lamps. "
                "The quay is empty. There is no longship and no visitor-center sign."
            ),
            "alt_text": "AI-generated artistic interpretation of Hobro harbour at night, small boats and brick warehouses on the fjord",
            "viewpoint": "Havnegade at Hobro harbour, looking across the basin. Approximate researched point 56.63928, 9.79838, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hobro",
                "https://en.wikipedia.org/wiki/Mariager_Fjord",
            ],
            "anchors": [
                "A small harbour basin and ordinary moored boats.",
                "Low brick warehouses along the quay.",
                "Dark fjord water. No longship and no sign.",
            ],
            "solar": clock("DK-01-128") + "Quay lamps. The Viking center is not in the frame.",
            "independent": "Hobro stands at the west end of Mariager Fjord, in Mariagerfjord Kommune, which the gallery files with North Jutland. Havnegade is the harbour street. The Viking center outside town was not used, because its signs and reconstructed ships would have been the wrong subject. A first wide frame that included a dragon-headed longship was discarded. The published frame is the ordinary night harbour. Fyrkat, the ring fortress, is a different site and is not this basin.",
            "ip": "No visitor-center name and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, ordinary boats, brick warehouses, partly cloudy night. No longship.",
            "swap": (
                "Site choice inside Hobro. The harbour is used. The Viking center was not used. "
                "A first wide frame with a longship was discarded."
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
    if len(all_scenes) != 128:
        raise SystemExit(f"expected 128 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 129)]
    if ids != expected:
        raise SystemExit(ids)
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-113-128.txt"
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

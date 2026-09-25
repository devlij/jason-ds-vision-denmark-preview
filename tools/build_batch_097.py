#!/usr/bin/env python3
"""Bake DK-01-097 through DK-01-112 and rebuild the gallery from every manifest."""

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
    "DK-01-097": (56.03615, 12.61355),
    "DK-01-098": (56.12470, 12.31020),
    "DK-01-099": (56.09220, 12.45680),
    "DK-01-100": (55.92980, 12.30050),
    "DK-01-101": (55.43006, 11.55652),
    "DK-01-102": (55.44280, 11.78740),
    "DK-01-103": (55.40363, 11.35450),
    "DK-01-104": (55.32830, 11.13000),
    "DK-01-105": (54.83150, 11.13700),
    "DK-01-106": (54.80020, 11.63800),
    "DK-01-107": (54.66640, 11.73180),
    "DK-01-108": (54.93680, 10.71050),
    "DK-01-109": (55.00152, 10.85593),
    "DK-01-110": (55.44940, 10.65720),
    "DK-01-111": (55.31350, 10.78950),
    "DK-01-112": (55.39420, 10.38880),
}

# Sky bucket at the retrieval used to depict the frames.
GEN_BUCKET = {
    "DK-01-097": "overcast",
    "DK-01-098": "overcast",
    "DK-01-099": "overcast",
    "DK-01-100": "overcast",
    "DK-01-101": "overcast",
    "DK-01-102": "overcast",
    "DK-01-103": "overcast",
    "DK-01-104": "overcast",
    "DK-01-105": "partly",
    "DK-01-106": "partly",
    "DK-01-107": "partly",
    "DK-01-108": "overcast",
    "DK-01-109": "overcast",
    "DK-01-110": "overcast",
    "DK-01-111": "overcast",
    "DK-01-112": "overcast",
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
    for n in range(97, 113):
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

    a = pack("DK-01-097")
    b = pack("DK-01-098")
    c = pack("DK-01-099")
    d = pack("DK-01-100")
    e = pack("DK-01-101")
    f = pack("DK-01-102")
    g = pack("DK-01-103")
    h = pack("DK-01-104")
    i = pack("DK-01-105")
    j = pack("DK-01-106")
    k = pack("DK-01-107")
    m = pack("DK-01-108")
    n = pack("DK-01-109")
    o = pack("DK-01-110")
    p = pack("DK-01-111")
    q = pack("DK-01-112")

    return [
        {
            "entry_id": "DK-01-097",
            "region": "Capital Region",
            "city": "Helsingør",
            "caption": "Sankt Olai, Helsingør",
            **a,
            "composition": "Red-brick basilica and a copper spire in the old town \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Sankt Olai stands in the old churchyard: a red-brick basilica with a high nave, lower side aisles, and one west tower under a copper spire. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C, with lime trees still in leaf and a few warm windows. "
                "Low town houses close the square. Kronborg and the shipyard dock are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Sankt Olai Church in Helsingør at night, a red-brick basilica with a copper spire",
            "viewpoint": "The old churchyard of Sankt Olai, looking at the west tower and the nave. Approximate researched point 56.03615, 12.61355, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/St._Olaf%27s_Church,_Helsing%C3%B8r",
                "https://helsingorleksikon.dk/index.php/Skt._Olai_Kirke",
            ],
            "anchors": [
                "A red-brick basilica with a high nave and lower side aisles.",
                "One west tower with a copper spire.",
                "A churchyard and low town houses. No castle and no sea.",
            ],
            "solar": clock("DK-01-097") + "Street lamps and a few warm windows. Not a floodlit show.",
            "independent": "Sankt Olai, Helsingør Cathedral since 1961, is the town church inland from the harbour. The present red-brick basilica was finished in 1559: a high nave, two lower aisles with their own roofs, no transept, and crow-stepped gables. The west tower carries the copper spire designed by H.B. Storck in 1898, replacing the spire lost in 1737. Lime trees and low houses surround the former churchyard. DK-01-004 is Kronborg on the Øresund, and DK-01-029 is the Maritime Museum dry dock. Neither is this square.",
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick basilica, copper spire, churchyard, overcast night. No Kronborg and no dry dock.",
            "swap": "No swap. The inland cathedral is distinct from Kronborg, DK-01-004, and from the Maritime Museum, DK-01-029.",
        },
        {
            "entry_id": "DK-01-098",
            "region": "Capital Region",
            "city": "Gilleleje",
            "caption": "Gilleleje Harbour, Gilleleje",
            **b,
            "composition": "Fishing cutters, stone moles, and red roofs \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, fishing cutters with bare masts lie inside the stone moles, and red-tiled roofs of the village stand behind the sheds. "
                f"The night is {b['word'].lower()}, about {b['temp']}\u00b0C, with quay lamps on dark water and the Kattegat beyond the entrance. "
                "The quay is empty. No boat name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Gilleleje harbour at night, fishing boats and red roofs under cloud",
            "viewpoint": "The public quay at Gilleleje harbour, looking across the fishing basin toward the mole and the village roofs. Approximate researched point 56.12470, 12.31020, not a surveyed camera.",
            "refs": [
                "https://marinaguide.dk/en/gilleleje-harbour/description",
                "https://en.wikipedia.org/wiki/Gilleleje",
            ],
            "anchors": [
                "Fishing cutters with bare masts inside stone moles.",
                "Low sheds and red-tiled village roofs.",
                "Dark open water beyond the entrance. No readable names.",
            ],
            "solar": clock("DK-01-098") + "Quay lamps. Nakkehoved lighthouse is not the subject.",
            "independent": "Gilleleje is the northernmost town on Zealand and still a working fishing harbour, with cutters, moles, and the village grown up around the basin. A marina sits apart from the commercial port. Nakkehoved lighthouse is east of town and is not this frame. A small flag may appear on a boat; it is not a shop mark. Late September is outside the summer market season, so the quay is quiet.",
            "ip": "No readable boat names or shop signs. A flag, if present, is not a brand. Internal review only, not a legal certification.",
            "visual": "Pass. Cutters, moles, red roofs, overcast night, empty quay. No readable names.",
            "swap": "No swap. The fishing harbour is the view, not the lighthouse and not the beach east of town.",
        },
        {
            "entry_id": "DK-01-099",
            "region": "Capital Region",
            "city": "Hornbæk",
            "caption": "Hornbæk Beach, Hornbæk",
            **c,
            "composition": "Pale sand, dune grass, and coastal pines \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Hornbæk Beach is a wide pale strand, with dune grass in front and a dark line of pines behind the sand. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, and the Kattegat is dark. "
                "The beach is empty. There are no umbrellas and no readable signs."
            ),
            "alt_text": "AI-generated artistic interpretation of Hornbæk beach at night, pale sand and pines under cloud",
            "viewpoint": "The sand at Hornbæk Strand, looking along the beach toward the sea, with the plantation behind the dunes. Approximate researched point 56.09220, 12.45680, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hornb%C3%A6k",
                "https://www.alltrails.com/poi/denmark/capital-region-of-denmark/hornbaek/Hornb%C3%A6k-Strand",
            ],
            "anchors": [
                "A wide pale sandy beach.",
                "Dune grass and a band of coastal pines.",
                "Dark sea. No umbrellas and no readable signs.",
            ],
            "solar": clock("DK-01-099") + "A few distant lamps from the town behind the trees. No beach-club lighting.",
            "independent": "Hornbæk Strand is the long sandy beach of this north-coast resort, backed by dunes and Hornbæk Plantage. Lifeguards are a summer service and are not depicted. Late September has no beach-umbrella season in this frame. Sweden's Kullen can be a daytime horizon from here; under this cloud it is not identified. The town harbour is a different viewpoint and is not the subject.",
            "ip": "No hotel or kiosk names. Internal review only, not a legal certification.",
            "visual": "Pass. Empty sand, dune grass, pines, dark sea, overcast night. No signage.",
            "swap": "No swap. The beach is the view, not Hornbæk harbour.",
        },
        {
            "entry_id": "DK-01-100",
            "region": "Capital Region",
            "city": "Hillerød",
            "caption": "Slotssøen, Hillerød",
            **d,
            "composition": "A lamp-lit path along the castle lake \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A gravel path follows the dark water of Slotssøen, under trees that are still in leaf, with a few lamp posts along the shore. "
                f"The night is {d['word'].lower()}, about {d['temp']}\u00b0C, and the path is empty. "
                "The castle is kept out of the frame, so this is the lake shore and not a second view of Frederiksborg."
            ),
            "alt_text": "AI-generated artistic interpretation of the path along Slotssøen in Hillerød at night, trees and dark water with no castle",
            "viewpoint": "The public shore path on the south side of Slotssøen, looking along the water. The castle is outside the frame. Approximate researched point 55.92980, 12.30050, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Frederiksborg_Castle",
                "https://www.visitdenmark.com/denmark/things-do/history-heritage/frederiksborg-castle",
            ],
            "anchors": [
                "A gravel path beside dark lake water.",
                "Trees still in leaf and a few lamp posts.",
                "No castle, no copper spires, and no palace facade.",
            ],
            "solar": clock("DK-01-100") + "Path lamps only. No castle floodlight, because the castle is not in the frame.",
            "independent": "Slotssøen is the lake around Frederiksborg. DK-01-005 already shows the red-brick castle and its copper spires across that water. This card is the public shore path, with the castle left outside the frame so the two Hillerød scenes do not repeat one facade. The baroque garden on the far side of the castle is also not the subject. The point is a researched south-shore location, not a surveyed camera.",
            "ip": "No signs and no castle shop marks. Internal review only, not a legal certification.",
            "visual": "Pass. Path, trees, dark water, lamps, overcast night. No castle in the frame.",
            "swap": (
                "Viewpoint swap, not a city swap. Frederiksborg already fills DK-01-005, so the catalogue's Slotssøen path is used "
                "and the castle is kept out of the frame. The city remains Hillerød."
            ),
        },
        {
            "entry_id": "DK-01-101",
            "region": "Zealand",
            "city": "Sorø",
            "caption": "Sorø Abbey Church, Sorø",
            **e,
            "composition": "Brick abbey church and a ridge spire beside the lake \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Sorø Abbey Church is a long red-brick cruciform building with round-arched windows and one slender ridge spire, standing by the dark lake. "
                f"The night is {e['word'].lower()}, about {e['temp']}\u00b0C, with trees still in leaf and a few warm windows. "
                "A pale academy wing sits to the side and is not the main mass. The grounds are empty."
            ),
            "alt_text": "AI-generated artistic interpretation of Sorø Abbey Church at night, a brick church and ridge spire beside the lake",
            "viewpoint": "The academy grounds northeast of the abbey church, with the lake beyond the building. Approximate researched point 55.43006, 11.55652, not a surveyed camera.",
            "refs": [
                "https://lex.dk/Sor%C3%B8_Klosterkirke",
                "https://www.visitdenmark.dk/danmark/explore/soroe-klosterkirke-absalons-kongegravkirke-gdk1158131",
            ],
            "anchors": [
                "A red-brick cruciform church with round-arched windows.",
                "One ridge spire, not a pair of west towers.",
                "Dark lake and trees. A pale academy wing is secondary.",
            ],
            "solar": clock("DK-01-101") + "A few warm windows. The grounds are not floodlit as a show.",
            "independent": "Sorø Klosterkirke stands on the north shore of Sorø Sø, on the academy grounds. It is a medieval brick church on a Cistercian cruciform plan, begun in the 1160s, with round-arched windows and a ridge turret whose spire dates from 1625. The monastic ranges burned in 1813. The present academy main building is the classical house of 1826, and it is kept to the side of this frame. The church, not a campus quad, is the subject.",
            "ip": "No academy signboard. Church and grounds exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. Brick church, one ridge spire, lake, overcast night. Not twin towers.",
            "swap": "No city swap. The abbey church by the lake is the subject. The academy wing is in the setting and is not a separate card.",
        },
        {
            "entry_id": "DK-01-102",
            "region": "Zealand",
            "city": "Ringsted",
            "caption": "Sankt Bendts Kirke, Ringsted",
            **f,
            "composition": "Brick cruciform church and one pyramidal tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Sankt Bendts Kirke is a red-brick Romanesque church with a broad transept, a semicircular apse, and one central tower under a dark pyramidal roof. "
                f"The night is {f['word'].lower()}, about {f['temp']}\u00b0C, and the square around it is quiet. "
                "There is no pair of west spires and no readable sign."
            ),
            "alt_text": "AI-generated artistic interpretation of Sankt Bendts Kirke in Ringsted at night, a brick church with a pyramidal central tower",
            "viewpoint": "The town side of Sankt Bendts Kirke, looking at the crossing tower and the apse. Approximate researched point 55.44280, 11.78740, not a surveyed camera.",
            "refs": [
                "https://sanktbendtskirke.dk/index.php/kirkens-historie/introduktion",
                "https://sanktbendtskirke.dk/index.php/kirkens-historie/kirketarn-og-spir",
            ],
            "anchors": [
                "One central brick tower with a pyramidal roof.",
                "A cruciform body and a large semicircular apse.",
                "Low town roofs. No twin west spires.",
            ],
            "solar": clock("DK-01-102") + "Street lamps. The tower is not a measured floodlight plot.",
            "independent": "Sankt Bendts Kirke is the medieval brick church in the centre of Ringsted, a Romanesque cruciform basilica with a large apse and smaller side apses. The crossing tower's present pyramidal roof comes from H.B. Storck's restoration of 1901–1909. The church's own account gives about 52 metres to the tip of that roof. The west front was rebuilt in that restoration. This is one central tower, not Roskilde's pair of spires.",
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. Central pyramidal tower, apse, red brick, overcast night. No twin spires.",
            "swap": "No swap. St. Bendt's is the town church the catalogue named.",
        },
        {
            "entry_id": "DK-01-103",
            "region": "Zealand",
            "city": "Slagelse",
            "caption": "Slagelse Old Town, Slagelse",
            **g,
            "composition": "Gothic brick church and a long brick barn \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A red-brick Gothic church with one west tower stands above a cobbled street of low houses, and a long low brick barn sits by the churchyard. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C, under street lamps. "
                "The street is empty, and no shop name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Slagelse old town at night, a brick church and a long brick barn",
            "viewpoint": "The street by Sankt Mikkels Kirke on Rosengade, looking at the west tower and the kirkelade. Approximate researched point 55.40363, 11.35450, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Sankt_Mikkels_Kirke",
                "https://www.sctmikkels.dk/",
            ],
            "anchors": [
                "One brick west tower on a low rise.",
                "A long low brick barn beside the churchyard.",
                "A cobbled street of low houses. No readable shop names.",
            ],
            "solar": clock("DK-01-103") + "Street lamps. The tower is not floodlit as a show.",
            "independent": "Sankt Mikkels Kirke stands on Mikkelsbjerget in the middle of Slagelse, at Rosengade 4A. The present brick church is from about 1333, on a site used since about 1080, and the tower is from the 1400s. Kirkeladen, the long brick barn beside it, is from about 1470 and later held the Latin school. The old town in this frame is that church and street, not the Antvorskov ruins outside town. The generated tower is an interpretation of the west end, not a measured elevation.",
            "ip": "No readable shop names. Church exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. One brick tower, long barn, cobbled street, overcast night, empty.",
            "swap": "No city swap. The old town around Sankt Mikkels is used. Antvorskov, outside town, is not the subject.",
        },
        {
            "entry_id": "DK-01-104",
            "region": "Zealand",
            "city": "Korsør",
            "caption": "Korsør Harbour, Korsør",
            **h,
            "composition": "Marina boats and the distant suspension bridge \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the marina quay, boats lie on dark water and the Great Belt suspension bridge crosses the strait in the distance, two pylons and a line of cables. "
                f"The night is {h['word'].lower()}, about {h['temp']}\u00b0C, with bridge lights and no rain. "
                "No boat name is readable, and the fortress is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Korsør harbour at night, boats and the Great Belt suspension bridge",
            "viewpoint": "Korsør marina quay, looking out toward the east bridge of the Great Belt. Approximate researched point 55.32830, 11.13000, not a surveyed camera.",
            "refs": [
                "https://www.visitdenmark.com/denmark/plan-your-trip/korsor-marina-gdk718584",
                "https://en.wikipedia.org/wiki/Great_Belt_Bridge",
            ],
            "anchors": [
                "A marina of moored boats in the foreground.",
                "A suspension bridge with two pylons in the distance.",
                "Dark water. No readable names and no toll sign.",
            ],
            "solar": clock("DK-01-104") + "Marina lamps and distant bridge lights. Not a fireworks display.",
            "independent": "Korsør marina, on Sylowsvej, looks toward the Great Belt. VisitDenmark describes the view from the water's edge to the bridge. The high bridge on this side is the East Bridge, the suspension span from Halsskov to Sprogø, opened in 1998. The low West Bridge is the Funen side and is not this silhouette. Korsør Fortress is the older harbour work and is not the subject of this marina view. No operator name is shown.",
            "ip": "No toll branding and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, two-pylon suspension bridge, overcast night. No readable sign.",
            "swap": "No city swap. The harbour-and-bridge viewpoint is used. The fortress is not the subject.",
        },
        {
            "entry_id": "DK-01-105",
            "region": "Lolland-Falster",
            "city": "Nakskov",
            "caption": "Nakskov Harbour, Nakskov",
            **i,
            "composition": "Half-timbered warehouse and a long brick harbour building \u00b7 AI-generated artistic interpretation",
            "description": (
                f"On the old quay, a half-timbered warehouse with black timber, yellow panels, and a red tile roof stands by a long red-brick harbour building. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, with boats on dark water and quay lamps. "
                "The quay is empty. No sculpture and no readable name are in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Nakskov harbour at night, a half-timbered warehouse and a brick harbour building",
            "viewpoint": "The old north quay at Nakskov harbour, looking at the warehouse row and the brick harbour building. Approximate researched point 54.83150, 11.13700, not a surveyed camera.",
            "refs": [
                "https://en.visitnakskov.dk/nakskov-havn",
                "https://www.kulturarv.dk/fbb/sagvis.pub?sag=9716294",
            ],
            "anchors": [
                "A half-timbered warehouse with black timber, yellow panels, and a red tile roof.",
                "A long red-brick harbour building.",
                "Moored boats. No sculpture and no readable name.",
            ],
            "solar": clock("DK-01-105") + "Quay lamps. The industrial south side is not the subject.",
            "independent": "Nakskov harbour has an old north quay of warehouses and a working port beyond it. Dronningens Pakhus, from about 1600, is a long half-timbered warehouse with black tarred timber, yellow panels, and a red tile roof. The long red harbour building and the customs house beside it are early-20th-century brick. A footbridge opened in 2025 farther along the quay; it is not required in this frame. Three granite heads by the post boat are a separate artwork and are not shown. A first wide frame that included a head was discarded.",
            "ip": "No readable wordmark and no sculpture. Warehouse exteriors only. Internal review only, not a legal certification.",
            "visual": "Pass. Timber warehouse, brick harbour building, boats, night under broken cloud. No head sculpture.",
            "swap": (
                "No city swap. A first wide frame included a quay sculpture and was discarded before publication. "
                "The published frame is the warehouse and the brick harbour building."
            ),
        },
        {
            "entry_id": "DK-01-106",
            "region": "Lolland-Falster",
            "city": "Sakskøbing",
            "caption": "Sakskøbing, Sakskøbing",
            **j,
            "composition": "Church spire, low bridge, and the narrow fjord \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Sakskøbing's narrow water is crossed by one low bridge, with tiled roofs along the banks and a red-brick church whose single west tower carries a tall spire. "
                f"The night is {j['word'].lower()}, about {j['temp']}\u00b0C, with breaks in the cloud and street lamps. "
                "The streets are empty. There is no giant face and no readable hotel name."
            ),
            "alt_text": "AI-generated artistic interpretation of Sakskøbing at night, a church spire and a low bridge over the narrow water",
            "viewpoint": "The waterfront where the bridge crosses the narrow fjord, with the church tower in the roofscape. Approximate researched point 54.80020, 11.63800, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Saksk%C3%B8bing",
                "https://lex.dk/Saksk%C3%B8bing_Kirke",
            ],
            "anchors": [
                "A narrow dark waterway and one low bridge.",
                "One brick west tower with a tall spire.",
                "Tiled town roofs. No giant face sculpture.",
            ],
            "solar": clock("DK-01-106") + "Street lamps. The moon is computed, not treated as observed in the frame.",
            "independent": "Sakskøbing sits on both sides of a narrow fjord passage, joined by a bridge at the harbour along Brogade. Sakskøbing Kirke, north of the old square, has a late-Romanesque brick body and a late-medieval west tower. Danish Wikipedia reports the tower, finished with its spire in 1852, at 48 metres. The large face sculpture in town is a separate artwork and is not the subject. The frame is the water, the bridge, and the church spire.",
            "ip": "No hotel name and no sculpture as the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Spire, bridge, water, partly cloudy night, empty. No face sculpture.",
            "swap": "No city swap. The town waterfront is used. The face sculpture was not made the subject.",
        },
        {
            "entry_id": "DK-01-107",
            "region": "Lolland-Falster",
            "city": "Nysted",
            "caption": "Nysted Harbour, Nysted",
            **k,
            "composition": "Small harbour, old houses, and a church tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Nysted's small harbour holds a few boats under quay lamps, with low half-timbered and plaster houses along the water and a church tower behind the roofs. "
                f"The night is {k['word'].lower()}, about {k['temp']}\u00b0C, and the quay is empty. "
                "No boat name is readable. The castle across the inlet is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Nysted harbour at night, boats, old houses, and a church tower",
            "viewpoint": "The quay at Nysted harbour, looking back at the town houses and the church tower. Approximate researched point 54.66640, 11.73180, not a surveyed camera.",
            "refs": [
                "http://www.sejlklubberne.dk/byerne.html",
                "https://historiskehuse.dk/wp-content/uploads/2024/09/09.01.24-Nationale-kulturmiljoeer-15-30-ikke-prioriteret.pdf",
            ],
            "anchors": [
                "A small harbour basin and moored boats.",
                "Low old houses, some half-timbered, along the quay.",
                "A church tower behind the roofs. No castle and no turbines.",
            ],
            "solar": clock("DK-01-107") + "Quay lamps. Offshore turbines are not identified in this cloud.",
            "independent": "Nysted is a small preserved market town on Nysted Nor, on the south coast of Lolland. The harbour is now mainly a marina in the inlet. Half-timbered and small classical houses survive around the town, and the church stands on the rise. Aalholm, the castle across the water, is a different subject and is not shown. Rødsand's offshore turbines lie outside the inlet and are not in this frame.",
            "ip": "No readable boat names or shop signs. Internal review only, not a legal certification.",
            "visual": "Pass. Harbour, old houses, church tower, night under broken cloud. No castle and no turbines.",
            "swap": "No city swap. The harbour is used. Aalholm Castle, across the inlet, is not the subject.",
        },
        {
            "entry_id": "DK-01-108",
            "region": "Funen",
            "city": "Rudkøbing",
            "caption": "Rudkøbing Harbour, Rudkøbing",
            **m,
            "composition": "Harbour basin, warehouses, and a brick quay building \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Rudkøbing harbour is a dark basin of moored boats, with warehouses, red-tiled houses, and a red-brick building with a tower by the quay. "
                f"The night is {m['word'].lower()}, about {m['temp']}\u00b0C, under quay lamps. "
                "The quay is empty, and no name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Rudkøbing harbour at night, boats and a brick building by the quay",
            "viewpoint": "The public quay at Rudkøbing harbour, looking across the basin toward the town warehouses. Approximate researched point 54.93680, 10.71050, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Rudk%C3%B8bing",
                "https://lex.dk/Rudk%C3%B8bing",
            ],
            "anchors": [
                "A harbour basin with moored boats.",
                "Warehouses and low houses with red tile roofs.",
                "A red-brick building with a tower. No readable name.",
            ],
            "solar": clock("DK-01-108") + "Quay lamps. The cloud hides the far water.",
            "independent": "Rudkøbing is the main town of Langeland, and its harbour is the old port beside the town centre. The gallery files Langeland with Funen, as it does Ærø. A red-brick customs house of 1891 is reported on this waterfront; the frame shows a brick quay building with a tower and does not claim a measured copy of that elevation. Tranekær Castle is a separate village and is DK-01-109. No silo brand is shown.",
            "ip": "No readable names and no silo brand. Internal review only, not a legal certification.",
            "visual": "Pass. Basin, warehouses, brick quay building, overcast night, empty.",
            "swap": "No swap. The city is Rudkøbing. Tranekær is the next card, not this harbour.",
        },
        {
            "entry_id": "DK-01-109",
            "region": "Funen",
            "city": "Tranekær",
            "caption": "Tranekær Castle, Tranekær",
            **n,
            "composition": "Red two-wing castle and an octagonal stair tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Tranekær Castle is an English-red two-wing house on a high mound, with crow-stepped gables, white windows, and an octagonal stair tower under a tall spire. "
                f"The night is {n['word'].lower()}, about {n['temp']}\u00b0C, with a dark moat, trees still in leaf, and a few warm windows. "
                "The lane below is empty. The house is a private home, shown from outside."
            ),
            "alt_text": "AI-generated artistic interpretation of Tranekær Castle at night, a red manor with an octagonal tower on a mound",
            "viewpoint": "The public lane below the castle mound at Tranekær, looking up at the two wings and the stair tower. Approximate researched point 55.00152, 10.85593, not a surveyed camera.",
            "refs": [
                "https://tranekaergods.dk/uk/about-the-castle/history.aspx",
                "https://da.wikipedia.org/wiki/Tranek%C3%A6r_Slot",
            ],
            "anchors": [
                "An English-red two-wing house on a mound.",
                "An octagonal stair tower with a tall spire.",
                "A moat and trees. No scaffolding and no sign.",
            ],
            "solar": clock("DK-01-109") + "A few warm windows. Not a floodlit show.",
            "independent": "Tranekær Slot stands on a mound at the north end of the village of Tranekær on Langeland. The present house is two plastered wings, English red with white woodwork since the 1947–49 restoration, and an octagonal stair tower with a spire from N.S. Nebelong's work of 1859–63. It is a private home and is not open to the public; this is the exterior from the lane. The city in the caption is Tranekær, the village. An English Wikipedia line that posts the manor at 4490 Jerslev Sjælland is not used. Rudkøbing harbour is DK-01-108.",
            "ip": "Private house, exterior only, no invitation to enter. No sign and no family crest as a logo. Internal review only, not a legal certification.",
            "visual": "Pass. Red wings, octagonal tower, spire, mound, moat, overcast night, empty lane.",
            "swap": (
                "City check, not a site swap. The castle is in the village of Tranekær, so the city is Tranekær, not Rudkøbing. "
                "The English Wikipedia postal line placing it in Jerslev Sjælland is rejected."
            ),
        },
        {
            "entry_id": "DK-01-110",
            "region": "Funen",
            "city": "Kerteminde",
            "caption": "Kerteminde Harbour, Kerteminde",
            **o,
            "composition": "Coloured houses along a narrow fishing harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Kerteminde's old harbour is a narrow channel of small boats between low houses in yellow, white, and red, all under red tile roofs. "
                f"The night is {o['word'].lower()}, about {o['temp']}\u00b0C, with quay lamps on the water. "
                "The quay is empty. No boat name is readable, and there is no moated castle."
            ),
            "alt_text": "AI-generated artistic interpretation of Kerteminde harbour at night, coloured houses and small boats",
            "viewpoint": "The quay of the old fishing harbour in Kerteminde, looking along the channel of houses. Approximate researched point 55.44940, 10.65720, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Kerteminde",
                "https://www.visitkerteminde.dk/",
            ],
            "anchors": [
                "A narrow harbour channel.",
                "Low houses in yellow, white, and red with tile roofs.",
                "Small boats. No moat and no copper castle spires.",
            ],
            "solar": clock("DK-01-110") + "Quay lamps. No aquarium sign.",
            "independent": "Kerteminde is a fishing town on the northeast coast of Funen. The old harbour is a channel lined with low coloured houses. Egeskov Castle is inland at Kværndrup and is already DK-01-009; it is not this waterfront. The fjord aquarium is a separate building and is not given a name or a logo here. Which boats were alongside this night was not checked.",
            "ip": "No readable boat names and no aquarium wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Coloured houses, boats, narrow harbour, overcast night. Distinct from Egeskov.",
            "swap": "No swap. The town harbour is used. Egeskov, DK-01-009, stays at Kværndrup.",
        },
        {
            "entry_id": "DK-01-111",
            "region": "Funen",
            "city": "Nyborg",
            "caption": "Nyborg Harbour, Nyborg",
            **p,
            "composition": "Marina piers and dark open water \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Nyborg's marina is a set of floating piers and moored sailboats on dark water, with low ordinary houses along the quay. "
                f"The night is {p['word'].lower()}, about {p['temp']}\u00b0C, and the quay is empty. "
                "No boat name is readable. The castle, its moat, and the conservation tents are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Nyborg harbour at night, marina boats and dark water",
            "viewpoint": "The marina quay at Nyborg, looking across the piers toward open water, with the castle outside the frame. Approximate researched point 55.31350, 10.78950, not a surveyed camera.",
            "refs": [
                "https://www.harbourmaps.com/en/harbour/nyborg",
                "https://en.wikipedia.org/wiki/Nyborg",
            ],
            "anchors": [
                "Floating piers and moored sailboats.",
                "Low ordinary waterfront houses.",
                "Dark open water. No castle and no white tents.",
            ],
            "solar": clock("DK-01-111") + "Quay lamps. No castle lighting, because the castle is another card.",
            "independent": "Nyborg's marina sits by the town on the Great Belt, with floating piers and a sheltered basin. DK-01-040 is Nyborg Castle, the red-brick King's Wing across its moat, with white conservation tents, and that project is not shown here. The suspension bridge of the Great Belt is the Zealand side, at Korsør in DK-01-104, and is not this marina. No boat name is treated as readable.",
            "ip": "No readable boat names and no fuel-brand marks. Internal review only, not a legal certification.",
            "visual": "Pass. Piers, boats, low houses, dark water, overcast night. No castle.",
            "swap": "No city swap. The harbour is kept separate from Nyborg Castle, DK-01-040.",
        },
        {
            "entry_id": "DK-01-112",
            "region": "Funen",
            "city": "Odense",
            "caption": "Munke Mose, Odense",
            **q,
            "composition": "River, footbridge, and a mill pond in the park \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Munke Mose is a city park: a dark river through lawns, one plain footbridge, and a small still pond, with trees still in leaf. "
                f"The night is {q['word'].lower()}, about {q['temp']}\u00b0C, and the paths are empty under a few lamps. "
                "There is no cathedral and no ochre lane. No boat is out."
            ),
            "alt_text": "AI-generated artistic interpretation of Munke Mose in Odense at night, a footbridge over the river and a small pond",
            "viewpoint": "The path in Munke Mose beside Odense Å, looking at the footbridge and the mill pond. Approximate researched point 55.39420, 10.38880, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Munke_Mose",
                "https://www.visitodense.com/munke-mose-park-gdk736110",
            ],
            "anchors": [
                "A dark river through lawns.",
                "One plain pedestrian footbridge.",
                "A small still pond and trees. No cathedral and no half-timbered lane.",
            ],
            "solar": clock("DK-01-112") + "Path lamps. The park is not lit as an event.",
            "independent": "Munke Mose is the city park along Odense Å, bought by the municipality from 1881 and laid out as a park in the early 20th century. The small pond is a remnant of the old mill pond. The footbridge from the centre was rebuilt and extended in 2008. Pleasure boats run in season and are not out at this hour. DK-01-008 is the H.C. Andersen quarter and DK-01-036 is the cathedral; neither is this park. The harbour was the other catalogue option and was not used.",
            "ip": "No readable park sign and no portrait statue as the subject. Internal review only, not a legal certification.",
            "visual": "Pass. River, footbridge, pond, lamps, overcast night, empty. Distinct from the cathedral and the Andersen quarter.",
            "swap": (
                "Chose Munke Mose rather than Odense Harbour. The park stays clear of quay branding and is distinct from "
                "the H.C. Andersen quarter, DK-01-008, and from Odense Cathedral, DK-01-036."
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
    if len(all_scenes) != 112:
        raise SystemExit(f"expected 112 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 113)]
    if ids != expected:
        raise SystemExit(ids)
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-097-112.txt"
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

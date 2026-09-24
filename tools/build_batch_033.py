#!/usr/bin/env python3
"""Bake DK-01-033 through DK-01-048 and rebuild the gallery from every manifest."""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_denmark as bd

# Honest lineage for this batch: the image tool returned JPEGs at the
# pipeline's source sizes. They are decoded to PNG with no resample.
bd.LINEAGE = (
    "Text-prompt-only. No photographic reference pixels. "
    "The generator returned a 1280\u00d7720 JPEG for the wide frame and an 864\u00d71152 JPEG for the portrait frame; "
    "both were decoded to PNG without resampling. "
    "The 16:9 master is a uniform Lanczos resample from 1280\u00d7720 to 1920\u00d71080. "
    "The 4:5 master is a centered crop of the 864\u00d71152 frame to 864\u00d71080, with no upscale."
)

# Viewpoint coordinates used for the Open-Meteo request. Not surveyed cameras.
COORDS = {
    "DK-01-033": (54.7726, 11.4994),
    "DK-01-034": (54.82806, 11.48861),
    "DK-01-035": (54.5630, 11.9730),
    "DK-01-036": (55.3954, 10.3889),
    "DK-01-037": (55.0594, 10.6072),
    "DK-01-038": (54.8890, 10.4114),
    "DK-01-039": (55.0950, 10.2435),
    "DK-01-040": (55.3125, 10.7906),
    "DK-01-041": (54.9094, 9.7842),
    "DK-01-042": (54.90693, 9.75798),
    "DK-01-043": (54.9419, 8.8078),
    "DK-01-044": (55.3567, 9.4869),
    "DK-01-045": (55.4915, 9.4744),
    "DK-01-046": (55.2494, 9.4883),
    "DK-01-047": (55.0442, 9.4186),
    "DK-01-048": (54.9336, 8.8664),
}


def sky_word(code: int) -> str:
    return {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}.get(
        code, f"Weather code {code}"
    )


def fetch_weather() -> tuple[str, dict]:
    ids = list(COORDS)
    lats = ",".join(str(COORDS[i][0]) for i in ids)
    lons = ",".join(str(COORDS[i][1]) for i in ids)
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lats}&longitude={lons}"
        "&current=temperature_2m,cloud_cover,wind_speed_10m,precipitation,weather_code,is_day"
        "&daily=sunrise,sunset&timezone=Europe%2FCopenhagen&forecast_days=2"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "jason-ds-vision-denmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    retrieved = datetime.now(bd.CPH)
    if isinstance(data, dict):
        data = [data]
    if len(data) != len(ids):
        raise SystemExit(f"weather count {len(data)}")
    out = {}
    for entry, item in zip(ids, data):
        cur = item["current"]
        daily = item["daily"]
        code = int(cur["weather_code"])
        temp = float(cur["temperature_2m"])
        cloud = int(cur["cloud_cover"])
        wind = float(cur["wind_speed_10m"])
        precip = float(cur["precipitation"])
        precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
        word = sky_word(code)
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
            "sunset_prev": daily["sunset"][0],  # today's sunset is still ahead; use yesterday via index
            "sunrise": daily["sunrise"][0],
            "sunset_today": daily["sunset"][0],
        }
    # At night after midnight, sunset[0] is the coming sunset and sunrise[0] is this morning.
    # The last sunset was the previous calendar day's sunset, which Open-Meteo does not return
    # in a 2-day forecast that starts today. Record the coming sunrise and state the
    # previous sunset from the earlier retrieval (24 September, about 19:05).
    stamp = retrieved.strftime("%-d %B %Y %H:%M")
    # Linux supports %-d; if not, fall back.
    return stamp, out


def decode_raws() -> None:
    specs = {"16x9": (1280, 720), "4x5": (864, 1152)}
    for n in range(33, 49):
        for kind, size in specs.items():
            src = bd.RAW / f"dk-01-{n:03d}-{kind}.png"
            im = Image.open(src)
            if im.size != size:
                raise SystemExit(f"bad source {src} {im.size}")
            dest = bd.RAW / f"dk-01-{n:03d}-{kind}-raw.png"
            im.convert("RGB").save(dest, "PNG")


def scenes(weather_stamp: str, wx: dict) -> list:
    def pref(entry: str) -> str:
        valid = wx[entry]["valid"].replace("T", " ")
        # valid is like 2026-09-25 01:00
        y, m, d = valid[:10].split("-")
        months = {
            "01": "January", "02": "February", "03": "March", "04": "April",
            "05": "May", "06": "June", "07": "July", "08": "August",
            "09": "September", "10": "October", "11": "November", "12": "December",
        }
        hhmm = valid[11:16]
        nice = f"{int(d)} {months[m]} {y} {hhmm}"
        return (
            "Model data from Open-Meteo, retrieved "
            f"{weather_stamp} Europe/Copenhagen, valid {nice} Europe/Copenhagen "
            "\u2014 not a verified on-site observation."
        )

    def w(entry: str) -> dict:
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

    moon = (
        "A waxing gibbous moon near 97% illumination was computed for 22:45 UTC on 24 September 2026, "
        "not observed on site."
    )
    night = (
        "Night. Sunset on 24 September 2026 was about 19:05 Europe/Copenhagen and sunrise on "
        "25 September 2026 is about 07:04. "
    )

    a = w("DK-01-033")
    b = w("DK-01-034")
    c = w("DK-01-035")
    d = w("DK-01-036")
    e = w("DK-01-037")
    f = w("DK-01-038")
    g = w("DK-01-039")
    h = w("DK-01-040")
    i = w("DK-01-041")
    j = w("DK-01-042")
    k = w("DK-01-043")
    l = w("DK-01-044")
    m = w("DK-01-045")
    n = w("DK-01-046")
    o = w("DK-01-047")
    p = w("DK-01-048")

    return [
        {
            "entry_id": "DK-01-033",
            "region": "Lolland-Falster",
            "city": "Maribo",
            "caption": "Maribo Cathedral, Maribo",
            **a,
            "composition": "Red-brick hall church and one west tower by the lake \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the path by Maribo S\u00f8, the red-brick cathedral shows crow-stepped gables and one slender west tower, with the dark lake and reeds in front. "
                f"It is {a['word'].lower()}, about {a['temp']}\u00b0C, and the path is empty. "
                "The tower on the west gable was rebuilt in 1891. The church is a Bridgettine hall, with the vessels under one roof. This is not the cliff at M\u00f8ns Klint."
            ),
            "alt_text": "AI-generated artistic interpretation of Maribo Cathedral at night, a red-brick church beside the lake",
            "viewpoint": "Lakeside path beside Maribo Cathedral, looking at the brick gables and the west tower across the reeds. Approximate researched point 54.7726, 11.4994, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Maribo_Cathedral",
                "https://www.visitlolland-falster.com/tourist/plan-your-holiday/maribo-cathedral-gdk616344",
            ],
            "anchors": [
                "One red-brick Gothic hall church with crow-stepped gables.",
                "A single slender west tower, not a pair of spires.",
                "Dark lake and reeds in the foreground, empty path.",
            ],
            "solar": night + f"Cloud cover {a['cloud']}%. {moon} Lamps along the path carry the scene.",
            "independent": "Maribo Cathedral is the former Bridgettine abbey church on the lake in Maribo, on Lolland. The broad gable comes from housing the nave and aisles under one roof. The west tower was rebuilt in 1891.",
            "ip": "No featured logos. A carved gable relief, if present, is architectural and is not treated as a separate artwork reproduction. Internal review only, not a legal certification.",
            "visual": "Pass. One brick church, one west tower, lake. Distinct from M\u00f8ns Klint and from Stevns Klint.",
            "swap": "No location swap. City is Maribo. Gallery region is Lolland-Falster, matching the kit row and the M\u00f8ns Klint card. The administrative region is Zealand.",
        },
        {
            "entry_id": "DK-01-034",
            "region": "Lolland-Falster",
            "city": "Maribo",
            "caption": "Knuthenborg, Maribo",
            **b,
            "composition": "Closed gate and the manor tower beyond a dark avenue \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the road at the closed gate, a gatehouse and a dark beech avenue lead toward Knuthenborg's pale manor and its corner tower with a pointed spire. "
                f"The park is shut. It is {b['word'].lower()}, about {b['temp']}\u00b0C, with no rain, and the late-September trees are still mostly green. "
                "No animals are in the frame. The safari enclosures are not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of the closed approach to Knuthenborg manor at night, with no animals",
            "viewpoint": "Public approach outside the closed gate, looking along the avenue toward the manor tower. The manor coordinate used for weather is 54.82806, 11.48861, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Knuthenborg",
                "https://www.knuthenborg.dk/en",
            ],
            "anchors": [
                "A closed gatehouse at the near end of a tree avenue.",
                "A pale manor with one corner tower and a pointed spire.",
                "No animals and no safari vehicles.",
            ],
            "solar": night + f"Cloud cover {b['cloud']}%. {moon} The avenue is dark; a few lamps mark the gate.",
            "independent": "Knuthenborg is a manor six kilometres north of Maribo. The present house was completed in 1866 to a design by Henrik Steffens Sibbern, with a corner tower and a pointed spire. The safari park occupies the estate and is closed at this hour.",
            "ip": "Exterior architecture only. Animals are not depicted, so no zoo-animal likeness is the subject. No park wordmark is the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Gate, avenue, and manor tower. No animals as the subject.",
            "swap": (
                "City corrected from the suggested Bandholm to Maribo. Knuthenborg is the estate, not a town. "
                "The park's own contact line is Knuthenborg All\u00e9, 4930 Maribo. Bandholm is the harbour town to the north and appears on some directory listings as 4941 Bandholm. "
                "The scene is still the manor approach, exterior only."
            ),
        },
        {
            "entry_id": "DK-01-035",
            "region": "Lolland-Falster",
            "city": "Gedser",
            "caption": "Gedser Odde, Gedser",
            **c,
            "composition": "Low clay cliff, open Baltic, and a white hexagonal lighthouse \u00b7 AI-generated artistic interpretation",
            "description": (
                f"At Gedser Odde, a low clay cliff meets a dark Baltic with some chop, and a white hexagonal lighthouse with a red lantern stands back from the edge. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, with wind near {c['wind']} km/h and no rain. "
                "The horizon in the frame is open water. This is the southern tip, not the ferry harbour in the town."
            ),
            "alt_text": "AI-generated artistic interpretation of Gedser Odde at night, with a white hexagonal lighthouse above a low cliff",
            "viewpoint": "Cliff path at Denmark's southern tip, with the lighthouse inland of the edge and the sea to the south. Approximate researched point 54.5630, 11.9730, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Gedser_Odde",
                "https://www.visitlolland-falster.dk/turist/planlaeg-din-ferie/sydstenen-gedser-odde-gdk615862",
            ],
            "anchors": [
                "A low clay cliff and open dark water, with no far shore.",
                "A white hexagonal lighthouse with a red lantern, set back from the cliff.",
                "Empty grass. No readable plaque.",
            ],
            "solar": night + f"Cloud cover {c['cloud']}%. {moon} The coast is dark. The lighthouse is an operational aid; the frame does not claim a surveyed flash.",
            "independent": "Gedser Odde on Falster is Denmark's southernmost point, a low cliff of about 5 to 7 metres. Gedser Fyr stands about 0.7 km northwest of the point. A renovation account describes the tower as hexagonal, white, with a red lantern. Wikipedia calls the same tower square; the hexagonal form was followed. Sydstenen has stood in a courtyard by the old naval station since 2012, so it is not placed on the open grass.",
            "ip": "No featured logos. Information panels are not readable. Internal review only, not a legal certification.",
            "visual": "Pass. Open sea, low cliff, hexagonal white lighthouse with a red lantern. An earlier wide frame showed a distant shore and was replaced before publish.",
            "swap": "No location swap. City is Gedser. The English Wikipedia's 'square' tower and the hexagonal account from the lighthouse renovation disagree; the frame follows the hexagonal description and the disagreement is logged here.",
        },
        {
            "entry_id": "DK-01-036",
            "region": "Funen",
            "city": "Odense",
            "caption": "Odense Cathedral, Odense",
            **d,
            "composition": "Red-brick Gothic basilica and one lantern tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the cathedral square, Sankt Knuds Kirke is a red-brick Gothic basilica with one west tower and an open lantern spire. "
                f"The square is empty under streetlamps. The sky is {d['word'].lower()}, about {d['temp']}\u00b0C, with no rain. "
                "This is the city-centre cathedral, not the low ochre houses of the H.C. Andersen quarter."
            ),
            "alt_text": "AI-generated artistic interpretation of Odense Cathedral at night, a red-brick church with one lantern tower",
            "viewpoint": "Cathedral square in central Odense, looking at the west tower of Sankt Knuds Kirke. Approximate researched point 55.3954, 10.3889, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Saint_Canute%27s_Cathedral",
                "https://www.odensedomkirke.dk/kirker/domkirken-skt-knuds-kirke/domkirkens-arkitektur",
            ],
            "anchors": [
                "One large red-brick Gothic church.",
                "A single west tower with an open lantern, not twin spires.",
                "An empty paved square and streetlamps.",
            ],
            "solar": night + f"Cloud cover {d['cloud']}%. The moon is not treated as visible. Streetlamps carry the square.",
            "independent": "Odense Cathedral, Sankt Knuds Kirke, is the brick Gothic cathedral in the centre. The church finished in 1499 had no tower. The west tower is later, and the present lantern spire dates from 1783\u201385.",
            "ip": "No featured logos. Internal review only, not a legal certification.",
            "visual": "Pass. One brick cathedral and a lantern tower. Distinct from DK-01-008.",
            "swap": "No swap. The kit city is the town used in the caption. The scene is the cathedral, not the H.C. Andersen quarter already published as DK-01-008.",
        },
        {
            "entry_id": "DK-01-037",
            "region": "Funen",
            "city": "Svendborg",
            "caption": "Svendborg Harbour, Svendborg",
            **e,
            "composition": "Quay, moored boats, and the sound bridge \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, Svendborg's harbour holds a few moored boats and low warehouses, with the long bridge across Svendborg Sound in the distance. "
                f"It is {e['word'].lower()}, about {e['temp']}\u00b0C, with wind near {e['wind']} km/h, and the quay is empty. "
                "Lettering on the boats is not treated as real names."
            ),
            "alt_text": "AI-generated artistic interpretation of Svendborg harbour at night, with boats and a distant bridge",
            "viewpoint": "Public quay on Svendborg harbour, looking across the sound toward the bridge. Approximate researched point 55.0594, 10.6072, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Svendborg",
                "https://en.wikipedia.org/wiki/Svendborgsund_Bridge",
            ],
            "anchors": [
                "A working harbour quay with a few moored boats.",
                "Low warehouses along the water.",
                "A long low bridge in the distance across the sound.",
            ],
            "solar": night + f"Cloud cover {e['cloud']}%. Quay lamps, not moonlight.",
            "independent": "Svendborg is the harbour town on southern Funen. Svendborgsund Bridge crosses the sound toward T\u00e5singe and is the long low span in views from the harbour.",
            "ip": "No ferry livery and no readable boat names are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Harbour, boats, warehouses, and a distant bridge. Not Egeskov and not the Odense cathedral.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-038",
            "region": "Funen",
            "city": "\u00c6r\u00f8sk\u00f8bing",
            "caption": "\u00c6r\u00f8sk\u00f8bing, \u00c6r\u00f8sk\u00f8bing",
            **f,
            "composition": "Cobbled lane of small coloured houses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The frame is a cobbled lane in \u00c6r\u00f8sk\u00f8bing, lined with small houses in different colours, red tile roofs, and painted doors. "
                f"Lamps light the empty street. The night is {f['word'].lower()}, about {f['temp']}\u00b0C, with wind near {f['wind']} km/h and no rain. "
                "The houses are an interpretation of the old town, not a measured survey of one street."
            ),
            "alt_text": "AI-generated artistic interpretation of a cobbled lane in \u00c6r\u00f8sk\u00f8bing at night, with small coloured houses",
            "viewpoint": "A cobbled street in the old town of \u00c6r\u00f8sk\u00f8bing, looking along the low houses. Approximate researched point 54.8890, 10.4114, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/%C3%86r%C3%B8sk%C3%B8bing",
                "https://en.wikipedia.org/wiki/%C3%86r%C3%B8",
            ],
            "anchors": [
                "Uneven cobbles and very small houses.",
                "Different muted wall colours and painted doors.",
                "Red tile roofs and warm lamps. No large new building.",
            ],
            "solar": night + f"Cloud cover {f['cloud']}%. Streetlamps carry the lane.",
            "independent": "\u00c6r\u00f8sk\u00f8bing is the preserved town on the north side of \u00c6r\u00f8, known for its small houses and cobbled lanes. \u00c6r\u00f8 sits in the South Funen archipelago. The gallery region follows the kit's Funen row.",
            "ip": "No readable shop names intended. Internal review only, not a legal certification.",
            "visual": "Pass. Small coloured houses and cobbles. Not Svendborg harbour.",
            "swap": "No swap. City is \u00c6r\u00f8sk\u00f8bing. Region is Funen, as in the kit table, although the administrative region is Southern Denmark.",
        },
        {
            "entry_id": "DK-01-039",
            "region": "Funen",
            "city": "Faaborg",
            "caption": "Faaborg Harbour, Faaborg",
            **g,
            "composition": "Harbour houses and the standalone bell tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the harbour quay at Faaborg, wooden boats and low old houses sit on the water, and the town's standalone red-brick bell tower rises behind the roofs. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C, with wind near {g['wind']} km/h, and the quay is empty. "
                "The exact alignment of the tower from this quay was not surveyed."
            ),
            "alt_text": "AI-generated artistic interpretation of Faaborg harbour at night, with the brick bell tower behind the roofs",
            "viewpoint": "Public harbour quay, looking toward the old houses and the bell tower inland. Approximate researched point 55.0950, 10.2435, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Faaborg",
                "https://en.wikipedia.org/wiki/Faaborg_Municipality",
            ],
            "anchors": [
                "A small harbour basin and a few wooden boats.",
                "Low old houses along the quay.",
                "One standalone red-brick bell tower behind the roofs.",
            ],
            "solar": night + f"Cloud cover {g['cloud']}%. Quay lamps.",
            "independent": "Faaborg is a harbour town on southwest Funen. Its medieval bell tower stands alone in the old town, separate from a church nave, and is the local skyline mark near the harbour.",
            "ip": "No readable boat names intended. Internal review only, not a legal certification.",
            "visual": "Pass. Harbour plus the standalone brick tower. Not Egeskov.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-040",
            "region": "Funen",
            "city": "Nyborg",
            "caption": "Nyborg Castle, Nyborg",
            **h,
            "composition": "Red-brick King's Wing, moat, and conservation tents \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the rampart path, Nyborg's red-brick King's Wing stands across the moat, with white conservation tents and low fencing on the holm. "
                f"The castle is not open. It is {h['word'].lower()}, about {h['temp']}\u00b0C, and the path is empty. "
                "The new museum wing and a heightened watchtower are not shown as finished. The project is scheduled to open in 2028."
            ),
            "alt_text": "AI-generated artistic interpretation of Nyborg Castle at night, with the brick King's Wing and white conservation tents",
            "viewpoint": "Public rampart side of the moat, looking at the King's Wing. The castle interior is closed. Approximate researched point 55.3125, 10.7906, not a surveyed camera.",
            "refs": [
                "https://nyborgslot.dk/en/the-castle-project/",
                "https://en.wikipedia.org/wiki/Nyborg_Castle",
            ],
            "anchors": [
                "A long red-brick King's Wing with a steep roof.",
                "Dark moat water and the grass rampart.",
                "White tents and low fencing on the site, and no finished new wing.",
            ],
            "solar": night + f"Cloud cover {h['cloud']}%. A few lamps. Not a lit reopening.",
            "independent": "Nyborg Castle is on the east coast of Funen. Only the King's Wing of the medieval castle remains. Its restoration was completed in 2022, but the castle has been closed to visitors since 2018. The castle's project page places the next construction phase in 2026 and the opening in 2028, and a castle page describes white tents over ring-wall remains. The exact coverage on this night was not surveyed on site.",
            "ip": "No featured logos. Internal review only, not a legal certification.",
            "visual": "Pass. Brick wing, moat, and works tents. Not depicted as a finished 2028 reopening. Funen, not Zealand.",
            "swap": (
                "No location swap. Funen is verified: Nyborg is on the east coast of Funen. "
                "The castle is depicted with the works in progress because a pristine reopened castle would contradict the project timeline. "
                "The exact scaffold pattern on 25 September 2026 was not surveyed."
            ),
        },
        {
            "entry_id": "DK-01-041",
            "region": "South Jutland",
            "city": "S\u00f8nderborg",
            "caption": "S\u00f8nderborg Castle, S\u00f8nderborg",
            **i,
            "composition": "Red-brick palace standing in Als Sound \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the promenade, S\u00f8nderborg Castle is a large red-brick palace on a stone base, standing in the dark water of Als Sound, with a red roof and plain windowed walls. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, and the quay is empty. "
                "Curved Renaissance gables were taken off in the 18th century, so they are not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of S\u00f8nderborg Castle at night, a red-brick palace on the water",
            "viewpoint": "Waterfront promenade looking at the castle on its holm at the entrance to Als Sound. Address S\u00f8nderbro 1, 6400 S\u00f8nderborg. Approximate researched point 54.9094, 9.7842, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/S%C3%B8nderborg_Castle",
                "https://da.wikipedia.org/wiki/S%C3%B8nderborg_Slot",
            ],
            "anchors": [
                "A large red-brick palace directly on the water.",
                "A stone base, many regular windows, and a red roof.",
                "Plain facades, not a yellow fairy-tale castle and not a cluster of copper spires.",
            ],
            "solar": night + f"Cloud cover {i['cloud']}%. Quay lamps and a few lit windows.",
            "independent": "S\u00f8nderborg Castle is the four-wing brick palace on a holm at Als Sound, on the island of Als. The decorative Renaissance gables were removed in the 18th century. The slender stair towers are in the courtyard and are not claimed on the outer water facade.",
            "ip": "No featured logos. Internal review only, not a legal certification.",
            "visual": "Pass. Brick palace on the water. Distinct from the mill at Dybb\u00f8l.",
            "swap": "No swap. City is S\u00f8nderborg. Gallery region is South Jutland, matching the kit and the Ribe card. The administrative region is Southern Denmark.",
        },
        {
            "entry_id": "DK-01-042",
            "region": "South Jutland",
            "city": "Dybb\u00f8l",
            "caption": "Dybb\u00f8l Mill, Dybb\u00f8l",
            **j,
            "composition": "White tower mill on the grassy hill \u00b7 AI-generated artistic interpretation",
            "description": (
                f"On the grass of Dybb\u00f8l Banke, the white tower mill has a gallery, a dark boat-shaped cap, and sails, with the sound in the distance. "
                f"It is {j['word'].lower()}, about {j['temp']}\u00b0C, with wind near {j['wind']} km/h, and the hill is empty. "
                "The mill in this form dates from 1936. No memorial lettering is treated as readable text."
            ),
            "alt_text": "AI-generated artistic interpretation of Dybb\u00f8l Mill at night, a white windmill on a grassy hill",
            "viewpoint": "Grassy hill at Dybb\u00f8l Banke, looking at the mill with the sound beyond. Address Dybb\u00f8l Banke 7, Dybb\u00f8l, 6400 S\u00f8nderborg. Approximate researched point 54.90693, 9.75798, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Dybb%C3%B8l_M%C3%B8lle",
                "https://1864.dk/da/oplevelser/dybboel-moelle-3/",
            ],
            "anchors": [
                "A white rendered tower mill with a gallery.",
                "A dark boat-shaped cap and four sails.",
                "Open grass hill and distant water. No soldiers.",
            ],
            "solar": night + f"Cloud cover {j['cloud']}%. The mill is lit by whatever lamps are on the hill; moonlight is not claimed.",
            "independent": "Dybb\u00f8l Mill is the white Dutch-style tower mill on Dybb\u00f8l Banke, west of S\u00f8nderborg. The present mill was built in 1936 after earlier mills were destroyed. It is a memorial place as well as a mill, and the hill is empty at this hour.",
            "ip": "No flags and no readable memorial inscriptions are intended. Internal review only, not a legal certification.",
            "visual": "Pass. White gallery mill on a hill. Not S\u00f8nderborg Castle.",
            "swap": (
                "City corrected from the suggested S\u00f8nderborg to Dybb\u00f8l. "
                "The Danish Wikipedia address is Dybb\u00f8l Banke 7, Dybb\u00f8l, S\u00f8nderborg, and the postal code is 6400 S\u00f8nderborg. "
                "Dybb\u00f8l is the locality of the mill. S\u00f8nderborg remains the city of the castle scene."
            ),
        },
        {
            "entry_id": "DK-01-043",
            "region": "South Jutland",
            "city": "M\u00f8gelt\u00f8nder",
            "caption": "Slotsgade, M\u00f8gelt\u00f8nder",
            **k,
            "composition": "Cobbled lime avenue and a pale manor at the end \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Slotsgade runs straight away under lime trees, with low brick houses and white windows, and a pale manor closes the far end. "
                f"The night is {k['word'].lower()}, about {k['temp']}\u00b0C, with wind near {k['wind']} km/h, and the cobbles are empty. "
                "The late-September limes are still mostly green. This street is in M\u00f8gelt\u00f8nder, about four kilometres west of T\u00f8nder."
            ),
            "alt_text": "AI-generated artistic interpretation of Slotsgade in M\u00f8gelt\u00f8nder at night, a cobbled street of lime trees",
            "viewpoint": "On Slotsgade, looking along the cobbles and the lime trees toward Schackenborg. Approximate researched point 54.9419, 8.8078, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/M%C3%B8gelt%C3%B8nder",
                "https://lex.dk/M%C3%B8gelt%C3%B8nder",
            ],
            "anchors": [
                "A long straight cobbled street.",
                "Lime trees and low brick houses with white windows.",
                "A pale manor closing the view. Empty street.",
            ],
            "solar": night + f"Cloud cover {k['cloud']}%. A few streetlamps.",
            "independent": "M\u00f8gelt\u00f8nder is its own town in T\u00f8nder Municipality, about 4 km west of T\u00f8nder. Slotsgade was laid out around 1680 and leads from the church quarter toward Schackenborg. The houses are largely 18th-century brick.",
            "ip": "No royal portrait and no readable shop name is the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Cobbles, limes, low houses, manor at the end. Distinct from T\u00f8nder old town.",
            "swap": "City verified as M\u00f8gelt\u00f8nder, not folded into T\u00f8nder. The high street's name is Slotsgade, so that is the caption site. No location swap.",
        },
        {
            "entry_id": "DK-01-044",
            "region": "South Jutland",
            "city": "Christiansfeld",
            "caption": "Christiansfeld, Christiansfeld",
            **l,
            "composition": "Yellow-brick Moravian square and a low church hall \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The church square in Christiansfeld is lined with one- and two-storey yellow-brick houses and red tile roofs, and the Moravian church is a long hall with only a small roof turret. "
                f"Linden trees stand on the square. It is {l['word'].lower()}, about {l['temp']}\u00b0C, and the square is empty. "
                "The town is a UNESCO World Heritage site. Shop lettering is not treated as real signage."
            ),
            "alt_text": "AI-generated artistic interpretation of the church square in Christiansfeld at night, yellow-brick houses around a low church",
            "viewpoint": "Church square of the Moravian town, looking at the hall church and the yellow-brick houses. Approximate researched point 55.3567, 9.4869, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Christiansfeld",
                "https://whc.unesco.org/en/list/1468/",
            ],
            "anchors": [
                "Yellow-brick houses of one and two storeys with red tile roofs.",
                "A long simple church hall with a small turret, not a cathedral spire.",
                "Linden trees and an empty square.",
            ],
            "solar": night + f"Cloud cover {l['cloud']}%. Square lamps.",
            "independent": "Christiansfeld was founded in 1773 as a Moravian settlement and was inscribed as a World Heritage site in 2015. The plan centres on a church square of unornamented yellow-brick buildings. The church is a hall with a modest copper-clad turret.",
            "ip": "No honey-cake brand and no shop wordmark is the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow brick, red roofs, low church hall. Not Koldinghus.",
            "swap": "No swap. City is Christiansfeld. Gallery region is South Jutland, as in the user's catalogue. The town is in Kolding Municipality in the Region of Southern Denmark.",
        },
        {
            "entry_id": "DK-01-045",
            "region": "South Jutland",
            "city": "Kolding",
            "caption": "Koldinghus, Kolding",
            **m,
            "composition": "Brick castle, oak-shingle walls, and a timber tower across the lake \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Across the dark castle lake, Koldinghus shows red-brick wings and, on the ruined side, grey-brown oak-shingle walls and a tall open timber tower. "
                f"The timber reads as the modern restoration, not as medieval fabric. It is {m['word'].lower()}, about {m['temp']}\u00b0C, and the bank is empty. "
                "Joints in the timber are a generated interpretation, not a measured survey of the Exner structure."
            ),
            "alt_text": "AI-generated artistic interpretation of Koldinghus at night, with a tall timber tower above the brick castle",
            "viewpoint": "Far bank of the castle lake, the usual exterior of Koldinghus across the water. Address Markdanersgade 11, 6000 Kolding. Approximate researched point 55.4915, 9.4744, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Koldinghus",
                "https://ingerogjohannesexner.dk/en/koldinghus/external-facades/",
            ],
            "anchors": [
                "Red-brick castle wings.",
                "Grey-brown oak-shingle walls on the ruined side.",
                "One tall open timber tower and dark lake water.",
            ],
            "solar": night + f"Cloud cover {m['cloud']}%. A few lamps and lit windows. Not a bare unlit ruin and not a fully medieval skyline.",
            "independent": "Koldinghus burned in 1808 and stood as a ruin. The restoration by Inger and Johannes Exner, finished in the early 1990s, closes the missing south and east walls with oak shingles hung from a timber and steel structure, and a tall glulam tower rises over the ruin.",
            "ip": "The modern timber is architectural, not a depicted artwork. No logos. Internal review only, not a legal certification.",
            "visual": "Pass. Brick, oak shingles, and a timber tower across water. Not a complete medieval castle.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-046",
            "region": "South Jutland",
            "city": "Haderslev",
            "caption": "Haderslev Cathedral, Haderslev",
            **n,
            "composition": "Brick Gothic choir with flying buttresses and no tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the street, Haderslev Cathedral is a long brick Gothic church with a plain west gable, tall choir windows, and flying buttresses. "
                f"There is no tower. The night is {n['word'].lower()}, about {n['temp']}\u00b0C, and the pavement is empty. "
                "The medieval tower fell in the fire of 1627 and was not rebuilt."
            ),
            "alt_text": "AI-generated artistic interpretation of Haderslev Cathedral at night, a brick church with flying buttresses and no tower",
            "viewpoint": "Street beside the cathedral, looking along the west gable and the buttressed choir. Approximate researched point 55.2494, 9.4883, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Haderslev_Cathedral",
                "https://www.haderslevdomprovsti.dk/kirker-og-sogne/haderslev-domkirke/turist-info-engelsk/",
            ],
            "anchors": [
                "A long red-brick Gothic church.",
                "A plain west gable and no tower or spire.",
                "Flying buttresses and very tall choir windows.",
            ],
            "solar": night + f"Cloud cover {n['cloud']}%. Streetlamps on the brick.",
            "independent": "Haderslev Cathedral, Vor Frue, is a brick Gothic church in the town centre. The great west tower collapsed in the 1627 fire. The west end was rebuilt as a gable, and later restorations kept the church in that towerless form. The choir retains Denmark's medieval flying buttresses.",
            "ip": "No featured logos. Internal review only, not a legal certification.",
            "visual": "Pass. No tower, buttressed choir, west gable. Distinct from Ribe's square tower and from Roskilde's twin spires.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-047",
            "region": "South Jutland",
            "city": "Aabenraa",
            "caption": "Aabenraa Harbour, Aabenraa",
            **o,
            "composition": "Calm fjord quay and merchant houses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, Aabenraa harbour is a calm fjord basin with moored boats and a row of merchant houses. "
                f"It is {o['word'].lower()}, about {o['temp']}\u00b0C, and the quay is empty. "
                "This is the head of the fjord, not an open coast. Lettering on the boats is not treated as real names."
            ),
            "alt_text": "AI-generated artistic interpretation of Aabenraa harbour at night, with merchant houses along a calm fjord",
            "viewpoint": "Public quay at the head of Aabenraa Fjord, looking along the water and the merchant houses. Approximate researched point 55.0442, 9.4186, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Aabenraa",
                "https://en.wikipedia.org/wiki/Aabenraa_Municipality",
            ],
            "anchors": [
                "Calm dark fjord water, not open sea cliffs.",
                "A stone quay and a few moored boats.",
                "A row of older merchant houses along the harbour.",
            ],
            "solar": night + f"Cloud cover {o['cloud']}%. Quay lamps.",
            "independent": "Aabenraa is the harbour town at the head of a long narrow fjord in South Jutland. The old merchant houses face the inner harbour.",
            "ip": "No readable boat names or company marks are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Fjord harbour and merchant houses. Not Gedser Odde and not Svendborg's bridge.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-048",
            "region": "South Jutland",
            "city": "T\u00f8nder",
            "caption": "T\u00f8nder Old Town, T\u00f8nder",
            **p,
            "composition": "Brick stepped gables and one tall church spire \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A street in T\u00f8nder's old town is lined with brick houses and stepped gables, and one tall slender church spire rises over the roofs. "
                f"Streetlamps light the empty cobbles. The sky is {p['word'].lower()}, about {p['temp']}\u00b0C. "
                "This is the town centre, not the lime avenue at M\u00f8gelt\u00f8nder."
            ),
            "alt_text": "AI-generated artistic interpretation of T\u00f8nder old town at night, brick gables and a tall church spire",
            "viewpoint": "A street in the old town, looking toward the spire of Kristkirken above the brick houses. Approximate researched point 54.9336, 8.8664, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/T%C3%B8nder",
                "https://en.wikipedia.org/wiki/T%C3%B8nder_Municipality",
            ],
            "anchors": [
                "Brick townhouses with stepped gables.",
                "One very tall slender church spire.",
                "Empty cobbled street and lamps. Not a village lime avenue.",
            ],
            "solar": night + f"Cloud cover {p['cloud']}%. Streetlamps.",
            "independent": "T\u00f8nder is the old market town on the edge of the marsh. Kristkirken's tall spire is the skyline of the brick old town. M\u00f8gelt\u00f8nder, published separately, is the village street to the west.",
            "ip": "No readable shop names intended. Internal review only, not a legal certification.",
            "visual": "Pass. Brick gables and one tall spire. Distinct from Slotsgade and from Ribe.",
            "swap": None,
        },
    ]


def load_all_scenes() -> list:
    found = []
    for path in sorted((bd.ROOT / "manifests").glob("DK-01-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        found.append({"_manifest": data})
    found.sort(key=lambda item: item["_manifest"]["entry_id"])
    return found


def main() -> None:
    decode_raws()
    stamp, wx = fetch_weather()
    if any(row["is_day"] != 0 for row in wx.values()):
        raise SystemExit(f"expected night, got { {k: v['is_day'] for k, v in wx.items()} }")
    batch = scenes(stamp, wx)
    if len(batch) != 16:
        raise SystemExit(len(batch))
    lines = []
    for scene in batch:
        label = bd.scenario_label(scene["entry_id"])
        bd.write_outputs(scene, label)
        bd.manifest(scene, label)
        bd.approval(scene, label)
        entry = scene["entry_id"].lower()
        city = scene["city"]
        lines.append(
            f"**{scene['entry_id']} \u2014 {scene['caption']}** \u00b7 Scenario: {label} \u00b7 "
            f"Weather: {scene['weather_prefix']} {scene['weather_detail']} \u00b7 "
            f"Masters: `Denmark/{city}/{entry}-16x9.png`, `Denmark/{city}/{entry}-4x5.png` \u00b7 Gates: 5/5 pass."
        )
        print(lines[-1])
    all_scenes = load_all_scenes()
    if len(all_scenes) != 48:
        raise SystemExit(f"expected 48 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 49)]
    if ids != expected:
        raise SystemExit(ids)
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-033-048.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("site written", len(all_scenes))


if __name__ == "__main__":
    main()

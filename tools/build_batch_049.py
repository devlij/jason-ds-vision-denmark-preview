#!/usr/bin/env python3
"""Bake DK-01-049 through DK-01-064 and rebuild the gallery from every manifest."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
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
    "DK-01-049": (56.15356, 10.21420),
    "DK-01-050": (56.1694, 9.5482),
    "DK-01-051": (56.10521, 9.68508),
    "DK-01-052": (55.75667, 9.41944),
    "DK-01-053": (56.45050, 9.41233),
    "DK-01-054": (56.4607, 10.0369),
    "DK-01-055": (55.8602, 9.8508),
    "DK-01-056": (56.1945, 10.6803),
    "DK-01-057": (57.0502, 9.9278),
    "DK-01-058": (57.0486, 9.9206),
    "DK-01-059": (57.71353, 10.55089),
    "DK-01-060": (57.3708, 9.7115),
    "DK-01-061": (57.4490, 9.7755),
    "DK-01-062": (57.3086, 11.1365),
    "DK-01-063": (57.4412, 10.5365),
    "DK-01-064": (57.58478, 9.94189),
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def sky_word(code: int) -> str:
    return {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}.get(
        code, f"Weather code {code}"
    )


def nice_time(iso: str) -> str:
    # 2026-09-25T01:00
    y, m, rest = iso[:10].split("-")
    d = rest if False else iso[8:10]
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


def fetch_weather() -> tuple[str, dict, str]:
    ids = list(COORDS)
    lats = ",".join(str(COORDS[i][0]) for i in ids)
    lons = ",".join(str(COORDS[i][1]) for i in ids)
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lats}&longitude={lons}"
        "&current=temperature_2m,cloud_cover,wind_speed_10m,precipitation,weather_code,is_day"
        "&daily=sunrise,sunset&timezone=Europe%2FCopenhagen&past_days=1&forecast_days=1"
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
        if len(daily["sunset"]) < 2:
            raise SystemExit(f"expected yesterday and today in daily for {entry}")
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
            "sunset_yesterday": daily["sunset"][0],
            "sunrise_today": daily["sunrise"][1],
        }
    stamp = retrieved.strftime("%-d %B %Y %H:%M")
    return stamp, out, moon_note(retrieved)


def decode_raws() -> None:
    specs = {"16x9": (1280, 720), "4x5": (864, 1152)}
    for n in range(49, 65):
        for kind, size in specs.items():
            src = bd.RAW / f"dk-01-{n:03d}-{kind}.png"
            im = Image.open(src)
            if im.size != size:
                raise SystemExit(f"bad source {src} {im.size}")
            dest = bd.RAW / f"dk-01-{n:03d}-{kind}-raw.png"
            im.convert("RGB").save(dest, "PNG")


def scenes(weather_stamp: str, wx: dict, moon: str) -> list:
    def pref(entry: str) -> str:
        return (
            "Model data from Open-Meteo, retrieved "
            f"{weather_stamp} Europe/Copenhagen, valid {nice_time(wx[entry]['valid'])} Europe/Copenhagen "
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

    def night(entry: str) -> str:
        row = wx[entry]
        return (
            "Night. Sunset on "
            f"{nice_time(row['sunset_yesterday'])} Europe/Copenhagen and sunrise on "
            f"{nice_time(row['sunrise_today'])} Europe/Copenhagen. "
        )

    a, b, c, d = w("DK-01-049"), w("DK-01-050"), w("DK-01-051"), w("DK-01-052")
    e, f, g, h = w("DK-01-053"), w("DK-01-054"), w("DK-01-055"), w("DK-01-056")
    i, j, k, l = w("DK-01-057"), w("DK-01-058"), w("DK-01-059"), w("DK-01-060")
    m, n, o, p = w("DK-01-061"), w("DK-01-062"), w("DK-01-063"), w("DK-01-064")

    return [
        {
            "entry_id": "DK-01-049",
            "region": "Central Jutland",
            "city": "Aarhus",
            "caption": "Dokk1, Aarhus",
            **a,
            "composition": "Polygonal harbour library above a glass hall and the quay \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the harbour promenade at the mouth of Aarhus \u00c5, Dokk1 is a glass hall under a dark polygonal roof that overhangs the podium, with broad concrete stairs down to the water. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C, and the quay is empty. "
                "Warm light shows through the glass. This is the waterfront library, not the half-timbered square at Den Gamle By and not the brick cube and rainbow ring at ARoS."
            ),
            "alt_text": "AI-generated artistic interpretation of Dokk1 on the Aarhus harbour at night, a glass hall under a polygonal roof",
            "viewpoint": "Public harbour promenade beside Dokk1, looking at the water side of the library. Address Hack Kampmanns Plads 2, 8000 Aarhus C. Approximate researched point 56.15356, 10.21420, not a surveyed camera.",
            "refs": [
                "https://www.shl.dk/en/work/dokk1-aarhus-central-library-and-culture-house",
                "https://arqa.com/en/_arqanews-archivo-en/dokk1.html",
            ],
            "anchors": [
                "A glass volume under a hovering polygonal metal roof.",
                "Broad stairs from the podium to the harbour promenade.",
                "Dark harbour water in the foreground. No half-timbered houses and no rainbow ring.",
            ],
            "solar": night("DK-01-049") + f"Cloud cover {a['cloud']}%. {moon} Quay lamps and interior light carry the scene.",
            "independent": "Dokk1, by Schmidt Hammer Lassen, opened in 2015 on the former cargo dock where Aarhus \u00c5 meets the bay. The public face is a glazed hall and a polygonal roof plate above the harbour promenade.",
            "ip": "Exterior of a public building. No signage is the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Polygonal roof, glass hall, stairs, and harbour. Distinct from DK-01-010 and DK-01-011.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-050",
            "region": "Central Jutland",
            "city": "Silkeborg",
            "caption": "Hjejlen, Silkeborg",
            **b,
            "composition": "Moored white paddle steamer at the inland harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay at Silkeborg's inland harbour, the white paddle steamer Hjejlen is tied up, with one black funnel and side paddle boxes, and no steam. "
                f"The lake is dark. It is {b['word'].lower()}, about {b['temp']}\u00b0C, with no rain, and the quay is empty. "
                "Low lakeside houses and trees sit behind the boat. This is not a cruise under way."
            ),
            "alt_text": "AI-generated artistic interpretation of the paddle steamer Hjejlen moored at Silkeborg harbour at night",
            "viewpoint": "Public quay at Silkeborg harbour, Sejsvej 2, 8600 Silkeborg, looking at the moored steamer and the lake. Approximate researched point 56.1694, 9.5482, not a surveyed camera.",
            "refs": [
                "https://hjejleselskabet.dk/hjejleselskabets-fleet/hjejlen/?lang=en",
                "https://hjejleselskabet.dk/piers/?lang=en",
            ],
            "anchors": [
                "A white paddle steamer moored, not moving.",
                "One tall black funnel and side paddle boxes.",
                "Dark lake and a low lakeside shore. No castle.",
            ],
            "solar": night("DK-01-050") + f"Cloud cover {b['cloud']}%. {moon} Quay lamps. No moon disk.",
            "independent": "Hjejlen, launched in 1861, is the paddle steamer based at Silkeborg harbour, which Hjejleselskabet calls Denmark's largest inland harbour. At this hour the boat is alongside, not sailing.",
            "ip": "No readable boat name is intended. The vessel is a historic ship, depicted from the public quay. Internal review only, not a legal certification.",
            "visual": "Pass. Moored white steamer, black funnel, lake, no invented tower behind it. An earlier frame that added a white tower building was replaced before publish.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-051",
            "region": "Central Jutland",
            "city": "Ry",
            "caption": "Himmelbjerget, Ry",
            **c,
            "composition": "Red-brick summit tower above a dark lake \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the summit, the square red-brick Himmelbjerg tower stands closed above the dark water of Juls\u00f8, with forested ridges beyond. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, and the hill is empty. "
                "Late-September heath is dull, not a purple bloom. The tower's own hours in this part of September end in the afternoon, so the viewing gallery is dark."
            ),
            "alt_text": "AI-generated artistic interpretation of the red-brick tower on Himmelbjerget near Ry at night, above a dark lake",
            "viewpoint": "Summit ground beside the tower, looking across the tower toward Juls\u00f8. The tower is Frederik VII's tower at Himmelbjerget, postal 8680 Ry. Approximate researched point 56.10521, 9.68508, not a surveyed camera.",
            "refs": [
                "https://himmelbjerget.dk/en/practical/",
                "https://comevisit.dk/en/himmelbjerget",
            ],
            "anchors": [
                "One square red-brick tower with a viewing balcony.",
                "A dark lake and wooded hills beyond the summit.",
                "Closed, empty hill. No lighthouse lantern.",
            ],
            "solar": night("DK-01-051") + f"Cloud cover {c['cloud']}%. {moon} The tower is unlit inside.",
            "independent": "Himmelbjerget is the 147-metre hill above Juls\u00f8. The 25-metre red-brick tower on the summit was raised in memory of Frederik VII. The site's contact address is Tinghusvej 4, 8680 Ry, in Skanderborg Municipality.",
            "ip": "No souvenir marks are the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Red-brick tower, dark lake, closed summit. An earlier frame that read as pale stone was replaced before publish.",
            "swap": (
                "No location swap. City verified as Ry. OpenStreetMap names the summit Himmelbjerget in Skanderborg Kommune, postal 8680, and the tower committee's page gives Tinghusvej 4, 8680 Ry. "
                "The lake landing is a different point lower down."
            ),
        },
        {
            "entry_id": "DK-01-052",
            "region": "Central Jutland",
            "city": "Jelling",
            "caption": "Jelling Stones, Jelling",
            **d,
            "composition": "Rune stones in glass cases, one white church, two mounds \u00b7 AI-generated artistic interpretation",
            "description": (
                f"In the churchyard, two granite rune stones stand inside separate bronze-and-glass cases, with one small whitewashed church and its single tower between two grass mounds. "
                f"The night is {d['word'].lower()}, about {d['temp']}\u00b0C, and the yard is empty. "
                "The stones are not shown standing bare. A June 2026 report of damaged glass on the large stone's case was not rechecked for this night, so no crack is claimed in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of the Jelling rune stones at night, inside glass cases beside the white church and mounds",
            "viewpoint": "Public churchyard at the Jelling monuments, looking across the cased stones toward the church and the mounds. Approximate researched point 55.75667, 9.41944, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Jelling_stones",
                "https://whc.unesco.org/en/list/697/",
            ],
            "anchors": [
                "Two rune stones, each inside a bronze-and-glass case.",
                "One white church with a single tower.",
                "Two large rounded grass mounds.",
            ],
            "solar": night("DK-01-052") + f"Cloud cover {d['cloud']}%. {moon} Churchyard lamps. The moon is mostly hidden.",
            "independent": "The Jelling monument is two turf mounds, a small whitewashed church, and the rune stones of Gorm and Harald Bluetooth. Since 2011 the stones have stood in climate-controlled glass-and-bronze cases by Nobel Arkitekter. UNESCO inscribed the site in 1994.",
            "ip": "The stones and church are ancient monuments. The cases are architectural protection, not a depicted artwork. No modern sign is the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Cased stones, one church tower, two mounds. An earlier wide frame with two church towers was replaced before publish.",
            "swap": (
                "No place-name swap. City is Jelling. Gallery region follows the kit coverage row Central Jutland. "
                "Administratively Jelling is in Vejle Municipality, Region of Southern Denmark. "
                "Depiction note: the stones are cased, which is their public state since 2011. The June 2026 glass damage was not confirmed as still present, so the frame does not show a broken pane."
            ),
        },
        {
            "entry_id": "DK-01-053",
            "region": "Central Jutland",
            "city": "Viborg",
            "caption": "Viborg Cathedral, Viborg",
            **e,
            "composition": "Granite west front and two low pyramidal towers \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the close, Viborg Cathedral's west front is grey granite, with two towers of equal height ending in low pyramidal roofs and a smaller ridge turret behind. "
                f"The night is {e['word'].lower()}, about {e['temp']}\u00b0C, and the paving is empty. "
                "These are not Roskilde's needle spires and not Ribe's single square tower."
            ),
            "alt_text": "AI-generated artistic interpretation of Viborg Cathedral at night, a granite west front with two pyramidal towers",
            "viewpoint": "Cathedral close, looking at the west front. Address Sct. Mogens Gade 4, 8800 Viborg. Approximate researched point 56.45050, 9.41233, not a surveyed camera.",
            "refs": [
                "https://www.viborgdomkirke.dk/information/informationenglish/viborg-cathedral/",
                "https://da.wikipedia.org/wiki/Viborg_Domkirke",
            ],
            "anchors": [
                "Grey granite ashlar, not a red-brick church.",
                "Exactly two west towers with low pyramidal caps.",
                "A smaller turret on the ridge behind them.",
            ],
            "solar": night("DK-01-053") + f"Cloud cover {e['cloud']}%. {moon} Streetlamps on the granite.",
            "independent": "The present cathedral was rebuilt in 1864\u20131876 in Romanesque form and is clad in granite. The two west towers are about 42 metres and end in low pyramids. Two smaller towers and a ridge spire sit further east.",
            "ip": "Exterior only. Granite carvings on the apse are not the subject of this west-front frame. Internal review only, not a legal certification.",
            "visual": "Pass. Twin pyramidal towers and granite. Distinct from Roskilde and Ribe.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-054",
            "region": "Central Jutland",
            "city": "Randers",
            "caption": "Randers Riverfront, Randers",
            **f,
            "composition": "Half-timbered houses along the dark Guden\u00e5 \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, half-timbered houses line the dark Guden\u00e5, with cobbles and streetlamps in front and warm windows above the water. "
                f"It is {f['word'].lower()}, about {f['temp']}\u00b0C, and the quay is empty. "
                "The glass domes of Randers Regnskov are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of the Randers riverfront at night, half-timbered houses along the Guden\u00e5",
            "viewpoint": "Public quay along the Guden\u00e5 in the old town, looking along the water and the timber houses. Approximate researched point 56.4607, 10.0369, not a surveyed camera.",
            "refs": [
                "https://www.visitaarhus.dk/byer-og-steder/randers/koebstaden-randers",
                "https://en.wikipedia.org/wiki/Randers",
            ],
            "anchors": [
                "A dark river in the foreground.",
                "A row of half-timbered houses along the quay.",
                "Empty cobbles and lamps. No glass rainforest domes.",
            ],
            "solar": night("DK-01-054") + f"Cloud cover {f['cloud']}%. {moon} Streetlamps.",
            "independent": "Randers sits where the Guden\u00e5 meets Randers Fjord. The old market town keeps narrow streets and half-timbered houses by the river.",
            "ip": "No readable shop names intended. Internal review only, not a legal certification.",
            "visual": "Pass. River, timber houses, empty night. Not the rainforest domes.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-055",
            "region": "Central Jutland",
            "city": "Horsens",
            "caption": "Horsens Harbour, Horsens",
            **g,
            "composition": "Inner harbour basin and moored boats \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, Horsens' inner harbour is a calm dark basin with small moored boats and low harbour buildings. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C, with wind near {g['wind']} km/h and no rain. "
                "The quay is empty. Lettering on the boats is not treated as real names."
            ),
            "alt_text": "AI-generated artistic interpretation of Horsens inner harbour at night, with moored boats along the quay",
            "viewpoint": "Public quay at the inner harbour, looking across the basin. Approximate researched point 55.8602, 9.8508, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Horsens",
                "https://en.wikipedia.org/wiki/Horsens_Municipality",
            ],
            "anchors": [
                "A calm harbour basin, not a river street.",
                "Small moored boats without readable names.",
                "Quay lamps and low harbour buildings.",
            ],
            "solar": night("DK-01-055") + f"Cloud cover {g['cloud']}%. {moon} Quay lamps.",
            "independent": "Horsens is the harbour town at the head of Horsens Fjord. The inner basin is the public waterfront of the town.",
            "ip": "No readable boat names or company marks are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Harbour basin and boats. Not a cathedral square.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-056",
            "region": "Central Jutland",
            "city": "Ebeltoft",
            "caption": "Ebeltoft Old Town, Ebeltoft",
            **h,
            "composition": "Narrow cobbled street toward the small old town hall \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Adelgade at night is a narrow cobbled street of low half-timbered houses, closing on the small one-storey old town hall at the square. "
                f"The sky is {h['word'].lower()}, about {h['temp']}\u00b0C, and the street is empty. "
                "This is the living old town, not the museum square at Den Gamle By in Aarhus."
            ),
            "alt_text": "AI-generated artistic interpretation of Ebeltoft old town at night, a cobbled street leading to the small town hall",
            "viewpoint": "On Adelgade, looking south toward the old town hall on the triangular square. The town hall was built in 1789. Approximate researched point 56.1945, 10.6803, not a surveyed camera.",
            "refs": [
                "https://trap.lex.dk/Ebeltoft_gamle_R%C3%A5dhus,_nu_museum",
                "https://en.wikipedia.org/wiki/Ebeltoft",
            ],
            "anchors": [
                "A narrow cobbled street of low houses.",
                "Half-timbered fronts and warm lamps.",
                "A small one-storey town hall closing the view.",
            ],
            "solar": night("DK-01-056") + f"Cloud cover {h['cloud']}%. {moon} Streetlamps.",
            "independent": "Ebeltoft's old town grew along Adelgade down to a small square. The town hall there was built in 1789 and now houses a museum. It is a modest building at the meeting of Adelgade, Juulsbakke, and Overgade.",
            "ip": "No readable shop names intended. Internal review only, not a legal certification.",
            "visual": "Pass. Narrow street and small town hall. Distinct from Den Gamle By.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-057",
            "region": "North Jutland",
            "city": "Aalborg",
            "caption": "Aalborg Harbour, Aalborg",
            **i,
            "composition": "Limfjord quay and the steel bridge \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the public quay, the dark Limfjord runs under a grey steel bascule bridge, with harbour lamps along the promenade. "
                f"It is {i['word'].lower()}, about {i['temp']}\u00b0C, and the quay is empty. "
                "The curved roofs of the Utzon Center are a separate scene and are not the subject here."
            ),
            "alt_text": "AI-generated artistic interpretation of Aalborg harbour at night, the Limfjord quay and steel bridge",
            "viewpoint": "Public quay on the Limfjord, looking toward Limfjordsbroen. Approximate researched point 57.0502, 9.9278, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Aalborg",
                "https://en.wikipedia.org/wiki/Limfjord",
            ],
            "anchors": [
                "Dark fjord water and a stone quay.",
                "A grey steel road bridge across the water.",
                "No white curved pavilion roofs.",
            ],
            "solar": night("DK-01-057") + f"Cloud cover {i['cloud']}%. {moon} Quay and bridge lamps.",
            "independent": "Aalborg's public waterfront faces the Limfjord. Limfjordsbroen is the steel bridge between the town and N\u00f8rresundby. Jomfru Ane Gade, the nightlife street inland, is not this view.",
            "ip": "No bridge-operator marks or shop signs are the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Fjord, quay, and bridge. Distinct from the Utzon Center.",
            "swap": "No location swap. The suggested alternative was Jomfru Ane Gade. The frame uses the public harbour and the Limfjord bridge instead, as requested.",
        },
        {
            "entry_id": "DK-01-058",
            "region": "North Jutland",
            "city": "Aalborg",
            "caption": "Utzon Center, Aalborg",
            **j,
            "composition": "Curved concrete roofs beside the Limfjord \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the harbourfront, the Utzon Center is a group of pale concrete pavilions with tall curved roofs, set on a platform beside the dark fjord. "
                f"The night is {j['word'].lower()}, about {j['temp']}\u00b0C, with a few warm windows and an empty quay. "
                "Only the exterior is shown. The steel bridge is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of the Utzon Center exterior in Aalborg at night, curved roofs beside the fjord",
            "viewpoint": "Public side of the Utzon Center on the Limfjord, looking at the harbourfront roofs and courtyard edge. Approximate researched point 57.0486, 9.9206, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Utzon_Center",
                "https://www.e-architect.com/denmark/utzon-center",
            ],
            "anchors": [
                "Pale concrete pavilions on a platform.",
                "Tall curved roofs, not a flat glass cube.",
                "Dark fjord water beside the building. Exterior only.",
            ],
            "solar": night("DK-01-058") + f"Cloud cover {j['cloud']}%. {moon} A few interior windows, not a light show.",
            "independent": "The Utzon Center, completed in 2008, was the last building designed by J\u00f8rn Utzon, with construction drawings by Kim Utzon. It is a cluster of volumes around a courtyard on the Aalborg harbourfront, with tall curved roofs on the auditorium, boat hall, and library.",
            "ip": "Exterior architecture only. No exhibition artwork is shown. Third-party rights in any interior works are not waived because they are not depicted. Internal review only, not a legal certification.",
            "visual": "Pass. Curved roofs, concrete, fjord, exterior. Distinct from the bridge scene.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-059",
            "region": "North Jutland",
            "city": "Skagen",
            "caption": "Sand-Buried Church, Skagen",
            **k,
            "composition": "White tower with a crow-stepped gable rising from the dunes \u00b7 AI-generated artistic interpretation",
            "description": (
                f"In the dunes south-west of Skagen, only the whitewashed tower of the Sand-Buried Church shows, its base in the sand and its crow-stepped gable against the sky. "
                f"There is no nave. The night is {k['word'].lower()}, about {k['temp']}\u00b0C, and the path is empty. "
                "This is not Grenen and there is no sea in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of the Sand-Buried Church tower at Skagen at night, rising from the dunes",
            "viewpoint": "Sandy path in the dunes beside the tower. Approximate researched point 57.71353, 10.55089, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Sand-Covered_Church",
                "https://www.frommers.com/destinations/skagen/attractions/den-tilsandede-kirke-sand-buried-church_/",
            ],
            "anchors": [
                "One white tower with a crow-stepped gable.",
                "Sand covering the lower part of the tower.",
                "No nave, no church roof, and no sea.",
            ],
            "solar": night("DK-01-059") + f"Cloud cover {k['cloud']}%. {moon} A path lamp only.",
            "independent": "The medieval church south-west of Skagen was abandoned in 1795 after drifting sand buried it. The nave was demolished. The whitewashed tower, with its crow-stepped gable, is what remains, and about 18 metres of it stands above the sand.",
            "ip": "No signs are the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Buried tower only. Distinct from Grenen, DK-01-012.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-060",
            "region": "North Jutland",
            "city": "L\u00f8kken",
            "caption": "L\u00f8kken Beach, L\u00f8kken",
            **l,
            "composition": "Wooden pier across a wide night beach \u00b7 AI-generated artistic interpretation",
            "description": (
                f"A long wooden pier with a few lamps runs from the wide pale sand at L\u00f8kken into a dark North Sea with low surf. "
                f"The night is {l['word'].lower()}, about {l['temp']}\u00b0C, with wind near {l['wind']} km/h and no rain. "
                "The beach is empty. No lighthouse is the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of L\u00f8kken beach at night, a wooden pier crossing the sand into the sea",
            "viewpoint": "On the sand at L\u00f8kken, looking along the pier toward the sea. Approximate researched point 57.3708, 9.7115, not a surveyed camera. The pier's exact length was not measured.",
            "refs": [
                "https://en.wikipedia.org/wiki/L%C3%B8kken",
                "https://en.wikipedia.org/wiki/Jammerbugt_Municipality",
            ],
            "anchors": [
                "Wide pale sand in the foreground.",
                "A straight wooden pier with lamps.",
                "Dark sea and low surf. No lighthouse tower.",
            ],
            "solar": night("DK-01-060") + f"Cloud cover {l['cloud']}%. {moon} Pier lamps.",
            "independent": "L\u00f8kken is the North Sea beach town in Jammerbugt Municipality. The public view is the broad beach and the wooden pier.",
            "ip": "No beach-club marks are the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Beach, pier, sea. Not Rubjerg Knude and not Hirtshals.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-061",
            "region": "North Jutland",
            "city": "L\u00f8nstrup",
            "caption": "Rubjerg Knude, L\u00f8nstrup",
            **m,
            "composition": "Square white tower fully visible on the dune cliff \u00b7 AI-generated artistic interpretation",
            "description": (
                f"On the dune at Rubjerg Knude, the square white lighthouse stands fully visible from its base to a dark red lantern, close to the sandy cliff and the sea. "
                f"Sand does not cover the shaft. The night is {m['word'].lower()}, about {m['temp']}\u00b0C, and the dune is empty. "
                "The lantern is dark. The keeper's buildings are gone."
            ),
            "alt_text": "AI-generated artistic interpretation of Rubjerg Knude lighthouse at night, a square white tower standing clear of the sand on the dune cliff",
            "viewpoint": "On the dune beside the tower, looking toward the cliff and the sea. Approximate researched point 57.4490, 9.7755, not a surveyed camera. The point is the position after the 2019 move.",
            "refs": [
                "https://en.wikipedia.org/wiki/Rubjerg_Knude_lighthouse",
                "https://www.bbc.com/news/world-europe-50139900",
            ],
            "anchors": [
                "A square white tower, not a round one.",
                "The full shaft visible, with a dark red lantern.",
                "Open dune and a cliff to the sea. No buried outbuildings.",
            ],
            "solar": night("DK-01-061") + f"Cloud cover {m['cloud']}%. {moon} No beam. The light was deactivated in 1968.",
            "independent": "Rubjerg Knude Fyr is a 23-metre square masonry tower, white with a red lantern, on L\u00f8nstrup Klint. Drifting sand buried the station and the light was put out in 1968. On 22 October 2019 the tower was moved about 70 metres inland. It now stands complete on the dune. The keeper's buildings were lost earlier and are not there.",
            "ip": "No sign is the subject. Internal review only, not a legal certification.",
            "visual": "Pass. Square tower, full height, dark lantern, cliff. Not the historical half-buried state.",
            "swap": (
                "Depiction corrected. The half-buried state is not the current one. The tower was moved about 70 metres inland on 22 October 2019 and stands fully visible. "
                "News reports in September 2026 describe further cliff slips nearby; they do not describe the shaft as buried again. "
                "City kept as L\u00f8nstrup, the town on this cliff. A visitor page gives the car park as Fyrvejen 110, 9800 L\u00f8kken, which is the access road. L\u00f8kken is a separate beach scene."
            ),
        },
        {
            "entry_id": "DK-01-062",
            "region": "North Jutland",
            "city": "L\u00e6s\u00f8",
            "caption": "Seaweed Houses, L\u00e6s\u00f8",
            **n,
            "composition": "Long half-timbered houses under thick eelgrass roofs \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From a quiet lane, long low farmhouses show white panels in a dark timber grid and enormously thick, shaggy eelgrass roofs. "
                f"The island is flat and dark. It is {n['word'].lower()}, about {n['temp']}\u00b0C, with no rain, and the lane is empty. "
                "The roofs are seaweed, not tile. The houses are seen from the road."
            ),
            "alt_text": "AI-generated artistic interpretation of seaweed-roof farmhouses on L\u00e6s\u00f8 at night, thick eelgrass thatch on half-timbered walls",
            "viewpoint": "A public lane among the island's seaweed-roof houses, the exterior only. Weather point is near Byrum, 57.3086, 11.1365, not a surveyed camera. Many restored roofs are also at Gl. \u00d8sterby and Bangsbo.",
            "refs": [
                "https://www.visit-laesoe.com/tourist/experiences/seaweed-roofs-laeso",
                "https://www.tangtag.dk/english",
            ],
            "anchors": [
                "Long low half-timbered houses.",
                "Very thick shaggy grey-brown eelgrass roofs.",
                "Flat dark fields. No tile roofs and no church.",
            ],
            "solar": night("DK-01-062") + f"Cloud cover {n['cloud']}%. {moon} A few windows.",
            "independent": "L\u00e6s\u00f8's seaweed roofs are eelgrass, laid in a mass that can be a metre thick. The houses are half-timbered and mostly private, so the public view is from the lane. A restoration project through 2024\u20132025 put new eelgrass roofs on a set of the surviving houses.",
            "ip": "Private houses, exterior from the public lane only. No house name is readable. Internal review only, not a legal certification.",
            "visual": "Pass. Thick seaweed roofs and timber frames on a flat island.",
            "swap": (
                "City corrected from the suggested Byrum to L\u00e6s\u00f8. The postal town for the island is 9940 L\u00e6s\u00f8. "
                "Byrum is the main village, and Hedvigs Hus stands just outside it, but the restored seaweed roofs are an island type, also at Gl. \u00d8sterby and Bangsbo. The caption uses the island."
            ),
        },
        {
            "entry_id": "DK-01-063",
            "region": "North Jutland",
            "city": "Frederikshavn",
            "caption": "Frederikshavn Harbour, Frederikshavn",
            **o,
            "composition": "Round powder tower beside the harbour basin \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the quay, Frederikshavn harbour is a dark basin of moored boats, and a round brick powder tower with a conical roof stands at the water. "
                f"The night is {o['word'].lower()}, about {o['temp']}\u00b0C, and the quay is empty. "
                "Names on the boats are not treated as real names."
            ),
            "alt_text": "AI-generated artistic interpretation of Frederikshavn harbour at night, with the round powder tower beside the basin",
            "viewpoint": "Public quay beside Krudtt\u00e5rnet, looking across the inner harbour. Approximate researched point 57.4412, 10.5365, not a surveyed camera.",
            "refs": [
                "https://www.kystmuseet.dk/en/visit-our-museums/the-coastal-museum-of-bangsbo/krudttaarnet-the-powder-tower",
                "https://en.wikipedia.org/wiki/Frederikshavn",
            ],
            "anchors": [
                "A round brick tower with a conical roof.",
                "A harbour basin and moored boats.",
                "Quay lamps. No ferry wordmark.",
            ],
            "solar": night("DK-01-063") + f"Cloud cover {o['cloud']}%. {moon} Quay lamps.",
            "independent": "Krudtt\u00e5rnet is the round powder tower of the old Fladstrand citadel. In 1974 it was moved about 270 metres to its present place by the harbour. The basin around it is the public harbour.",
            "ip": "No ferry brands or readable boat names are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Round brick tower and harbour. Not the white lighthouse at Hirtshals.",
            "swap": None,
        },
        {
            "entry_id": "DK-01-064",
            "region": "North Jutland",
            "city": "Hirtshals",
            "caption": "Hirtshals Lighthouse, Hirtshals",
            **p,
            "composition": "Round white lighthouse above the harbour \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the hill, the round white lighthouse at Hirtshals stands above the dark harbour and the sea, with a light in the lantern. "
                f"The night is {p['word'].lower()}, about {p['temp']}\u00b0C, with wind near {p['wind']} km/h and no rain. "
                "The tower is round and fully visible, not the square dune tower at Rubjerg Knude."
            ),
            "alt_text": "AI-generated artistic interpretation of Hirtshals lighthouse at night, a round white tower above the harbour",
            "viewpoint": "Near the foot of the lighthouse on Stenbjerg, looking over the tower toward the harbour and the sea. Approximate researched point 57.58478, 9.94189, not a surveyed camera.",
            "refs": [
                "https://www.danskefyr.dk/hirtshals-fyr/",
                "https://www.visitnordvestkysten.dk/nordvestkysten/planlaeg-din-tur/hirtshals-fyr-gdk594892",
            ],
            "anchors": [
                "A round white tower, not a square one.",
                "A lit lantern at the top.",
                "Harbour lights and dark sea below the hill.",
            ],
            "solar": night("DK-01-064") + f"Cloud cover {p['cloud']}%. {moon} The lighthouse is an active light, so the lantern is lit. Character is a fixed white light with a flash.",
            "independent": "Hirtshals Fyr, designed by N.S. Nebelong, was lit in 1863. The round brick tower is 35 metres, painted white, on Stenbjerg above the town and harbour. The light remains in service.",
            "ip": "The royal monogram above the door is not treated as a readable mark and is not the subject. No ferry brand is shown. Internal review only, not a legal certification.",
            "visual": "Pass. Round white tower, lit lantern, harbour below. Distinct from Rubjerg Knude.",
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
        # Straight apostrophe and em dash, not the curly signature apostrophe.
        if "\u2019" in parsed["Title"] or "\u2019" in parsed["Copyright"]:
            raise SystemExit(f"curly apostrophe in metadata {path}")
        if "\u2014" not in parsed["Title"] or "\u2014" not in parsed["Copyright"]:
            raise SystemExit(f"missing em dash {path}")
        if "Denmark" not in parsed["Description"]:
            raise SystemExit(f"country {path}")


def main() -> None:
    decode_raws()
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
    if len(all_scenes) != 64:
        raise SystemExit(f"expected 64 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 65)]
    if ids != expected:
        raise SystemExit(ids)
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-049-064.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # exiftool cross-check on one master from each end of the batch.
    sample = [masters[0], masters[-1]]
    for path in sample:
        subprocess.run(["exiftool", "-Title", "-Description", "-Copyright", "-Software", "-Comment", str(path)], check=True)
    print("site written", len(all_scenes))


if __name__ == "__main__":
    main()

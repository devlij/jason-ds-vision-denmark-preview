#!/usr/bin/env python3
"""Bake DK-01-225 through DK-01-240 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-225-240.json.
This script does not issue a new shared forecast and does not copy one
scene's weather block onto another.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-225-240.json").read_text(encoding="utf-8"))

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def sky_word(code: int) -> str:
    return {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}[code]


def nice_time(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[iso[5:7]]} {iso[0:4]} {iso[11:16]}"


def stamp_words(raw: str) -> str:
    # 2026-09-25T06:10:15+02:00
    return f"{int(raw[8:10])} {MONTHS[raw[5:7]]} {raw[0:4]} {raw[11:19]}"


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


def pack(entry: str) -> dict:
    row = WX[entry]
    when = datetime.fromisoformat(row["retrieved"])
    local_valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=timezone(timedelta(seconds=7200)))
    alt = sun_alt(row["lat"], row["lon"], local_valid.astimezone(timezone.utc))
    word = sky_word(int(row["code"]))
    temp = float(row["temp"])
    wind = float(row["wind"])
    precip = float(row["precip"])
    if precip != 0:
        raise SystemExit(f"{entry} precip {precip}")
    if int(row["is_day"]) != 0:
        raise SystemExit(f"{entry} is_day")
    if not str(row["valid"]).startswith("2026-09-25T06:"):
        raise SystemExit(f"{entry} valid hour {row['valid']}")
    if not str(row["retrieved"]).startswith("2026-09-25T06:"):
        raise SystemExit(f"{entry} retrieval hour {row['retrieved']}")
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": f"{word}, {temp:.1f}\u00b0C, cloud cover {row['cloud']}%, wind {wind:.1f} km/h, no precipitation.",
        "temp": f"{temp:.1f}",
        "cloud": int(row["cloud"]),
        "wind": f"{wind:.1f}",
        "code": int(row["code"]),
        "valid": row["valid"],
        "sunset": row["sunset"],
        "sunrise": row["sunrise"],
        "sun_alt": alt,
        "retrieved_stamp": stamp_words(row["retrieved"]),
        "moon": moon_note(when),
        "prefix": (
            "Model data from Open-Meteo, retrieved "
            f"{stamp_words(row['retrieved'])} Europe/Copenhagen, valid "
            f"{nice_time(row['valid'])} Europe/Copenhagen "
            "\u2014 not a verified on-site observation. "
            f"Separate request for {row['lat']:.5f}, {row['lon']:.5f}. "
            "The model-valid hour is 06:00\u201306:59 Europe/Copenhagen."
        ),
    }


def light(row: dict) -> str:
    if row["cloud"] >= 80:
        return "The cloud deck hides the moon, and a few lamps carry the light."
    if row["cloud"] >= 45:
        return "Broken cloud hides much of the moon."
    return "Moonlight reaches the ground under a thin cloud cover."


def clock(row: dict) -> str:
    text = (
        "Night. Sunset on "
        f"{nice_time(row['sunset'])} Europe/Copenhagen and sunrise on "
        f"{nice_time(row['sunrise'])} Europe/Copenhagen. "
    )
    text += twilight_phrase(row["sun_alt"]) + " "
    text += f"Cloud cover {row['cloud']}%. "
    text += "The cloud deck hides the moon. " if row["cloud"] >= 80 else row["moon"] + " "
    text += "The scenario minute has to fall inside this scene's own model-valid hour, 06:00\u201306:59 Europe/Copenhagen."
    return text


def prepare_raws() -> None:
    for n in range(225, 241):
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

    a = base("DK-01-225")
    b = base("DK-01-226")
    c = base("DK-01-227")
    d = base("DK-01-228")
    e = base("DK-01-229")
    f = base("DK-01-230")
    g = base("DK-01-231")
    h = base("DK-01-232")
    i = base("DK-01-233")
    j = base("DK-01-234")
    k = base("DK-01-235")
    m = base("DK-01-236")
    n = base("DK-01-237")
    o = base("DK-01-238")
    p = base("DK-01-239")
    q = base("DK-01-240")

    return [
        {
            "entry_id": "DK-01-225",
            "region": "North Jutland",
            "city": "Aalborg",
            "caption": "Aalborghus, Aalborg",
            **a,
            "composition": "Red-timber east wing and the moat \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the public side of the moat, Aalborghus shows the east wing's red timber framing, white panels, and a red tile roof, with grass ramparts behind dark water. "
                f"The grounds are empty. The night is {a['word'].lower()}, about {a['temp']}\u00b0C. "
                f"{light(a)} The steel Limfjord bridge and the Utzon roofs are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Aalborghus at night, a half-timbered wing across the moat",
            "viewpoint": "The public grounds beside the moat at Aalborghus, Slotspladsen side of the harbour front. Approximate researched point 57.04942, 9.92476, not a surveyed camera. Nominatim places Aalborghus in Aalborg, postal 9000. The published visiting hours for the courtyard are 08:00\u201321:00, so this frame is the exterior before opening.",
            "refs": [
                "https://slks.dk/omraader/slotte-og-ejendomme/slotte-og-haver/aalborghus-slot-og-anlaeg",
                "https://trap.lex.dk/Aalborghus",
            ],
            "anchors": [
                "A low range with red timber framing and white panels.",
                "A red tile roof and grass ramparts.",
                "Dark moat water in the foreground. No bridge.",
            ],
            "solar": clock(a["_row"]) + " A few path lamps and warm windows. No facade floodlight show.",
            "independent": (
                "The Agency for Palaces and Culture says Aalborghus is the half-timbered castle by the harbour front in central Aalborg, with thick outer walls and Aalborg half-timbering toward the courtyard. Only the east wing is largely the original range. The north wing toward the harbour is from the 1630s. "
                "Trap Danmark describes the Renaissance complex behind ramparts near the water. "
                "Aalborg Harbour, including the steel bridge, is already DK-01-057. The Utzon Center is DK-01-058. Budolfi is DK-01-129."
            ),
            "ip": "No readable sign and no agency wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Half-timber wing, moat, ramparts, overcast night. No bridge and no curved concrete roofs.",
            "swap": (
                "The suggested Aalborg waterfront and Limfjord quay is already DK-01-057, Aalborg Harbour, Aalborg, and that frame includes the steel bridge. "
                "The Utzon Center is DK-01-058 and Budolfi is DK-01-129. The caption is Aalborghus. City remains Aalborg."
            ),
        },
        {
            "entry_id": "DK-01-226",
            "region": "North Jutland",
            "city": "N\u00f8rresundby",
            "caption": "Limfjord Bridge, N\u00f8rresundby",
            **b,
            "composition": "Closed steel bascule bridge from the north bank \u00b7 AI-generated artistic interpretation",
            "description": (
                "From the N\u00f8rresundby promenade, Limfjordsbroen runs south as a low grey plate-girder bridge, the bascule leaves closed and flat, with dark water underneath and ordinary town lights on the far bank. "
                f"The promenade is empty. The night is {b['word'].lower()}, about {b['temp']}\u00b0C. "
                f"{light(b)} There is no arch and no suspension cable."
            ),
            "alt_text": "AI-generated artistic interpretation of the Limfjord bridge at night from the N\u00f8rresundby shore",
            "viewpoint": "The public north-bank promenade at Stigsborg, looking south across the closed road bridge. Approximate researched point 57.05780, 9.92050, not a surveyed camera. A nearby reverse geocode on Torvegade returns postal 9400, the N\u00f8rresundby postcode, in the Stigsborg district. OSM also prints the city name Aalborg because the municipality is Aalborg.",
            "refs": [
                "https://www.aalborg.dk/mit-liv/trafik-og-parkering/trafik-og-veje/faerger-og-broer/limfjordsbroen/",
                "https://en.wikipedia.org/wiki/Limfjordsbroen",
            ],
            "anchors": [
                "A low grey steel girder bridge, leaves closed, deck flat.",
                "Dark water and an empty paved foreground.",
                "Far-bank town lights. No arch, no cables, no lattice truss.",
            ],
            "solar": clock(b["_row"]) + " A line of roadway lights. The bridge is shown closed.",
            "independent": (
                "Aalborg Municipality says Limfjordsbroen is a fixed bridge with a moving section between Aalborg and N\u00f8rresundby. The navigation opening is 30 m, and there are fixed spans on both sides of the bascule. "
                "Structurae and the English article describe a steel double-leaf bascule opened in 1933, not a suspension bridge and not an arch. "
                "The Aalborg-quay view of this same bridge is already DK-01-057, so this frame is the north shore and leaves the Utzon roofs out."
            ),
            "ip": "No readable road sign and no vehicle badge. Internal review only, not a legal certification.",
            "visual": "Pass. Low closed girder bridge from the north bank, overcast night. Not an arch and not a cable-stayed bridge.",
            "swap": (
                "No site swap. The bridge from the Aalborg quay is already inside DK-01-057, Aalborg Harbour, Aalborg. "
                "This caption is Limfjord Bridge and the city is N\u00f8rresundby, the north bank. Lindholm H\u00f8je, on the hill above this shore, remains DK-01-130 and is not in the frame."
            ),
        },
        {
            "entry_id": "DK-01-227",
            "region": "North Jutland",
            "city": "Skagen",
            "caption": "Skagen Harbour, Skagen",
            **c,
            "composition": "Fishing boats and low warehouses in the basin \u00b7 AI-generated artistic interpretation",
            "description": (
                "Skagen harbour at night is a fishing basin with ordinary boats, low warehouses, and quay lamps on dark water. "
                f"The quay is empty. The night is {c['word'].lower()}, about {c['temp']}\u00b0C. "
                f"{light(c)} The sand spit, the buried church, and the yellow old-town lane are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Skagen harbour at night, fishing boats in a dark basin",
            "viewpoint": "The public quay at Skagen Havn. Approximate researched point 57.71688, 10.59469, not a surveyed camera. Nominatim places the harbour in Skagen, postal 9990.",
            "refs": [
                "https://en.wikipedia.org/wiki/Skagen",
                "https://da.wikipedia.org/wiki/Skagen_Havn",
            ],
            "anchors": [
                "A working basin with fishing boats.",
                "Low warehouses and quay lamps.",
                "Dark water. No sand spit and no yellow cottage street.",
            ],
            "solar": clock(c["_row"]) + " Harbour lamps. No readable boat name.",
            "independent": (
                "Skagen's harbour is the fishing port south of the town, distinct from Grenen, where the seas meet, and from the old town of yellow houses. "
                "Grenen is DK-01-012. The Sand-Buried Church is DK-01-059. Skagen Old Town is DK-01-132."
            ),
            "ip": "No readable boat name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Fishing basin, warehouses, lamps, overcast night. Not Grenen.",
            "swap": "No site swap. The harbour is distinct from Grenen, the Sand-Buried Church, and Skagen Old Town. City remains Skagen.",
        },
        {
            "entry_id": "DK-01-228",
            "region": "North Jutland",
            "city": "Frederikshavn",
            "caption": "Krudtt\u00e5rnet, Frederikshavn",
            **d,
            "composition": "A solitary round brick gun tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Krudtt\u00e5rnet is a solitary round red-brick tower on a grass plot, with a dark roof and a few small openings. "
                f"The plot is empty. The night is {d['word'].lower()}, about {d['temp']}\u00b0C, and the wind is fresh. "
                f"{light(d)} The old citadel walls are gone, and no shipyard mark is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Krudtt\u00e5rnet in Frederikshavn at night, a round brick tower",
            "viewpoint": "The public grass plot around Krudtt\u00e5rnet at Kragholmen. Approximate researched point 57.43982, 10.54086, not a surveyed camera. Nominatim places the tower in Frederikshavn, postal 9900.",
            "refs": [
                "https://en.wikipedia.org/wiki/Krudtt%C3%A5rnet",
                "https://da.wikipedia.org/wiki/Krudtt%C3%A5rnet",
            ],
            "anchors": [
                "One round red-brick tower, standing alone.",
                "A dark simple roof and small openings.",
                "Grass. No star fort and no shipyard logo.",
            ],
            "solar": clock(d["_row"]) + " A couple of lamps. No readable plaque.",
            "independent": (
                "The English article describes Krudtt\u00e5rnet as the surviving part of the Fladstrand citadel, built in 1687 as a round gun tower. In 1974 it was moved about 270 m to make room for the shipyard and reopened in 1976. "
                "The frame shows the tower where it stands now, alone, not inside a reconstructed citadel. Frederikshavn Harbour is already DK-01-063."
            ),
            "ip": "No shipyard wordmark and no readable plaque. Internal review only, not a legal certification.",
            "visual": "Pass. Solitary round brick tower, overcast night. No citadel walls and no logo.",
            "swap": (
                "Swapped from Frederikshavn Harbour. That port is already DK-01-063, Frederikshavn Harbour, Frederikshavn. "
                "The caption is Krudtt\u00e5rnet. City remains Frederikshavn."
            ),
        },
        {
            "entry_id": "DK-01-229",
            "region": "North Jutland",
            "city": "S\u00e6by",
            "caption": "S\u00e6by Church, S\u00e6by",
            **e,
            "composition": "A long white church and one west tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "S\u00e6by Church is a long whitewashed building with a dark lead roof, buttresses, and one square west tower, standing in an empty churchyard. "
                f"The night is {e['word'].lower()}, about {e['temp']}\u00b0C. "
                f"{light(e)} The demolished cloister and the harbour are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of S\u00e6by Church at night, a long white church with one tower",
            "viewpoint": "The public churchyard at Sankt Mari\u00e6 Kirke, Strandgade 5A. Approximate researched point 57.33320, 10.52870, not a surveyed camera. Nominatim places the church in S\u00e6by, postal 9300. This is the Vendsyssel church, not S\u00e6by Church in Lejre.",
            "refs": [
                "https://da.wikipedia.org/wiki/S%C3%A6by_Kirke_(Frederikshavn_Kommune)",
                "https://lex.dk/S%C3%A6by_Kirke",
            ],
            "anchors": [
                "A long whitewashed church with a dark lead roof.",
                "Buttresses and one square west tower.",
                "An empty churchyard. No cloister and no harbour.",
            ],
            "solar": clock(e["_row"]) + " Two churchyard lamps. No shop name.",
            "independent": (
                "The Danish article places S\u00e6by Kirke at Strandgade 5A, 9300 S\u00e6by, and describes a long church with a west tower, formerly the south wing of the Carmelite house Mariested. The cloister ranges were demolished. Lex describes the whitewash, the lead roof, and the simple exterior broken by buttresses. "
                "S\u00e6by Harbour is already DK-01-134. The parish site's phrase about it being the finest town church in Vendsyssel is a local claim and is not repeated as a measured ranking."
            ),
            "ip": "No readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Long white church, one west tower, lead roof, empty churchyard, overcast night. No harbour.",
            "swap": (
                "Swapped from S\u00e6by Harbour. That waterfront is already DK-01-134, S\u00e6by Harbour, S\u00e6by. "
                "The caption is S\u00e6by Church. City remains S\u00e6by."
            ),
        },
        {
            "entry_id": "DK-01-230",
            "region": "North Jutland",
            "city": "Hirtshals",
            "caption": "Hirtshals Harbour, Hirtshals",
            **f,
            "composition": "A concrete mole and a choppy basin \u00b7 AI-generated artistic interpretation",
            "description": (
                "Hirtshals harbour is a concrete mole and basin with a few fishing boats, quay lamps, and dark choppy water. "
                f"The quay is empty. The night is {f['word'].lower()}, about {f['temp']}\u00b0C, with a fresh wind. "
                f"{light(f)} The cliff lighthouse is a different scene and is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Hirtshals harbour at night, a mole and fishing boats",
            "viewpoint": "The public quay at Hirtshals Havn, near Vestmolen. Approximate researched point 57.59506, 9.95930, not a surveyed camera. Nominatim places the harbour in Hirtshals, postal 9850.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hirtshals",
                "https://www.portofhirtshals.dk/",
            ],
            "anchors": [
                "A concrete mole and a harbour basin.",
                "Fishing boats and quay lamps.",
                "Choppy dark water. No cliff lighthouse as the subject.",
            ],
            "solar": clock(f["_row"]) + " Quay lamps. No readable ferry name.",
            "independent": (
                "Hirtshals is the ferry and fishing port on the North Sea. The white lighthouse stands on the cliff south of the harbour and is already DK-01-064, Hirtshals Lighthouse, Hirtshals. This frame stays on the mole and leaves that tower out."
            ),
            "ip": "No readable ferry name and no oceanarium mark. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, boats, choppy water, overcast night. The cliff lighthouse is not the subject.",
            "swap": (
                "Swapped from Hirtshals Lighthouse. That white tower is already DK-01-064, Hirtshals Lighthouse, Hirtshals. "
                "The caption is Hirtshals Harbour. City remains Hirtshals."
            ),
        },
        {
            "entry_id": "DK-01-231",
            "region": "North Jutland",
            "city": "B\u00f8rglum",
            "caption": "B\u00f8rglum Abbey, B\u00f8rglum",
            **g,
            "composition": "A white baroque abbey on an open hill \u00b7 AI-generated artistic interpretation",
            "description": (
                "B\u00f8rglum Abbey is a whitewashed two-storey baroque complex on an open hill, with hipped roofs of red and black tile and a triangular pediment over the south gateway. "
                f"The lawn is empty. The night is {g['word'].lower()}, about {g['temp']}\u00b0C, and the wind is fresh. "
                f"{light(g)} No windmill is the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of B\u00f8rglum Abbey at night, a white baroque complex on a hill",
            "viewpoint": "The public approach to B\u00f8rglum Kloster, B\u00f8rglum Klostervej 255A. Approximate researched point 57.36901, 9.79893, not a surveyed camera. Nominatim gives postal 9760. The road name is B\u00f8rglum. OSM's town field says Hj\u00f8rring, which is the municipality centre, not this hill.",
            "refs": [
                "https://www.boerglumkloster.dk/en/discover-history/buildings",
                "https://trap.lex.dk/B%C3%B8rglumkloster",
            ],
            "anchors": [
                "Whitewashed two-storey ranges.",
                "Hipped roofs in red and black tile.",
                "A triangular pediment over a gateway. No stepped gables.",
            ],
            "solar": clock(g["_row"]) + " A few warm windows. No hotel wordmark.",
            "independent": (
                "The abbey's own building page says Laurids de Thurah, in 1750\u201355, removed the stepped gables and gave the complex the baroque exterior it has now, including the port through the south wing. "
                "Trap Danmark places it on a moraine hill and describes the whitewashed baroque roofs that date from that rebuilding. The east wing is gone. "
                "L\u00f8kken Beach is already DK-01-060. Postal 9760 is the Vr\u00e5 post town. The place of the abbey is B\u00f8rglum."
            ),
            "ip": "No hotel wordmark and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. White baroque ranges, hipped roofs, pediment, empty hill, overcast night. No windmill as the subject.",
            "swap": (
                "Swapped from L\u00f8kken Beach. That shore is already DK-01-060, L\u00f8kken Beach, L\u00f8kken. "
                "The caption is B\u00f8rglum Abbey. City is B\u00f8rglum. The postal town on the address is Vr\u00e5, 9760."
            ),
        },
        {
            "entry_id": "DK-01-232",
            "region": "North Jutland",
            "city": "Blokhus",
            "caption": "Blokhus Beach, Blokhus",
            **h,
            "composition": "A wide dune beach and a choppy North Sea \u00b7 AI-generated artistic interpretation",
            "description": (
                "Blokhus beach is a wide empty strand, marram dunes, and a dark choppy North Sea. "
                f"The night is {h['word'].lower()}, about {h['temp']}\u00b0C, with a fresh wind. "
                f"{light(h)} There is no pier and no summer crowd."
            ),
            "alt_text": "AI-generated artistic interpretation of Blokhus beach at night, empty sand and dunes",
            "viewpoint": "The public sand at Blokhus Strand, looking along the North Sea. Approximate researched point 57.24929, 9.57189, not a surveyed camera. Nominatim places the beach in Blokhus, Jammerbugt Municipality.",
            "refs": [
                "https://en.wikipedia.org/wiki/Blokhus",
                "https://lex.dk/Blokhus",
            ],
            "anchors": [
                "A wide sandy beach.",
                "Low dunes with marram grass.",
                "Dark choppy water. No pier and no umbrellas.",
            ],
            "solar": clock(h["_row"]) + " No beach-club lighting. Late September, so the shore is empty.",
            "independent": (
                "Blokhus is the holiday town and beach on the North Sea in Jammerbugt. This is the open strand, not L\u00f8kken's beach, which is already DK-01-060. "
                "Late September night is outside the summer season, so the sand is empty and no beach kiosk is open."
            ),
            "ip": "No kiosk logo and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Wide beach, dunes, choppy sea, broken cloud, empty sand. No pier.",
            "swap": "No site swap. Blokhus Beach was not used in DK-01-001 through DK-01-224. City is Blokhus.",
        },
        {
            "entry_id": "DK-01-233",
            "region": "North Jutland",
            "city": "L\u00f8nstrup",
            "caption": "L\u00f8nstrup Beach, L\u00f8nstrup",
            **i,
            "composition": "Boats on the sand under a steep cliff \u00b7 AI-generated artistic interpretation",
            "description": (
                "L\u00f8nstrup beach at night is sand under a steep grass and clay cliff, with a few houses along the top and two small boats hauled up. "
                f"The beach is empty. The night is {i['word'].lower()}, about {i['temp']}\u00b0C, with a fresh wind. "
                f"{light(i)} Rubjerg Knude and the removed M\u00e5rup church are not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of L\u00f8nstrup beach at night, boats under a cliff",
            "viewpoint": "The public sand at L\u00f8nstrup Strand, S\u00f8ndre Strandvej. Approximate researched point 57.47568, 9.79539, not a surveyed camera. Nominatim places the beach in L\u00f8nstrup.",
            "refs": [
                "https://en.wikipedia.org/wiki/L%C3%B8nstrup",
                "https://en.wikipedia.org/wiki/M%C3%A5rup_Church",
            ],
            "anchors": [
                "A steep grass and clay cliff with a few houses on top.",
                "Two small boats hauled onto the sand.",
                "Dark choppy water. No lighthouse and no standing church.",
            ],
            "solar": clock(i["_row"]) + " A little light from the houses above. No swimmers.",
            "independent": (
                "L\u00f8nstrup is the cliff village and landing place on the North Sea. Fishing boats are drawn up on the sand below the houses. "
                "M\u00e5rup Church, on the cliff to the south, was dismantled by 2015. Naturstyrelsen says the church is gone and the churchyard remains. A 2024 local report said the Crescent anchor was to be taken down for restoration and later set at L\u00f8nstrup churchyard, so neither a standing ruin nor the anchor is shown. "
                "Rubjerg Knude lighthouse, half-buried in the dune, is already DK-01-061."
            ),
            "ip": "No readable boat name. Internal review only, not a legal certification.",
            "visual": "Pass. Cliff, houses, boats on the sand, broken cloud. No lighthouse and no standing church ruin.",
            "swap": (
                "Swapped from M\u00e5rup Church ruin. The church was taken down by 2015, so a standing ruin would be false, and the anchor's 2024 move was not treated as still on the cliff. "
                "The caption is L\u00f8nstrup Beach. City remains L\u00f8nstrup. Rubjerg Knude stays DK-01-061."
            ),
        },
        {
            "entry_id": "DK-01-234",
            "region": "North Jutland",
            "city": "Vestervig",
            "caption": "Vestervig Church, Vestervig",
            **j,
            "composition": "A granite basilica and a white saddle-roof tower \u00b7 AI-generated artistic interpretation",
            "description": (
                "Vestervig Church shows a long nave of bare grey granite, a rounded apse, lead roofs, and a whitewashed west tower under a saddle roof. "
                f"The churchyard is empty. The night is {j['word'].lower()}, about {j['temp']}\u00b0C. "
                f"{light(j)} The lost monastery ranges are not shown."
            ),
            "alt_text": "AI-generated artistic interpretation of Vestervig Church at night, grey granite and a white tower",
            "viewpoint": "The public churchyard at Vestervig Kirke, Klostergade. Approximate researched point 56.77316, 8.31728, not a surveyed camera. Nominatim places the church in Vestervig, postal 7770.",
            "refs": [
                "https://lex.dk/Vestervig_Kirke",
                "https://da.wikipedia.org/wiki/Vestervig_Kirke",
            ],
            "anchors": [
                "Bare grey granite on the nave and apse, not whitewash.",
                "A whitewashed west tower with a saddle roof, no spire.",
                "Lead-grey roofs. No monastery ranges.",
            ],
            "solar": clock(j["_row"]) + " Two path lamps. No readable gravestone treated as a sign.",
            "independent": (
                "Lex describes a granite basilica whose nave stands in bare masonry, while the west tower is whitewashed, with lead roofs. The spire blew down in 1588 and was replaced by the present saddle roof. The apse and choir were rebuilt in 1917\u201321 on the old foundations. "
                "The Danish Wikipedia calls it Denmark's largest village church because of the lost monastery; that phrase is a source claim, not a new measurement, and it is not painted on the image. "
                "Thisted Harbour is already DK-01-135. Vestervig is in Thisted Municipality, Region Nordjylland, so the gallery region is North Jutland."
            ),
            "ip": "No readable inscription treated as a sign. Internal review only, not a legal certification.",
            "visual": "Pass. Grey granite nave, white saddle-roof tower, empty churchyard, broken cloud. No monastery.",
            "swap": (
                "Swapped from Thisted Harbour. That basin is already DK-01-135, Thisted Harbour, Thisted. "
                "The caption is Vestervig Church. City is Vestervig."
            ),
        },
        {
            "entry_id": "DK-01-235",
            "region": "North Jutland",
            "city": "Nyk\u00f8bing Mors",
            "caption": "Dueholm, Nyk\u00f8bing Mors",
            **k,
            "composition": "A whitewashed monastery wing and a red tile roof \u00b7 AI-generated artistic interpretation",
            "description": (
                "Dueholm is a long whitewashed monastery wing with a half-hipped red tile roof, pointed blind arches, and a short stone stair to a plain door. "
                f"The courtyard is empty. The night is {k['word'].lower()}, about {k['temp']}\u00b0C, with a light wind. "
                f"{light(k)} The harbour is not in this frame, and no museum banner is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Dueholm in Nyk\u00f8bing Mors at night, a white monastery wing",
            "viewpoint": "The courtyard side of Dueholm Kloster, Dueholmgade 9. Approximate researched point 56.79459, 8.85285, not a surveyed camera. Nominatim places the monastery in Nyk\u00f8bing Mors, postal 7900.",
            "refs": [
                "https://museummors.dk/en/museums-and-archive/dueholm-monastery/",
                "https://kulturarv.dk/fbb/sagvis.pub?sag=19725715",
            ],
            "anchors": [
                "A long whitewashed wing, one storey over a high cellar.",
                "A half-hipped red tile roof.",
                "Pointed blind arches and a short stone stair. No harbour.",
            ],
            "solar": clock(k["_row"]) + " A few lamps. The museum is closed at this hour.",
            "independent": (
                "Museum Mors gives the address Dueholmgade 9, 7900 Nyk\u00f8bing Mors, and describes the protected main building of the former Knights Hospitaller house. "
                "The heritage listing says the north wing is whitewashed masonry, one storey over a high cellar, with a half-hipped red tile roof and pointed blind arches on the courtyard side. "
                "Nyk\u00f8bing Mors Harbour is already DK-01-136."
            ),
            "ip": "No museum banner and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. White wing, red tile roof, pointed arches, moonlit courtyard. No harbour.",
            "swap": (
                "Swapped from Nyk\u00f8bing Mors Harbour. That basin is already DK-01-136, Nyk\u00f8bing Mors Harbour, Nyk\u00f8bing Mors. "
                "The caption is Dueholm. City remains Nyk\u00f8bing Mors."
            ),
        },
        {
            "entry_id": "DK-01-236",
            "region": "Central Jutland",
            "city": "Fur",
            "caption": "Sten\u00f8re Quay, Fur",
            **m,
            "composition": "A short ferry ramp and a small car ferry \u00b7 AI-generated artistic interpretation",
            "description": (
                "The Sten\u00f8re quay on Fur is a short concrete ramp with a small plain car ferry and calm dark water. "
                f"The quay is empty. The night is {m['word'].lower()}, about {m['temp']}\u00b0C. "
                f"{light(m)} There is no large port and no readable name on the ferry."
            ),
            "alt_text": "AI-generated artistic interpretation of the Sten\u00f8re ferry quay on Fur at night",
            "viewpoint": "The public ferry ramp at Sten\u00f8re on the south side of Fur. Approximate researched point 56.80454, 9.02068, not a surveyed camera. Nominatim's village field is Nederby, the quarter is Sten\u00f8re, and the postcode is 7884. Destination Limfjorden addresses the ferry as Sten\u00f8re, 7884 Fur.",
            "refs": [
                "https://www.destinationlimfjorden.com/fjord-holiday/the-guide/ferry-fur-branden-gdk602207",
                "https://en.wikipedia.org/wiki/Fur_(island)",
            ],
            "anchors": [
                "A short concrete ferry ramp.",
                "A small plain car ferry with no readable name.",
                "Calm dark Limfjord water. No cranes.",
            ],
            "solar": clock(m["_row"]) + " Two quay lamps. No kiosk lettering.",
            "independent": (
                "Destination Limfjorden says the ferry between Fur and Branden takes a few minutes and gives the Fur side as Sten\u00f8re, 7884 Fur. The English island article says Nederby is the largest village and that the ferry sails from Branden. "
                "The quay itself is Sten\u00f8re. City is recorded as Fur, the post town printed on the ferry address. Nederby is the inland village in the OSM address, not a second town invented for the caption."
            ),
            "ip": "No ferry name and no kiosk logo. Internal review only, not a legal certification.",
            "visual": "Pass. Short ramp, plain ferry, calm water, moonlight. No readable name.",
            "swap": (
                "No subject swap. City is Fur, the post town on the Sten\u00f8re address, rather than Nederby, which is the OSM village for the same point. "
                "The caption is Sten\u00f8re Quay."
            ),
        },
        {
            "entry_id": "DK-01-237",
            "region": "Central Jutland",
            "city": "Struer",
            "caption": "Struer Harbour, Struer",
            **n,
            "composition": "A modest Limfjord basin and low sheds \u00b7 AI-generated artistic interpretation",
            "description": (
                "Struer harbour is a modest Limfjord basin, small boats, a plain quay, and low brick sheds. "
                f"The quay is empty. The night is {n['word'].lower()}, about {n['temp']}\u00b0C, and the water is calm. "
                f"{light(n)} No crane and no readable boat name."
            ),
            "alt_text": "AI-generated artistic interpretation of Struer harbour at night, small boats on the Limfjord",
            "viewpoint": "The public quay at Struer Havn. Approximate researched point 56.49451, 8.59158, not a surveyed camera. Nominatim places the harbour in Struer, postal 7600.",
            "refs": [
                "https://en.wikipedia.org/wiki/Struer,_Denmark",
                "https://da.wikipedia.org/wiki/Struer",
            ],
            "anchors": [
                "A small harbour basin on calm water.",
                "Ordinary boats and a plain quay.",
                "Low brick sheds. No container cranes.",
            ],
            "solar": clock(n["_row"]) + " A few quay lamps. No readable name.",
            "independent": (
                "Struer is the Limfjord town west of the sound, and its harbour is a modest basin rather than a container port. "
                "The scene was not used in DK-01-001 through DK-01-224. The municipality is in Region Midtjylland, so the gallery region is Central Jutland."
            ),
            "ip": "No readable boat name and no company mark. Internal review only, not a legal certification.",
            "visual": "Pass. Small basin, brick sheds, calm moonlit water. No cranes.",
            "swap": "No site swap. Struer Harbour was not used in DK-01-001 through DK-01-224. City is Struer.",
        },
        {
            "entry_id": "DK-01-238",
            "region": "Central Jutland",
            "city": "Holstebro",
            "caption": "Stor\u00e5en, Holstebro",
            **o,
            "composition": "The town river under a low bridge \u00b7 AI-generated artistic interpretation",
            "description": (
                "Stor\u00e5en in Holstebro is a dark smooth river under one low bridge, with brick buildings set back and trees still mostly green. "
                f"The bank is empty. The night is {o['word'].lower()}, about {o['temp']}\u00b0C, with only a light wind. "
                f"{light(o)} No sculpture is the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of the Stor\u00e5 river in Holstebro at night",
            "viewpoint": "The public bank of Stor\u00e5en in central Holstebro, near the low town bridge. Approximate researched point 56.36070, 8.61620, not a surveyed camera. Nominatim places Stor\u00e5 in Holstebro, postal 7500.",
            "refs": [
                "https://en.wikipedia.org/wiki/Holstebro",
                "https://en.wikipedia.org/wiki/Stor%C3%A5",
            ],
            "anchors": [
                "A dark smooth river.",
                "One simple low bridge.",
                "Brick buildings set back and trees still mostly green. No sculpture.",
            ],
            "solar": clock(o["_row"]) + " A little street light. No readable shop name.",
            "independent": (
                "Stor\u00e5en runs through Holstebro. The English river article identifies Stor\u00e5 as the stream through western Jutland, and the town article places Holstebro on it. "
                "The town has outdoor sculptures elsewhere. None is asserted on this bank, and none is the subject. Late September trees are still mostly green."
            ),
            "ip": "No readable sign and no sculpture treated as a named artwork. Internal review only, not a legal certification.",
            "visual": "Pass. River, one low bridge, brick town, moonlight, light wind. No sculpture.",
            "swap": "No site swap. The Stor\u00e5 waterfront in Holstebro was not used in DK-01-001 through DK-01-224. City is Holstebro.",
        },
        {
            "entry_id": "DK-01-239",
            "region": "Central Jutland",
            "city": "Ferring",
            "caption": "Bovbjerg Lighthouse, Ferring",
            **p,
            "composition": "A red tower on the grass cliff \u00b7 AI-generated artistic interpretation",
            "description": (
                "Bovbjerg Lighthouse is a red round tower with a glass lantern on a grass cliff above a dark sea, and a low white keeper's house beside it. "
                f"The cliff is empty. The night is {p['word'].lower()}, about {p['temp']}\u00b0C, with a fresh wind. "
                f"{light(p)} The sea has a little chop."
            ),
            "alt_text": "AI-generated artistic interpretation of Bovbjerg Lighthouse at night, a red tower on a cliff",
            "viewpoint": "The public cliff path at Bovbjerg Fyr, Fyrvej 27, Ferring. Approximate researched point 56.51318, 8.11968, not a surveyed camera. Nominatim places the lighthouse in Ferring, Lemvig Municipality. The postal town on the lighthouse address is 7620 Lemvig.",
            "refs": [
                "https://bovbjergfyr.dk/praktisk/english",
                "https://en.wikipedia.org/wiki/Bovbjerg",
            ],
            "anchors": [
                "A red cylindrical tower, not a white one.",
                "A glass lantern and a low white keeper's house.",
                "A grass cliff and the North Sea. No cafe sign.",
            ],
            "solar": clock(p["_row"]) + " The lantern is a small practical light, not a drawn beam. No cafe lettering.",
            "independent": (
                "The lighthouse's own English page says it was built in 1876\u201377, is still active, and stands at Fyrvej 27, Ferring, DK-7620 Lemvig. "
                "The English Bovbjerg article places the cliff and lighthouse just south of the village Ferring. The tower was painted red so it would not be mistaken for the white church towers at Ferring and Trans. "
                "Lemvig Harbour is already DK-01-137. City is Ferring, the village, not Lemvig."
            ),
            "ip": "No cafe logo and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Red tower, keeper's house, grass cliff, dark sea, broken cloud. No sign.",
            "swap": (
                "Swapped from Lemvig Harbour. That basin is already DK-01-137, Lemvig Harbour, Lemvig. "
                "The caption is Bovbjerg Lighthouse. City is Ferring. The postal town is Lemvig."
            ),
        },
        {
            "entry_id": "DK-01-240",
            "region": "North Jutland",
            "city": "Hanstholm",
            "caption": "Hanstholm Lighthouse, Hanstholm",
            **q,
            "composition": "A white octagonal tower and the keeper's house \u00b7 AI-generated artistic interpretation",
            "description": (
                "Hanstholm Lighthouse is a white octagonal tower with a lantern, joined to a two-storey keeper's house on a grassy knoll, with a small church nearby and the sea only at the horizon. "
                f"The knoll is empty. The night is {q['word'].lower()}, about {q['temp']}\u00b0C, and the wind is fresh. "
                f"{light(q)} The fishing harbour is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Hanstholm Lighthouse at night, a white octagonal tower",
            "viewpoint": "The public ground at Hanstholm Fyr, T\u00e5rnvej, beside Hansted Church. Approximate researched point 57.11271, 8.59855, not a surveyed camera. Nominatim places the lighthouse in Hanstholm, postal 7730.",
            "refs": [
                "https://da.wikipedia.org/wiki/Hanstholm_Fyr",
                "https://lex.dk/Hanstholm_Fyr",
            ],
            "anchors": [
                "A white octagonal tower, not a square box and not a round cylinder.",
                "A lantern and a short link to a two-storey keeper's house.",
                "A grassy knoll. The harbour cranes are not in the frame.",
            ],
            "solar": clock(q["_row"]) + " Moonlight on the white tower. No readable plaque.",
            "independent": (
                "Lex and the Danish article describe Hanstholm Fyr as the octagonal lighthouse built on Hanstholmknuden in 1843, 23 m tall, with the light 65 m above the sea. It stands by Hansted Church, inland of the harbour, not on a mole. "
                "Thybor\u00f8n Harbour is already DK-01-138. Hanstholm is in Thisted Municipality, Region Nordjylland, so the gallery region is North Jutland. The 65 m figure is the published focal height, not a new measurement."
            ),
            "ip": "No readable plaque and no harbour logo. Internal review only, not a legal certification.",
            "visual": "Pass. White octagonal tower, keeper's house, grassy knoll, moonlight. No harbour cranes.",
            "swap": (
                "Swapped from Thybor\u00f8n Harbour. That canal port is already DK-01-138, Thybor\u00f8n Harbour, Thybor\u00f8n. "
                "The caption is Hanstholm Lighthouse. City is Hanstholm."
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
    if len(all_scenes) != 240:
        raise SystemExit(f"expected 240 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 241)]
    if ids != expected:
        raise SystemExit("id sequence mismatch")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    descriptions = [item["_manifest"]["description"] for item in all_scenes]
    if len(descriptions) != len(set(descriptions)):
        raise SystemExit("duplicate description")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-225-240.txt"
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

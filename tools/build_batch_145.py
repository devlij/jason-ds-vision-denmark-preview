#!/usr/bin/env python3
"""Bake DK-01-145 through DK-01-160 and rebuild the gallery from every manifest."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.parse
import urllib.request
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

COORDS = {
    "DK-01-145": (55.67540, 12.58380),
    "DK-01-146": (55.67660, 12.58360),
    "DK-01-147": (55.68928, 12.59759),
    "DK-01-148": (55.67355, 12.58286),
    "DK-01-149": (55.65479, 12.64806),
    "DK-01-150": (55.77721, 12.59205),
    "DK-01-151": (55.88470, 12.54681),
    "DK-01-152": (55.92974, 12.30283),
    "DK-01-153": (56.02369, 12.19743),
    "DK-01-154": (55.25438, 12.37347),
    "DK-01-155": (55.02226, 10.65315),
    "DK-01-156": (54.74994, 10.71560),
    "DK-01-157": (55.27848, 14.80144),
    "DK-01-158": (55.18858, 14.70310),
    "DK-01-159": (62.01020, -6.77480),
    "DK-01-160": (61.15555, -45.42386),
}

GEN_BUCKET = {
    "DK-01-145": "overcast",
    "DK-01-146": "overcast",
    "DK-01-147": "overcast",
    "DK-01-148": "overcast",
    "DK-01-149": "overcast",
    "DK-01-150": "overcast",
    "DK-01-151": "overcast",
    "DK-01-152": "overcast",
    "DK-01-153": "overcast",
    "DK-01-154": "overcast",
    "DK-01-155": "overcast",
    "DK-01-156": "overcast",
    "DK-01-157": "overcast",
    "DK-01-158": "overcast",
    "DK-01-159": "partly",
    "DK-01-160": "clear",
}

# Depicted from the 02:56 Europe/Copenhagen retrieval, valid 02:45.
# Kept if a later hour changes the sky bucket or leaves night.
_BASE = {
    "is_day": 0,
    "valid": "2026-09-25T02:45",
    "retrieved_stamp": "25 September 2026 02:56",
    "offset": 7200,
    "precip": 0.0,
}
SNAPSHOT = {
    "DK-01-145": {**_BASE, "word": "Overcast", "temp": 13.9, "cloud": 100, "wind": 10.8, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-146": {**_BASE, "word": "Overcast", "temp": 13.9, "cloud": 100, "wind": 10.8, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-147": {**_BASE, "word": "Overcast", "temp": 13.5, "cloud": 99, "wind": 11.9, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-148": {**_BASE, "word": "Overcast", "temp": 14.0, "cloud": 100, "wind": 11.2, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-149": {**_BASE, "word": "Overcast", "temp": 13.3, "cloud": 99, "wind": 13.3, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-150": {**_BASE, "word": "Overcast", "temp": 12.6, "cloud": 98, "wind": 9.0, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-151": {**_BASE, "word": "Overcast", "temp": 13.2, "cloud": 96, "wind": 9.0, "code": 3, "sunset_yesterday": "2026-09-24T19:03", "sunrise_today": "2026-09-25T07:00"},
    "DK-01-152": {**_BASE, "word": "Overcast", "temp": 12.5, "cloud": 100, "wind": 5.0, "code": 3, "sunset_yesterday": "2026-09-24T19:04", "sunrise_today": "2026-09-25T07:01"},
    "DK-01-153": {**_BASE, "word": "Overcast", "temp": 13.6, "cloud": 100, "wind": 7.9, "code": 3, "sunset_yesterday": "2026-09-24T19:05", "sunrise_today": "2026-09-25T07:02"},
    "DK-01-154": {**_BASE, "word": "Overcast", "temp": 13.5, "cloud": 91, "wind": 14.0, "code": 3, "sunset_yesterday": "2026-09-24T19:04", "sunrise_today": "2026-09-25T07:01"},
    "DK-01-155": {**_BASE, "word": "Overcast", "temp": 11.5, "cloud": 92, "wind": 16.6, "code": 3, "sunset_yesterday": "2026-09-24T19:11", "sunrise_today": "2026-09-25T07:08"},
    "DK-01-156": {**_BASE, "word": "Overcast", "temp": 12.6, "cloud": 78, "wind": 18.7, "code": 3, "sunset_yesterday": "2026-09-24T19:11", "sunrise_today": "2026-09-25T07:07"},
    "DK-01-157": {**_BASE, "word": "Overcast", "temp": 14.1, "cloud": 99, "wind": 13.7, "code": 3, "sunset_yesterday": "2026-09-24T18:54", "sunrise_today": "2026-09-25T06:51"},
    "DK-01-158": {**_BASE, "word": "Overcast", "temp": 14.4, "cloud": 98, "wind": 14.0, "code": 3, "sunset_yesterday": "2026-09-24T18:55", "sunrise_today": "2026-09-25T06:52"},
    "DK-01-159": {**_BASE, "word": "Partly cloudy", "temp": 10.5, "cloud": 78, "wind": 42.1, "code": 2, "sunset_yesterday": "2026-09-24T20:21", "sunrise_today": "2026-09-25T08:18"},
    "DK-01-160": {**_BASE, "word": "Clear", "temp": -1.1, "cloud": 17, "wind": 6.5, "code": 0, "sunset_yesterday": "2026-09-24T22:55", "sunrise_today": "2026-09-25T10:53"},
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def bucket(code: int) -> str:
    return {0: "clear", 1: "mainly", 2: "partly", 3: "overcast"}.get(code, "other")


def sky_word(code: int) -> str:
    return {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}.get(code, f"Weather code {code}")


def nice_time(iso: str) -> str:
    return f"{int(iso[8:10])} {MONTHS[iso[5:7]]} {iso[0:4]} {iso[11:16]}"


def nice_dt(dt: datetime) -> str:
    return f"{dt.day} {MONTHS[f'{dt.month:02d}']} {dt.year} {dt.strftime('%H:%M')}"


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
    return f"A computed sun altitude of about {alt:.0f}\u00b0 ({band}), not an on-site observation."


def pack_current(entry: str, item: dict, stamp: str) -> dict:
    cur = item["current"]
    daily = item["daily"]
    offset = int(item["utc_offset_seconds"])
    local = datetime.fromisoformat(cur["time"]).replace(tzinfo=timezone(timedelta(seconds=offset)))
    code = int(cur["weather_code"])
    temp = float(cur["temperature_2m"])
    cloud = int(cur["cloud_cover"])
    wind = float(cur["wind_speed_10m"])
    precip = float(cur["precipitation"])
    alt = sun_alt(COORDS[entry][0], COORDS[entry][1], local.astimezone(timezone.utc))
    word = sky_word(code)
    precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": f"{word}, {temp:.1f}\u00b0C, cloud cover {cloud}%, wind {wind:.1f} km/h, {precip_words}.",
        "temp": f"{temp:.1f}",
        "cloud": cloud,
        "wind": f"{wind:.1f}",
        "code": code,
        "is_day": cur.get("is_day"),
        "valid": cur["time"],
        "sunset_yesterday": daily["sunset"][0],
        "sunrise_today": daily["sunrise"][1],
        "sun_alt": alt,
        "retrieved_stamp": stamp,
        "fallback": False,
    }


def pack_snapshot(entry: str, snap: dict) -> dict:
    local = datetime.fromisoformat(snap["valid"]).replace(tzinfo=timezone(timedelta(seconds=snap["offset"])))
    alt = sun_alt(COORDS[entry][0], COORDS[entry][1], local.astimezone(timezone.utc))
    temp = float(snap["temp"])
    wind = float(snap["wind"])
    precip = float(snap["precip"])
    word = snap["word"]
    precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
    return {
        "word": word,
        "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
        "detail": f"{word}, {temp:.1f}\u00b0C, cloud cover {snap['cloud']}%, wind {wind:.1f} km/h, {precip_words}.",
        "temp": f"{temp:.1f}",
        "cloud": snap["cloud"],
        "wind": f"{wind:.1f}",
        "code": snap["code"],
        "is_day": snap["is_day"],
        "valid": snap["valid"],
        "sunset_yesterday": snap["sunset_yesterday"],
        "sunrise_today": snap["sunrise_today"],
        "sun_alt": alt,
        "retrieved_stamp": snap["retrieved_stamp"],
        "fallback": True,
    }


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
    stamp = retrieved.strftime("%-d %B %Y %H:%M")
    out = {}
    for entry, item in zip(ids, data):
        cur = item["current"]
        code = int(cur["weather_code"])
        live_bucket = bucket(code)
        night = int(cur.get("is_day") or 0) == 0
        if live_bucket == GEN_BUCKET[entry] and night:
            out[entry] = pack_current(entry, item, stamp)
            continue
        snap = SNAPSHOT.get(entry)
        if snap is not None and bucket(snap["code"]) == GEN_BUCKET[entry]:
            print(
                f"{entry} live bucket {live_bucket} is_day {cur.get('is_day')} "
                f"differs from depicted {GEN_BUCKET[entry]} night; "
                f"keeping the {snap['retrieved_stamp']} retrieval the frame was built from"
            )
            out[entry] = pack_snapshot(entry, snap)
            continue
        raise SystemExit(f"{entry} sky bucket changed from {GEN_BUCKET[entry]} to {live_bucket}")
    return stamp, out, moon_note(retrieved)


def prepare_raws() -> None:
    for n in range(145, 161):
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
        stamp = row.get("retrieved_stamp", weather_stamp)
        return (
            "Model data from Open-Meteo, retrieved "
            f"{stamp} Europe/Copenhagen, valid {valid} "
            "\u2014 not a verified on-site observation."
        )

    def pref_zone(entry: str, zone: str, label: str) -> str:
        row = wx[entry]
        valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=ZoneInfo("Europe/Copenhagen"))
        local = valid.astimezone(ZoneInfo(zone))
        stamp = row.get("retrieved_stamp", weather_stamp)
        return (
            "Model data from Open-Meteo, retrieved "
            f"{stamp} Europe/Copenhagen, valid {nice_dt(local)} {label} "
            f"(the same instant as {nice_time(row['valid'])} Europe/Copenhagen) "
            "\u2014 not a verified on-site observation."
        )

    def pack(entry: str, zone: str | None = None, label: str | None = None) -> dict:
        row = wx[entry]
        weather_prefix = pref(entry) if zone is None else pref_zone(entry, zone, label or "")
        return {
            "weather_prefix": weather_prefix,
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
        text += "The cloud deck hides the moon. " if row["cloud"] >= 80 else moon + " "
        return text

    def clock_zone(entry: str, zone: str, label: str) -> str:
        row = wx[entry]
        def conv(iso: str) -> datetime:
            return datetime.fromisoformat(iso).replace(tzinfo=ZoneInfo("Europe/Copenhagen")).astimezone(ZoneInfo(zone))
        valid = datetime.fromisoformat(row["valid"]).replace(tzinfo=ZoneInfo("Europe/Copenhagen")).astimezone(ZoneInfo(zone))
        text = (
            "Night. Sunset on "
            f"{nice_dt(conv(row['sunset_yesterday']))} {label} and sunrise on "
            f"{nice_dt(conv(row['sunrise_today']))} {label}. "
            "The clock printed on the image is Europe/Copenhagen. "
            f"Local valid time is {nice_dt(valid)} {label}. "
        )
        text += twilight_phrase(row["sun_alt"]) + " "
        text += f"Cloud cover {row['cloud']}%. "
        text += "The cloud deck hides the moon. " if row["cloud"] >= 80 else moon + " "
        return text

    a = pack("DK-01-145")
    b = pack("DK-01-146")
    c = pack("DK-01-147")
    d = pack("DK-01-148")
    e = pack("DK-01-149")
    f = pack("DK-01-150")
    g = pack("DK-01-151")
    h = pack("DK-01-152")
    i = pack("DK-01-153")
    j = pack("DK-01-154")
    k = pack("DK-01-155")
    m = pack("DK-01-156")
    n = pack("DK-01-157")
    o = pack("DK-01-158")
    p = pack("DK-01-159", "Atlantic/Faroe", "Atlantic/Faroe")
    q = pack("DK-01-160", "America/Nuuk", "America/Nuuk")

    return [
        {
            "entry_id": "DK-01-145",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Børsen, Copenhagen",
            **a,
            "composition": "Red-brick exchange, copper roof, and a gap where the spire stood \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the canal quay, Børsen is the long red-brick Renaissance building with sandstone gables. "
                f"The eastern roof is copper. The dragon spire is absent, and the burned central section is under a construction cover with scaffolding. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C, and the quay is empty."
            ),
            "alt_text": "AI-generated artistic interpretation of Børsen in Copenhagen at night, without the dragon spire, with scaffolding on the burned section",
            "viewpoint": "The public quay along Børsgraven, looking along the long facade. Approximate researched point 55.67540, 12.58380, not a surveyed camera.",
            "refs": [
                "https://www.sammenomborsen.dk/english/here-is-the-vision/",
                "https://en.wikipedia.org/wiki/B%C3%B8rsen",
            ],
            "anchors": [
                "A long red-brick building with ornate gables beside a canal.",
                "Copper roof on the less-damaged eastern half.",
                "No dragon spire. A construction cover and scaffolding where the tower stood.",
            ],
            "solar": clock("DK-01-145") + "Street lamps and a few work lights. No floodlit spire, because the spire is not there.",
            "independent": (
                "Børsen, Christian IV's exchange on Slotsholmen, lost its dragon-tail spire in the fire of 16 April 2024. "
                "The western half burned. Dansk Erhverv's rebuild page says the dragons are to return with a reopening aimed at 2029, and that the design was still a vision pending approvals. "
                "On 16 April 2026 scaffolding began to come off the less-damaged eastern section, with the rest of that scaffolding described as coming down over the following months. "
                "This frame keeps the gap and the construction cover. It does not put the four dragons back."
            ),
            "ip": "No owner name and no readable site sign. Internal review only, not a legal certification.",
            "visual": "Pass. Canal, red-brick gables, copper roof, scaffolding, and an empty roofline. No dragon spire.",
            "swap": (
                "No city swap. The dragon-tail spire was not drawn. It fell in the 16 April 2024 fire and has not been rebuilt. "
                "The published frames show the eastern copper roof and scaffolding on the burned half, which is the state described by the rebuild project in 2026."
            ),
        },
        {
            "entry_id": "DK-01-146",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Holmens Kirke, Copenhagen",
            **b,
            "composition": "Red-brick church and one copper spire across the canal \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From across Holmens Kanal, Holmens Kirke is a red-brick church with sandstone gables and one copper spire, standing on its island site. "
                f"Dark canal water fills the foreground. The night is {b['word'].lower()}, about {b['temp']}\u00b0C, and the quay is empty. "
                "This is not the spiral tower of the Church of Our Saviour."
            ),
            "alt_text": "AI-generated artistic interpretation of Holmens Kirke in Copenhagen at night, a brick church and copper spire across the canal",
            "viewpoint": "Holmens Kanal, looking across the water at the church. Approximate researched point 55.67660, 12.58360, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Church_of_Holmen",
                "https://da.wikipedia.org/wiki/Holmens_Kirke",
            ],
            "anchors": [
                "A red-brick church with sandstone gables.",
                "One copper spire, not an external spiral stair.",
                "Canal water in the foreground.",
            ],
            "solar": clock("DK-01-146") + "Street lamps on the water. The spire is an interpretation of the copper crown, not a measured elevation.",
            "independent": (
                "Holmens Kirke stands on its own site in Holmens Kanal, beside Slotsholmen. "
                "It began as an anchor forge and was made a church for the navy. The brick body, Dutch gables, and a single spire are the exterior a visitor sees from the canal. "
                "DK-01-025 is the Church of Our Saviour in Christianshavn, which has the external spiral. This card is the canal church."
            ),
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. Brick church, one copper spire, canal, overcast night. No external spiral stair.",
            "swap": "No swap. The canal front of Holmens Kirke is the view.",
        },
        {
            "entry_id": "DK-01-147",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Gefion Fountain, Copenhagen",
            **c,
            "composition": "Bronze goddess and four oxen above a stone basin \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The Gefion Fountain is a bronze group of a woman driving four oxen, with water falling into a wide stone basin in the park by the harbour promenade. "
                f"Trees stand behind the basin. The night is {c['word'].lower()}, about {c['temp']}\u00b0C, and the fountain is lit by lamps. "
                "There is no mermaid on a rock."
            ),
            "alt_text": "AI-generated artistic interpretation of the Gefion Fountain in Copenhagen at night, a bronze woman and four oxen",
            "viewpoint": "The public rim of the Gefion Fountain basin at Churchillparken. Approximate researched point 55.68928, 12.59759, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Gefion_Fountain",
                "https://da.wikipedia.org/wiki/Gefionspringvandet",
            ],
            "anchors": [
                "A bronze woman and four oxen.",
                "Water falling into a wide stone basin.",
                "Trees behind. No mermaid statue.",
            ],
            "solar": clock("DK-01-147") + "Fountain lamps. No rainfall in the model; the water belongs to the fountain.",
            "independent": (
                "Gefionspringvandet, by Anders Bundgaard, was inaugurated in 1908 beside the harbour promenade at Churchillparken. "
                "The group shows Gefjon and the four oxen of the myth, ploughing, with the basin below. "
                "The Little Mermaid, DK-01-002, is farther along Langelinie and is not in this frame. Bundgaard died in 1937."
            ),
            "ip": "The sculptor died in 1937. No living person's portrait. No logo. Internal review only, not a legal certification.",
            "visual": "Pass. Woman, four oxen, basin, trees, overcast night. Not the Little Mermaid.",
            "swap": "No swap. The fountain at Churchillparken is the view, not the statue farther along the promenade.",
        },
        {
            "entry_id": "DK-01-148",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "The Black Diamond, Copenhagen",
            **d,
            "composition": "Two black granite wings split by a glass atrium \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the harbour, the Black Diamond is two polished black granite volumes leaning over the water, split by a tall glass atrium. "
                f"A piece of the older red-brick library shows beside them. The night is {d['word'].lower()}, about {d['temp']}\u00b0C, and quay lamps reflect on the water. "
                "No lettering is treated as readable."
            ),
            "alt_text": "AI-generated artistic interpretation of the Black Diamond library in Copenhagen at night, black granite wings over the harbour",
            "viewpoint": "The harbour side of Christians Brygge, looking at the waterfront facade. Approximate researched point 55.67355, 12.58286, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Royal_Danish_Library",
                "https://www.kb.dk/besoeg-os/den-sorte-diamant",
            ],
            "anchors": [
                "Two black granite volumes leaning toward the water.",
                "A glass atrium between them.",
                "Harbour water in front. No readable name.",
            ],
            "solar": clock("DK-01-148") + "Quay lamps and a faint interior glow. No sign band.",
            "independent": (
                "The Black Diamond is the 1999 waterfront extension of the Royal Danish Library on Slotsholmen, at Christians Brygge. "
                "Two black granite masses lean outward and are divided by a glass gorge. The older brick library stands behind that front. "
                "DK-01-026 is Islands Brygge, across the inner harbour, and is not this building."
            ),
            "ip": "No library wordmark and no readable sign. Internal review only, not a legal certification.",
            "visual": "Pass. Two black wings, glass split, harbour water, overcast night. No readable lettering.",
            "swap": "No swap. The waterfront exterior is the view. The reading rooms are not shown.",
        },
        {
            "entry_id": "DK-01-149",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Øresund Bridge, Copenhagen",
            **e,
            "composition": "A distant lit deck and two cable pylons \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the empty seaward beach on Amager, the Øresund Bridge is a long low line of lights with two cable-stayed pylons far to the south. "
                f"Sand and a little dune grass fill the foreground. The night is {e['word'].lower()}, about {e['temp']}\u00b0C. "
                "There is no lagoon footbridge and no yellow fishing village."
            ),
            "alt_text": "AI-generated artistic interpretation of the Øresund Bridge at night from the Amager beach in Copenhagen, two distant pylons",
            "viewpoint": "The seaward beach at Amager Strandpark, looking south toward the bridge. Approximate researched point 55.65479, 12.64806, not a surveyed camera. Nominatim places this park in Copenhagen.",
            "refs": [
                "https://en.wikipedia.org/wiki/%C3%98resund_Bridge",
                "https://www.oresundsbron.com/en/private",
            ],
            "anchors": [
                "Empty sand in the foreground.",
                "A long low bridge deck marked by lights.",
                "Two distant cable-stayed pylons, not one.",
            ],
            "solar": clock("DK-01-149") + "Bridge lights and no beach crowd. Late September, so the sand is empty.",
            "independent": (
                "The Øresund Bridge runs from Kastrup on Amager toward Sweden, with a cable-stayed section of two pylons. "
                "From the seaward side of Amager Strandpark the deck is a distant lit line and the pylons are small. "
                "Nominatim places Amager Strandpark in Copenhagen. Kastrup Søbad, farther south, is in Kastrup and was not used. "
                "DK-01-081 is the lagoon and island beach, not this view of the bridge. Dragør harbour is DK-01-030 and was not used."
            ),
            "ip": "No bridge operator mark and no toll sign. Internal review only, not a legal certification.",
            "visual": "Pass. Beach, distant lit deck, two pylons, overcast night. Not the lagoon and not Dragør.",
            "swap": (
                "No city swap. The overlook is the seaward beach of Amager Strandpark, which Nominatim places in Copenhagen. "
                "A first wide frame with a single pylon was discarded and replaced with two pylons. "
                "Kastrup Søbad was not used, because that beach is in Kastrup."
            ),
        },
        {
            "entry_id": "DK-01-150",
            "region": "Capital Region",
            "city": "Klampenborg",
            "caption": "Bellevue Beach, Klampenborg",
            **f,
            "composition": "Blue-and-white lifeguard towers on an empty beach \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Bellevue Beach is a curve of sand on the Øresund, with Arne Jacobsen's cylindrical lifeguard cabins, blue and white stripes on white poles, standing on wooden piers. "
                f"The night is {f['word'].lower()}, about {f['temp']}\u00b0C, and the beach is empty. "
                "No theatre name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Bellevue Beach in Klampenborg at night, striped lifeguard towers on the sand",
            "viewpoint": "The public sand at Bellevue Strand, looking along the piers. Approximate researched point 55.77721, 12.59205, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Bellevue_Beach",
                "https://www.visitcopenhagen.com/copenhagen/planning/bellevue-gdk482349",
            ],
            "anchors": [
                "A sandy beach and dark water.",
                "Cylindrical cabins with horizontal blue and white stripes, raised on white poles.",
                "Wooden piers. No readable theatre name.",
            ],
            "solar": clock("DK-01-150") + "A few promenade lamps. Late September, so there are no swimmers.",
            "independent": (
                "Bellevue Strand is the beach at Klampenborg, in Gentofte Kommune. VisitCopenhagen gives the address as Strandvejen 340, 2930 Klampenborg. "
                "Arne Jacobsen's 1932 lifeguard towers are cylindrical blue-and-white striped cabins on poles, now on the bathing piers. "
                "The Bellevue Theatre stands nearby. Its name is not the subject. The city is Klampenborg, not Copenhagen."
            ),
            "ip": "No theatre name and no cafe logo. Jacobsen died in 1971. Internal review only, not a legal certification.",
            "visual": "Pass. Striped towers on poles, empty sand, dark water, overcast night. No readable name.",
            "swap": "No swap. City verified as Klampenborg. The beach and the lifeguard towers are the view, not the theatre front.",
        },
        {
            "entry_id": "DK-01-151",
            "region": "Capital Region",
            "city": "Rungsted",
            "caption": "Rungsted Harbour, Rungsted",
            **g,
            "composition": "A small marina, stone piers, and low houses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Rungsted harbour is a quiet marina of ordinary boats inside stone piers, with low houses and trees behind the quay. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C, and lamps lie on dark water. "
                "The quay is empty. There is no country house and no readable boat name."
            ),
            "alt_text": "AI-generated artistic interpretation of Rungsted harbour at night, boats and low houses on the Øresund",
            "viewpoint": "The public quay at Rungsted Havn, looking across the basin. Approximate researched point 55.88470, 12.54681, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Rungsted",
                "https://da.wikipedia.org/wiki/Rungsted",
            ],
            "anchors": [
                "A small marina basin and ordinary boats.",
                "Stone piers and quay lamps.",
                "Low houses and trees. No manor house.",
            ],
            "solar": clock("DK-01-151") + "Quay lamps. No museum lighting.",
            "independent": (
                "Rungsted Havn is the marina on the Øresund at Rungsted. Nominatim lists the municipality as Hørsholm and the locality as Rungsted, postal 2960. "
                "The caption city is Rungsted, the place in the address, not the municipality name. "
                "Rungstedlund, the Karen Blixen house, is inland and is not this frame. No boat name is treated as readable."
            ),
            "ip": "No museum name and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, piers, low houses, overcast night, empty quay. No manor.",
            "swap": (
                "No city swap. City kept as Rungsted. Nominatim's municipality field is Hørsholm, and the harbour display name includes the locality Rungsted. "
                "The Karen Blixen museum was not used."
            ),
        },
        {
            "entry_id": "DK-01-152",
            "region": "Capital Region",
            "city": "Hillerød",
            "caption": "Torvet, Hillerød",
            **h,
            "composition": "Neo-Gothic town hall and a bronze statue on the square \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Torvet is a paved town square closed in by ordinary buildings. The landmark is the neo-Gothic red-brick old town hall, with a bronze standing figure on a plinth. "
                f"The night is {h['word'].lower()}, about {h['temp']}\u00b0C, under street lamps. "
                "There is no castle and no lake."
            ),
            "alt_text": "AI-generated artistic interpretation of Torvet in Hillerød at night, a red-brick town hall and a statue on the square",
            "viewpoint": "The public square at Torvet, looking at the old town hall. Approximate researched point 55.92974, 12.30283, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hiller%C3%B8d",
                "https://hilleroedleksikon.dk/leksikonartikler/hillerod-kirke",
            ],
            "anchors": [
                "A paved square and three-storey town buildings.",
                "A neo-Gothic red-brick town hall.",
                "One bronze standing statue. No castle and no lake.",
            ],
            "solar": clock("DK-01-152") + "Street lamps. No shop name is readable. The statue is not a portrait of a living person.",
            "independent": (
                "Torvet is the town square in the centre of Hillerød. The neo-Gothic rådhus of 1888, by Vilhelm Holck, faces the square, and the bronze of Frederik VII, finished by Vilhelm Bissen and unveiled in 1880, stands on the paving. "
                "Frederiksborg Castle is DK-01-005 and Slotssøen is DK-01-100. Neither is in this frame. "
                "A first portrait that still showed a distant castle and water was discarded."
            ),
            "ip": "No readable shop signs. The statue is a 19th-century monument. Internal review only, not a legal certification.",
            "visual": "Pass. Town hall, statue, paved square, overcast night. No castle and no lake.",
            "swap": (
                "No city swap. The square is used so the card stays distinct from Frederiksborg Castle, DK-01-005, and Slotssøen, DK-01-100. "
                "A portrait frame that still included a castle silhouette was discarded."
            ),
        },
        {
            "entry_id": "DK-01-153",
            "region": "Capital Region",
            "city": "Helsinge",
            "caption": "Helsinge Church, Helsinge",
            **i,
            "composition": "Whitewashed church and a heavy west tower on the town street \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Helsinge Church is a whitewashed church with a red tile roof and a heavy west tower, on a quiet street of low houses. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, under street lamps. "
                "The forest is not the subject, and there is no castle."
            ),
            "alt_text": "AI-generated artistic interpretation of Helsinge Church at night, a white tower and red roof on a town street",
            "viewpoint": "The street beside Helsinge Kirke. Approximate researched point 56.02369, 12.19743, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Helsinge",
                "https://da.wikipedia.org/wiki/Helsinge_Kirke",
            ],
            "anchors": [
                "A whitewashed church.",
                "A heavy west tower and a red tile roof.",
                "Low town houses. No forest panorama.",
            ],
            "solar": clock("DK-01-153") + "Street lamps. The tower roof is an interpretation, not a measured elevation.",
            "independent": (
                "Helsinge is the town in Gribskov Kommune, in the Capital Region. Gribskov is the municipality, not the town name in the caption. "
                "Helsinge Kirke stands in the town, a whitewashed church with a west tower. "
                "This is not Kirke Helsinge, which is a different town in West Zealand. The frame is the church street, not the surrounding forest."
            ),
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. White church, west tower, red roof, town street, overcast night. No forest as the subject.",
            "swap": "No swap. City verified as Helsinge. Gribskov is the municipality and is not used as the city.",
        },
        {
            "entry_id": "DK-01-154",
            "region": "Zealand",
            "city": "Rødvig",
            "caption": "Rødvig Harbour, Rødvig",
            **j,
            "composition": "Fishing boats inside stone moles \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Rødvig harbour is a small basin of fishing boats inside stone moles, with low houses along the quay. "
                f"The night is {j['word'].lower()}, about {j['temp']}\u00b0C, and quay lamps lie on dark water. "
                "The quay is empty. There is no church on a cliff."
            ),
            "alt_text": "AI-generated artistic interpretation of Rødvig harbour at night, fishing boats and stone piers",
            "viewpoint": "The quay at Rødvig harbour, looking across the basin. Approximate researched point 55.25438, 12.37347, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/R%C3%B8dvig",
                "https://da.wikipedia.org/wiki/R%C3%B8dvig",
            ],
            "anchors": [
                "A small fishing basin and ordinary boats.",
                "Stone moles and low houses.",
                "No truncated church and no cliff-edge ruin.",
            ],
            "solar": clock("DK-01-154") + "Quay lamps. No boat name is readable.",
            "independent": (
                "Rødvig is the fishing harbour at the south end of the Stevns peninsula, in Stevns Kommune, postal 4673. Nominatim names the town Rødvig. "
                "The gallery region is Zealand. Højerup old church, on the cliff, is already the subject of DK-01-032, Stevns Klint, Store Heddinge. "
                "This card is the harbour, several kilometres from that church. No boat name is treated as readable."
            ),
            "ip": "No readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Boats, stone moles, low houses, overcast night. No cliff church.",
            "swap": (
                "Swapped from Højerup old church. That truncated church is already the subject of DK-01-032, Stevns Klint, Store Heddinge. "
                "Rødvig Harbour is the surplus Stevns view. City is Rødvig, not Store Heddinge."
            ),
        },
        {
            "entry_id": "DK-01-155",
            "region": "Funen",
            "city": "Troense",
            "caption": "Valdemars Slot, Troense",
            **k,
            "composition": "White Baroque palace, dark roof, and the sound \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Valdemars Slot is a long white Baroque palace with a dark hipped roof and a central pediment, set behind a lawn with the sound in front. "
                f"The night is {k['word'].lower()}, about {k['temp']}\u00b0C, and a few windows are lit. "
                "There is no dome and no readable sign."
            ),
            "alt_text": "AI-generated artistic interpretation of Valdemars Slot at Troense at night, a white palace across a lawn",
            "viewpoint": "The public garden front of Valdemars Slot, looking at the main facade with the sound in the foreground. Approximate researched point 55.02226, 10.65315, not a surveyed camera.",
            "refs": [
                "https://www.valdemarsslot.dk/about",
                "https://en.wikipedia.org/wiki/Valdemar%27s_Castle",
            ],
            "anchors": [
                "A long white symmetrical palace.",
                "A dark hipped roof and a central pediment. No dome.",
                "A lawn and dark water in front.",
            ],
            "solar": clock("DK-01-155") + "A few lit windows. Exterior only.",
            "independent": (
                "Valdemars Slot stands on Tåsinge, a short walk from Troense. Nominatim places the building in Troense. "
                "The castle's own address is Slotsalléen 100, 5700 Svendborg, the postal town across the sound. "
                "The caption city is Troense, the locality of the building. The gallery files Tåsinge with Funen, as it does Svendborg and Langeland. "
                "The frame is the exterior. A first wide frame that added a cupola was discarded."
            ),
            "ip": "No hotel or estate wordmark. Exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. White palace, pediment, dark roof, lawn, water, overcast night. No dome and no sign.",
            "swap": (
                "No city swap. City kept as Troense after Nominatim placed Valdemars Slot in Troense. "
                "The postal address is 5700 Svendborg. A first wide frame with a cupola was discarded."
            ),
        },
        {
            "entry_id": "DK-01-156",
            "region": "Funen",
            "city": "Bagenkop",
            "caption": "Langelandsfort, Bagenkop",
            **m,
            "composition": "A coastal gun and concrete bunkers above the sea \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Langelandsfort is a concrete bunker and an open gun emplacement on a grassy coastal bluff, with the dark sea below. "
                f"The night is {m['word'].lower()}, about {m['temp']}\u00b0C. "
                "There is no submarine, no aircraft, and no harbour."
            ),
            "alt_text": "AI-generated artistic interpretation of Langelandsfort at night, a coastal gun and bunker above the sea",
            "viewpoint": "The public gun line at Langelandsfort, looking toward the sea. Approximate researched point 54.74994, 10.71560, not a surveyed camera.",
            "refs": [
                "https://www.langelandsfortet.dk/english/opening-hours-and-prices",
                "https://da.wikipedia.org/wiki/Langelandsfortet",
            ],
            "anchors": [
                "A low concrete bunker in the grass.",
                "One coastal artillery gun in an open emplacement.",
                "Dark sea below. No submarine and no aircraft.",
            ],
            "solar": clock("DK-01-156") + "Little site lighting. No museum sign and no flag with writing.",
            "independent": (
                "Langelandsfort is the Cold War coastal battery turned museum at Vognsbjergvej 4B, 5935 Bagenkop. "
                "The museum's own page says it is open to visitors in season, with tickets at the entrance, so it is not a closed military site. "
                "Nominatim names a nearby hamlet Søndenbro. The postal town on the address is Bagenkop, and that is the caption city, matching DK-01-115. "
                "This card is the bunker and gun on the bluff, not Bagenkop harbour. The submarine and aircraft on the museum grounds are not in the frame."
            ),
            "ip": "No museum wordmark, no aircraft marking, and no submarine name. Internal review only, not a legal certification.",
            "visual": "Pass. Bunker, coastal gun, grass, sea, cloudy night. No submarine and no harbour.",
            "swap": (
                "No site swap. The fort is a public museum, not a restricted site, so the exterior was kept. "
                "City kept as Bagenkop from the postal address. OSM's hamlet name Søndenbro was not used. "
                "Distinct from Bagenkop Harbour, DK-01-115."
            ),
        },
        {
            "entry_id": "DK-01-157",
            "region": "Bornholm",
            "city": "Allinge",
            "caption": "Allinge Harbour, Allinge",
            **n,
            "composition": "Granite quay, small boats, and low coloured houses \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Allinge harbour is a granite basin of small boats, with white, yellow, and red houses rising behind the quay. "
                f"The night is {n['word'].lower()}, about {n['temp']}\u00b0C, and lamps reflect on the water. "
                "The quay is empty. There is no cliff-top castle."
            ),
            "alt_text": "AI-generated artistic interpretation of Allinge harbour at night, boats and coloured houses on a granite quay",
            "viewpoint": "The public quay at Allinge harbour, looking across the basin toward the houses. Approximate researched point 55.27848, 14.80144, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Allinge-Sandvig",
                "https://da.wikipedia.org/wiki/Allinge-Sandvig",
            ],
            "anchors": [
                "A small granite harbour and ordinary boats.",
                "Low white, yellow, and red houses.",
                "No cliff ruin.",
            ],
            "solar": clock("DK-01-157") + "Quay lamps. No boat name is readable.",
            "independent": (
                "Allinge harbour is the fishing and marina basin in Allinge, on the north coast of Bornholm. "
                "Nominatim's town name is the compound Allinge-Sandvig. The gallery already uses Allinge for Hammershus, DK-01-014, and this card uses the same city. "
                "Hammershus is the cliff ruin north of town and is not in the harbour frame. No boat name is treated as readable."
            ),
            "ip": "No readable boat names and no shop signs. Internal review only, not a legal certification.",
            "visual": "Pass. Granite quay, boats, coloured houses, overcast night. No castle ruin.",
            "swap": "No swap. City kept as Allinge, consistent with DK-01-014, rather than the compound Allinge-Sandvig. The harbour is distinct from Hammershus.",
        },
        {
            "entry_id": "DK-01-158",
            "region": "Bornholm",
            "city": "Hasle",
            "caption": "Hasle Harbour, Hasle",
            **o,
            "composition": "White smokehouse chimneys beside a granite quay \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Hasle harbour is a granite quay with a few fishing boats and a long white smokehouse whose row of square chimneys stands by the water. "
                f"The night is {o['word'].lower()}, about {o['temp']}\u00b0C, and the quay is empty. "
                "No name is written on the building."
            ),
            "alt_text": "AI-generated artistic interpretation of Hasle harbour at night, white chimneys beside the quay",
            "viewpoint": "The public quay at Hasle harbour, looking toward the smokehouse and the basin. Approximate researched point 55.18858, 14.70310, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Hasle,_Bornholm",
                "https://da.wikipedia.org/wiki/Hasle_(Bornholm)",
            ],
            "anchors": [
                "A granite harbour quay and a few boats.",
                "A long white building with a row of tall square chimneys.",
                "No readable name on the building.",
            ],
            "solar": clock("DK-01-158") + "Quay lamps. The chimneys are the landmark, not a sign.",
            "independent": (
                "Hasle is the harbour town on the west coast of Bornholm. The white smokehouses and their square chimneys stand at the harbour and are the usual landmark from the quay. "
                "The building is shown without a name. No boat name is treated as readable."
            ),
            "ip": "No smokehouse wordmark and no readable boat names. Internal review only, not a legal certification.",
            "visual": "Pass. Chimneys, white building, quay, boats, overcast night. No readable name.",
            "swap": "No swap. The harbour and the chimney row are the view.",
        },
        {
            "entry_id": "DK-01-159",
            "region": "Faroe Islands",
            "city": "Tórshavn",
            "caption": "Vestaravág, Tórshavn",
            **p,
            "composition": "Sailboats in the western basin under broken cloud \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Vestaravág is the western boat basin of Tórshavn, a quay of ordinary sailboats on wind-streaked dark water, with a steep hill and town lights behind. "
                f"The night is {p['word'].lower()}, about {p['temp']}\u00b0C, and the wind is about {p['wind']} km/h. "
                "The red turf-roofed point of Tinganes is not the subject."
            ),
            "alt_text": "AI-generated artistic interpretation of Vestaravág in Tórshavn at night, sailboats in a windy harbour basin",
            "viewpoint": "The public quay on the west side of Vestaravág, looking across the marina. Approximate researched point 62.01020, -6.77480, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/T%C3%B3rshavn",
                "https://trap.fo/en/the-islands-towns-and-settlements/streymoy/torshavn/",
            ],
            "anchors": [
                "A marina of ordinary sailboats.",
                "Wind-streaked dark water and a steep hill.",
                "No red turf-roofed government point as the subject.",
            ],
            "solar": clock_zone("DK-01-159", "Atlantic/Faroe", "Atlantic/Faroe") + "Quay lamps. Wind chop on the basin. No boat name is readable.",
            "independent": (
                "Tinganes divides Tórshavn harbour into Eystaravág and Vestaravág. Reynagarður was the vicarage on Tinganes, and that peninsula is already DK-01-070. "
                "This card is the western basin. Trap Føroyar describes the port as the town's working harbour, separate from the old point. "
                "A frame that centered black turf-roofed houses was discarded. The published frames are the boat basin. "
                "The scenario clock on the image is Europe/Copenhagen. The weather valid time is Atlantic/Faroe."
            ),
            "ip": "No readable boat names and no government wordmark. Internal review only, not a legal certification.",
            "visual": "Pass. Marina, wind on the water, broken cloud, hill behind. Tinganes is not the subject.",
            "swap": (
                "Swapped from Reynagarður. Reynagarður is the old vicarage on Tinganes, already the subject of DK-01-070. "
                "Vestaravág, the western harbour, is used instead. A frame of turf-roofed houses was discarded. "
                "The frames were depicted from the 02:56 retrieval, partly cloudy with cloud cover 78%. "
                "A later model hour moved the code to overcast. The frames were not regenerated for that one-step change, and the card keeps the earlier retrieval."
            ),
        },
        {
            "entry_id": "DK-01-160",
            "region": "Greenland",
            "city": "Narsarsuaq",
            "caption": "Narsarsuaq Fjord, Narsarsuaq",
            **q,
            "composition": "A moonlit fjord between steep mountains \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the valley, Narsarsuaq is a few small lights on the floor of a steep fjord, with snow only on the high peaks. "
                f"The night is {q['word'].lower()}, about {q['temp']}\u00b0C, and the moon is out. "
                "There is no airport terminal and no airplane."
            ),
            "alt_text": "AI-generated artistic interpretation of the fjord at Narsarsuaq at night, moonlit water between steep mountains",
            "viewpoint": "A public view from the valley floor at Narsarsuaq, looking along the fjord. Approximate researched point 61.15555, -45.42386, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Narsarsuaq",
                "https://en.wikipedia.org/wiki/Tunulliarfik_Fjord",
            ],
            "anchors": [
                "A dark fjord between steep mountains.",
                "A few lights of a low settlement.",
                "Snow only on the high peaks. No runway and no terminal.",
            ],
            "solar": clock_zone("DK-01-160", "America/Nuuk", "America/Nuuk") + "Moonlight. No airfield lighting as the subject. The valley is not buried in snow.",
            "independent": (
                "Narsarsuaq sits at the head of Tunulliarfik Fjord in South Greenland. The usual view is the fjord and the mountains, with the settlement small on the valley floor. "
                "Late September at about freezing is not a snow-covered town. High peaks can still carry snow. "
                "The airfield is in the same valley and is not the subject. Kangerlussuaq was not used. "
                "The scenario clock on the image is Europe/Copenhagen. The weather valid time is America/Nuuk, taken from the zoneinfo offset on this machine."
            ),
            "ip": "No airline mark and no terminal name. Internal review only, not a legal certification.",
            "visual": "Pass. Fjord, steep mountains, a few lights, moon, clear night. No terminal and no airplane.",
            "swap": (
                "No city swap. Narsarsuaq fjord is used. Kangerlussuaq airport was not used, and the Narsarsuaq runway is not the subject. "
                "Paamiut was the other surplus option and was not needed."
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
    if len(all_scenes) != 160:
        raise SystemExit(f"expected 160 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 161)]
    if ids != expected:
        raise SystemExit(f"id sequence {ids[:3]} ... {ids[-3:]}")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-145-160.txt"
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

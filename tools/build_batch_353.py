#!/usr/bin/env python3
"""Bake DK-01-353 through DK-01-365 from per-scene Open-Meteo retrievals.

Each scene has its own build-time request, stored in tools/wx-dk-01-353-365.json.
This script does not issue a new forecast and does not copy one scene's weather
block onto another. It stops at 365.
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

WX = json.loads((Path(__file__).resolve().parent / "wx-dk-01-353-365.json").read_text(encoding="utf-8"))
CATALOG = json.loads((Path(__file__).resolve().parent / "catalog-dk-01-353-365.json").read_text(encoding="utf-8"))
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
    if hour != "16":
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
    if entry == "DK-01-363":
        return FAROE
    if entry in {"DK-01-364", "DK-01-365"}:
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
    for n in range(353, 366):
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
    if len(WX) != 13:
        raise SystemExit("expected 13 weather records")
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

    rows = {f"DK-01-{n:03d}": base(f"DK-01-{n:03d}") for n in range(353, 366)}

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

    catalog = CATALOG

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
        fold = str.maketrans({
            "\u00e6": "ae", "\u00c6": "ae",
            "\u00f8": "o", "\u00d8": "o",
            "\u00e5": "a", "\u00c5": "a",
            "\u00f0": "d", "\u00d0": "d",
            "\u00ed": "i", "\u00e1": "a", "\u00f3": "o", "\u00fa": "u", "\u00fd": "y",
            "\u00e9": "e", "\u00f6": "o", "\u00e4": "a",
        })
        stems = []
        for word in caption.replace(",", " ").split():
            folded = word.translate(fold)
            ascii_word = "".join(ch for ch in folded if ch.isascii() and ch.isalpha())
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
    if len(batch) != 13:
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
    if len(all_scenes) != 365:
        raise SystemExit(f"expected 365 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 366)]
    if ids != expected:
        raise SystemExit("id sequence mismatch")
    captions = [item["_manifest"]["caption"] for item in all_scenes]
    if len(captions) != len(set(captions)):
        raise SystemExit("duplicate caption")
    descriptions = [item["_manifest"]["description"] for item in all_scenes]
    if len(descriptions) != len(set(descriptions)):
        raise SystemExit("duplicate description")
    for item in all_scenes:
        status = item["_manifest"].get("approval_status")
        entry_id = item["_manifest"]["entry_id"]
        if entry_id >= "DK-01-353" and status not in (None, "Candidate"):
            raise SystemExit(f"status {entry_id}")
        if status not in (None, "Candidate", "Approved"):
            raise SystemExit(f"status {entry_id} {status}")
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-353-365.txt"
    lines.append(
        "Denmark kit close: DK-01-001 through DK-01-365. 730 masters. 365 cards. "
        "Denmark kit is 365/365 Candidate pending Cosmo QC. Stop. Do not start the Netherlands or any other country."
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pngs = list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-16x9.png"))
    pngs += list((bd.ROOT / "library" / "world" / "Denmark").rglob("dk-01-*-4x5.png"))
    if len(pngs) != 730:
        raise SystemExit(f"expected 730 masters, got {len(pngs)}")
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

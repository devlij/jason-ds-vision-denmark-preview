#!/usr/bin/env python3
"""Candidate pack DK-01-366..368. Plates label bars and writes manifests.

Does not approve, does not invent a QC pass, and does not touch motion clips.
Weather numbers come from tools/wx-dk-01-366-368.json, one seasonal retrieval
per scene. Those numbers are a seasonal artistic interpretation, not a
December forecast.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path("/workspace")
RAW = Path("/opt/cursor/artifacts/assets")
FONT_MED = "/usr/share/fonts/truetype/macos/Inter-Medium.ttf"
FONT_REG = "/usr/share/fonts/truetype/macos/Inter-Regular.ttf"

BAR_H = 190
BG = (14, 14, 18)
INK = (245, 245, 247)
SCENARIO_INK = (210, 214, 220)
DISCLOSURE_INK = (186, 186, 190)
DEVLIN_INK = (243, 239, 230)
SIG = "Jason D\u2019s Vision"
DEVLIN = "Jason A. Devlin"
DISCLOSURE = "AI-generated artistic interpretation \u00b7 Not a photograph."

ART50 = {
    "Title": "Jason D's Vision \u2014 AI-generated artistic interpretation",
    "Description": "AI-generated artistic interpretation from the Jason D's Vision Denmark gallery. Created with generative AI; not a photograph.",
    "Copyright": "Jason D's Vision \u2014 AI-generated content",
    "Software": "Jason D's Vision library pipeline",
    "Comment": "EU AI Act Art. 50 transparency note: this image is AI-generated content. Machine-readable disclosure embedded 2026-09-24.",
}
ITXT_KEYS = {"Title", "Copyright"}

SOURCES = {
    "DK-01-366": {
        "16x9": RAW / "dk-01-366-16x9-raw2.jpg",
        "4x5": RAW / "dk-01-366-34-raw2.jpg",
        "9x16": RAW / "dk-01-366-916-raw2.jpg",
        "city": "Copenhagen",
    },
    "DK-01-367": {
        "16x9": RAW / "dk-01-367-16x9-raw.jpg",
        "4x5": RAW / "dk-01-367-34-raw2.jpg",
        "9x16": RAW / "dk-01-367-916-raw2.jpg",
        "city": "Aarhus",
    },
    "DK-01-368": {
        "16x9": RAW / "dk-01-368-16x9-raw.jpg",
        "4x5": RAW / "dk-01-368-34-raw.jpg",
        "9x16": RAW / "dk-01-368-916-raw.jpg",
        "city": "Odense",
    },
}

PHOTO = {
    "16x9": (1920, 1080),
    "4x5": (864, 1080),
    "9x16": (1080, 1920),
}


def png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def tEXt(keyword: str, text: str) -> bytes:
    data = keyword.encode("latin-1") + b"\x00" + text.encode("latin-1")
    return png_chunk(b"tEXt", data)


def iTXt(keyword: str, text: str) -> bytes:
    data = keyword.encode("latin-1") + b"\x00\x00\x00\x00\x00" + text.encode("utf-8")
    return png_chunk(b"iTXt", data)


def read_text_chunks(path: Path) -> dict:
    data = path.read_bytes()
    pos = 8
    found = {}
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"tEXt":
            key, text = chunk.split(b"\x00", 1)
            found[key.decode("latin-1")] = text.decode("latin-1")
        elif tag == b"iTXt":
            key, rest = chunk.split(b"\x00", 1)
            rest = rest[2:]
            _lang, rest = rest.split(b"\x00", 1)
            _trans, text = rest.split(b"\x00", 1)
            found[key.decode("latin-1")] = text.decode("utf-8")
        if tag == b"IEND":
            break
    return found


def embed_art50(path: Path) -> str:
    raw = path.read_bytes()
    sig = b"\x89PNG\r\n\x1a\n"
    if not raw.startswith(sig):
        raise SystemExit(f"not png: {path}")
    before = hashlib.sha256(Image.open(path).tobytes()).hexdigest()
    iend = raw.rfind(b"IEND")
    pos = iend - 4
    extra = b""
    for key, val in ART50.items():
        extra += iTXt(key, val) if key in ITXT_KEYS else tEXt(key, val)
    path.write_bytes(raw[:pos] + extra + raw[pos:])
    after = hashlib.sha256(Image.open(path).tobytes()).hexdigest()
    if before != after:
        raise SystemExit(f"pixels changed: {path}")
    parsed = read_text_chunks(path)
    for key, val in ART50.items():
        if parsed.get(key) != val:
            raise SystemExit(f"chunk mismatch {path} {key}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def to_photo(src: Path, kind: str) -> Image.Image:
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    tw, th = PHOTO[kind]
    if kind == "4x5":
        w, h = im.size
        target_ratio = 4 / 5
        current = w / h
        if current < target_ratio - 0.002:
            new_h = int(round(w / target_ratio))
            top = max(0, (h - new_h) // 2)
            im = im.crop((0, top, w, top + new_h))
        elif current > target_ratio + 0.002:
            new_w = int(round(h * target_ratio))
            left = max(0, (w - new_w) // 2)
            im = im.crop((left, 0, left + new_w, h))
    return im.resize((tw, th), Image.Resampling.LANCZOS)


def font_at(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def plate(photo: Image.Image, caption: str, scenario_label: str) -> Image.Image:
    w, _h = photo.size
    bar = Image.new("RGB", (w, BAR_H), BG)
    draw = ImageDraw.Draw(bar)
    pad_l = 29 if w >= 1000 else 25
    pad_r = 30 if w >= 1000 else 22
    cap_size = 22
    sig_size = 18
    scen_size = 15
    disc_size = 14
    dev_size = 15
    cap_font = font_at(FONT_MED, cap_size)
    sig_font = font_at(FONT_REG, sig_size)
    scen_font = font_at(FONT_REG, scen_size)
    disc_font = font_at(FONT_REG, disc_size)
    dev_font = font_at(FONT_REG, dev_size)
    scenario = f"Scenario: {scenario_label}"

    def width(text: str, font: ImageFont.FreeTypeFont) -> int:
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]

    sig_w = width(SIG, sig_font)
    dev_w = width(DEVLIN, dev_font)
    # Keep the scenario off the right-hand credit.
    while width(scenario, scen_font) > w - pad_l - pad_r - dev_w - 28 and scen_size > 11:
        scen_size -= 1
        scen_font = font_at(FONT_REG, scen_size)
    while width(caption, cap_font) > w - pad_l - pad_r - sig_w - 24 and cap_size > 14:
        cap_size -= 1
        cap_font = font_at(FONT_MED, cap_size)

    # Measured against the 190px Denmark label bar: caption ink near y=68.
    draw.text((pad_l, 64), caption, font=cap_font, fill=INK)
    draw.text((w - pad_r, 78), SIG, font=sig_font, fill=INK, anchor="ra")
    draw.text((pad_l, 96), scenario, font=scen_font, fill=SCENARIO_INK)
    draw.text((pad_l, 118), DISCLOSURE, font=disc_font, fill=DISCLOSURE_INK)
    draw.text((w - pad_r, 124), DEVLIN, font=dev_font, fill=DEVLIN_INK, anchor="ra")

    out = Image.new("RGB", (w, photo.size[1] + BAR_H), BG)
    out.paste(photo, (0, 0))
    out.paste(bar, (0, photo.size[1]))
    return out


def main() -> None:
    captions = {
        "DK-01-366": ("Tivoli Christmas, Copenhagen", "12 December 2026 \u00b7 17:40 Europe/Copenhagen"),
        "DK-01-367": ("Christmas market, Aarhus", "13 December 2026 \u00b7 17:55 Europe/Copenhagen"),
        "DK-01-368": ("H.C. Andersen Christmas, Odense", "18 December 2026 \u00b7 18:10 Europe/Copenhagen"),
    }
    for entry, spec in SOURCES.items():
        caption, label = captions[entry]
        folder = ROOT / "library" / "world" / "Denmark" / spec["city"]
        folder.mkdir(parents=True, exist_ok=True)
        for kind in ("16x9", "4x5", "9x16"):
            src = spec[kind]
            if not src.exists():
                raise SystemExit(f"missing {src}")
            photo = to_photo(src, kind)
            if photo.size != PHOTO[kind]:
                raise SystemExit(f"bad photo {entry} {kind} {photo.size}")
            master = plate(photo, caption, label)
            expect_h = PHOTO[kind][1] + BAR_H
            if master.size != (PHOTO[kind][0], expect_h):
                raise SystemExit(f"bad master {entry} {kind} {master.size}")
            dest = folder / f"{entry.lower()}-{kind}.png"
            master.save(dest, "PNG", optimize=False)
            digest = embed_art50(dest)
            print(entry, kind, master.size, digest[:12], dest.name)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build image-sitemap.xml from live Denmark scene manifests.

Approved scenes only (approval_status == "Approved"). Candidates stay out,
including held re-renders that never received an approval field.

Per approved scene: one <url> whose loc is the canonical gallery URL plus the
copy-link fragment (#entry_id). One <image:image> per existing 16:9, 4:5, and
9:16 master on disk. Daylight variants are not masters and are omitted.

Field mapping:
  image:loc          absolute URL of that master
  image:caption      scene caption
  image:title        "{site}, {City}" where site is the gallery name
  image:geo_location "{City}, {Country}" from the manifest
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
WORLD = ROOT / "library" / "world"
OUT = ROOT / "image-sitemap.xml"

ORIGIN = "https://devlij.github.io/jason-ds-vision-denmark-preview"
# Image bytes live in the assets repo. Page <loc> values stay on ORIGIN.
ASSET_ORIGIN = "https://devlij.github.io/jason-ds-vision-denmark-assets"
# Public site name, matching the gallery <title> / heading (U+2019).
SITE_NAME = "Jason D\u2019s Vision"

# Night masters only. Daylight files use a "-daylight-" infix and are skipped.
FORMATS = (
    ("16x9", "-16x9.png"),
    ("4x5", "-4x5.png"),
    ("9x16", "-9x16.png"),
)


def robots_txt() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {ORIGIN}/sitemap.xml\n"
        f"Sitemap: {ORIGIN}/image-sitemap.xml\n"
    )


def xml_text(value: str) -> str:
    return escape(value, {"'": "&apos;", '"': "&quot;"})


def absolute_url(rel: str) -> str:
    """RFC 3986-encode a library path and prefix the assets CDN.

    Each path segment is UTF-8 percent-encoded (space is %20). That is the
    same encoding the browser applies when it requests the gallery's img src
    and download hrefs, and the encoding already used in image-sitemap.xml.
    """
    encoded = "/".join(quote(part, safe="") for part in rel.split("/"))
    return f"{ASSET_ORIGIN}/{encoded}"


def scene_title(city: str) -> str:
    return f"{SITE_NAME}, {city}"


def scene_alt(caption: str, city: str) -> str:
    return f"{caption} \u2014 {scene_title(city)}"


def geo_location(city: str, country: str) -> str:
    return f"{city}, {country}"


def master_rels(data: dict) -> list[tuple[str, str]]:
    """Return (format, library-relative path) for masters that exist on disk."""
    night = data.get("file_16x9") or ""
    found: list[tuple[str, str]] = []
    if night.endswith("-16x9.png") and "/" in night:
        folder, name = night.rsplit("/", 1)
        stem = name[: -len("-16x9.png")]
        for label, suffix in FORMATS:
            rel = f"{folder}/{stem}{suffix}"
            if (WORLD / rel).is_file():
                found.append((label, rel))
        return found
    for label, key in (("16x9", "file_16x9"), ("4x5", "file_4x5"), ("9x16", "file_9x16")):
        rel = data.get(key)
        if rel and (WORLD / rel).is_file():
            found.append((label, rel))
    return found


def load_approved() -> tuple[list[dict], list[str]]:
    approved: list[dict] = []
    skipped: list[str] = []
    for path in sorted(MANIFESTS.glob("DK-01-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data.get("entry_id") or path.stem
        if data.get("approval_status") == "Approved":
            approved.append(data)
        else:
            skipped.append(entry)
    approved.sort(key=lambda item: item["entry_id"])
    skipped.sort()
    return approved, skipped


def render(approved: list[dict]) -> tuple[str, dict[str, int]]:
    counts = {"scenes": 0, "16x9": 0, "4x5": 0, "9x16": 0, "images": 0}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    for data in approved:
        entry = data["entry_id"]
        caption = data["caption"]
        city = data["city"]
        country = data["country"]
        masters = master_rels(data)
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_text(ORIGIN + '/#' + entry)}</loc>")
        for label, rel in masters:
            loc = absolute_url("library/world/" + rel)
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{xml_text(loc)}</image:loc>")
            lines.append(f"      <image:caption>{xml_text(caption)}</image:caption>")
            lines.append(f"      <image:title>{xml_text(scene_title(city))}</image:title>")
            lines.append(
                f"      <image:geo_location>{xml_text(geo_location(city, country))}</image:geo_location>"
            )
            lines.append("    </image:image>")
            counts[label] += 1
            counts["images"] += 1
        lines.append("  </url>")
        counts["scenes"] += 1
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines), counts


def write_image_sitemap(root: Path | None = None) -> dict[str, int]:
    approved, skipped = load_approved()
    body, counts = render(approved)
    target = (root or ROOT) / "image-sitemap.xml"
    target.write_text(body, encoding="utf-8")
    counts["skipped"] = len(skipped)
    return counts


def main() -> None:
    approved, skipped = load_approved()
    body, counts = render(approved)
    OUT.write_text(body, encoding="utf-8")
    print(
        "scenes {scenes} images {images} 16x9 {c16} 4x5 {c45} 9x16 {c916} skipped {skip}".format(
            scenes=counts["scenes"],
            images=counts["images"],
            c16=counts["16x9"],
            c45=counts["4x5"],
            c916=counts["9x16"],
            skip=len(skipped),
        )
    )
    if skipped:
        print("skipped " + " ".join(skipped))


if __name__ == "__main__":
    main()

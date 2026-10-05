#!/usr/bin/env python3
"""Confirm every asset URL the Denmark gallery can request maps to library/.

Collects:
  * static URLs in index.html (og:image, DENMARK_META thumbs, any other
    quoted library/world path)
  * image-sitemap.xml <image:loc> values
  * the variant, hero, and download URLs index.html builds for every card
    (ASSET_BASE + 'library/world/' + the scene file fields)

Each URL must resolve to an existing file under library/ in this repo.
Paths are matched after UTF-8 percent-decoding, so a sitemap loc of
.../Faxe%20Ladeplads/... and a page src of .../Faxe Ladeplads/... are the
same asset. That encoding is what the browser sends for the page URLs.

    python3 tools/check_cdn_urls.py
    python3 tools/check_cdn_urls.py --live

--live HEAD-requests each distinct CDN URL and lists non-200 responses.
The assets host may not be published yet; a non-200 report is expected
until that upload finishes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CDN_BASE = "https://devlij.github.io/jason-ds-vision-denmark-assets/"
LIBRARY_PREFIX = "library/world/"
VARIANT_KEYS = (
    "file_16x9",
    "file_4x5",
    "file_9x16",
    "file_16x9_day",
    "file_4x5_day",
    "file_9x16_day",
    "file_16x9_postcard",
    "file_4x5_postcard",
    "file_9x16_postcard",
)


def encode_library_path(rel: str) -> str:
    """Percent-encode each segment the way the gallery sitemap and browser do."""
    return "/".join(quote(part, safe="") for part in rel.split("/"))


def cdn_url(rel: str) -> str:
    if not rel.startswith(LIBRARY_PREFIX):
        raise ValueError(rel)
    return CDN_BASE + encode_library_path(rel)


def repo_rel(url: str) -> str:
    text = unquote(url.split("?", 1)[0].replace("&amp;", "&"))
    idx = text.find(LIBRARY_PREFIX)
    if idx < 0:
        raise ValueError(f"not a library asset URL: {url}")
    rel = text[idx:]
    if rel.endswith("/"):
        raise ValueError(f"directory URL: {url}")
    return rel


def load_json_const(html: str, name: str):
    marker = f"const {name} = "
    start = html.find(marker)
    if start < 0:
        raise SystemExit(f"index.html is missing {name}")
    value, _end = json.JSONDecoder().raw_decode(html, start + len(marker))
    return value


def asset_prefix(html: str) -> str:
    match = re.search(r'const ASSET_BASE = "([^"]+)"', html)
    if not match:
        raise SystemExit("index.html is missing ASSET_BASE")
    base = match.group(1)
    if base != CDN_BASE:
        raise SystemExit(f"ASSET_BASE is {base!r}, expected {CDN_BASE!r}")
    if html.count("ASSET_BASE + 'library/world/'") != 9:
        raise SystemExit("variant paths are not all prefixed with ASSET_BASE")
    return base + LIBRARY_PREFIX


def card_urls(scene: dict, prefix: str) -> set[str]:
    """Mirror index.html render(): variant data-src, hero, and download hrefs."""

    def one(key: str) -> str:
        rel = scene.get(key) or ""
        return (prefix + rel) if rel else ""

    file16 = one("file_16x9")
    file45 = one("file_4x5")
    file916 = one("file_9x16")
    day16 = one("file_16x9_day")
    day45 = one("file_4x5_day")
    day916 = one("file_9x16_day")
    pc16 = one("file_16x9_postcard")
    pc45 = one("file_4x5_postcard")
    pc916 = one("file_9x16_postcard")
    urls = {
        u
        for u in (
            file16,
            file45,
            file916,
            day16,
            day45,
            day916,
            pc16,
            pc45,
            pc916,
        )
        if u
    }
    has_pc = bool(pc16 or pc45 or pc916)
    scene_hero = file16 or file45 or file916
    hero = (pc16 or pc45 or pc916) if has_pc else scene_hero
    dl16 = pc16 if has_pc and pc16 else file16
    dl45 = pc45 if has_pc and pc45 else file45
    dl916 = pc916 if has_pc and pc916 else file916
    for url in (hero, dl16, dl45, dl916):
        if url:
            urls.add(url)
    return urls


def static_urls(html: str) -> set[str]:
    found = set(re.findall(r"""["']([^"']*library/world/[^"']*)["']""", html))
    return {url for url in found if url not in {LIBRARY_PREFIX, "library/world/"}}


def collect(html: str, sitemap: str) -> tuple[set[str], set[str]]:
    scenes = load_json_const(html, "SCENES")
    prefix = asset_prefix(html)
    page_urls: set[str] = set()
    for scene in scenes:
        page_urls |= card_urls(scene, prefix)
    page_urls |= static_urls(html)
    image_urls = set(re.findall(r"<image:loc>(.*?)</image:loc>", sitemap))
    page_locs = re.findall(r"<loc>(.*?)</loc>", sitemap)
    return page_urls | image_urls, set(page_locs)


def head_status(url: str, timeout: float) -> tuple[str, str]:
    request = Request(
        url,
        method="HEAD",
        headers={"User-Agent": "denmark-cdn-url-check"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return str(response.status), ""
    except HTTPError as exc:
        return str(exc.code), ""
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        return "error", str(reason)
    except Exception as exc:  # noqa: BLE001 — report the live failure and continue
        return "error", str(exc)


def check_live(rels: list[str], timeout: float, workers: int) -> int:
    targets = [cdn_url(rel) for rel in rels]
    print(f"live HEAD {CDN_BASE}")
    print(f"checked: {len(targets)}")
    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(head_status, url, timeout): url for url in targets}
        for future in as_completed(futures):
            url = futures[future]
            status, detail = future.result()
            label = status if not detail else f"{status} {detail}"
            counts[label] += 1
            bucket = samples.setdefault(label, [])
            if len(bucket) < 8:
                bucket.append(url)
    non_200 = sum(n for label, n in counts.items() if not label.startswith("200"))
    print(f"non-200: {non_200}")
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {label}: {count}")
        if not label.startswith("200"):
            for url in samples[label]:
                print(f"    {url}")
    return 1 if non_200 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="HEAD-request each CDN URL and report non-200 responses",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    sitemap = (ROOT / "image-sitemap.xml").read_text(encoding="utf-8")
    urls, page_locs = collect(html, sitemap)

    missing: list[tuple[str, str]] = []
    non_cdn: list[str] = []
    encoding_mismatch: list[str] = []
    rels: list[str] = []
    for url in sorted(urls):
        if not url.startswith(CDN_BASE):
            non_cdn.append(url)
        try:
            rel = repo_rel(url)
        except ValueError as exc:
            missing.append((url, str(exc)))
            continue
        rels.append(rel)
        if not (ROOT / rel).is_file():
            missing.append((url, rel))
        # Percent-encoded URLs (image-sitemap locs) must already match the
        # browser's request. Page src/href values keep spaces and Danish
        # letters; the browser encodes those on request, so they are not
        # required to equal the encoded form in the HTML source.
        if "%" in url and url != cdn_url(rel):
            encoding_mismatch.append(f"{url} != {cdn_url(rel)}")

    distinct = sorted(set(rels))
    preview_assets = [url for url in urls if "jason-ds-vision-denmark-preview/library/" in url]
    cdn_pages = [loc for loc in page_locs if "jason-ds-vision-denmark-assets" in loc]

    print(f"distinct asset URLs: {len(distinct)}")
    print(f"url strings: {len(urls)}")
    print(f"missing library files: {len(missing)}")
    print(f"non-cdn urls: {len(non_cdn)}")
    print(f"encoding mismatches: {len(set(encoding_mismatch))}")
    for url, rel in missing[:20]:
        print(f"MISSING {rel}")
        print(f"  from {url}")
    for url in non_cdn[:20]:
        print(f"NON-CDN {url}")
    for item in sorted(set(encoding_mismatch))[:10]:
        print(f"ENCODING {item}")
    for url in preview_assets[:5]:
        print(f"PREVIEW {url}")
    for loc in cdn_pages[:5]:
        print(f"PAGE-ON-CDN {loc}")

    failed = bool(missing or non_cdn or encoding_mismatch or preview_assets or cdn_pages)
    if args.live and distinct:
        live_code = check_live(distinct, args.timeout, args.workers)
        failed = failed or bool(live_code)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

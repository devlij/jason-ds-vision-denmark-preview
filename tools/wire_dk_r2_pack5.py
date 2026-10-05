#!/usr/bin/env python3
"""Wire ▶ 360° for the scenes shipped by static_ambient_dk_r2_pack5.py.

Gallery paths are the staged preview files under assets/. Full CDN URLs are
used only when the assets repo accepted the push (see --cdn). approval_status
is not touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "motion" / "DK-360-r2-pack5-2026-10-05.json"
PROOF = ROOT / "evidence" / "motion" / "DK-360-r2-pack5-2026-10-05-proof.md"
CDN_BASE = "https://devlij.github.io/jason-ds-vision-denmark-assets/assets/"


def clip_name(entry_id: str) -> str:
    return entry_id.lower() + "-motion-10s-4x5.mp4"


def poster_name(entry_id: str) -> str:
    return entry_id.lower() + "-motion-10s-4x5-poster.jpg"


def urls(entry_id: str, cdn: bool) -> tuple[str, str]:
    if cdn:
        return CDN_BASE + clip_name(entry_id), CDN_BASE + poster_name(entry_id)
    return "assets/" + clip_name(entry_id), "assets/" + poster_name(entry_id)


def wire(html: str, motion: dict) -> str:
    if "const DENMARK_MOTION" in html:
        raise SystemExit("DENMARK_MOTION already present; refusing to double-wire")
    css = (
        ".fmt-tab:disabled, .fmt-tab.is-disabled { opacity: 0.4; cursor: default; }\n"
        "    .motion-tab { background: #243049; color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 5px 10px; font: inherit; font-size: 12px; line-height: 1.2; cursor: pointer; }\n"
        "    .motion-tab:hover { border-color: var(--accent); }\n"
        "    .motion-tab.is-active { background: #e8b23a; border-color: #e8b23a; color: #1a1405; font-weight: 700; }\n"
        "    .thumb video.motion-clip { width: 100%; height: auto; display: block; border-radius: 8px; background: #000; aspect-ratio: 4 / 5; object-fit: cover; }"
    )
    old_css = ".fmt-tab:disabled, .fmt-tab.is-disabled { opacity: 0.4; cursor: default; }"
    if html.count(old_css) != 1:
        raise SystemExit("css anchor missing")
    html = html.replace(old_css, css, 1)

    stop_fn = """    function stopCardMotion(card) {
      const v = card.querySelector('video.motion-clip');
      if (v) v.remove();
      const img = card.querySelector('a.thumb img');
      if (img) img.style.display = '';
      const mtab = card.querySelector('.motion-tab');
      if (mtab) {
        mtab.classList.remove('is-active');
        mtab.setAttribute('aria-pressed', 'false');
        mtab.innerHTML = '▶ 360°';
      }
      const link = card.querySelector('a.thumb');
      const ftab = card.querySelector('.fmt-tab.is-active');
      const dfmt = ftab ? ftab.getAttribute('data-format') : '16x9';
      if (link) {
        link.classList.toggle('tall', dfmt === '4x5');
        link.classList.toggle('tall916', dfmt === '9x16');
      }
    }
    function render() {"""
    if html.count("    function render() {") != 1:
        raise SystemExit("render anchor missing")
    html = html.replace("    function render() {", stop_fn, 1)

    tabs_old = "        const tabs = (show16 ? tab('16x9', '16:9') : '') + (show45 ? tab('4x5', '4:5') : '') + (show916 ? tab('9x16', '9:16') : '');"
    tabs_new = """        const motionPair = (typeof DENMARK_MOTION !== "undefined") ? DENMARK_MOTION[s.entry_id] : null;
        const motion = motionPair && motionPair[0] ? motionPair[0] : "";
        const motionPoster = motionPair && motionPair[1] ? motionPair[1] : "";
        const motionBtn = motion
          ? `<button type="button" class="motion-tab" data-motion="${esc(motion)}"${motionPoster ? ` data-poster="${esc(motionPoster)}"` : ""} title="Play the 360° daylight motion clip" aria-pressed="false">\\u25B6 360\\u00B0</button>`
          : "";
        const tabs = (show16 ? tab('16x9', '16:9') : '') + (show45 ? tab('4x5', '4:5') : '') + (show916 ? tab('9x16', '9:16') : '') + motionBtn;"""
    if html.count(tabs_old) != 1:
        raise SystemExit("tabs anchor missing")
    html = html.replace(tabs_old, tabs_new, 1)

    replacements = [
        (
            "        if (!ncard) return;\n        ntab.classList.add('is-active');",
            "        if (!ncard) return;\n        stopCardMotion(ncard);\n        ntab.classList.add('is-active');",
        ),
        (
            "        if (!card) return;\n        const on = !ptab.classList.contains('is-active');",
            "        if (!card) return;\n        stopCardMotion(card);\n        const on = !ptab.classList.contains('is-active');",
        ),
        (
            "        if (!dcard) return;\n        const isDay = !dtab.classList.contains('is-active');",
            "        if (!dcard) return;\n        stopCardMotion(dcard);\n        const isDay = !dtab.classList.contains('is-active');",
        ),
        (
            "      if (!card) return;\n      const fmt = tab.getAttribute('data-format');",
            "      if (!card) return;\n      stopCardMotion(card);\n      const fmt = tab.getAttribute('data-format');",
        ),
    ]
    for old, new in replacements:
        if html.count(old) != 1:
            raise SystemExit(f"handler anchor missing: {old[:60]!r}")
        html = html.replace(old, new, 1)

    click_old = "    grid.addEventListener('click', (event) => {\n      const nbtn = event.target.closest('.narrate');"
    click_new = """    grid.addEventListener('click', (event) => {
      if (event.target.closest('video.motion-clip')) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      const mtab = event.target.closest('.motion-tab');
      if (mtab) {
        event.preventDefault();
        const mcard = mtab.closest('.card');
        if (!mcard) return;
        if (mcard.querySelector('video.motion-clip')) { stopCardMotion(mcard); return; }
        document.querySelectorAll('article.card').forEach(function (other) {
          if (other !== mcard) stopCardMotion(other);
        });
        const mlink = mcard.querySelector('a.thumb');
        const mimg = mlink && mlink.querySelector('img');
        const vid = document.createElement('video');
        vid.className = 'motion-clip';
        vid.src = mtab.getAttribute('data-motion');
        const poster = mtab.getAttribute('data-poster');
        if (poster) vid.poster = poster;
        vid.autoplay = true; vid.loop = true; vid.muted = true; vid.playsInline = true; vid.controls = false;
        vid.defaultMuted = true;
        vid.setAttribute('muted', '');
        vid.setAttribute('autoplay', '');
        vid.setAttribute('loop', '');
        vid.setAttribute('playsinline', '');
        vid.disablePictureInPicture = true;
        vid.setAttribute('controlsList', 'nodownload nofullscreen noremoteplayback');
        if (mimg) mimg.style.display = 'none';
        if (mlink) { mlink.classList.add('tall'); mlink.classList.remove('tall916'); mlink.appendChild(vid); }
        mtab.classList.add('is-active');
        mtab.setAttribute('aria-pressed', 'true');
        mtab.innerHTML = '\\u2715 Close';
        vid.play().catch(function () {});
        return;
      }
      const nbtn = event.target.closest('.narrate');"""
    if html.count(click_old) != 1:
        raise SystemExit("click anchor missing")
    html = html.replace(click_old, click_new, 1)

    blob = json.dumps(motion, separators=(",", ":"), ensure_ascii=False)
    script = (
        "<script>\n"
        "/* Daylight 360 clips. Entry is [mp4, poster]. Absent entries have no button. "
        "Candidate clips only; approval_status is not changed here. */\n"
        f"const DENMARK_MOTION = {blob};\n"
        "</script>\n"
        "<script>\nconst DENMARK_META = "
    )
    anchor = "<script>\nconst DENMARK_META = "
    if html.count(anchor) != 1:
        raise SystemExit("DENMARK_META anchor missing")
    html = html.replace(anchor, script, 1)
    return html


def fmt_num(n: float) -> str:
    text = f"{n:.3f}".rstrip("0").rstrip(".")
    return text


def write_proof(evidence: dict, cdn: bool, cdn_note: str) -> None:
    shipped = [s for s in evidence["scenes"] if s.get("status") == "shipped"]
    lumas = [v for s in shipped for v in s["probe"]["luma_samples"]]
    maes = [s["probe"]["ends_mae"] for s in shipped]
    rows = []
    for s in shipped:
        dark = min(s["probe"]["luma_samples"])
        rows.append(
            f"| {s['entry_id']} | {s.get('caption') or ''} | ken-burns-sweep | "
            f"10.0s 864×1080 MAE {fmt_num(s['probe']['ends_mae'])} luma {fmt_num(dark)} |"
        )
    first = shipped[0]["entry_id"] if shipped else "n/a"
    last = shipped[-1]["entry_id"] if shipped else "n/a"
    asset_lines = []
    for s in shipped:
        mp4, poster = urls(s["entry_id"], cdn=False)
        asset_lines.append(f"- `{mp4}`")
        asset_lines.append(f"- `{poster}`")
    path_note = (
        "Gallery `▶ 360°` points at the full CDN URLs "
        f"(`{CDN_BASE}<id>-motion-10s-4x5.mp4` and the matching poster)."
        if cdn
        else "Gallery `▶ 360°` points at those preview paths."
    )
    text = f"""# Denmark 360 r2 pack 5 — proof note

Candidate clips only. This note is the baker's record. It is not Cosmo QC and it is not an approval. `approval_status` on the scene cards was not changed.

Work order `wo-360-kickoff-denmark-20261005` (Jason, 2026-10-05). Image-to-video is not available. These clips use the October 2 France/Netherlands ffmpeg contingency: a Ken Burns pan, the same sideways sweep as pack 1 (`tools/static_ambient_dk_r2_pack1.py` on draft PR #79), pack 2 (`tools/static_ambient_dk_r2_pack2.py` on draft PR #82), pack 3 (`tools/static_ambient_dk_r2_pack3.py` on draft PR #83), and pack 4 (`tools/static_ambient_dk_r2_pack4.py` on draft PR #84). No zoom, orbit, roll, or vertical move. No masked locked-camera ambient. Open Candidate drafts #32–#56 were not edited. Draft PRs #79, #82, #83, and #84 were not edited. Scenes already wired there were not regenerated.

Selection walks `DENMARK_META` after pack 4. DK-01-209 through DK-01-272 are `night` and each manifest carries an interim `daylight_variant`. Those 64 scenes are not eligible. Native daytime after pack 4 resumes at DK-01-337. The next 20 native daytime primaries are {first} through {last}. None of those manifests has a `daylight_variant`. Postcard files were not opened. DK-01-357 through DK-01-365 are also native daytime and were left for a later pack.

Source masters are the native daytime 16:9 primaries on the Denmark assets CDN. Each file's SHA-256 matched `manifests/DK-01-*.json` `sha256_16x9`. The label bar was cropped (top 1080 of 1920×1270) before the sweep. `DENMARK_META` time is `day` for every plated scene.

Self-QC for every shipped clip: 864×1080, 240 frames, 10.0s, h264, yuv420p, 24 fps, +faststart, no audio, sampled luma above black, first-to-last frame MAE above the locked-hold floor. One attempt per scene. No self-QC failures, so the three-different-scenes stop did not fire.

| Scene | Caption | Method | Self-QC |
|---|---|---|---|
{chr(10).join(rows)}

MAE range {fmt_num(min(maes))}–{fmt_num(max(maes))} (locked-hold floor is 8). Sampled luma {fmt_num(min(lumas))}–{fmt_num(max(lumas))}. The luma column is the darkest of the five sampled frames.

## Skipped

DK-01-209 through DK-01-272 (64 scenes): night-only / interim daylight. `DENMARK_META` time is `night` and each manifest has `daylight_variant`. Not baked.

Already wired, not regenerated:

- Pack 1 draft PR #79: DK-01-193–208 and DK-01-273–276
- Pack 2 draft PR #82: DK-01-277–296
- Pack 3 draft PR #83: DK-01-297–316
- Pack 4 draft PR #84: DK-01-317–336

No QC failures. DK-01-357 and later were not reached; the pack stopped after {len(shipped)} shipped scenes.

Gallery `▶ 360°` buttons exist only for these {len(shipped)} cards. Do not merge.

## Assets

{cdn_note}

{chr(10).join(asset_lines)}

{path_note} Do not merge.
"""
    # The "no QC failures / left for later" sentences assume a clean 20-scene run.
    # Rewrite those sentences from the evidence when the run was not that shape.
    fails = evidence.get("qc_fail") or []
    if fails or evidence.get("stopped_after_three_qc_failures") or len(shipped) != 20:
        text = text.replace(
            "One attempt per scene. No self-QC failures, so the three-different-scenes stop did not fire.",
            "One attempt per scene. "
            + (
                "Self-QC failures: " + ", ".join(fails) + ". "
                + (
                    "Three consecutive failures on three different scenes stopped the run."
                    if evidence.get("stopped_after_three_qc_failures")
                    else "The three-different-scenes stop did not fire."
                )
            ),
        )
    PROOF.write_text(text)


def main() -> None:
    cdn = "--cdn" in sys.argv
    cdn_note = sys.argv[sys.argv.index("--note") + 1] if "--note" in sys.argv else ""
    evidence = json.loads(EVIDENCE.read_text())
    shipped = evidence["shipped"]
    if not shipped:
        raise SystemExit("nothing shipped")
    motion = {eid: list(urls(eid, cdn)) for eid in shipped}
    index = ROOT / "index.html"
    index.write_text(wire(index.read_text(), motion))
    if not cdn_note:
        cdn_note = (
            "CDN push was not requested for this wiring pass. "
            "Mp4s and posters are staged in this preview repo under `assets/`."
        )
    write_proof(evidence, cdn, cdn_note)
    print(json.dumps({"wired": shipped, "cdn": cdn, "proof": str(PROOF)}))


if __name__ == "__main__":
    main()

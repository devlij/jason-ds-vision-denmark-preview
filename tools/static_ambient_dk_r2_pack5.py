#!/usr/bin/env python3
"""Denmark 360 r2 pack 5 — FR/NL sideways-sweep contingency.

Work order wo-360-kickoff-denmark-20261005. Image-to-video is not used.
This is the October 2 France/Netherlands ffmpeg path (tools/static_ambient.py
--sweep): a slow left-to-right glide across the native daytime 16:9 plate.
The label bar under the photo is cropped off. An 864-wide window then eases
across 18% of the 1920-wide plate. No zoom, orbit, roll, vertical move, or
generated frames. The camera move is the Ken Burns pan those packs shipped.

Output matches the Denmark Candidate packs: 864×1080, 240 frames, 10.0s,
h264, yuv420p, +faststart, no audio, plus a poster jpg.

A scene that fails self-QC is not retried. Three self-QC failures in a row
on three different scenes stop the run.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CDN = "https://devlij.github.io/jason-ds-vision-denmark-assets/library/world/"
FPS = 24
FRAMES = 240
PHOTO_W = 864
PHOTO_H = 1080
PLATE_W = 1920
SWEEP_TRAVEL_FRAC = 0.18
# Pack 1 plated DK-01-193–208 and DK-01-273–276. Pack 2 plated DK-01-277–296.
# Pack 3 plated DK-01-297–316. Pack 4 plated DK-01-317–336.
# Do not regenerate those. Do not edit draft PRs #79, #82, #83, or #84.
PACK1_IDS = {f"DK-01-{n:03d}" for n in list(range(193, 209)) + list(range(273, 277))}
PACK2_IDS = {f"DK-01-{n:03d}" for n in range(277, 297)}
PACK3_IDS = {f"DK-01-{n:03d}" for n in range(297, 317)}
PACK4_IDS = {f"DK-01-{n:03d}" for n in range(317, 337)}
ALREADY_WIRED = PACK1_IDS | PACK2_IDS | PACK3_IDS | PACK4_IDS
# Night-only interim daylight (DENMARK_META time night + daylight_variant). Not eligible.
NIGHT_INTERIM_IDS = [f"DK-01-{n:03d}" for n in range(209, 273)]
# Native daytime after pack 4. Bake until 20 ship, or through DK-01-365 if fewer remain.
CANDIDATE_IDS = [f"DK-01-{n:03d}" for n in range(337, 366)]
TARGET_SHIPPED = 20

# Center-anchored 18% glide. start = (960 - 432) - travel/2.
TRAVEL = PLATE_W * SWEEP_TRAVEL_FRAC
X0 = (PLATE_W / 2.0 - PHOTO_W / 2.0) - TRAVEL / 2.0
X1 = X0 + TRAVEL


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def quote_path(rel: str) -> str:
    from urllib.parse import quote

    return "/".join(quote(part) for part in rel.split("/"))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True)


def ffprobe_json(path: Path) -> dict:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height,nb_frames,codec_name,pix_fmt,avg_frame_rate",
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            str(path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-500:])
    return json.loads(proc.stdout)


def image_size(path: Path) -> tuple[int, int]:
    info = ffprobe_json(path)
    stream = info["streams"][0]
    return int(stream["width"]), int(stream["height"])


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "dk-360-r2-pack5"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())


def load_manifest(entry_id: str) -> dict:
    path = ROOT / "manifests" / f"{entry_id}.json"
    return json.loads(path.read_text())


def meta_time(entry_id: str) -> str:
    html = (ROOT / "index.html").read_text()
    marker = "const DENMARK_META = "
    start = html.find(marker)
    if start < 0:
        raise RuntimeError("DENMARK_META missing")
    blob = html[start:]
    key = f'"{entry_id}": ['
    i = blob.find(key)
    if i < 0:
        raise RuntimeError(f"{entry_id} missing from DENMARK_META")
    chunk = blob[i : i + 400]
    # ["Region", "day", ...
    parts = chunk.split('"', 6)
    # 0=prefix, 1=id, 2=after id, 3=region, 4=after, 5=time
    return parts[5]


def prepare_plate(src: Path, dest: Path) -> str:
    """Crop the label bar. Scale only when the photo is not already 1920×1080."""
    width, height = image_size(src)
    if height < PHOTO_H:
        raise RuntimeError(f"plate {src.name} is {width}x{height}, shorter than {PHOTO_H}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if width == PLATE_W:
        vf = f"crop={PLATE_W}:{PHOTO_H}:0:0"
        note = f"crop top {PHOTO_H} of {width}x{height}"
    else:
        vf = f"crop={width}:{PHOTO_H}:0:0,scale={PLATE_W}:{PHOTO_H}:flags=lanczos"
        note = f"crop top {PHOTO_H} of {width}x{height}, scale to {PLATE_W}x{PHOTO_H}"
    proc = run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-vf",
            vf,
            "-frames:v",
            "1",
            str(dest),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-500:])
    got = image_size(dest)
    if got != (PLATE_W, PHOTO_H):
        raise RuntimeError(f"prepared plate is {got}")
    return note


def encode_sweep(plate: Path, dest: Path) -> None:
    # n/(FRAMES-1) ease-in-out, left to right, no vertical, no zoom.
    x_expr = f"{X0:.4f}+{TRAVEL:.4f}*(0.5-0.5*cos(PI*n/{FRAMES - 1}))"
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-i",
            str(plate),
            "-vf",
            f"crop={PHOTO_W}:{PHOTO_H}:'{x_expr}':0,format=yuv420p",
            "-frames:v",
            str(FRAMES),
            "-r",
            str(FPS),
            "-an",
            "-c:v",
            "libx264",
            "-profile:v",
            "high",
            "-level:v",
            "3.2",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-preset",
            "medium",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-800:])


def write_poster(clip: Path, dest: Path) -> None:
    proc = run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(clip),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(dest),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-400:])


def raw_frame(clip: Path, n: int) -> bytes:
    proc = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(clip),
            "-vf",
            f"select=eq(n\\,{n})",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    if proc.returncode != 0 or len(proc.stdout) != PHOTO_W * PHOTO_H * 3:
        raise RuntimeError(f"frame {n} decode failed ({len(proc.stdout)} bytes)")
    return proc.stdout


def mean_luma(rgb: bytes) -> float:
    # Rec. 601 integer luma, sampled every 16th pixel to stay cheap.
    step = 16 * 3
    total = 0
    count = 0
    for i in range(0, len(rgb) - 2, step):
        r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
        total += (77 * r + 150 * g + 29 * b) >> 8
        count += 1
    return total / count


def frame_mae(a: bytes, b: bytes) -> float:
    step = 16 * 3
    total = 0
    count = 0
    for i in range(0, len(a) - 2, step):
        total += abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2])
        count += 3
    return total / count


def qc_clip(path: Path) -> dict:
    info = ffprobe_json(path)
    stream = info["streams"][0]
    duration = float(info["format"]["duration"])
    problems = []
    if int(stream["width"]) != PHOTO_W or int(stream["height"]) != PHOTO_H:
        problems.append(f"size {stream['width']}x{stream['height']}")
    if stream.get("codec_name") != "h264" or stream.get("pix_fmt") != "yuv420p":
        problems.append(f"codec {stream.get('codec_name')} {stream.get('pix_fmt')}")
    if stream.get("avg_frame_rate") != f"{FPS}/1":
        problems.append(f"fps {stream.get('avg_frame_rate')}")
    if str(stream.get("nb_frames")) != str(FRAMES):
        problems.append(f"frames {stream.get('nb_frames')}")
    if abs(duration - 10.0) > 0.05:
        problems.append(f"duration {duration}")
    audio = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    if audio.stdout.strip():
        problems.append("audio present")
    # moov before mdat is the +faststart layout.
    head = path.read_bytes()[:4096]
    if b"moov" not in head:
        problems.append("moov not in the first 4KB (faststart)")
    samples = [0, 60, 120, 180, 239]
    frames = []
    lumas = []
    for n in samples:
        frame = raw_frame(path, n)
        frames.append(frame)
        luma = mean_luma(frame)
        lumas.append(round(luma, 2))
        if luma < 8.0:
            problems.append(f"black frame n={n} luma={luma:.2f}")
    ends = frame_mae(frames[0], frames[-1])
    if ends < 8.0:
        problems.append(f"frozen or locked hold MAE {ends:.2f}")
    # Adjacent sampled frames should not be identical for the whole clip.
    still = 0
    for a, b in zip(frames, frames[1:]):
        if frame_mae(a, b) < 0.5:
            still += 1
    if still >= 3:
        problems.append("sampled frames are frozen")
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "codec": stream.get("codec_name"),
        "pix_fmt": stream.get("pix_fmt"),
        "nb_frames": stream.get("nb_frames"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "duration": duration,
        "audio": bool(audio.stdout.strip()),
        "faststart": b"moov" in head,
        "luma_samples": lumas,
        "ends_mae": round(ends, 3),
        "problems": problems,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def clip_name(entry_id: str) -> str:
    return entry_id.lower() + "-motion-10s-4x5.mp4"


def poster_name(entry_id: str) -> str:
    return entry_id.lower() + "-motion-10s-4x5-poster.jpg"


def already_wired_reason(entry_id: str) -> str:
    if entry_id in PACK1_IDS:
        return "already wired in pack 1 draft PR #79"
    if entry_id in PACK2_IDS:
        return "already wired in pack 2 draft PR #82"
    if entry_id in PACK3_IDS:
        return "already wired in pack 3 draft PR #83"
    return "already wired in pack 4 draft PR #84"


def bake_one(entry_id: str, work: Path) -> dict:
    manifest = load_manifest(entry_id)
    when = meta_time(entry_id)
    row = {
        "entry_id": entry_id,
        "caption": manifest.get("caption"),
        "method": "ken-burns-sweep",
        "camera": "pan",
        "zoom": False,
        "approval_status_unchanged": manifest.get("approval_status"),
        "attempts": 1,
        "meta_time": when,
    }
    if when != "day":
        row["status"] = "skipped"
        row["reason"] = f"DENMARK_META time is {when}; native daytime only"
        return row
    if "daylight_variant" in manifest:
        row["status"] = "skipped"
        row["reason"] = "interim daylight_variant; native daytime primary only"
        return row
    rel = manifest.get("file_16x9")
    if not rel:
        row["status"] = "qc_fail"
        row["reason"] = "no file_16x9"
        return row
    # Interim daylight files are not the source. Native primary only.
    src = work / f"{entry_id}-16x9.png"
    url = CDN + quote_path(rel)
    try:
        download(url, src)
    except Exception as exc:
        row["status"] = "qc_fail"
        row["reason"] = f"download failed: {exc}"
        return row
    digest = sha256(src)
    expected = manifest.get("sha256_16x9")
    row["anchor"] = {
        "repo_path": f"library/world/{rel}",
        "sha256": digest,
        "manifest_sha256": expected,
        "manifest_sha256_match": digest == expected,
        "bytes": src.stat().st_size,
        "download_url": url,
        "source_kind": "native daytime 16:9 primary",
        "source": "denmark assets CDN",
    }
    if expected and digest != expected:
        row["status"] = "qc_fail"
        row["reason"] = "sha256 does not match manifest sha256_16x9"
        return row
    plate = work / f"{entry_id}-plate.png"
    try:
        row["plate"] = prepare_plate(src, plate)
        dest = ROOT / "assets" / clip_name(entry_id)
        poster = ROOT / "assets" / poster_name(entry_id)
        encode_sweep(plate, dest)
        write_poster(dest, poster)
        probe = qc_clip(dest)
    except Exception as exc:
        row["status"] = "qc_fail"
        row["reason"] = str(exc)
        return row
    row["probe"] = probe
    row["file"] = f"assets/{clip_name(entry_id)}"
    row["poster"] = f"assets/{poster_name(entry_id)}"
    row["window"] = [round(X0, 3), round(X1, 3)]
    row["travel_frac"] = SWEEP_TRAVEL_FRAC
    if probe["problems"]:
        dest.unlink(missing_ok=True)
        poster.unlink(missing_ok=True)
        row["status"] = "qc_fail"
        row["reason"] = "; ".join(probe["problems"])
        return row
    row["status"] = "shipped"
    return row


def main() -> None:
    work = Path("/tmp/dk-360-r2-pack5")
    work.mkdir(parents=True, exist_ok=True)
    scenes = []
    for entry_id in NIGHT_INTERIM_IDS:
        manifest = load_manifest(entry_id)
        when = meta_time(entry_id)
        scenes.append(
            {
                "entry_id": entry_id,
                "caption": manifest.get("caption"),
                "status": "skipped",
                "reason": (
                    f"DENMARK_META time is {when}; interim daylight_variant present; "
                    "night-only / interim-daylight skipped"
                    if "daylight_variant" in manifest
                    else f"DENMARK_META time is {when}; native daytime only"
                ),
                "meta_time": when,
                "interim_daylight": "daylight_variant" in manifest,
                "attempts": 0,
            }
        )
    for entry_id in sorted(ALREADY_WIRED):
        scenes.append(
            {
                "entry_id": entry_id,
                "status": "skipped",
                "reason": already_wired_reason(entry_id),
                "attempts": 0,
            }
        )
    streak = 0
    stopped = False
    shipped_n = 0
    for entry_id in CANDIDATE_IDS:
        if entry_id in ALREADY_WIRED:
            continue
        if stopped or shipped_n >= TARGET_SHIPPED:
            break
        print(f"baking {entry_id}", flush=True)
        row = bake_one(entry_id, work)
        scenes.append(row)
        print(json.dumps({"entry_id": entry_id, "status": row["status"], "reason": row.get("reason")}), flush=True)
        if row["status"] == "shipped":
            shipped_n += 1
            streak = 0
        elif row["status"] == "qc_fail":
            streak += 1
            if streak >= 3:
                stopped = True
        else:
            streak = 0
    evidence = {
        "work_order": "wo-360-kickoff-denmark-20261005",
        "pack": "DK-360-r2-pack5",
        "date": "2026-10-05",
        "target_shipped": TARGET_SHIPPED,
        "selection_note": (
            "Next native-daytime scenes after pack 4 (DK-01-317–336). "
            "Walk starts at DK-01-337. DK-01-209–272 are night in DENMARK_META and carry an interim daylight_variant; skipped. "
            "Open Candidate drafts #32–#56 were not edited. Draft PRs #79, #82, #83, and #84 were not edited. "
            "Scenes already wired in those drafts were not regenerated."
        ),
        "method": "ken-burns-sweep",
        "method_note": (
            "October 2 France/Netherlands sideways sweep (ffmpeg crop glide, "
            "18% of the 1920 plate, ease in-out, no zoom). Not image-to-video. "
            "Not the masked locked-camera ambient used in Candidate packs #32–#56."
        ),
        "i2v": "unavailable",
        "cosmo_qc": None,
        "approval_status": "unchanged",
        "cdn_push": "pending",
        "spec": {
            "width": PHOTO_W,
            "height": PHOTO_H,
            "frames": FRAMES,
            "fps": FPS,
            "duration_s": 10.0,
            "codec": "h264",
            "pix_fmt": "yuv420p",
            "faststart": True,
            "audio": False,
            "travel_frac": SWEEP_TRAVEL_FRAC,
            "window_x": [X0, X1],
        },
        "stopped_after_three_qc_failures": stopped,
        "scenes": scenes,
        "shipped": [s["entry_id"] for s in scenes if s.get("status") == "shipped"],
        "skipped": [s["entry_id"] for s in scenes if s.get("status") == "skipped"],
        "qc_fail": [s["entry_id"] for s in scenes if s.get("status") == "qc_fail"],
    }
    out = ROOT / "evidence" / "motion" / "DK-360-r2-pack5-2026-10-05.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"shipped": evidence["shipped"], "qc_fail": evidence["qc_fail"], "stopped": stopped, "shipped_n": shipped_n}))
    if stopped:
        sys.exit(3)


if __name__ == "__main__":
    main()

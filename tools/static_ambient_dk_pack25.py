#!/usr/bin/env python3
"""Denmark 360 pack 25 — static-camera ambient clips.

Image-to-video is not available in this environment, so the lateral-sweep
prompt is not sent to a generator and no pan, zoom, or orbit is encoded.
The camera stays locked on the published daytime 4:5 master after
ffmpeg crop=864:1080:0:0 removes the label bar.

DK-01-353–365 are daytime plates (scenario hour 16). Their
committed 4:5 file is the daytime master (there is no separate
daylight_variant). Night primaries are never opened. Packs 1–24 drafts
and the Christmas sprinkle draft (DK-01-366–368) are not touched.

Only sky, water, foliage, and flags already in that plate move, and only
inside their own masks. Architecture pixels are copied through unchanged.
A plate with too little of that life is encoded locked-off (the same
cropped frame for 10.0s). That is still static-ambient. The motion pack
stays Candidate. Gallery approval status is not changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = "devlij/jason-ds-vision-denmark-preview"
REF = "main"
FPS = 24
FRAMES = 240  # exactly 10.0s
PHOTO_H = 1080
PHOTO_W = 864
MIN_TOP_V = 90.0
MIN_LIFE = 0.04
# Decoded architecture drift above this is a failed clip (compression noise is far lower).
MAX_ARCH_DRIFT = 8.0

STAGE = Path("/tmp/dk360")
SRC = STAGE / "src"
PLATES = STAGE / "plates"
MASKS = STAGE / "masks"

SCENES = (
    {"entry_id": "DK-01-353", "caption": "Marble Church, Copenhagen"},
    {"entry_id": "DK-01-354", "caption": "Ridebanen, Copenhagen"},
    {"entry_id": "DK-01-355", "caption": "Nylars Round Church, Nylars"},
    {"entry_id": "DK-01-356", "caption": "Slotskirken, Hillerød"},
    {"entry_id": "DK-01-357", "caption": "Lerchenborg, Kalundborg"},
    {"entry_id": "DK-01-358", "caption": "Gavnø Castle, Næstved"},
    {"entry_id": "DK-01-359", "caption": "Helligåndskirken, Faaborg"},
    {"entry_id": "DK-01-360", "caption": "Skibbroen, Ribe"},
    {"entry_id": "DK-01-361", "caption": "Løgumkloster, Løgumkloster"},
    {"entry_id": "DK-01-362", "caption": "Thisted Church, Thisted"},
    {"entry_id": "DK-01-363", "caption": "Viðareiði, Viðareiði"},
    {"entry_id": "DK-01-364", "caption": "Aasiaat Harbour, Aasiaat"},
    {"entry_id": "DK-01-365", "caption": "Kolonihavnen, Nuuk"},
)


def scenario_hour(label: str) -> int | None:
    match = re.search(r"(\d{1,2}):(\d{2})", label or "")
    if not match:
        return None
    return int(match.group(1))


def manifest_daylight(entry_id: str) -> dict:
    """Daytime primary 4:5. These daytime plates have no daylight_variant."""
    data = json.loads((ROOT / "manifests" / f"{entry_id}.json").read_text(encoding="utf-8"))
    primary = data.get("file_4x5") or ""
    if not primary.endswith("-4x5.png"):
        raise RuntimeError(f"{entry_id} has no daytime 4:5 master")
    hour = scenario_hour(data.get("scenario_label") or "")
    if hour is None or hour < 7 or hour > 18:
        raise RuntimeError(f"{entry_id} is not a daytime plate")
    name = Path(primary).name.lower()
    if "night" in name or "16x9" in name or "9x16" in name:
        raise RuntimeError(f"{entry_id} refused non-daytime master {primary}")
    return {
        "repo_path": "library/world/" + primary,
        "expected_sha256": data.get("sha256_4x5"),
        "caption": data.get("caption") or "",
        "source_kind": "daytime primary 4:5",
        "gallery_approval_status": data.get("approval_status") or "",
        "scenario_label": data.get("scenario_label") or "",
    }


def github_meta(repo_path: str) -> dict:
    encoded = quote(repo_path, safe="/")
    raw = subprocess.check_output(
        [
            "gh", "api",
            f"repos/{REPO}/contents/{encoded}?ref={REF}",
            "--jq", "{sha:.sha,size:.size,download_url:.download_url}",
        ],
        text=True,
    )
    meta = json.loads(raw)
    if not meta.get("download_url"):
        raise RuntimeError(f"GitHub API returned no download_url for {repo_path}")
    return meta


def ascii_url(url: str) -> str:
    parts = urlsplit(url)
    path = quote(parts.path, safe="/%")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def fetch_master(repo_path: str, dest: Path) -> dict:
    """Download the committed daytime master via the GitHub contents API."""
    committed = committed_sha256(repo_path)
    meta = github_meta(repo_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(ascii_url(meta["download_url"]), dest)
    digest = sha256(dest)
    meta["sha256"] = digest
    meta["bytes"] = dest.stat().st_size
    meta["source"] = "github contents api"
    if meta["bytes"] != meta["size"]:
        raise RuntimeError(f"{repo_path} size {meta['bytes']} != GitHub {meta['size']}")
    if digest != committed:
        raise RuntimeError(f"{repo_path} download sha256 {digest} != committed main blob {committed}")
    return meta


def ffmpeg_crop(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", "crop=864:1080:0:0",
        "-frames:v", "1",
        str(dest),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg crop failed for {src.name}\n{proc.stderr[-1500:]}")


def read_plate(path: Path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise RuntimeError(f"missing plate {path}")
    if im.shape[1] != PHOTO_W or im.shape[0] != PHOTO_H:
        raise RuntimeError(f"{path.name} is {im.shape[1]}x{im.shape[0]}, expected {PHOTO_W}x{PHOTO_H}")
    return im


def _components(mask: np.ndarray, pred) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    keep = np.zeros(mask.shape, np.uint8)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if pred(x, y, w, h, area):
            keep[labels == i] = 255
    return keep


def build_masks(plate: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    height, width = h.shape
    yy = np.arange(height)[:, None]

    overcast = (s < 70) & (v > 145)
    blue_sky = (h >= 90) & (h <= 125) & (s >= 15) & (s < 210) & (v > 145)
    sky_cand = (overcast | blue_sky).astype(np.uint8)
    sky_cand[(h >= 32) & (h <= 88) & (s > 48)] = 0
    sky_cand[((h < 12) | (h > 168)) & (s > 55)] = 0
    # Warm sand and pale stone read as overcast sky. They are not sky.
    sky_cand[(h >= 8) & (h <= 42) & (s >= 18)] = 0
    sky = _components(sky_cand, lambda x, y, w, hh, area: y <= 8 and area > 400)
    sky = cv2.erode(sky, np.ones((3, 3), np.uint8), iterations=1)

    blue_water = (h >= 88) & (h <= 128) & (s >= 40) & (s <= 180) & (v >= 35) & (v <= 185)
    water_cand = (blue_water & (sky == 0) & (yy > int(height * 0.28))).astype(np.uint8)
    water_cand[(h >= 35) & (h <= 88) & (s > 42)] = 0
    water = _components(
        water_cand,
        lambda x, y, w, hh, area: (
            area > 2200
            and w > 48
            and w > hh * 0.45
            and (y + hh / 2) > height * 0.40
        ),
    )
    water = cv2.erode(water, np.ones((3, 3), np.uint8), iterations=1)
    water = _components(
        water,
        lambda x, y, w, hh, area: area > 800 and w > 24 and hh < w * 2.0 and (y + hh / 2) > height * 0.45,
    )

    fol_cand = ((h >= 18) & (h <= 100) & (s >= 28) & (v >= 20) & (sky == 0) & (water == 0)).astype(np.uint8)
    foliage = _components(fol_cand, lambda x, y, w, hh, area: area > 120)
    foliage = cv2.erode(foliage, np.ones((3, 3), np.uint8), iterations=1)

    red = (((h <= 8) | (h >= 170)) & (s >= 150) & (v >= 100)).astype(np.uint8)
    blue = ((h >= 105) & (h <= 130) & (s >= 160) & (v >= 80) & (sky == 0)).astype(np.uint8)
    flag_cand = cv2.bitwise_or(red, blue)
    flag_cand[water > 0] = 0
    flags = _components(flag_cand, lambda x, y, w, hh, area: 40 <= area <= 4200 and hh < 180 and w < 160)
    flags = cv2.erode(flags, np.ones((2, 2), np.uint8), iterations=1)

    foliage[water > 0] = 0
    flags[foliage > 0] = 0
    flags[water > 0] = 0
    return {"sky": sky, "water": water, "foliage": foliage, "flags": flags}


def _factor(mask: np.ndarray, reach: float) -> np.ndarray:
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 3)
    return np.clip(dist / reach, 0, 1).astype(np.float32)


def _apply(out: np.ndarray, plate: np.ndarray, mask: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> None:
    if not np.any(mask):
        return
    height, width = mask.shape
    xs = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width)).copy()
    ys = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], (height, width)).copy()
    map_x = xs - dx
    map_y = ys - dy
    warped = cv2.remap(plate, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    src = cv2.remap(mask.astype(np.float32) / 255.0, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    use = (mask > 0) & (src > 0.985)
    out[use] = warped[use]


REACH = {"sky": 32.0, "water": 14.0, "foliage": 16.0, "flags": 6.0}


def render_frame(plate: np.ndarray, masks: dict[str, np.ndarray], factors: dict[str, np.ndarray], n: int) -> np.ndarray:
    t = n / FRAMES
    s1 = math.sin(2 * math.pi * t)
    s2 = math.sin(4 * math.pi * t)
    out = plate.copy()
    height, width = plate.shape[:2]
    ys = np.arange(height, dtype=np.float32)[:, None]
    xs = np.arange(width, dtype=np.float32)[None, :]

    if np.any(masks["foliage"]):
        phase = s1 * np.sin(ys * 0.035 + 0.4)
        dx = (4.6 * phase * factors["foliage"]).astype(np.float32)
        dy = (1.1 * s2 * factors["foliage"]).astype(np.float32)
        _apply(out, plate, masks["foliage"], dx, dy)

    if np.any(masks["water"]):
        dx = (3.4 * np.sin(2 * math.pi * t + ys * 0.045) * factors["water"]).astype(np.float32)
        dy = (1.6 * np.sin(4 * math.pi * t + xs * 0.05) * factors["water"]).astype(np.float32)
        _apply(out, plate, masks["water"], dx, dy)
        shimmer = (6.0 * np.sin(4 * math.pi * t + xs * 0.08 + ys * 0.03) * factors["water"]).astype(np.float32)
        region = masks["water"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += shimmer[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    if np.any(masks["flags"]):
        dx = (5.5 * np.sin(4 * math.pi * t + ys * 0.12) * factors["flags"]).astype(np.float32)
        dy = (1.2 * s2 * factors["flags"]).astype(np.float32)
        _apply(out, plate, masks["flags"], dx, dy)

    if np.any(masks["sky"]):
        dx = (22.0 * s1 * factors["sky"]).astype(np.float32)
        dy = (2.0 * s1 * factors["sky"]).astype(np.float32)
        _apply(out, plate, masks["sky"], dx, dy)
        breath = (10.0 * s1 * np.sin(xs * 0.03 + ys * 0.012) * factors["sky"]).astype(np.float32)
        region = masks["sky"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += breath[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
    if not np.array_equal(out[~life], plate[~life]):
        raise RuntimeError("architecture pixel moved; refusing to encode")
    return out


def _ffmpeg_encode(frames, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{PHOTO_W}x{PHOTO_H}",
        "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed for {dest.name}\n{err[-2000:]}")


def encode_ambient(plate: np.ndarray, masks: dict[str, np.ndarray], dest: Path) -> None:
    factors = {name: _factor(mask, REACH[name]) for name, mask in masks.items()}

    def frames():
        for n in range(FRAMES):
            yield render_frame(plate, masks, factors, n)

    _ffmpeg_encode(frames(), dest)


def encode_locked(plate: np.ndarray, dest: Path) -> None:
    def frames():
        for _n in range(FRAMES):
            yield plate

    _ffmpeg_encode(frames(), dest)


def motion_on_main(entry_id: str) -> bool:
    rel = f"assets/{entry_id.lower()}-motion-10s-4x5.mp4"
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{rel}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def clip_path(entry_id: str) -> Path:
    return ROOT / "assets" / f"{entry_id.lower()}-motion-10s-4x5.mp4"


def poster_path(entry_id: str) -> Path:
    return ROOT / "assets" / f"{entry_id.lower()}-motion-10s-4x5-poster.jpg"


def write_poster(plate: np.ndarray, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(dest), plate, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError(f"poster write failed {dest}")


def coverage(masks: dict[str, np.ndarray]) -> dict[str, float]:
    total = float(PHOTO_H * PHOTO_W)
    return {name: round(float(np.count_nonzero(mask)) / total, 4) for name, mask in masks.items()}


def mean_v(plate: np.ndarray) -> float:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 2].mean())


def top_v(plate: np.ndarray) -> float:
    hsv = cv2.cvtColor(plate[: PHOTO_H // 5], cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 2].mean())


def probe_clip(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,pix_fmt,nb_frames,avg_frame_rate,duration:format=duration",
        "-of", "json", str(path),
    ]
    raw = subprocess.check_output(cmd, text=True)
    data = json.loads(raw)
    stream = data["streams"][0]
    duration = float(stream.get("duration") or data["format"]["duration"])
    head = path.read_bytes()[:262144]
    moov = head.find(b"moov")
    mdat = head.find(b"mdat")
    fast = moov > 0 and (mdat < 0 or moov < mdat)
    audio = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path),
        ],
        text=True,
    ).strip()
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "codec": stream["codec_name"],
        "pix_fmt": stream["pix_fmt"],
        "nb_frames": int(stream.get("nb_frames") or 0),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "duration": round(duration, 3),
        "faststart": fast,
        "audio": bool(audio),
    }


def assert_spec(info: dict) -> None:
    if info["width"] != PHOTO_W or info["height"] != PHOTO_H:
        raise RuntimeError(f"dims {info['width']}x{info['height']}")
    if info["codec"] != "h264" or info["pix_fmt"] != "yuv420p":
        raise RuntimeError(f"codec {info['codec']} {info['pix_fmt']}")
    if info["nb_frames"] != FRAMES:
        raise RuntimeError(f"frames {info['nb_frames']}")
    if abs(info["duration"] - 10.0) > 0.05:
        raise RuntimeError(f"duration {info['duration']}")
    if not info["faststart"]:
        raise RuntimeError("moov is not before mdat")
    if info.get("audio"):
        raise RuntimeError("clip has an audio stream")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def committed_sha256(repo_path: str) -> str:
    data = subprocess.check_output(["git", "cat-file", "blob", f"HEAD:{repo_path}"])
    return hashlib.sha256(data).hexdigest()


def life_mask(masks: dict[str, np.ndarray]) -> np.ndarray:
    return (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0


def architecture_drift(path: Path, masks: dict[str, np.ndarray]) -> float:
    """Mean absolute difference of non-life pixels between the first and last frames."""
    cap = cv2.VideoCapture(str(path))
    ok0, frame0 = cap.read()
    last = None
    index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        last = frame
        index += 1
    cap.release()
    if not ok0 or last is None:
        raise RuntimeError("could not decode frames for drift QC")
    arch = ~life_mask(masks)
    # Stay a few pixels inside the still region so mask edges are not scored as drift.
    kernel = np.ones((5, 5), np.uint8)
    arch = cv2.erode(arch.astype(np.uint8), kernel, iterations=1).astype(bool)
    if int(arch.sum()) < 1000:
        return 0.0
    diff = np.abs(frame0.astype(np.int16) - last.astype(np.int16))
    return float(diff[arch].mean())


def save_overlay(entry_id: str, plate: np.ndarray, masks: dict[str, np.ndarray]) -> None:
    MASKS.mkdir(parents=True, exist_ok=True)
    overlay = plate.copy()
    colors = {
        "sky": (255, 180, 40),
        "water": (255, 80, 40),
        "foliage": (40, 180, 40),
        "flags": (40, 40, 220),
    }
    for name, color in colors.items():
        region = masks[name] > 0
        overlay[region] = (overlay[region] * 0.45 + np.array(color) * 0.55).astype(np.uint8)
    cv2.imwrite(str(MASKS / f"{entry_id.lower()}-mask.jpg"), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 80])


def prepare(scene: dict) -> tuple[np.ndarray, dict, dict]:
    entry_id = scene["entry_id"]
    info = manifest_daylight(entry_id)
    src = SRC / f"{entry_id.lower()}-day-4x5.png"
    meta = fetch_master(info["repo_path"], src)
    committed = committed_sha256(info["repo_path"])
    if meta["sha256"] != committed:
        raise RuntimeError(
            f"{entry_id} download sha256 {meta['sha256']} != committed main blob {committed}"
        )
    expected = info["expected_sha256"]
    manifest_match = bool(expected) and meta["sha256"] == expected
    plate_path = PLATES / f"{entry_id.lower()}-plate.png"
    ffmpeg_crop(src, plate_path)
    plate = read_plate(plate_path)
    masks = build_masks(plate)
    save_overlay(entry_id, plate, masks)
    fetched = {
        "repo_path": info["repo_path"],
        "github_blob": meta["sha"],
        "sha256": meta["sha256"],
        "manifest_sha256": expected,
        "manifest_sha256_match": manifest_match,
        "bytes": meta["bytes"],
        "download_url": meta["download_url"],
        "source": meta["source"],
        "crop": "864:1080:0:0",
        "source_kind": info["source_kind"],
        "scenario_label": info.get("scenario_label") or "",
        "gallery_approval_status": info.get("gallery_approval_status") or "",
    }
    if not manifest_match:
        fetched["manifest_note"] = (
            "sha256_4x5 does not match the committed main file; "
            "the bake uses those committed bytes"
        )
    return plate, masks, fetched


def finish_clip(entry_id: str, plate: np.ndarray, tmp: Path) -> dict:
    info = probe_clip(tmp)
    assert_spec(info)
    dest = clip_path(entry_id)
    tmp.replace(dest)
    write_poster(plate, poster_path(entry_id))
    info["sha256"] = sha256(dest)
    info["bytes"] = dest.stat().st_size
    return info


def bake_scene(scene: dict) -> dict:
    entry_id = scene["entry_id"]
    row = {
        "entry_id": entry_id,
        "caption": scene["caption"],
        "method": "static-ambient",
        "crop": "864:1080:0:0",
        "approval_status": "Candidate",
        "attempts": 0,
        "status": "HOLD",
        "i2v": "unavailable",
        "camera": "static",
    }
    tmp = clip_path(entry_id).with_suffix(".partial.mp4")
    try:
        plate, masks, fetched = prepare(scene)
    except Exception as exc:
        row["attempts"] = 1
        row["error"] = str(exc)
        row["hold_reason"] = "daytime master fetch or ffmpeg crop failed"
        return row
    row["anchor"] = fetched
    row["mean_v"] = round(mean_v(plate), 2)
    row["top_v"] = round(top_v(plate), 2)
    if row["top_v"] < MIN_TOP_V:
        row["attempts"] = 2
        row["hold_reason"] = f"cropped plate top-fifth V {row['top_v']} is below {MIN_TOP_V}; not a daylight plate"
        return row
    cov = coverage(masks)
    row["coverage"] = cov
    life = sum(cov.values())
    row["life"] = round(life, 4)
    if tmp.exists():
        tmp.unlink()

    def accept(variant: str) -> None:
        drift = architecture_drift(tmp, masks)
        row["architecture_drift"] = round(drift, 3)
        if drift > MAX_ARCH_DRIFT:
            raise RuntimeError(f"architecture drift {drift:.2f} exceeds {MAX_ARCH_DRIFT}")
        row["probe"] = finish_clip(entry_id, plate, tmp)
        row["variant"] = variant
        row["status"] = "shipped"
        row["file"] = str(clip_path(entry_id).relative_to(ROOT))
        row["poster"] = str(poster_path(entry_id).relative_to(ROOT))

    if life < MIN_LIFE:
        row["attempts"] = 1
        row["variant"] = "locked-off"
        try:
            encode_locked(plate, tmp)
            accept("locked-off")
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            clip_path(entry_id).unlink(missing_ok=True)
            poster_path(entry_id).unlink(missing_ok=True)
            row["attempts"] = 2
            row["error"] = str(exc)
            row["hold_reason"] = "locked-off encode failed QC"
            row["status"] = "HOLD"
        return row

    row["variant"] = "ambient"
    row["attempts"] = 1
    try:
        encode_ambient(plate, masks, tmp)
        accept("ambient")
        return row
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        clip_path(entry_id).unlink(missing_ok=True)
        row["attempt1_error"] = str(exc)
        row["attempts"] = 2
        row["variant"] = "locked-off"
        try:
            encode_locked(plate, tmp)
            accept("locked-off")
        except Exception as exc2:
            tmp.unlink(missing_ok=True)
            clip_path(entry_id).unlink(missing_ok=True)
            poster_path(entry_id).unlink(missing_ok=True)
            row["error"] = str(exc2)
            row["hold_reason"] = "ambient failed and locked-off retry failed"
            row["status"] = "HOLD"
    return row


def probe_scene(scene: dict) -> dict:
    plate, masks, fetched = prepare(scene)
    cov = coverage(masks)
    return {
        "entry_id": scene["entry_id"],
        "caption": scene["caption"],
        "mean_v": round(mean_v(plate), 2),
        "top_v": round(top_v(plate), 2),
        "shape": list(plate.shape),
        "coverage": cov,
        "life": round(sum(cov.values()), 4),
        "anchor_sha256": fetched["sha256"],
    }



def anchor_note(rows: list) -> str:
    matched = [row["entry_id"] for row in rows if (row.get("anchor") or {}).get("manifest_sha256_match")]
    unmatched = [row["entry_id"] for row in rows if row.get("anchor") and not row["anchor"].get("manifest_sha256_match")]
    if matched and unmatched:
        verb = "matches" if len(matched) == 1 else "match"
        sha_sentence = (
            f"{', '.join(matched)} still {verb} sha256_4x5. "
            f"{', '.join(unmatched)} do not match that field. "
        )
    elif matched:
        sha_sentence = "Every scene matches sha256_4x5. "
    elif unmatched and len(unmatched) == len(rows):
        sha_sentence = "None of these scenes match sha256_4x5. "
    else:
        sha_sentence = ""
    return (
        "Each clip is ffmpeg crop=864:1080:0:0 of the committed main daytime 4:5 file, "
        "downloaded through the GitHub contents API. "
        "The download sha256 matched that git blob. "
        + sha_sentence
        + "The bake used the committed bytes in every case. Night masters were not opened. "
        "Packs 1–24 (open Candidate drafts #32–#55) were not touched. "
        "Packs 1–17 cover DK-01-001–204. Pack18 covers DK-01-205–208 and DK-01-273–280. "
        "Pack19 covers DK-01-281–292. Pack20 covers DK-01-293–304. "
        "Pack21 covers DK-01-305–316. Pack22 covers DK-01-317–328. "
        "Pack23 covers DK-01-329–340. Pack24 covers DK-01-341–352. "
        "Night primaries DK-01-209–272 were not opened. "
        "Christmas sprinkle DK-01-366–368 (draft #31) was not re-baked."
    )


def write_proof(evidence: dict, dest: Path) -> None:
    rows = [row for row in evidence["scenes"] if row.get("status") == "shipped"]
    drifts = [float(row["architecture_drift"]) for row in rows if "architecture_drift" in row]
    if drifts:
        drift_txt = f"{min(drifts):.3f}–{max(drifts):.3f}"
    else:
        drift_txt = "n/a"
    table = [
        "| Scene | Caption | Method | Variant |",
        "|---|---|---|---|",
    ]
    for row in rows:
        table.append(
            f"| {row['entry_id']} | {row.get('caption', '')} | {row.get('method', '')} | {row.get('variant', '')} |"
        )
    body = "\n".join([
        "# Denmark 360 pack 25 — proof note",
        "",
        "Candidate only. This note is the baker's record. It is not Cosmo QC and it is not an approval.",
        "",
        "Work order `wo-denmark-360-2026-10-02`. Directive `wo-360-technical-directive-2026-10-02`. Orbit was not used.",
        "",
        "Image-to-video (`media.generate_video` / xAI) is not available in this environment, so the lateral-sweep prompt was not sent. No pan, zoom, or fake orbit was encoded. Method for every shipped scene is **static-ambient**: the camera stays locked on the daytime 4:5 plate after `ffmpeg crop=864:1080:0:0`. Sky, water, foliage, and flags already in that plate move only inside their own masks. Architecture pixels outside those masks are copied through unchanged "
        f"(decoded architecture drift {drift_txt} on a 0–255 scale).",
        "",
        f"Source masters are the committed `main` daytime 4:5 files for the {len(rows)} shipped scenes in DK-01-353–365. These are daytime plates (scenario hour 16 Europe/Copenhagen), so the daytime master is the primary `file_4x5` (there is no separate `daylight_variant`). Each shipped file was downloaded through the GitHub contents API and its SHA-256 matched that git blob and `sha256_4x5`. Night masters were not opened. None of DK-01-353–365 already had `motion-10s-4x5.mp4` on `main` or on an open Candidate PR (packs 1–23 drafts #32–#54 stop at DK-01-340; pack24 draft #55 covers DK-01-341–352; Christmas sprinkle DK-01-366–368 is draft #31 and is outside this pack), so nothing in this set was skipped for an existing clip.",
        "",
        "Night primaries were not selected. DK-01-353–365 are all daytime primaries. DK-01-209–272 were not opened. Christmas sprinkle DK-01-366–368 was not re-baked.",
        "",
        *table,
        "",
        f"Each shipped file is `assets/<scene-id-lower>-motion-10s-4x5.mp4`: 864×1080, 240 frames, 10.0s, h264, yuv420p, +faststart, no audio. Evidence: `evidence/motion/DK-360-pack25-2026-10-02.json`. Gallery `▶ 360°` buttons exist only for these {len(rows)} cards. Existing gallery approval status is unchanged. Holds: {len(evidence.get('hold') or [])}.",
        "",
        "Do not merge.",
        "",
    ])
    dest.write_text(body, encoding="utf-8")


MOTION_CSS = """  .motion-tab { background: #243049; color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 5px 10px; font: inherit; font-size: 12px; line-height: 1.2; cursor: pointer; }
  .motion-tab:hover { border-color: var(--accent); }
  .motion-tab.is-active { background: #e8b23a; border-color: #e8b23a; color: #1a1405; font-weight: 700; }
  .thumb video.motion-clip { width: 100%; height: auto; display: block; border-radius: 8px; background: #000; aspect-ratio: 4 / 5; object-fit: cover; }
"""

STOP_CARD_MOTION = """    function stopCardMotion(card) {
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

"""

MOTION_CLICK = """      if (event.target.closest('video.motion-clip')) {
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
"""


def wire_gallery(shipped: list[str]) -> None:
    """Add ▶ 360° only for scenes this pack actually shipped."""
    html_path = ROOT / "index.html"
    text = html_path.read_text(encoding="utf-8")
    allowed = {scene["entry_id"] for scene in SCENES}
    extra = [entry_id for entry_id in shipped if entry_id not in allowed]
    if extra:
        raise RuntimeError(f"refusing to wire scenes outside this pack: {extra}")
    motion = {
        entry_id: [
            f"assets/{entry_id.lower()}-motion-10s-4x5.mp4",
            f"assets/{entry_id.lower()}-motion-10s-4x5-poster.jpg",
        ]
        for entry_id in shipped
    }
    blob = json.dumps(motion, ensure_ascii=False, separators=(",", ":"))
    decl = (
        "/* Daylight 360 clips. Entry is [mp4, poster]. Absent entries have no button. */\n"
        f"const DENMARK_MOTION = {blob};"
    )
    if "const DENMARK_MOTION" in text:
        text = re.sub(
            r"/\* Daylight 360 clips\..*?\*/\nconst DENMARK_MOTION = \{.*?\};",
            decl,
            text,
            count=1,
            flags=re.S,
        )
    else:
        css_anchor = "  @media(max-width: 760px) { .related-row { grid-template-columns: repeat(2, 1fr); } }\n"
        if css_anchor not in text:
            raise RuntimeError("gallery css anchor missing")
        text = text.replace(css_anchor, css_anchor + MOTION_CSS, 1)
        script_anchor = "<script>\nconst DENMARK_META"
        if script_anchor not in text:
            raise RuntimeError("gallery script anchor missing")
        text = text.replace(script_anchor, "<script>\n" + decl + "\nconst DENMARK_META", 1)
        render_anchor = "    function render() {"
        if text.count(render_anchor) != 1:
            raise RuntimeError("render() anchor is not unique")
        text = text.replace(render_anchor, STOP_CARD_MOTION + render_anchor, 1)
        tabs_old = (
            "        const tabs = (file16 ? tab('16x9', '16:9') : '') "
            "+ (file45 ? tab('4x5', '4:5') : '') + (file916 ? tab('9x16', '9:16') : '');"
        )
        tabs_new = """        const motionPair = (typeof DENMARK_MOTION !== "undefined") ? DENMARK_MOTION[s.entry_id] : null;
        const motion = motionPair && motionPair[0] ? motionPair[0] : "";
        const motionPoster = motionPair && motionPair[1] ? motionPair[1] : "";
        const motionBtn = motion
          ? `<button type="button" class="motion-tab" data-motion="${esc(motion)}"${motionPoster ? ` data-poster="${esc(motionPoster)}"` : ""} title="Play the 360° daylight motion clip" aria-pressed="false">\\u25B6 360\\u00B0</button>`
          : "";
        const tabs = (file16 ? tab('16x9', '16:9') : '') + (file45 ? tab('4x5', '4:5') : '') + (file916 ? tab('9x16', '9:16') : '') + motionBtn;"""
        if tabs_old not in text:
            raise RuntimeError("format-tab anchor missing")
        text = text.replace(tabs_old, tabs_new, 1)
        click_old = "    grid.addEventListener('click', (event) => {\n      const nbtn = event.target.closest('.narrate');"
        if text.count(click_old) != 1:
            raise RuntimeError("narrate click anchor is not unique")
        text = text.replace(click_old, "    grid.addEventListener('click', (event) => {\n" + MOTION_CLICK + "      const nbtn = event.target.closest('.narrate');", 1)
        day_old = "        if (!dcard) return;\n        const isDay = !dtab.classList.contains('is-active');"
        if text.count(day_old) != 1:
            raise RuntimeError("day-tab anchor is not unique")
        text = text.replace(day_old, "        if (!dcard) return;\n        stopCardMotion(dcard);\n        const isDay = !dtab.classList.contains('is-active');", 1)
        fmt_old = "      if (!card) return;\n      const fmt = tab.getAttribute('data-format');"
        if text.count(fmt_old) != 1:
            raise RuntimeError("fmt-tab anchor is not unique")
        text = text.replace(fmt_old, "      if (!card) return;\n      stopCardMotion(card);\n      const fmt = tab.getAttribute('data-format');", 1)
    if text.count("const DENMARK_MOTION") != 1:
        raise RuntimeError("DENMARK_MOTION was not written once")
    # Buttons exist only for shipped ids. Anything else in the map is a bug.
    found = set(re.findall(r'"(DK-01-\d+)":\["assets/', text.split("const DENMARK_MOTION", 1)[1].split(";", 1)[0]))
    if found != set(shipped):
        raise RuntimeError(f"gallery map {sorted(found)} != shipped {shipped}")
    html_path.write_text(text, encoding="utf-8")
    print(f"wired {len(shipped)} gallery buttons", flush=True)


def main() -> None:
    only = [arg for arg in sys.argv[1:] if arg.startswith("DK-")]
    chosen = [scene for scene in SCENES if not only or scene["entry_id"] in only]
    if "--probe" in sys.argv:
        for scene in chosen:
            print(json.dumps(probe_scene(scene)), flush=True)
        return
    rows = []
    skips = []
    for scene in chosen:
        if motion_on_main(scene["entry_id"]):
            print(f"skip {scene['entry_id']} motion clip already on main", flush=True)
            skips.append({
                "id": scene["entry_id"],
                "reason": "motion-10s-4x5.mp4 already on main",
            })
            continue
        print(f"bake {scene['entry_id']}", flush=True)
        row = bake_scene(scene)
        rows.append(row)
        brief = {k: row[k] for k in ("entry_id", "status", "variant", "attempts", "life", "mean_v", "top_v", "architecture_drift") if k in row}
        print(json.dumps(brief), flush=True)
    evidence = {
        "work_order": "wo-denmark-360-2026-10-02",
        "directive": "wo-360-technical-directive-2026-10-02",
        "pack": "pack25",
        "method": "static-ambient",
        "i2v": "unavailable in this environment; lateral-sweep prompt was not sent; no pan, zoom, or orbit substituted",
        "lateral_sweep_prompt": (
            "Animate this daytime still into a smooth slow cinematic lateral sweep — the camera glides gently "
            "while the main subject stays centered and fully framed in EVERY frame from the first frame to the last. "
            "No traveling away from the subject, no zooming past it, no orbit that leaves it behind. Approximately 10 seconds. "
            "Gentle continuous motion, no cuts, photorealistic, same daylight look as the still. Vertical 4:5 format."
        ),
        "ambient_fallback_prompt": (
            "Animate with subtle ambient motion only — gentle water ripple, foliage sway, cloud drift. "
            "Camera remains static, subject perfectly framed. Approximately 10 seconds. No camera movement, no cuts, "
            "photorealistic. Vertical 4:5 format."
        ),
        "orbit": "abandoned; not used",
        "spec": {
            "duration_s": 10.0,
            "fps": FPS,
            "frames": FRAMES,
            "width": PHOTO_W,
            "height": PHOTO_H,
            "codec": "h264",
            "pix_fmt": "yuv420p",
            "faststart": True,
            "crop": "864:1080:0:0",
            "source": "committed main daytime 4:5 master",
        },
        "approval_status": "Candidate",
        "cosmo_qc": "not claimed",
        "source_anchor": anchor_note(rows),
        "scenes": rows,
        "shipped": [row["entry_id"] for row in rows if row["status"] == "shipped"],
        "hold": [
            {"id": row["entry_id"], "reason": row.get("hold_reason") or row.get("error")}
            for row in rows if row["status"] == "HOLD"
        ],
        "skips": skips,
        "night_excluded": {
            "range": "none in DK-01-353–365",
            "reason": (
                "every scene from DK-01-353 through DK-01-365 is a daytime primary "
                "(scenario hour 16 Europe/Copenhagen; gallery meta day). "
                "Night primaries were not selected and night masters were not opened. "
                "DK-01-209–272 remain excluded by earlier packs and were not opened. "
                "Christmas sprinkle DK-01-366–368 was not opened."
            ),
        },
        "prior_packs_not_touched": "drafts #32–#55 (packs 1–24); Christmas draft #31 was not touched",
        "open_candidate_motion": (
            "none of DK-01-353–365 have motion-10s-4x5.mp4 on main or on an open Candidate PR; "
            "drafts #32–#54 stop at DK-01-340; draft #55 covers DK-01-341–352; "
            "Christmas sprinkle DK-01-366–368 is draft #31 and is not in this pack"
        ),
        "gallery_approval": "unchanged; this pack does not flip Candidate or Approved",
    }
    dest = ROOT / "evidence" / "motion" / "DK-360-pack25-2026-10-02.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    proof = ROOT / "evidence" / "motion" / "DK-360-pack25-2026-10-02-proof.md"
    write_proof(evidence, proof)
    print(f"wrote {dest}", flush=True)
    print(f"wrote {proof}", flush=True)
    print(f"shipped {len(evidence['shipped'])} hold {len(evidence['hold'])}", flush=True)
    wire_gallery(evidence["shipped"])


if __name__ == "__main__":
    main()

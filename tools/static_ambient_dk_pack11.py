#!/usr/bin/env python3
"""Denmark 360 pack 11 — static-camera ambient clips.

Image-to-video is not available in this environment, so the lateral-sweep
prompt is not sent to a generator and no pan, zoom, or orbit is encoded.
The camera stays locked on the published daytime 4:5 master after
ffmpeg crop=864:1080:0:0 removes the label bar.

Only sky, water, foliage, and flags already in that plate move, and only
inside their own masks. Architecture pixels are copied through unchanged.
A plate with too little of that life is encoded locked-off (the same
cropped frame for 10.0s). That is still static-ambient. Night masters
are never opened. Approval stays Candidate.
"""

from __future__ import annotations

import hashlib
import json
import math
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
    {"entry_id": "DK-01-121", "caption": "Vor Frelsers Kirke, Horsens"},
    {"entry_id": "DK-01-122", "caption": "Silkeborg Church, Silkeborg"},
    {"entry_id": "DK-01-123", "caption": "Skanderborg Lake, Skanderborg"},
    {"entry_id": "DK-01-124", "caption": "Odder Church, Odder"},
    {"entry_id": "DK-01-125", "caption": "Grenaa Harbour, Grenaa"},
    {"entry_id": "DK-01-126", "caption": "Gammel Estrup, Auning"},
    {"entry_id": "DK-01-127", "caption": "Mariager Old Town, Mariager"},
    {"entry_id": "DK-01-128", "caption": "Hobro Harbour, Hobro"},
    {"entry_id": "DK-01-129", "caption": "Budolfi, Aalborg"},
    {"entry_id": "DK-01-130", "caption": "Lindholm Høje, Nørresundby"},
    {"entry_id": "DK-01-131", "caption": "Rebild Bakker, Rebild"},
    {"entry_id": "DK-01-132", "caption": "Skagen Old Town, Skagen"},
)


def manifest_daylight(entry_id: str) -> dict:
    data = json.loads((ROOT / "manifests" / f"{entry_id}.json").read_text(encoding="utf-8"))
    variant = data.get("daylight_variant") or {}
    files = variant.get("files") or {}
    path = files.get("4x5")
    if not path or "daylight-4x5" not in path:
        raise RuntimeError(f"{entry_id} has no daytime 4:5 master")
    sha = (variant.get("sha256") or {}).get("4x5")
    return {
        "repo_path": path,
        "expected_sha256": sha,
        "caption": data.get("caption") or "",
    }


def github_meta(repo_path: str) -> dict:
    raw = subprocess.check_output(
        [
            "gh", "api",
            f"repos/{REPO}/contents/{repo_path}?ref={REF}",
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
    """Load the committed daytime master. Local bytes must match the git blob."""
    committed = committed_sha256(repo_path)
    local = ROOT / repo_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if local.is_file() and sha256(local) == committed:
        dest.write_bytes(local.read_bytes())
        blob = subprocess.check_output(["git", "rev-parse", f"HEAD:{repo_path}"], text=True).strip()
        return {
            "sha": blob,
            "size": dest.stat().st_size,
            "download_url": f"https://github.com/{REPO}/blob/{REF}/{repo_path}",
            "sha256": committed,
            "bytes": dest.stat().st_size,
            "source": "committed main working tree (sha256 matches git blob)",
        }
    meta = github_meta(repo_path)
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
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "codec": stream["codec_name"],
        "pix_fmt": stream["pix_fmt"],
        "nb_frames": int(stream.get("nb_frames") or 0),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "duration": round(duration, 3),
        "faststart": fast,
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
    src = SRC / f"{entry_id.lower()}-daylight-4x5.png"
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
        "crop": "864:1080:0:0",
    }
    if not manifest_match:
        fetched["manifest_note"] = (
            "daylight_variant.sha256.4x5 does not match the committed main file; "
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
        sha_sentence = (
            f"{', '.join(matched)} still match daylight_variant.sha256.4x5. "
            f"{', '.join(unmatched)} do not match that field. "
        )
    elif matched:
        sha_sentence = "Every scene matches daylight_variant.sha256.4x5. "
    elif unmatched and len(unmatched) == len(rows):
        sha_sentence = "None of these scenes match daylight_variant.sha256.4x5. "
    else:
        sha_sentence = ""
    return (
        "Each clip is ffmpeg crop=864:1080:0:0 of the committed main daytime 4:5 file. "
        "The download sha256 matched that git blob. "
        + sha_sentence
        +         "The bake used the committed bytes in every case. Night masters were not opened. "
        "Packs 1–10 (open Candidate drafts #32–#41, DK-01-001–120) were not touched."
    )


def main() -> None:
    only = [arg for arg in sys.argv[1:] if arg.startswith("DK-")]
    chosen = [scene for scene in SCENES if not only or scene["entry_id"] in only]
    if "--probe" in sys.argv:
        for scene in chosen:
            print(json.dumps(probe_scene(scene)), flush=True)
        return
    rows = []
    for scene in chosen:
        print(f"bake {scene['entry_id']}", flush=True)
        row = bake_scene(scene)
        rows.append(row)
        brief = {k: row[k] for k in ("entry_id", "status", "variant", "attempts", "life", "mean_v", "top_v", "architecture_drift") if k in row}
        print(json.dumps(brief), flush=True)
    evidence = {
        "work_order": "wo-denmark-360-2026-10-02",
        "directive": "wo-360-technical-directive-2026-10-02",
        "pack": "pack11",
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
        "skips": [],
    }
    dest = ROOT / "evidence" / "motion" / "DK-360-pack11-2026-10-02.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {dest}", flush=True)
    print(f"shipped {len(evidence['shipped'])} hold {len(evidence['hold'])}", flush=True)


if __name__ == "__main__":
    main()

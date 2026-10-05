# BLOCKER: Denmark 360 pack 1 — no image-to-video tool

Work order: wo-360-kickoff-denmark-20261005 (Jason, 2026-10-05).
Pack: Denmark 360 motion pack 1 (DK-360-r2-pack1).
Date checked: 2026-10-05.

No motion mp4s were generated. No Ken Burns, pan/zoom, masked static-ambient, or looped-still substitute was made. Drafts #32–#56 were not touched.

## Daylight check (before any generation)

`DENMARK_META[id][1]` in `index.html` is `"day"` for every scene in this pack. None were skipped as night. Generation still did not start, because no image-to-video tool exists.

| Scene | `DENMARK_META` time | Result |
| --- | --- | --- |
| DK-01-193 | day | blocked — no i2v tool |
| DK-01-194 | day | blocked — no i2v tool |
| DK-01-195 | day | blocked — no i2v tool |
| DK-01-196 | day | blocked — no i2v tool |
| DK-01-197 | day | blocked — no i2v tool |
| DK-01-198 | day | blocked — no i2v tool |
| DK-01-199 | day | blocked — no i2v tool |
| DK-01-200 | day | blocked — no i2v tool |
| DK-01-201 | day | blocked — no i2v tool |
| DK-01-202 | day | blocked — no i2v tool |
| DK-01-203 | day | blocked — no i2v tool |
| DK-01-204 | day | blocked — no i2v tool |
| DK-01-205 | day | blocked — no i2v tool |
| DK-01-206 | day | blocked — no i2v tool |
| DK-01-207 | day | blocked — no i2v tool |
| DK-01-208 | day | blocked — no i2v tool |
| DK-01-273 | day | blocked — no i2v tool |
| DK-01-274 | day | blocked — no i2v tool |
| DK-01-275 | day | blocked — no i2v tool |
| DK-01-276 | day | blocked — no i2v tool |

## What was looked for, and what failed

### 1. Cursor dynamic tools (MCP catalog)

Full catalog for this run: namespaces `cursor`, `cursor-cloud`, `cursor-subscriptions`, and `Github`.

- `cursor` / `GenerateImage` — still-image text-to-image only. It writes an image file from a text description. It has no video output, no duration, no image-to-video mode, and no 4:5 aspect. It cannot produce `*-motion-10s-4x5.mp4`.
- No image-to-video tool under any name: Runway, Kling, Luma, Veo, Sora, Fal, Replicate, Pika, Minimax, Hailuo, Seedance, or Wan.
- `cursor-cloud` and `cursor-subscriptions` are run diagnostics and event subscriptions, not media generation.
- `Github` MCP failed live tool discovery (`namespaceStatus: error`). It is not a video API.

### 2. Local CLIs

`command -v` found `ffmpeg`, `python3`, `node`, `npx`, and `curl`.

Missing (not on `PATH`): `runway`, `kling`, `luma`, `fal`, `replicate`, `huggingface-cli`, `hf`, `openai`, `gcloud`, `aws`.

`ffmpeg` is installed. It was not used to invent motion. The work order forbids Ken Burns, pan/zoom, masked static-ambient, and looped stills.

### 3. API credentials

Process environment has no video-provider keys. Names checked and absent include Runway, Fal, Replicate, Luma, Kling, OpenAI/Sora, Hugging Face, Gemini/Veo, Stability, Pika, Minimax/Hailuo, and generic `API_KEY` / `API_TOKEN`. No `.env` or provider credential file was present under the home directory, `/opt`, or the repo. Calling those HTTP APIs without a key would fail the same way, so no request was sent.

### 4. Libraries

`python3 -m pip list` has no `fal-client`, `replicate`, `runwayml`, `diffusers`, `torch`, or `transformers`. Global npm packages are empty. Nothing local can run an image-to-video model.

## What was not done

- No crops, no mp4s, no poster jpgs.
- No branch `tmp/dk-360-r2-pack1-assets`.
- No gallery wiring, no `file_motion_4x5` edits, no `approval_status` or QC field edits.
- Escalation (3 QC fails in a row) did not trigger, because no clip was generated.

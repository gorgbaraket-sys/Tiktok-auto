"""
pipeline.py
AI video generation pipeline — saves final .mp4 locally for download.

Steps:
  1. Generate a viral video idea         → Claude claude-haiku-4-5
  2. Generate 3 scene prompts            → Claude claude-haiku-4-5
  3. Generate video clips (Seedance)     → Wavespeed AI
  4. Generate sound effect               → Fal AI (stable-audio)
  5. Stitch clips + audio                → local ffmpeg
  6. Save final .mp4 to /videos folder
"""

import os
import json
import time
import subprocess
import tempfile
import requests
import fal_client
import anthropic
from datetime import datetime

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL  = "claude-haiku-4-5-20251001"

VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)


# ── STEP 1 — Generate idea ────────────────────────────────────────────────────

def generate_idea(niche: str = "") -> str:
    niche_hint = f" The content niche is: {niche}." if niche else ""
    msg = claude.messages.create(
        model=MODEL,
        max_tokens=256,
        system=(
            "You are a viral content strategist specialised in TikTok, "
            "Instagram Reels, and YouTube Shorts. Generate ONE creative idea "
            "for a short AI-generated viral video (15-20 seconds)."
            f"{niche_hint}"
            " Return only the idea itself in 2-3 sentences — no bullet points, "
            "no preamble."
        ),
        messages=[{"role": "user", "content": "Give me a fresh, trending viral video idea."}],
    )
    return msg.content[0].text.strip()


# ── STEP 2 — Generate scene prompts ──────────────────────────────────────────

def generate_scene_prompts(idea: str) -> list[str]:
    msg = claude.messages.create(
        model=MODEL,
        max_tokens=512,
        system=(
            "You are an AI video director. Given a video idea, produce exactly "
            "3 detailed scene prompts for the Seedance AI video model.\n"
            "Each prompt must be:\n"
            "- Self-contained (5-7 seconds of footage)\n"
            "- Cinematic and highly visual\n"
            "- In 9:16 vertical portrait format\n"
            "- Photorealistic unless told otherwise\n\n"
            "Return ONLY a JSON array of 3 strings. No markdown fences, no extra text."
        ),
        messages=[{"role": "user", "content": f"Video idea: {idea}"}],
    )
    raw = msg.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    prompts = json.loads(raw)
    if not isinstance(prompts, list) or len(prompts) < 1:
        raise ValueError("Claude returned invalid prompt list")
    return prompts


# ── STEP 3 — Generate clips via Wavespeed AI (Seedance) ─────────────────────

WAVESPEED_BASE  = "https://api.wavespeed.ai/api/v2"
WAVESPEED_MODEL = "bytedance/seedance-1-lite"

def _wavespeed_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['WAVESPEED_API_KEY']}",
        "Content-Type": "application/json",
    }

def generate_single_clip(prompt: str, index: int) -> str:
    r = requests.post(
        f"{WAVESPEED_BASE}/{WAVESPEED_MODEL}",
        headers=_wavespeed_headers(),
        json={"prompt": prompt, "duration": 5, "aspect_ratio": "9:16", "resolution": "720p"},
        timeout=30,
    )
    r.raise_for_status()
    job_id = r.json()["data"]["id"]
    print(f"    Clip {index}: submitted → {job_id}")

    for attempt in range(90):
        time.sleep(5)
        poll = requests.get(
            f"{WAVESPEED_BASE}/predictions/{job_id}",
            headers=_wavespeed_headers(), timeout=15,
        )
        poll.raise_for_status()
        data = poll.json()["data"]
        if data.get("status") == "completed":
            url = data["outputs"][0]
            print(f"    Clip {index}: ready → {url}")
            return url
        elif data.get("status") == "failed":
            raise RuntimeError(f"Clip {index} failed: {data.get('error')}")
        if attempt % 6 == 0:
            print(f"    Clip {index}: {data.get('status')} ({attempt*5}s)…")

    raise TimeoutError(f"Clip {index} timed out")

def generate_all_clips(prompts: list[str]) -> list[str]:
    urls = []
    for i, prompt in enumerate(prompts, 1):
        print(f"  Generating clip {i}/{len(prompts)}…")
        urls.append(generate_single_clip(prompt, i))
    return urls


# ── STEP 4 — Generate sound via Fal AI ──────────────────────────────────────

def generate_sound(idea: str, duration_secs: int = 20) -> str:
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]
    result = fal_client.subscribe(
        "fal-ai/stable-audio",
        arguments={
            "prompt": (
                f"Background music for a viral social media video about: {idea}. "
                "Upbeat, energetic, engaging, no vocals."
            ),
            "seconds_total": duration_secs,
            "steps": 100,
        },
    )
    audio_url = result["audio_file"]["url"]
    print(f"  Sound ready → {audio_url}")
    return audio_url


# ── STEP 5 — Download, stitch, save ─────────────────────────────────────────

def _download(url: str, dest: str) -> None:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

def stitch_and_save(clip_urls: list[str], audio_url: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        clip_paths = []
        for i, url in enumerate(clip_urls):
            path = os.path.join(tmpdir, f"clip_{i:02d}.mp4")
            print(f"  Downloading clip {i+1}…")
            _download(url, path)
            clip_paths.append(path)

        audio_path = os.path.join(tmpdir, "audio.mp3")
        print("  Downloading audio…")
        _download(audio_url, audio_path)

        list_path = os.path.join(tmpdir, "list.txt")
        with open(list_path, "w") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        concat_path = os.path.join(tmpdir, "concat.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_path, "-c", "copy", concat_path],
            check=True, capture_output=True,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"video_{timestamp}.mp4"
        out_path  = os.path.join(VIDEOS_DIR, filename)

        subprocess.run(
            ["ffmpeg", "-y",
             "-i", concat_path, "-i", audio_path,
             "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac",
             "-t", str(5 * len(clip_paths)), "-shortest",
             out_path],
            check=True, capture_output=True,
        )

    size_mb = os.path.getsize(out_path) / 1_000_000
    print(f"  Saved → {filename} ({size_mb:.1f} MB)")
    return filename


# ── MASTER RUNNER ─────────────────────────────────────────────────────────────

def run_pipeline(niche: str = "") -> dict:
    results: dict = {"status": "running", "niche": niche}

    try:
        print("━━━ STEP 1 — Generating idea ━━━")
        idea = generate_idea(niche)
        results["idea"] = idea
        print(f"  {idea}\n")

        print("━━━ STEP 2 — Generating scene prompts ━━━")
        prompts = generate_scene_prompts(idea)
        results["prompts"] = prompts
        for i, p in enumerate(prompts, 1):
            print(f"  Scene {i}: {p[:80]}…")
        print()

        print("━━━ STEP 3 — Generating video clips ━━━")
        clip_urls = generate_all_clips(prompts)
        results["clip_urls"] = clip_urls
        print()

        print("━━━ STEP 4 — Generating sound effect ━━━")
        audio_url = generate_sound(idea, duration_secs=len(clip_urls) * 5 + 2)
        results["audio_url"] = audio_url
        print()

        print("━━━ STEP 5 — Stitching & saving ━━━")
        filename = stitch_and_save(clip_urls, audio_url)
        results["filename"] = filename
        print()

        results["status"] = "success"
        print("✅ Pipeline complete!")

    except Exception as exc:
        results["status"] = "error"
        results["error"] = str(exc)
        print(f"❌ Pipeline error: {exc}")

    return results

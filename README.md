# 🎬 Seedance TikTok Bot

Fully automated AI video pipeline — generates viral short-form videos and saves them locally for download.

---

## Pipeline

```
OpenAI GPT-4o-mini       → viral video idea
OpenAI GPT-4o-mini       → 3 cinematic scene prompts (9:16 vertical)
Wavespeed AI (Seedance)  → 3 × 5-second video clips
Fal AI (stable-audio)    → background sound effect
local ffmpeg             → concatenate clips + mix audio → final .mp4
Flask dashboard          → preview & download button
Google Sheets (optional) → log each run
```

Runs on a schedule (default every 6 hours).  
A web dashboard lets you monitor runs, preview videos in-browser, and download them.

---

## API Keys

| Service | Link | Used for |
|---|---|---|
| OpenAI | https://platform.openai.com | Idea + prompt generation |
| Wavespeed AI | https://wavespeed.ai | Seedance video clips |
| Fal AI | https://fal.ai/dashboard/keys | Sound effect generation |

---

## Deploy to Railway

```bash
# 1 — push to GitHub
git init
git add .
git commit -m "init"
gh repo create seedance-tiktok-bot --public --push

# 2 — deploy
# Railway → New Project → Deploy from GitHub repo
# Railway auto-detects the Dockerfile
```

In Railway → **Variables**, add:
```
OPENAI_API_KEY
WAVESPEED_API_KEY
FAL_API_KEY
```

Dashboard available at your Railway public URL.

---

## Local Development

```bash
cp .env.example .env      # fill in your keys
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

> **ffmpeg required locally:**  
> macOS: `brew install ffmpeg`  
> Ubuntu: `sudo apt install ffmpeg`

---

## Configuration

| Env var | Default | Description |
|---|---|---|
| `SCHEDULE_HOURS` | `6` | Auto-run interval in hours |
| `VIDEO_NICHE` | _(blank)_ | Content niche override |
| `GOOGLE_SHEET_ID` | _(blank)_ | Disables logging if empty |
| `GOOGLE_CREDENTIALS_JSON` | _(blank)_ | Service account JSON |

---

## Dashboard

| Route | Description |
|---|---|
| `/` | Dashboard — stats, trigger, run history, video library |
| `/trigger` | `POST {"niche": "optional"}` — start a run |
| `/download/<filename>` | Download a generated `.mp4` |
| `/videos/<filename>` | Stream video for in-browser preview |
| `/status` | JSON status |
| `/health` | Health check |

> **Note:** Videos are stored in a `videos/` folder inside the container.  
> On Railway, this resets on redeploy — download your videos before redeploying,  
> or mount a Railway Volume for persistence.

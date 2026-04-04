# 🚀 TikTok Auto-Poster — Luxury Trading Mindset

4 automated videos/day · Beirut UTC+3 · Railway deployment

## 📅 Daily Schedule

| Time (Beirut) | Video Type        | Duration  | Goal              |
|---------------|-------------------|-----------|-------------------|
| 1:00 PM       | Short Hook        | 7–12s     | Go viral fast     |
| 6:30 PM       | Core Message      | 20–35s    | Retention + shares|
| 9:00 PM 🔥    | Authority         | 40–60s    | Build trust       |
| 11:30 PM      | Loop Video        | 15–25s    | Replay boost      |

## 🔑 APIs Required

| API          | Tier    | Link                              |
|--------------|---------|-----------------------------------|
| Groq         | Free    | https://console.groq.com          |
| ElevenLabs   | Free    | https://elevenlabs.io             |
| Pexels       | Free    | https://www.pexels.com/api/       |
| TikTok       | Approval| https://developers.tiktok.com     |

## 🚀 Deploy to Railway

1. Push this folder to a GitHub repo
2. Connect repo to Railway
3. Add all variables from `.env.example` to Railway → Variables tab
4. Deploy → done ✅

## 🧪 Test endpoints

- `GET /` — status + next scheduled runs
- `GET /trigger/short_hook` — fire manually
- `GET /trigger/core_message` — fire manually
- `GET /trigger/authority` — fire manually
- `GET /trigger/loop_video` — fire manually
- `GET /trigger/all` — fire all 4 now

## 📦 Stack

- **Groq** (llama-3.3-70b-versatile) — script generation
- **ElevenLabs** (eleven_multilingual_v2) — AI voiceover
- **Pexels** — luxury background videos
- **FFmpeg** — video assembly + burned-in subtitles
- **TikTok API v2** — Content Posting API (direct file upload)
- **Flask + APScheduler** — scheduling engine
- **Railway** — hosting + always-on

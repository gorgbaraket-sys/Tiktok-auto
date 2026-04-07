# YT → TikTok AI Clipper

Paste a YouTube channel URL → AI finds the best moments → Download 9:16 TikTok-ready clips.

## How it works

1. You paste a YouTube channel or video URL
2. App fetches the latest videos from that channel
3. You pick which video to clip
4. The app:
   - Downloads it via `yt-dlp`
   - Transcribes it with **Groq Whisper**
   - Sends the transcript to **LLaMA 3.3 70B** to find 4–5 viral moments
   - Renders each clip with FFmpeg: center-cropped to **9:16**, title overlay burned in
5. You download each clip directly

## Stack

- **Flask** — web server
- **yt-dlp** — YouTube downloader
- **Groq** — Whisper transcription + LLaMA highlight detection
- **FFmpeg** — video processing & 9:16 crop

---

## Deploy to Railway

### 1. Fork / push this repo to GitHub

### 2. Create Railway project

- Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo

### 3. Add environment variable

In Railway → your service → Variables:

```
GROQ_API_KEY = your_groq_api_key_here
```

Get a free key at [console.groq.com](https://console.groq.com)

### 4. Deploy

Railway will automatically build using `nixpacks.toml` (installs FFmpeg + Python) and
start the server with the command in `railway.toml`.

---

## Local run

```bash
pip install -r requirements.txt
# FFmpeg must be installed on your system
export GROQ_API_KEY=your_key
python app.py
```

---

## Supported URL formats

```
https://youtube.com/@ChannelHandle
https://youtube.com/@ChannelHandle/videos
https://youtube.com/channel/UCxxxxxxxxxxxxxxxx
https://youtube.com/c/ChannelName
https://youtube.com/watch?v=VIDEO_ID   (single video)
```

## Notes

- Groq Whisper has a **25 MB** audio limit. The app compresses audio to 32kbps mono
  and caps at 10 minutes to stay within limits.
- Videos are stored in `/tmp` (Railway ephemeral storage) and lost on restart.
  Download your clips before restarting.
- Set `timeout = 600` in `railway.toml` because long videos take time.

# 👑 Luxury TikTok Bot

Fully automated TikTok video generator for the **Luxury Trading Mindset** niche.  
4 videos per day, black-and-gold aesthetic, zero manual work.

---

## 📅 Daily Schedule (Beirut Time UTC+3)

| Time    | Type          | Duration  | Goal              |
|---------|---------------|-----------|-------------------|
| 1:00 PM | Short Hook    | 7–12s     | Go viral fast     |
| 6:30 PM | Core Message  | 20–35s    | Retention + shares|
| 9:00 PM 🔥 | Authority  | 40–60s    | Build trust       |
| 11:30 PM | Loop Video   | 15–25s    | Replay boost      |

---

## 🚀 Deploy on Railway (5 minutes)

### Step 1 — Push to GitHub
```bash
# On your phone, go to github.com → New repository
# Name it: tiktok-luxury-bot
# Upload all files from this ZIP
```

### Step 2 — Create Railway project
1. Go to [railway.app](https://railway.app)
2. **New Project → Deploy from GitHub repo**
3. Select your `tiktok-luxury-bot` repo
4. Railway auto-detects nixpacks.toml and builds

### Step 3 — Set Environment Variables
In Railway dashboard → your service → **Variables** tab:
```
ANTHROPIC_API_KEY = sk-ant-xxxxxxxxxxxx
```

### Step 4 — Generate a domain
Railway → your service → **Settings** → **Generate Domain**  
Your dashboard will be live at `https://yourapp.up.railway.app`

---

## 🖥️ Dashboard Features

- **Live schedule** — see all 4 daily jobs and their next run times
- **Manual trigger** — generate any video type instantly via button
- **Video history** — download all generated MP4s
- **Live logs** — real-time bot activity

---

## 🎬 Video Style

- **Background**: Deep black with gold geometric accents
- **Text**: Bold white/gold, uppercase for hooks
- **Brand**: "LUXURY MINDSET" watermark
- **Progress**: Gold dot indicators
- **No audio** (add your own trending sound on TikTok when posting)

---

## 📁 Project Structure

```
tiktok-luxury-bot/
├── app.py                  # Flask app + scheduler
├── modules/
│   ├── script_generator.py # Claude API script generation
│   └── video_creator.py    # MoviePy/Pillow video renderer
├── templates/
│   └── dashboard.html      # Web dashboard
├── videos/                 # Generated MP4s saved here
├── logs/                   # Bot activity logs
├── requirements.txt
├── Procfile
├── railway.toml
└── nixpacks.toml           # FFmpeg + fonts for Railway
```

---

## 💡 Local Testing (optional)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-xxxxx
python app.py
# Open http://localhost:5000
```

---

## ⚙️ Customization

Edit `app.py` → `SCHEDULE` list to change times or video types.  
Edit `modules/script_generator.py` → `STYLE_PROMPTS` to change niche/tone.  
Edit `modules/video_creator.py` → colors/fonts/layout to change visual style.

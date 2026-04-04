import os, json, random, logging, threading, subprocess, requests, uuid, asyncio
import edge_tts
from flask import Flask, jsonify, request, send_file
from groq import Groq

try:
    from openai import OpenAI as _OpenAI
    _openai_available = True
except ImportError:
    _openai_available = False

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── ENV ───────────────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.environ.get('GROQ_API_KEY', '')
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

groq_client   = Groq(api_key=GROQ_API_KEY)
openai_client = _OpenAI(api_key=OPENAI_API_KEY) if (_openai_available and OPENAI_API_KEY) else None

os.makedirs('videos', exist_ok=True)

# ── FONT SETUP ────────────────────────────────────────────────────────────────
FONT_PATH = '/tmp/Montserrat-Bold.ttf'
FONT_URL  = 'https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf'

def ensure_font():
    if os.path.exists(FONT_PATH):
        return FONT_PATH
    try:
        r = requests.get(FONT_URL, timeout=30)
        r.raise_for_status()
        with open(FONT_PATH, 'wb') as f:
            f.write(r.content)
        logger.info('✅ Font ready: Montserrat Bold')
        return FONT_PATH
    except Exception as e:
        logger.warning(f'⚠️  Font download failed ({e}) — using system default')
        return None

FONT = ensure_font()

# ── VOICE CONFIG ──────────────────────────────────────────────────────────────
OPENAI_VOICES = {
    'short_hook':   'echo',      # energetic, punchy
    'core_message': 'echo',      # confident, clear
    'authority':    'onyx',      # deep, commanding
    'loop_video':   'fable',     # smooth, hypnotic
}
EDGE_VOICES = {
    'short_hook':   'en-US-AndrewNeural',
    'core_message': 'en-US-AndrewNeural',
    'authority':    'en-US-ChristopherNeural',
    'loop_video':   'en-US-AndrewNeural',
}

VOICE_ENGINE = (
    f"OpenAI tts-1-hd"
    if openai_client else
    "Microsoft Neural (free)"
)

# Job tracker
jobs = {}

# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
TOPICS = {
    'short_hook': [
        "The one mindset shift that separates 7-figure traders from broke ones",
        "Why 90% of traders lose money — and it has nothing to do with strategy",
        "The luxury lifestyle starts with this single trading rule",
        "Most traders quit right before they were about to win",
        "Your emotions are costing you more than your losses",
        "The difference between a Lambo and a loss is your mindset",
        "Discipline is the only strategy that never fails in trading",
        "Rich traders do this ONE thing differently",
        "Stop blaming the market — the problem is in your head",
        "Trading is 20% strategy, 80% psychology",
    ],
    'core_message': [
        "How to kill fear and greed before they kill your account",
        "The trading psychology loop that keeps you poor",
        "Why professional traders never rush a single entry",
        "How discipline creates the luxury life you want",
        "The mindset of a trader who never blows their account",
        "What separates consistent winners from emotional losers in trading",
        "How to detach your ego from your trades",
        "The patience principle behind every wealthy trader",
        "Why revenge trading always ends the same way",
        "How to build a trading routine that creates freedom",
    ],
    'authority': [
        "The complete psychology of a profitable trader — explained",
        "Why the wealthy think about risk in a completely different way",
        "How top traders use journaling to eliminate emotional decisions",
        "The full breakdown of why traders fail despite good strategies",
        "Building a mindset that attracts consistent trading profits",
        "How to think like a hedge fund manager with a $100 account",
        "The 5 psychological traps that destroy trading accounts",
        "Why patience is the rarest and most profitable trading skill",
        "How to build mental resilience that survives any market",
        "The psychology behind position sizing and wealth preservation",
    ],
    'loop_video': [
        "Watch this on repeat until your mindset changes forever",
        "The trading truth that loops in every rich trader's mind",
        "This one principle replays in profitable traders' heads daily",
        "Keep watching this until discipline becomes automatic",
        "One rule. Loop it. Repeat it. Live it.",
    ]
}

TYPE_CONFIG = {
    'short_hook':   {'words': '15-30',   'style': 'Ultra-punchy. ONE shocking statement. Stops scroll instantly. Zero filler.', 'dur': '7-12s'},
    'core_message': {'words': '70-110',  'style': 'Educational, direct, confident. Short sentences. Builds to one key insight.', 'dur': '20-35s'},
    'authority':    {'words': '130-190', 'style': 'Expert-level authority. Deep insight. Trading mentor tone. Structured points.', 'dur': '40-60s'},
    'loop_video':   {'words': '45-75',   'style': 'Hypnotic, repeatable. Each line hits hard. Ends making viewer want to replay.', 'dur': '15-25s'},
}

def generate_script(video_type):
    topic = random.choice(TOPICS[video_type])
    cfg   = TYPE_CONFIG[video_type]
    prompt = f"""You are an elite TikTok scriptwriter for luxury trading psychology content.

Video Type: {video_type.replace('_', ' ').title()}
Topic: {topic}
Word Count: {cfg['words']} words (strictly)
Style: {cfg['style']}
Tone: Premium, zero-fluff, confident. Short punchy sentences under 12 words each.
Themes: discipline, patience, emotional control, risk management, wealth psychology.

Rules:
- NO greetings ("Hey guys", "Welcome back", etc.) — start with impact immediately
- NO weak openers ("In this video...", "Today we talk about...")
- Every sentence must earn its place
- Avoid repeating ideas — one clear thread throughout

Respond ONLY in valid JSON with NO markdown, NO code blocks, NO extra text:
{{"script":"full spoken script here","caption":"TikTok caption under 120 chars","hashtags":"#trading #tradingpsychology #mindset #wealthmindset #forex #discipline #luxurylifestyle","topic":"{topic}"}}"""

    resp = groq_client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.85,
        max_tokens=700,
    )
    raw = resp.choices[0].message.content.strip()
    if '```json' in raw: raw = raw.split('```json')[1].split('```')[0].strip()
    elif '```' in raw:   raw = raw.split('```')[1].split('```')[0].strip()
    return json.loads(raw)

# ══════════════════════════════════════════════════════════════════════════════
# VOICE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
async def _tts_edge(text, voice, path):
    communicate = edge_tts.Communicate(text, voice, rate='+3%', pitch='+0Hz')
    await communicate.save(path)

def generate_voiceover(script, video_type, uid):
    path = f'videos/audio_{uid}.mp3'

    if openai_client:
        # ── OpenAI tts-1-hd — high quality neural voice ────────────────────
        voice = OPENAI_VOICES.get(video_type, 'echo')
        resp  = openai_client.audio.speech.create(
            model='tts-1-hd',
            voice=voice,
            input=script,
            speed=1.05,
        )
        with open(path, 'wb') as f:
            f.write(resp.content)
        logger.info(f'🎙️  Voice: OpenAI {voice}')
    else:
        # ── edge-tts fallback — free Microsoft Neural ───────────────────────
        voice = EDGE_VOICES.get(video_type, 'en-US-AndrewNeural')
        asyncio.run(_tts_edge(script, voice, path))
        logger.info(f'🎙️  Voice: edge-tts {voice}')

    return path

# ══════════════════════════════════════════════════════════════════════════════
# VIDEO GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
BG_QUERIES = [
    'luxury car driving night', 'stock market trading screen', 'private jet interior',
    'luxury penthouse city view', 'forex charts finance', 'businessman walking city',
    'luxury watch close up', 'skyscraper city night lights', 'trading desk multiple screens',
    'yacht ocean luxury', 'speed luxury sports car', 'financial district blur', 'gold bars wealth',
]

def get_pexels_video(query, min_dur=10):
    headers = {'Authorization': PEXELS_API_KEY}
    def fetch(q):
        try:
            r = requests.get(
                f'https://api.pexels.com/videos/search?query={q}&per_page=20&orientation=portrait&size=large',
                headers=headers, timeout=30,
            )
            return r.json().get('videos', [])
        except:
            return []

    videos  = fetch(query) or fetch('luxury lifestyle')
    suitable = [v for v in videos if v.get('duration', 0) >= min_dur] or videos
    video    = random.choice(suitable)
    files    = video.get('video_files', [])

    # Prefer HD portrait files
    portrait = [f for f in files if f.get('width', 1) < f.get('height', 0)] or files
    portrait.sort(key=lambda f: f.get('width', 0) * f.get('height', 0), reverse=True)
    return portrait[0]['link']

def download_file(url, path):
    r = requests.get(url, stream=True, timeout=90)
    r.raise_for_status()
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def get_audio_duration(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', path],
        capture_output=True, text=True,
    )
    for s in json.loads(result.stdout).get('streams', []):
        if s.get('codec_type') == 'audio':
            return float(s.get('duration', 30.0))
    return 30.0

def esc(text):
    return (text
        .replace('\\', '\\\\')
        .replace("'", "\\'")
        .replace(':', '\\:')
        .replace('%', '\\%')
        .replace('[', '\\[')
        .replace(']', '\\]')
    )

def build_subtitle_filters(script, dur):
    """3 words at a time with a modern semi-transparent background box."""
    words  = script.split()
    chunks = [' '.join(words[i:i+3]) for i in range(0, len(words), 3)]
    tpc    = dur / max(len(chunks), 1)
    font_arg = f":fontfile='{FONT}'" if FONT and os.path.exists(FONT) else ''

    filters = []
    for i, chunk in enumerate(chunks):
        t_start = round(i * tpc, 2)
        t_end   = round((i + 1) * tpc - 0.05, 2)
        filters.append(
            f"drawtext=text='{esc(chunk)}'"
            f":fontsize=64"
            f":fontcolor=white"
            f":box=1:boxcolor=black@0.55:boxborderw=24"
            f"{font_arg}"
            f":x=(w-text_w)/2"
            f":y=(h*0.70)"
            f":enable='between(t,{t_start},{t_end})'"
        )
    return filters

def create_video(audio_path, script_data, video_type, uid):
    bg_path  = f'videos/bg_{uid}.mp4'
    out_path = f'videos/final_{uid}.mp4'
    dur      = get_audio_duration(audio_path)

    bg_url = get_pexels_video(random.choice(BG_QUERIES), int(dur))
    download_file(bg_url, bg_path)

    font_arg = f":fontfile='{FONT}'" if FONT and os.path.exists(FONT) else ''
    watermark = (
        f"drawtext=text='TRADING MINDSET'"
        f":fontsize=30"
        f":fontcolor=#FFD700"
        f":box=1:boxcolor=black@0.45:boxborderw=14"
        f"{font_arg}"
        f":x=(w-text_w)/2"
        f":y=64"
    )

    sub_filters = build_subtitle_filters(script_data['script'], dur)

    vf = ','.join([
        # ── Scale & crop to full HD vertical (1080×1920) ──────────────────
        'scale=1080:1920:force_original_aspect_ratio=increase',
        'crop=1080:1920',
        # ── Cinematic colour grade: rich, dark, punchy ────────────────────
        'eq=brightness=-0.08:saturation=1.40:contrast=1.10:gamma=0.92',
        # ── Subtle teal-orange tint via curves ────────────────────────────
        "curves=r='0/0 0.5/0.48 1/0.90':b='0/0 0.5/0.52 1/1.0'",
        # ── Edge vignette ─────────────────────────────────────────────────
        'vignette=PI/4.5',
        # ── Soft fade-in ──────────────────────────────────────────────────
        'fade=t=in:st=0:d=0.5',
        # ── Watermark & subtitles ─────────────────────────────────────────
        watermark,
    ] + sub_filters)

    cmd = [
        'ffmpeg', '-y',
        '-stream_loop', '-1', '-i', bg_path,
        '-i', audio_path,
        '-vf', vf,
        # Audio: boost + gentle compression for consistent loudness
        '-af', 'volume=1.3,acompressor=threshold=-18dB:ratio=3:attack=5:release=50',
        '-t', str(dur + 0.3),
        # Video: H.264, medium preset, CRF 20 for high quality
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        # Audio: AAC 192k
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest', '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        out_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    for p in [bg_path, audio_path]:
        try: os.remove(p)
        except: pass

    if result.returncode != 0:
        raise RuntimeError(f'FFmpeg failed:\n{result.stderr[-2000:]}')
    return out_path

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
def run_pipeline(job_id, video_type):
    uid = job_id
    try:
        jobs[job_id] = {'status': 'running', 'step': '✍️ Writing script...', 'file': None, 'error': None, 'type': video_type}
        script_data = generate_script(video_type)

        jobs[job_id]['step'] = '🎙️ Generating voiceover...'
        audio_path = generate_voiceover(script_data['script'], video_type, uid)

        jobs[job_id]['step'] = '🎬 Building video...'
        video_path = create_video(audio_path, script_data, video_type, uid)

        jobs[job_id] = {
            'status':  'done',
            'step':    '✅ Ready!',
            'file':    video_path,
            'error':   None,
            'type':    video_type,
            'caption': script_data.get('caption', ''),
            'hashtags': script_data.get('hashtags', ''),
            'voice':   VOICE_ENGINE,
        }
        logger.info(f'✅ Job {job_id} done')

    except Exception as e:
        logger.error(f'❌ Job {job_id} failed: {e}', exc_info=True)
        jobs[job_id] = {'status': 'error', 'step': '❌ Failed', 'file': None, 'error': str(e), 'type': video_type}

# ══════════════════════════════════════════════════════════════════════════════
# HTML UI
# ══════════════════════════════════════════════════════════════════════════════
_VOICE_BADGE = (
    '🎙️ OpenAI Neural HD · 1080p'
    if openai_client else
    '🎙️ Microsoft Neural · 1080p · Free'
)

HTML = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta charset="UTF-8">
<title>Trading Video Generator</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --gold:    #FFD700;
    --gold2:   #FF8C00;
    --red:     #FF416C;
    --bg:      #080810;
    --surface: #10101c;
    --border:  #1e1e30;
    --text:    #e8e8f0;
    --muted:   #5a5a78;
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
    padding: 32px 16px 48px;
    /* Subtle grid texture */
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 48px 48px;
    background-position: center center;
  }}

  /* ── Header ─────────────────────────────────────────────── */
  .header {{
    text-align: center;
    margin-bottom: 36px;
  }}
  h1 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 42px;
    letter-spacing: 3px;
    background: linear-gradient(135deg, var(--gold), var(--red));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.1;
    margin-bottom: 6px;
  }}
  .sub {{
    color: var(--muted);
    font-size: 13px;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 16px;
  }}
  .badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 100px;
    padding: 5px 14px;
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.5px;
  }}
  .badge-dot {{
    width: 6px; height: 6px;
    background: #3ddc84;
    border-radius: 50%;
    box-shadow: 0 0 8px #3ddc84;
    flex-shrink: 0;
  }}

  /* ── Grid buttons ───────────────────────────────────────── */
  .grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    max-width: 540px;
    margin: 0 auto 36px;
  }}
  .btn {{
    border: 1px solid transparent;
    border-radius: 16px;
    padding: 22px 14px 18px;
    cursor: pointer;
    color: #fff;
    transition: transform .18s, box-shadow .18s, opacity .18s;
    text-align: left;
    position: relative;
    overflow: hidden;
  }}
  .btn::after {{
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,.08), transparent);
    pointer-events: none;
  }}
  .btn:hover  {{ transform: translateY(-2px); box-shadow: 0 12px 32px rgba(0,0,0,.5); }}
  .btn:active {{ transform: scale(0.97); opacity: .85; }}
  .btn .icon  {{ font-size: 26px; display: block; margin-bottom: 10px; }}
  .btn .label {{ display: block; font-size: 14px; font-weight: 700; letter-spacing: .3px; }}
  .btn .dur   {{ display: block; font-size: 11px; opacity: .65; margin-top: 3px; }}

  .b1 {{ background: linear-gradient(135deg, #FF416C, #FF4B2B); border-color: #ff416c44; }}
  .b2 {{ background: linear-gradient(135deg, #4776E6, #8E54E9); border-color: #4776e644; }}
  .b3 {{ background: linear-gradient(135deg, #F7971E, #FFD200); border-color: #ffd20044; }}
  .b3 .label, .b3 .dur {{ color: #1a1000; }}
  .b4 {{ background: linear-gradient(135deg, #0f9b58, #00f2c3); border-color: #00f2c344; }}
  .b4 .label, .b4 .dur {{ color: #001a12; }}

  /* ── Status area ────────────────────────────────────────── */
  #status-box {{ max-width: 540px; margin: 0 auto; }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 22px;
    margin-bottom: 14px;
  }}
  .card-label {{
    font-size: 10px;
    font-weight: 600;
    color: var(--muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 10px;
  }}
  .step-text {{
    font-size: 17px;
    font-weight: 600;
    min-height: 26px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .progress {{
    height: 3px;
    background: var(--border);
    border-radius: 4px;
    margin-top: 16px;
    overflow: hidden;
  }}
  .progress-bar {{
    height: 100%;
    background: linear-gradient(90deg, var(--gold), var(--red));
    border-radius: 4px;
    transition: width .5s cubic-bezier(.4,0,.2,1);
  }}

  .dl-btn {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 18px;
    background: linear-gradient(135deg, var(--gold), var(--gold2));
    border: none;
    border-radius: 14px;
    color: #1a0f00;
    font-size: 16px;
    font-weight: 800;
    cursor: pointer;
    text-decoration: none;
    letter-spacing: .5px;
    margin-top: 16px;
    transition: transform .15s, box-shadow .15s;
  }}
  .dl-btn:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(255,215,0,.3);
  }}

  .caption-box {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 13px;
    color: #9090b0;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-word;
  }}
  .meta-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 12px;
  }}
  .meta-pill {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 100px;
    padding: 3px 10px;
    font-size: 10px;
  }}

  .hidden {{ display: none; }}
  .error  {{ color: #FF416C; font-size: 13px; line-height: 1.5; }}

  .spinner {{
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid var(--border);
    border-top-color: var(--gold);
    border-radius: 50%;
    animation: spin .7s linear infinite;
    flex-shrink: 0;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>

<div class="header">
  <h1>⚡ Trading Video<br>Generator</h1>
  <p class="sub">Luxury · Mindset · Psychology</p>
  <div>
    <span class="badge">
      <span class="badge-dot"></span>
      {_VOICE_BADGE}
    </span>
  </div>
</div>

<div class="grid">
  <button class="btn b1" onclick="generate('short_hook')">
    <span class="icon">🪝</span>
    <span class="label">Short Hook</span>
    <span class="dur">7–12s · Go viral</span>
  </button>
  <button class="btn b2" onclick="generate('core_message')">
    <span class="icon">📢</span>
    <span class="label">Core Message</span>
    <span class="dur">20–35s · Retention</span>
  </button>
  <button class="btn b3" onclick="generate('authority')">
    <span class="icon">🔥</span>
    <span class="label">Authority</span>
    <span class="dur">40–60s · Build trust</span>
  </button>
  <button class="btn b4" onclick="generate('loop_video')">
    <span class="icon">🔄</span>
    <span class="label">Loop Video</span>
    <span class="dur">15–25s · Replay boost</span>
  </button>
</div>

<div id="status-box" class="hidden">
  <div class="card">
    <div class="card-label">Status</div>
    <div class="step-text" id="step-text">Starting...</div>
    <div class="progress">
      <div class="progress-bar" id="prog" style="width:5%"></div>
    </div>
  </div>

  <div id="result-box" class="hidden">
    <a id="dl-link" class="dl-btn" href="#" download>
      <span>⬇️</span> Download Video
    </a>
    <div class="card" style="margin-top:12px">
      <div class="card-label">Caption + Hashtags</div>
      <div class="meta-row">
        <span class="meta-pill" id="voice-pill">—</span>
        <span class="meta-pill">1080 × 1920</span>
        <span class="meta-pill">MP4</span>
      </div>
      <div class="caption-box" id="caption-text"></div>
    </div>
  </div>

  <div id="error-box" class="hidden card">
    <div class="card-label">Error</div>
    <div class="error" id="error-text"></div>
  </div>
</div>

<script>
const PROGS = {{
  '✍️ Writing script...':      20,
  '🎙️ Generating voiceover...': 55,
  '🎬 Building video...':       82,
  '✅ Ready!':                  100,
}};
let pollTimer = null;

function generate(type) {{
  clearInterval(pollTimer);
  document.getElementById('status-box').classList.remove('hidden');
  document.getElementById('result-box').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  setStep('<span class="spinner"></span> Starting...');
  document.getElementById('prog').style.width = '5%';

  fetch('/generate', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{type}}),
  }})
  .then(r => r.json())
  .then(d => {{ if (d.job_id) poll(d.job_id); }});
}}

function poll(id) {{
  pollTimer = setInterval(() => {{
    fetch('/status/' + id)
    .then(r => r.json())
    .then(d => {{
      const pct = PROGS[d.step] || 10;
      document.getElementById('prog').style.width = pct + '%';

      if (d.status === 'running') {{
        setStep('<span class="spinner"></span> ' + d.step);
      }} else if (d.status === 'done') {{
        clearInterval(pollTimer);
        setStep('✅ Video Ready!');
        document.getElementById('prog').style.width = '100%';
        document.getElementById('result-box').classList.remove('hidden');
        document.getElementById('dl-link').href = '/download/' + id;
        document.getElementById('voice-pill').textContent = d.voice || '';
        const cap = (d.caption || '') + '\\n\\n' + (d.hashtags || '');
        document.getElementById('caption-text').textContent = cap.trim();
      }} else if (d.status === 'error') {{
        clearInterval(pollTimer);
        setStep('❌ Failed');
        document.getElementById('error-box').classList.remove('hidden');
        document.getElementById('error-text').textContent = d.error;
      }}
    }});
  }}, 2000);
}}

function setStep(html) {{
  document.getElementById('step-text').innerHTML = html;
}}
</script>
</body>
</html>'''

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def index():
    return HTML

@app.route('/generate', methods=['POST'])
def generate():
    data       = request.get_json()
    video_type = data.get('type', 'short_hook')
    if video_type not in TYPE_CONFIG:
        return jsonify({'error': 'Invalid type'}), 400
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {'status': 'running', 'step': '✍️ Writing script...', 'file': None, 'error': None, 'type': video_type}
    threading.Thread(target=run_pipeline, args=(job_id, video_type), daemon=True).start()
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def status(job_id):
    return jsonify(jobs.get(job_id, {'status': 'not_found', 'step': '?', 'error': 'Job not found'}))

@app.route('/download/<job_id>')
def download(job_id):
    job = jobs.get(job_id)
    if not job or not job.get('file') or not os.path.exists(job['file']):
        return 'File not found', 404
    filename = f"trading_{job.get('type', 'video')}_{job_id[:6]}.mp4"
    return send_file(job['file'], as_attachment=True, download_name=filename, mimetype='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

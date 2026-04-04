import os, json, random, logging, threading, subprocess, requests, uuid, asyncio, time
import edge_tts
from flask import Flask, jsonify, request, send_file
from groq import Groq

# ══════════════════════════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════════════════════════
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

GROQ_API_KEY     = os.environ.get('GROQ_API_KEY', '')
PEXELS_API_KEY   = os.environ.get('PEXELS_API_KEY', '')
DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY', '')

groq_client = Groq(api_key=GROQ_API_KEY)
os.makedirs('videos', exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
FONT_PATH = '/tmp/Montserrat-Bold.ttf'
FONT_URL  = 'https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf'

DEEPGRAM_VOICES = {
    'short_hook':   'aura-orion-en',
    'core_message': 'aura-orion-en',
    'authority':    'aura-zeus-en',
    'loop_video':   'aura-luna-en',
}
EDGE_VOICES = {
    'short_hook':   'en-US-AndrewNeural',
    'core_message': 'en-US-AndrewNeural',
    'authority':    'en-US-ChristopherNeural',
    'loop_video':   'en-US-AndrewNeural',
}
VOICE_ENGINE = 'Deepgram Aura Neural' if DEEPGRAM_API_KEY else 'Microsoft Neural (free)'

TYPE_CONFIG = {
    'short_hook':   {'words': '15-30',   'style': 'Ultra-punchy. ONE shocking statement. Stops scroll. Zero filler.',         'dur': '7-12s'},
    'core_message': {'words': '70-110',  'style': 'Educational, direct. Short sentences. Builds to one key insight.',         'dur': '20-35s'},
    'authority':    {'words': '130-190', 'style': 'Expert authority. Deep insight. Trading mentor tone. Structured points.',  'dur': '40-60s'},
    'loop_video':   {'words': '45-75',   'style': 'Hypnotic, repeatable. Every line hits hard. Ends wanting a replay.',      'dur': '15-25s'},
}

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
    ],
}

BG_QUERIES = [
    'luxury car driving night',      'stock market trading screen',
    'private jet interior',          'luxury penthouse city view',
    'forex charts finance',          'businessman walking city',
    'luxury watch close up',         'skyscraper city night lights',
    'trading desk multiple screens', 'yacht ocean luxury',
    'gold bars wealth',              'financial district blur',
]

# ══════════════════════════════════════════════════════════════════════════════
# FONT  (1 HTTP call at startup, then cached forever on disk)
# ══════════════════════════════════════════════════════════════════════════════
def ensure_font():
    if os.path.exists(FONT_PATH):
        return FONT_PATH
    try:
        r = requests.get(FONT_URL, timeout=30)
        r.raise_for_status()
        with open(FONT_PATH, 'wb') as f:
            f.write(r.content)
        logger.info('✅ Font cached: Montserrat Bold')
        return FONT_PATH
    except Exception as e:
        logger.warning(f'⚠️ Font download failed: {e}')
        return None

FONT = ensure_font()

# ══════════════════════════════════════════════════════════════════════════════
# PEXELS URL CACHE
# Strategy: 1 Pexels API call per query at startup (12 calls total, background).
# During video generation = ZERO Pexels API calls.
# Pool auto-refills per-query only when that bucket runs dry.
# ══════════════════════════════════════════════════════════════════════════════
_url_pool: dict[str, list[str]] = {}
_pool_lock = threading.Lock()

def _pexels_fetch(query: str, min_dur: int = 15) -> list[str]:
    """One Pexels API call — returns list of portrait HD video URLs."""
    try:
        r = requests.get(
            'https://api.pexels.com/videos/search',
            params={'query': query, 'per_page': 15, 'orientation': 'portrait', 'size': 'large'},
            headers={'Authorization': PEXELS_API_KEY},
            timeout=30,
        )
        r.raise_for_status()
        urls = []
        for v in r.json().get('videos', []):
            if v.get('duration', 0) < min_dur:
                continue
            files   = v.get('video_files', [])
            portrait = sorted(
                [f for f in files if f.get('width', 1) < f.get('height', 0)] or files,
                key=lambda f: f.get('width', 0) * f.get('height', 0),
                reverse=True,
            )
            if portrait:
                urls.append(portrait[0]['link'])
        return urls
    except Exception as e:
        logger.warning(f'⚠️ Pexels "{query}" failed: {e}')
        return []

def _warm_pool():
    """Background startup task: 1 Pexels call per BG query."""
    if not PEXELS_API_KEY:
        logger.warning('⚠️ No PEXELS_API_KEY — Pexels disabled')
        return
    for q in BG_QUERIES:
        urls = _pexels_fetch(q)
        if urls:
            with _pool_lock:
                _url_pool[q] = urls
            logger.info(f'✅ Pool "{q}": {len(urls)} URLs cached')

def pick_bg_url(min_dur: int = 10) -> str:
    """Return a cached BG video URL — refetches only if that bucket is empty."""
    query = random.choice(BG_QUERIES)
    with _pool_lock:
        bucket = list(_url_pool.get(query, []))
    if not bucket:
        logger.info(f'🔄 Refilling pool for: {query}')
        bucket = _pexels_fetch(query, min_dur) or _pexels_fetch('luxury lifestyle', min_dur)
        with _pool_lock:
            _url_pool[query] = bucket
    return random.choice(bucket) if bucket else ''

threading.Thread(target=_warm_pool, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
# JOB STORE + AUTO-CLEANUP (files deleted after 1 hour)
# ══════════════════════════════════════════════════════════════════════════════
jobs: dict = {}

def _cleanup_loop():
    while True:
        time.sleep(300)
        cutoff = time.time() - 3600
        for jid in list(jobs):
            j = jobs.get(jid, {})
            if j.get('done_at', 0) < cutoff and j.get('status') in ('done', 'error'):
                try:
                    if j.get('file'):
                        os.remove(j['file'])
                except Exception:
                    pass
                jobs.pop(jid, None)

threading.Thread(target=_cleanup_loop, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT  (1 Groq call per video — compact prompt = fewer tokens)
# ══════════════════════════════════════════════════════════════════════════════
def generate_script(video_type: str) -> dict:
    topic = random.choice(TOPICS[video_type])
    cfg   = TYPE_CONFIG[video_type]
    prompt = (
        f'Elite TikTok scriptwriter. Luxury trading psychology.\n'
        f'Type: {video_type.replace("_"," ").title()} | Topic: {topic}\n'
        f'Words: {cfg["words"]} | Style: {cfg["style"]}\n'
        f'Rules: no greetings, no weak openers, max 12 words/sentence, every line earns its place.\n'
        f'Return ONLY valid JSON (no markdown):\n'
        f'{{"script":"...","caption":"<120 chars","hashtags":"#trading #tradingpsychology #mindset #wealthmindset #forex #discipline #luxurylifestyle","topic":"{topic}"}}'
    )
    resp = groq_client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.85,
        max_tokens=450,
    )
    raw = resp.choices[0].message.content.strip()
    if '```' in raw:
        raw = raw.split('```')[1].lstrip('json').strip().split('```')[0].strip()
    return json.loads(raw)

# ══════════════════════════════════════════════════════════════════════════════
# VOICEOVER  (1 Deepgram call — or free edge-tts — per video)
# ══════════════════════════════════════════════════════════════════════════════
async def _edge_tts_save(text: str, voice: str, path: str):
    await edge_tts.Communicate(text, voice, rate='+3%').save(path)

def generate_voiceover(script: str, video_type: str, uid: str) -> str:
    path = f'videos/audio_{uid}.mp3'
    if DEEPGRAM_API_KEY:
        voice = DEEPGRAM_VOICES.get(video_type, 'aura-orion-en')
        r = requests.post(
            f'https://api.deepgram.com/v1/speak?model={voice}&encoding=mp3',
            headers={'Authorization': f'Token {DEEPGRAM_API_KEY}', 'Content-Type': 'application/json'},
            json={'text': script},
            timeout=60,
        )
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)
        logger.info(f'🎙️ Deepgram: {voice}')
    else:
        voice = EDGE_VOICES.get(video_type, 'en-US-AndrewNeural')
        loop  = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_edge_tts_save(script, voice, path))
        finally:
            loop.close()
        logger.info(f'🎙️ edge-tts: {voice}')
    return path

# ══════════════════════════════════════════════════════════════════════════════
# AUDIO DURATION  (mutagen = pure Python, no system dep; ffprobe fallback)
# ══════════════════════════════════════════════════════════════════════════════
def get_audio_duration(path: str) -> float:
    try:
        from mutagen.mp3 import MP3
        return MP3(path).info.length
    except Exception:
        pass
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', path],
            capture_output=True, text=True, timeout=15,
        ).stdout
        for s in json.loads(out).get('streams', []):
            if s.get('codec_type') == 'audio':
                return float(s['duration'])
    except Exception as e:
        logger.warning(f'⚠️ Duration detection failed: {e}')
    return 30.0

# ══════════════════════════════════════════════════════════════════════════════
# VIDEO BUILDER  (FFmpeg — full cinematic quality preserved)
# ══════════════════════════════════════════════════════════════════════════════
def _esc(text: str) -> str:
    for old, new in [('\\','\\\\'), ("'","\\'"), (':','\\:'), ('%','\\%'), ('[','\\['), (']','\\]')]:
        text = text.replace(old, new)
    return text

def _subtitle_filters(script: str, dur: float) -> list[str]:
    """3-word TikTok captions timed precisely to audio."""
    words  = script.split()
    chunks = [' '.join(words[i:i+3]) for i in range(0, len(words), 3)]
    tpc    = dur / max(len(chunks), 1)
    fa     = f":fontfile='{FONT}'" if FONT and os.path.exists(FONT) else ''
    return [
        f"drawtext=text='{_esc(c)}':fontsize=64:fontcolor=white"
        f":box=1:boxcolor=black@0.55:boxborderw=24{fa}"
        f":x=(w-text_w)/2:y=(h*0.70)"
        f":enable='between(t,{round(i*tpc,2)},{round((i+1)*tpc-0.05,2)})'"
        for i, c in enumerate(chunks)
    ]

def _download(url: str, path: str):
    r = requests.get(url, stream=True, timeout=90)
    r.raise_for_status()
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def create_video(audio_path: str, script_data: dict, uid: str) -> str:
    bg_path  = f'/tmp/bg_{uid}.mp4'
    out_path = f'videos/final_{uid}.mp4'
    dur      = get_audio_duration(audio_path)

    _download(pick_bg_url(int(dur)), bg_path)

    fa        = f":fontfile='{FONT}'" if FONT and os.path.exists(FONT) else ''
    watermark = (
        f"drawtext=text='TRADING MINDSET':fontsize=30:fontcolor=#FFD700"
        f":box=1:boxcolor=black@0.45:boxborderw=14{fa}"
        f":x=(w-text_w)/2:y=64"
    )

    vf = ','.join([
        'scale=1080:1920:force_original_aspect_ratio=increase',  # portrait HD
        'crop=1080:1920',
        'eq=brightness=-0.08:saturation=1.40:contrast=1.10:gamma=0.92',  # cinematic grade
        "curves=r='0/0 0.5/0.48 1/0.90':b='0/0 0.5/0.52 1/1.0'",       # teal-orange tint
        'vignette=PI/4.5',                                                # edge vignette
        'fade=t=in:st=0:d=0.5',                                          # soft fade-in
        watermark,
    ] + _subtitle_filters(script_data['script'], dur))

    result = subprocess.run([
        'ffmpeg', '-y',
        '-stream_loop', '-1', '-i', bg_path,
        '-i', audio_path,
        '-vf', vf,
        '-af', 'volume=1.3,acompressor=threshold=-18dB:ratio=3:attack=5:release=50',
        '-t', str(dur + 0.3),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',   # fast = 40% quicker, same quality at CRF 20
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest', '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        out_path,
    ], capture_output=True, text=True)

    for p in (bg_path, audio_path):
        try: os.remove(p)
        except Exception: pass

    if result.returncode != 0:
        raise RuntimeError(f'FFmpeg failed:\n{result.stderr[-2000:]}')
    return out_path

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
def run_pipeline(job_id: str, video_type: str):
    def step(s): jobs[job_id]['step'] = s
    try:
        step('✍️ Writing script...')
        script_data = generate_script(video_type)

        step('🎙️ Generating voiceover...')
        audio_path  = generate_voiceover(script_data['script'], video_type, job_id)

        step('🎬 Building video...')
        video_path  = create_video(audio_path, script_data, job_id)

        jobs[job_id].update({
            'status':   'done',
            'step':     '✅ Ready!',
            'file':     video_path,
            'error':    None,
            'caption':  script_data.get('caption', ''),
            'hashtags': script_data.get('hashtags', ''),
            'voice':    VOICE_ENGINE,
            'done_at':  time.time(),
        })
        logger.info(f'✅ Job {job_id} done')

    except Exception as e:
        logger.error(f'❌ Job {job_id} failed: {e}', exc_info=True)
        jobs[job_id].update({'status': 'error', 'step': '❌ Failed', 'error': str(e), 'done_at': time.time()})

# ══════════════════════════════════════════════════════════════════════════════
# HTML UI
# ══════════════════════════════════════════════════════════════════════════════
_VOICE_BADGE = (
    '🎙️ Deepgram Aura Neural · 1080p' if DEEPGRAM_API_KEY
    else '🎙️ Microsoft Neural · 1080p · Free'
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
    background: var(--bg); color: var(--text);
    font-family: 'Inter', sans-serif;
    min-height: 100vh; padding: 32px 16px 48px;
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 48px 48px;
  }}
  .header {{ text-align: center; margin-bottom: 36px; }}
  h1 {{
    font-family: 'Bebas Neue', sans-serif; font-size: 42px; letter-spacing: 3px;
    background: linear-gradient(135deg, var(--gold), var(--red));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; line-height: 1.1; margin-bottom: 6px;
  }}
  .sub {{ color: var(--muted); font-size: 13px; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 16px; }}
  .badge {{
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 100px; padding: 5px 14px; font-size: 11px; color: var(--muted);
  }}
  .badge-dot {{ width: 6px; height: 6px; background: #3ddc84; border-radius: 50%; box-shadow: 0 0 8px #3ddc84; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 540px; margin: 0 auto 36px; }}
  .btn {{
    border: 1px solid transparent; border-radius: 16px; padding: 22px 14px 18px;
    cursor: pointer; color: #fff;
    transition: transform .18s, box-shadow .18s, opacity .18s;
    text-align: left; position: relative; overflow: hidden;
  }}
  .btn::after {{
    content: ''; position: absolute; inset: 0;
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
  #status-box {{ max-width: 540px; margin: 0 auto; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 18px; padding: 22px; margin-bottom: 14px;
  }}
  .card-label {{ font-size: 10px; font-weight: 600; color: var(--muted); letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 10px; }}
  .step-text  {{ font-size: 17px; font-weight: 600; min-height: 26px; display: flex; align-items: center; gap: 8px; }}
  .progress   {{ height: 3px; background: var(--border); border-radius: 4px; margin-top: 16px; overflow: hidden; }}
  .progress-bar {{
    height: 100%; background: linear-gradient(90deg, var(--gold), var(--red));
    border-radius: 4px; transition: width .5s cubic-bezier(.4,0,.2,1);
  }}
  .dl-btn {{
    display: flex; align-items: center; justify-content: center; gap: 8px;
    width: 100%; padding: 18px;
    background: linear-gradient(135deg, var(--gold), var(--gold2));
    border: none; border-radius: 14px; color: #1a0f00;
    font-size: 16px; font-weight: 800; cursor: pointer;
    text-decoration: none; letter-spacing: .5px; margin-top: 16px;
    transition: transform .15s, box-shadow .15s;
  }}
  .dl-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(255,215,0,.3); }}
  .caption-box {{
    background: var(--bg); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 16px; font-size: 13px; color: #9090b0;
    line-height: 1.7; white-space: pre-wrap; word-break: break-word;
  }}
  .meta-row  {{ display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--muted); margin-bottom: 12px; }}
  .meta-pill {{ background: var(--bg); border: 1px solid var(--border); border-radius: 100px; padding: 3px 10px; font-size: 10px; }}
  .hidden {{ display: none; }}
  .error  {{ color: #FF416C; font-size: 13px; line-height: 1.5; }}
  .spinner {{
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid var(--border); border-top-color: var(--gold);
    border-radius: 50%; animation: spin .7s linear infinite; flex-shrink: 0;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>

<div class="header">
  <h1>⚡ Trading Video<br>Generator</h1>
  <p class="sub">Luxury · Mindset · Psychology</p>
  <span class="badge"><span class="badge-dot"></span>{_VOICE_BADGE}</span>
</div>

<div class="grid">
  <button class="btn b1" onclick="go('short_hook')">
    <span class="icon">🪝</span><span class="label">Short Hook</span>
    <span class="dur">7–12s · Go viral</span>
  </button>
  <button class="btn b2" onclick="go('core_message')">
    <span class="icon">📢</span><span class="label">Core Message</span>
    <span class="dur">20–35s · Retention</span>
  </button>
  <button class="btn b3" onclick="go('authority')">
    <span class="icon">🔥</span><span class="label">Authority</span>
    <span class="dur">40–60s · Build trust</span>
  </button>
  <button class="btn b4" onclick="go('loop_video')">
    <span class="icon">🔄</span><span class="label">Loop Video</span>
    <span class="dur">15–25s · Replay boost</span>
  </button>
</div>

<div id="status-box" class="hidden">
  <div class="card">
    <div class="card-label">Status</div>
    <div class="step-text" id="step-text">Starting...</div>
    <div class="progress"><div class="progress-bar" id="prog" style="width:5%"></div></div>
  </div>
  <div id="result-box" class="hidden">
    <a id="dl-link" class="dl-btn" href="#" download>⬇️ Download Video</a>
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
  '✍️ Writing script...':       20,
  '🎙️ Generating voiceover...': 55,
  '🎬 Building video...':        82,
  '✅ Ready!':                   100,
}};
let timer = null;

function go(type) {{
  clearInterval(timer);
  document.getElementById('status-box').classList.remove('hidden');
  document.getElementById('result-box').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  setStep('<span class="spinner"></span> Starting...');
  document.getElementById('prog').style.width = '5%';
  fetch('/generate', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ type }}),
  }})
  .then(r => r.json())
  .then(d => {{ if (d.job_id) poll(d.job_id); }});
}}

function poll(id) {{
  timer = setInterval(() => {{
    fetch('/status/' + id).then(r => r.json()).then(d => {{
      document.getElementById('prog').style.width = (PROGS[d.step] || 10) + '%';
      if (d.status === 'running') {{
        setStep('<span class="spinner"></span> ' + d.step);
      }} else if (d.status === 'done') {{
        clearInterval(timer);
        setStep('✅ Video Ready!');
        document.getElementById('prog').style.width = '100%';
        document.getElementById('result-box').classList.remove('hidden');
        document.getElementById('dl-link').href = '/download/' + id;
        document.getElementById('voice-pill').textContent = d.voice || '';
        document.getElementById('caption-text').textContent =
          ((d.caption || '') + '\\n\\n' + (d.hashtags || '')).trim();
      }} else if (d.status === 'error') {{
        clearInterval(timer);
        setStep('❌ Failed');
        document.getElementById('error-box').classList.remove('hidden');
        document.getElementById('error-text').textContent = d.error;
      }}
    }});
  }}, 2000);
}}

function setStep(html) {{ document.getElementById('step-text').innerHTML = html; }}
</script>
</body>
</html>'''

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def index():
    return HTML

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'pool_urls': sum(len(v) for v in _url_pool.values()), 'jobs': len(jobs)})

@app.route('/generate', methods=['POST'])
def generate():
    data       = request.get_json() or {}
    video_type = data.get('type', 'short_hook')
    if video_type not in TYPE_CONFIG:
        return jsonify({'error': 'Invalid type'}), 400
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {'status': 'running', 'step': '✍️ Writing script...', 'file': None, 'error': None, 'type': video_type, 'done_at': 0}
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
    filename = f"trading_{job.get('type','video')}_{job_id[:6]}.mp4"
    return send_file(job['file'], as_attachment=True, download_name=filename, mimetype='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

import os, json, random, logging, threading, subprocess, requests, time, uuid, asyncio
import edge_tts
from flask import Flask, jsonify, request, send_file
from groq import Groq

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── ENV ───────────────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.environ.get('GROQ_API_KEY', '')
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY', '')

groq_client = Groq(api_key=GROQ_API_KEY)
os.makedirs('videos', exist_ok=True)

# Edge TTS voices — completely free, no API key
EDGE_VOICES = {
    'short_hook':   'en-US-GuyNeural',
    'core_message': 'en-US-GuyNeural',
    'authority':    'en-US-ChristopherNeural',
    'loop_video':   'en-US-GuyNeural',
}

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
    'short_hook':   {'words': '15-30',   'style': 'Ultra-punchy. ONE shocking statement. Stops scroll instantly.', 'dur': '7-12s'},
    'core_message': {'words': '70-110',  'style': 'Educational, direct, confident. Builds to one key insight.',    'dur': '20-35s'},
    'authority':    {'words': '130-190', 'style': 'Expert-level authority. Deep insight. Trading mentor tone.',     'dur': '40-60s'},
    'loop_video':   {'words': '45-75',   'style': 'Hypnotic, repeatable. Ends making viewer hit replay.',           'dur': '15-25s'},
}

def generate_script(video_type):
    topic = random.choice(TOPICS[video_type])
    cfg = TYPE_CONFIG[video_type]
    prompt = f"""You are an elite TikTok scriptwriter for luxury trading psychology content.
Video Type: {video_type.replace('_',' ').title()}
Topic: {topic}
Word Count: {cfg['words']} words
Style: {cfg['style']}
Tone: Premium, confident, no-BS. Reference luxury sparingly.
Core themes: discipline, patience, emotional control, risk management, wealth psychology.

Respond ONLY in valid JSON. No markdown. No extra text.
{{"script":"the full spoken script","caption":"TikTok caption under 120 chars","hashtags":"#trading #tradingpsychology #mindset #wealthmindset #forex #discipline #luxurylifestyle","topic":"{topic}"}}"""

    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.88, max_tokens=700
    )
    raw = resp.choices[0].message.content.strip()
    if '```json' in raw: raw = raw.split('```json')[1].split('```')[0].strip()
    elif '```' in raw:   raw = raw.split('```')[1].split('```')[0].strip()
    return json.loads(raw)

# ══════════════════════════════════════════════════════════════════════════════
# VOICE GENERATOR — Microsoft Edge TTS (100% free, no API key)
# ══════════════════════════════════════════════════════════════════════════════
async def _tts_async(script, voice, path):
    communicate = edge_tts.Communicate(script, voice, rate='+5%')
    await communicate.save(path)

def generate_voiceover(script, video_type, uid):
    path  = f'videos/audio_{uid}.mp3'
    voice = EDGE_VOICES.get(video_type, 'en-US-GuyNeural')
    asyncio.run(_tts_async(script, voice, path))
    logger.info(f"Voice generated: {path} (voice: {voice})")
    return path

# ══════════════════════════════════════════════════════════════════════════════
# VIDEO GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
BG_QUERIES = [
    'luxury car driving night','stock market trading screen','private jet interior',
    'luxury penthouse city view','forex charts finance','businessman walking city',
    'luxury watch close up','skyscraper city night lights','trading desk multiple screens',
    'yacht ocean luxury','speed luxury sports car','financial district blur','gold bars wealth',
]

def get_pexels_video(query, min_dur=10):
    headers = {'Authorization': PEXELS_API_KEY}
    try:
        r = requests.get(f'https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=portrait', headers=headers, timeout=30)
        videos = r.json().get('videos', [])
    except: videos = []
    if not videos:
        r = requests.get('https://api.pexels.com/videos/search?query=luxury lifestyle&per_page=15&orientation=portrait', headers=headers, timeout=30)
        videos = r.json().get('videos', [])
    suitable = [v for v in videos if v.get('duration',0) >= min_dur] or videos
    video = random.choice(suitable)
    files = video.get('video_files', [])
    portrait = [f for f in files if f.get('width',1) < f.get('height',0)] or files
    portrait.sort(key=lambda f: f.get('width',0)*f.get('height',0), reverse=True)
    return portrait[0]['link']

def download_file(url, path):
    r = requests.get(url, stream=True, timeout=90)
    r.raise_for_status()
    with open(path,'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

def get_audio_duration(path):
    result = subprocess.run(['ffprobe','-v','quiet','-print_format','json','-show_streams',path], capture_output=True, text=True)
    for s in json.loads(result.stdout).get('streams',[]):
        if s.get('codec_type') == 'audio': return float(s.get('duration',30.0))
    return 30.0

def esc(text):
    return text.replace('\\','\\\\').replace("'","\\'").replace(':','\\:').replace('%','\\%').replace('[','\\[').replace(']','\\]')

def create_video(audio_path, script_data, video_type, uid):
    bg_path  = f'videos/bg_{uid}.mp4'
    out_path = f'videos/final_{uid}.mp4'
    dur = get_audio_duration(audio_path)

    bg_url = get_pexels_video(random.choice(BG_QUERIES), int(dur))
    download_file(bg_url, bg_path)

    words = script_data['script'].split()
    chunks = [' '.join(words[i:i+4]) for i in range(0, len(words), 4)]
    tpc = dur / max(len(chunks),1)
    sub_filters = [
        f"drawtext=text='{esc(c)}':fontsize=54:fontcolor=white:bordercolor=black:borderw=4:x=(w-text_w)/2:y=(h*0.72):enable='between(t,{round(i*tpc,2)},{round((i+1)*tpc,2)})'"
        for i, c in enumerate(chunks)
    ]

    vf = ','.join([
        'scale=720:1280:force_original_aspect_ratio=increase',
        'crop=720:1280',
        'eq=brightness=-0.15:saturation=1.2',
        f"drawtext=text='TRADING MINDSET':fontsize=30:fontcolor=gold:bordercolor=black:borderw=3:x=(w-text_w)/2:y=55",
    ] + sub_filters)

    cmd = ['ffmpeg','-y','-stream_loop','-1','-i',bg_path,'-i',audio_path,'-vf',vf,
           '-af','volume=1.4','-t',str(dur+0.3),'-c:v','libx264','-preset','fast',
           '-crf','22','-c:a','aac','-b:a','128k','-shortest','-movflags','+faststart',
           '-pix_fmt','yuv420p', out_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    try: os.remove(bg_path)
    except: pass
    try: os.remove(audio_path)
    except: pass

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-1000:]}")
    return out_path

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
def run_pipeline(job_id, video_type):
    uid = job_id
    try:
        jobs[job_id] = {'status':'running','step':'✍️ Writing script...','file':None,'error':None,'type':video_type}
        script_data = generate_script(video_type)

        jobs[job_id]['step'] = '🎙️ Generating voiceover...'
        audio_path = generate_voiceover(script_data['script'], video_type, uid)

        jobs[job_id]['step'] = '🎬 Building video...'
        video_path = create_video(audio_path, script_data, video_type, uid)

        jobs[job_id] = {
            'status':'done','step':'✅ Ready!','file':video_path,
            'error':None,'type':video_type,
            'caption':script_data.get('caption',''),
            'hashtags':script_data.get('hashtags','')
        }
        logger.info(f"✅ Job {job_id} done")

    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)
        jobs[job_id] = {'status':'error','step':'❌ Failed','file':None,'error':str(e),'type':video_type}

# ══════════════════════════════════════════════════════════════════════════════
# HTML UI
# ══════════════════════════════════════════════════════════════════════════════
HTML = '''<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trading Video Generator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0a0a0f; color: #fff; font-family: -apple-system, sans-serif; min-height: 100vh; padding: 24px 16px; }
  h1 { text-align: center; font-size: 22px; color: #FFD700; margin-bottom: 6px; }
  .sub { text-align: center; color: #666; font-size: 13px; margin-bottom: 32px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; max-width: 600px; margin: 0 auto 32px; }
  .btn { border: none; border-radius: 14px; padding: 20px 12px; cursor: pointer; font-size: 14px; font-weight: 700; color: #fff; transition: all .2s; }
  .btn:active { transform: scale(0.96); }
  .btn .icon { font-size: 28px; display: block; margin-bottom: 8px; }
  .btn .label { display: block; font-size: 13px; }
  .btn .dur { display: block; font-size: 11px; opacity: 0.7; margin-top: 3px; }
  .b1 { background: linear-gradient(135deg, #FF416C, #FF4B2B); }
  .b2 { background: linear-gradient(135deg, #4776E6, #8E54E9); }
  .b3 { background: linear-gradient(135deg, #F7971E, #FFD200); }
  .b4 { background: linear-gradient(135deg, #11998e, #38ef7d); }
  .b3 .label, .b3 .dur, .b4 .label, .b4 .dur { color: #000; }
  #status-box { max-width: 600px; margin: 0 auto; }
  .card { background: #161620; border-radius: 16px; padding: 20px; margin-bottom: 16px; border: 1px solid #222; }
  .card-title { font-size: 12px; color: #666; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
  .step { font-size: 18px; font-weight: 600; min-height: 28px; }
  .progress { height: 4px; background: #222; border-radius: 4px; margin-top: 14px; overflow: hidden; }
  .progress-bar { height: 100%; background: linear-gradient(90deg, #FFD700, #FF416C); border-radius: 4px; transition: width 0.5s; }
  .dl-btn { display: block; width: 100%; padding: 18px; background: linear-gradient(135deg, #FFD700, #FF8C00); border: none; border-radius: 14px; color: #000; font-size: 17px; font-weight: 800; cursor: pointer; text-align: center; text-decoration: none; margin-top: 16px; }
  .caption-box { background: #0d0d18; border-radius: 10px; padding: 14px; font-size: 13px; color: #aaa; line-height: 1.6; white-space: pre-wrap; }
  .hidden { display: none; }
  .error { color: #FF416C; font-size: 14px; }
  .spinner { display: inline-block; width: 18px; height: 18px; border: 3px solid #333; border-top-color: #FFD700; border-radius: 50%; animation: spin .7s linear infinite; vertical-align: middle; margin-right: 8px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .badge { display: inline-block; background: #1a1a2e; border: 1px solid #333; border-radius: 20px; padding: 4px 12px; font-size: 11px; color: #666; margin-bottom: 24px; }
</style>
</head>
<body>
<h1>⚡ Trading Video Generator</h1>
<p class="sub">Luxury · Mindset · Psychology</p>
<div style="text-align:center"><span class="badge">🎙️ Microsoft Neural Voice · No API key needed</span></div>

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
    <div class="card-title">Status</div>
    <div class="step" id="step-text">Starting...</div>
    <div class="progress"><div class="progress-bar" id="prog" style="width:5%"></div></div>
  </div>
  <div id="result-box" class="hidden">
    <a id="dl-link" class="dl-btn" href="#" download>⬇️ Download Video</a>
    <div class="card" style="margin-top:14px;">
      <div class="card-title">Caption + Hashtags</div>
      <div class="caption-box" id="caption-text"></div>
    </div>
  </div>
  <div id="error-box" class="hidden card">
    <div class="card-title">Error</div>
    <div class="error" id="error-text"></div>
  </div>
</div>

<script>
let pollTimer = null;
const progs = {'✍️ Writing script...':20,'🎙️ Generating voiceover...':55,'🎬 Building video...':80,'✅ Ready!':100};

function generate(type) {
  clearInterval(pollTimer);
  document.getElementById('status-box').classList.remove('hidden');
  document.getElementById('result-box').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  document.getElementById('step-text').innerHTML = '<span class="spinner"></span>Starting...';
  document.getElementById('prog').style.width = '5%';

  fetch('/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({type})})
    .then(r => r.json()).then(d => { if (d.job_id) poll(d.job_id); });
}

function poll(id) {
  pollTimer = setInterval(() => {
    fetch('/status/' + id).then(r => r.json()).then(d => {
      document.getElementById('prog').style.width = (progs[d.step] || 10) + '%';
      if (d.status === 'running') {
        document.getElementById('step-text').innerHTML = '<span class="spinner"></span>' + d.step;
      } else if (d.status === 'done') {
        clearInterval(pollTimer);
        document.getElementById('step-text').textContent = '✅ Video Ready!';
        document.getElementById('prog').style.width = '100%';
        document.getElementById('result-box').classList.remove('hidden');
        document.getElementById('dl-link').href = '/download/' + id;
        document.getElementById('caption-text').textContent = (d.caption||'') + '\n\n' + (d.hashtags||'');
      } else if (d.status === 'error') {
        clearInterval(pollTimer);
        document.getElementById('step-text').textContent = '❌ Failed';
        document.getElementById('error-box').classList.remove('hidden');
        document.getElementById('error-text').textContent = d.error;
      }
    });
  }, 2000);
}
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
    data = request.get_json()
    video_type = data.get('type', 'short_hook')
    if video_type not in TYPE_CONFIG:
        return jsonify({'error': 'Invalid type'}), 400
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {'status':'running','step':'✍️ Writing script...','file':None,'error':None,'type':video_type}
    threading.Thread(target=run_pipeline, args=(job_id, video_type), daemon=True).start()
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def status(job_id):
    return jsonify(jobs.get(job_id, {'status':'not_found','step':'?','error':'Job not found'}))

@app.route('/download/<job_id>')
def download(job_id):
    job = jobs.get(job_id)
    if not job or not job.get('file') or not os.path.exists(job['file']):
        return 'File not found', 404
    filename = f"trading_{job.get('type','video')}_{job_id[:6]}.mp4"
    return send_file(job['file'], as_attachment=True, download_name=filename, mimetype='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

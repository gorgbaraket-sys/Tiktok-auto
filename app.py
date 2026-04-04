import os, json, random, logging, threading, subprocess, requests, time
from flask import Flask, jsonify, redirect, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime
from groq import Groq

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── ENV ───────────────────────────────────────────────────────────────────────
BEIRUT_TZ     = pytz.timezone('Asia/Beirut')
GROQ_API_KEY        = os.environ.get('GROQ_API_KEY', '')
ELEVENLABS_API_KEY  = os.environ.get('ELEVENLABS_API_KEY', '')
ELEVENLABS_VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')
PEXELS_API_KEY      = os.environ.get('PEXELS_API_KEY', '')
CLIENT_KEY          = os.environ.get('TIKTOK_CLIENT_KEY', '')
CLIENT_SECRET       = os.environ.get('TIKTOK_CLIENT_SECRET', '')
RAILWAY_DOMAIN      = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
REDIRECT_URI        = f'https://{RAILWAY_DOMAIN}/callback'

groq_client = Groq(api_key=GROQ_API_KEY)

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
    'short_hook':   {'words': '15-30',   'style': 'Ultra-punchy. ONE shocking statement. Stops scroll instantly.'},
    'core_message': {'words': '70-110',  'style': 'Educational, direct, confident. Builds to one key insight.'},
    'authority':    {'words': '130-190', 'style': 'Expert-level authority. Deep insight. Trading mentor tone.'},
    'loop_video':   {'words': '45-75',   'style': 'Hypnotic, repeatable. Ends making viewer hit replay.'},
}

def generate_script(video_type, duration_range):
    topic = random.choice(TOPICS[video_type])
    cfg = TYPE_CONFIG[video_type]
    prompt = f"""You are an elite TikTok scriptwriter for luxury trading psychology content.
Video Type: {video_type.replace('_',' ').title()}
Topic: {topic}
Duration: {duration_range[0]}-{duration_range[1]} seconds when spoken
Word Count: {cfg['words']} words
Style: {cfg['style']}
Tone: Premium, confident, no-BS. Reference luxury sparingly (freedom, Lambo, private jet).
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
# VOICE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
VOICE_SETTINGS = {
    'short_hook':   {'stability':0.35,'similarity_boost':0.80,'style':0.70},
    'core_message': {'stability':0.50,'similarity_boost':0.75,'style':0.50},
    'authority':    {'stability':0.65,'similarity_boost':0.75,'style':0.35},
    'loop_video':   {'stability':0.55,'similarity_boost':0.78,'style':0.55},
}

def generate_voiceover(script, video_type):
    os.makedirs('videos', exist_ok=True)
    uid = os.urandom(4).hex()
    path = f'videos/{video_type}_{uid}.mp3'
    s = VOICE_SETTINGS.get(video_type, VOICE_SETTINGS['core_message'])
    resp = requests.post(
        f'https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}',
        headers={'Accept':'audio/mpeg','Content-Type':'application/json','xi-api-key':ELEVENLABS_API_KEY},
        json={'text':script,'model_id':'eleven_multilingual_v2','voice_settings':{**s,'use_speaker_boost':True}},
        timeout=60
    )
    resp.raise_for_status()
    with open(path,'wb') as f: f.write(resp.content)
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
    return path

def get_audio_duration(path):
    result = subprocess.run(['ffprobe','-v','quiet','-print_format','json','-show_streams',path], capture_output=True, text=True)
    for s in json.loads(result.stdout).get('streams',[]):
        if s.get('codec_type') == 'audio': return float(s.get('duration',30.0))
    return 30.0

def esc(text):
    return text.replace('\\','\\\\').replace("'","\\'").replace(':','\\:').replace('%','\\%').replace('[','\\[').replace(']','\\]')

def create_video(audio_path, script_data, video_type):
    os.makedirs('videos', exist_ok=True)
    uid = os.urandom(4).hex()
    bg_path = f'videos/bg_{uid}.mp4'
    out_path = f'videos/{video_type}_{uid}_final.mp4'
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
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-1500:]}")

    for p in [bg_path, audio_path]:
        try: os.remove(p)
        except: pass

    return out_path

# ══════════════════════════════════════════════════════════════════════════════
# TIKTOK POSTER
# ══════════════════════════════════════════════════════════════════════════════
def post_to_tiktok(video_path, caption, hashtags):
    token = os.environ.get('TIKTOK_ACCESS_TOKEN','')
    if not token: raise RuntimeError("TIKTOK_ACCESS_TOKEN not set")
    file_size = os.path.getsize(video_path)
    full_title = f"{caption}\n\n{hashtags}"[:2200]
    headers = {'Authorization':f'Bearer {token}','Content-Type':'application/json; charset=UTF-8'}

    init = requests.post(f'https://open.tiktokapis.com/v2/post/publish/video/init/',
        json={'post_info':{'title':full_title,'privacy_level':'PUBLIC_TO_EVERYONE','disable_duet':False,'disable_comment':False,'disable_stitch':False,'video_cover_timestamp_ms':1000},
              'source_info':{'source':'FILE_UPLOAD','video_size':file_size,'chunk_size':file_size,'total_chunk_count':1}},
        headers=headers, timeout=30)
    init.raise_for_status()
    data = init.json()
    upload_url = data['data']['upload_url']
    publish_id = data['data']['publish_id']

    with open(video_path,'rb') as f: video_bytes = f.read()
    requests.put(upload_url, data=video_bytes,
        headers={'Content-Type':'video/mp4','Content-Range':f'bytes 0-{file_size-1}/{file_size}','Content-Length':str(file_size)},
        timeout=120).raise_for_status()

    status = 'PROCESSING'
    for _ in range(10):
        time.sleep(3)
        r = requests.post('https://open.tiktokapis.com/v2/post/publish/status/fetch/',
            json={'publish_id':publish_id}, headers=headers, timeout=30)
        status = r.json().get('data',{}).get('status','UNKNOWN')
        if status in ('PUBLISH_COMPLETE','SUCCESS'): break
        if status in ('FAILED','ERROR'): raise RuntimeError(f"TikTok publish failed: {status}")

    try: os.remove(video_path)
    except: pass
    return {'publish_id':publish_id,'status':status}

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
def generate_and_post(video_type, duration_range):
    logger.info(f"▶ Pipeline: {video_type}")
    script_data = generate_script(video_type, duration_range)
    audio_path  = generate_voiceover(script_data['script'], video_type)
    video_path  = create_video(audio_path, script_data, video_type)
    result      = post_to_tiktok(video_path, script_data['caption'], script_data['hashtags'])
    logger.info(f"✅ Done: {result}")
    return result

# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════
scheduler = BackgroundScheduler(timezone=BEIRUT_TZ)
scheduler.add_job(lambda: generate_and_post('short_hook',   (7, 12)), CronTrigger(hour=13, minute=0,  timezone=BEIRUT_TZ), id='short_hook')
scheduler.add_job(lambda: generate_and_post('core_message', (20,35)), CronTrigger(hour=18, minute=30, timezone=BEIRUT_TZ), id='core_message')
scheduler.add_job(lambda: generate_and_post('authority',    (40,60)), CronTrigger(hour=21, minute=0,  timezone=BEIRUT_TZ), id='authority')
scheduler.add_job(lambda: generate_and_post('loop_video',   (15,25)), CronTrigger(hour=23, minute=30, timezone=BEIRUT_TZ), id='loop_video')
scheduler.start()
logger.info("✅ Scheduler started — Beirut UTC+3")

# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def index():
    token_set = '✅ Set' if os.environ.get('TIKTOK_ACCESS_TOKEN') else '❌ Missing — visit /setup'
    return jsonify({
        'status': '🟢 Running',
        'beirut_time': datetime.now(BEIRUT_TZ).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'tiktok_token': token_set,
        'schedule': {'1:00PM':'Short Hook','6:30PM':'Core Message','9:00PM':'Authority','11:30PM':'Loop Video'}
    })

@app.route('/setup')
def setup():
    if not CLIENT_KEY:
        return '<h2>❌ Add TIKTOK_CLIENT_KEY to Railway variables</h2>', 400
    url = (f'https://www.tiktok.com/v2/auth/authorize/?client_key={CLIENT_KEY}'
           f'&scope=video.upload,video.publish&response_type=code&redirect_uri={REDIRECT_URI}&state=setup')
    return redirect(url)

@app.route('/callback')
def callback():
    code  = request.args.get('code')
    error = request.args.get('error')
    if error: return f'<h2>❌ TikTok error: {error}</h2>', 400
    if not code: return '<h2>❌ No code received</h2>', 400

    resp = requests.post('https://open.tiktokapis.com/v2/oauth/token/',
        headers={'Content-Type':'application/x-www-form-urlencoded'},
        data={'client_key':CLIENT_KEY,'client_secret':CLIENT_SECRET,'code':code,
              'grant_type':'authorization_code','redirect_uri':REDIRECT_URI}, timeout=30)
    data = resp.json()
    token   = data.get('access_token','')
    refresh = data.get('refresh_token','')
    expires = data.get('expires_in', 86400)
    if not token: return f'<h2>❌ Failed</h2><pre>{data}</pre>', 400

    return f'''<!DOCTYPE html><html>
<body style="font-family:monospace;background:#0a0a0a;color:#00ff88;padding:40px;max-width:800px;margin:auto;">
<h2>✅ TikTok Connected!</h2>
<p style="color:#aaa">Add this to Railway → Variables:</p>
<div style="background:#1a1a1a;padding:24px;border-radius:10px;margin:20px 0;border:1px solid #00ff88;">
  <div style="color:#888;margin-bottom:8px;">TIKTOK_ACCESS_TOKEN=</div>
  <div style="color:#ffff00;word-break:break-all;font-size:14px;">{token}</div>
</div>
<div style="background:#1a1a1a;padding:16px;border-radius:10px;border:1px solid #333;">
  <div style="color:#888;font-size:12px;">Refresh token (save — valid 1 year):</div>
  <div style="color:#00ccff;word-break:break-all;font-size:12px;">{refresh}</div>
</div>
<p style="color:#888;margin-top:20px;">Token expires in {expires//3600} hours. After adding to Railway → redeploy.</p>
</body></html>'''

@app.route('/trigger/<video_type>')
def trigger(video_type):
    durations = {'short_hook':(7,12),'core_message':(20,35),'authority':(40,60),'loop_video':(15,25)}
    if video_type not in durations:
        return jsonify({'error':f'Use: {list(durations.keys())}'}), 400
    threading.Thread(target=generate_and_post, args=(video_type, durations[video_type]), daemon=True).start()
    return jsonify({'status':'🚀 Triggered','video_type':video_type})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))

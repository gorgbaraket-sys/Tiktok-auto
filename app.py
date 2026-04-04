import os
import logging
import threading
import requests
from flask import Flask, jsonify, redirect, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime

from generator.pipeline import generate_and_post

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BEIRUT_TZ     = pytz.timezone('Asia/Beirut')
CLIENT_KEY    = os.environ.get('TIKTOK_CLIENT_KEY', '')
CLIENT_SECRET = os.environ.get('TIKTOK_CLIENT_SECRET', '')
RAILWAY_URL   = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
REDIRECT_URI  = f'https://{RAILWAY_URL}/callback'

# ── Schedule runners ──────────────────────────────────────────────────────────
def run_short_hook():
    logger.info("⚡ 1:00 PM — Short Hook")
    generate_and_post('short_hook', (7, 12))

def run_core_message():
    logger.info("📢 6:30 PM — Core Message")
    generate_and_post('core_message', (20, 35))

def run_authority():
    logger.info("🔥 9:00 PM — Authority")
    generate_and_post('authority', (40, 60))

def run_loop_video():
    logger.info("🔄 11:30 PM — Loop Video")
    generate_and_post('loop_video', (15, 25))

# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=BEIRUT_TZ)
scheduler.add_job(run_short_hook,   CronTrigger(hour=13, minute=0,  timezone=BEIRUT_TZ), id='short_hook')
scheduler.add_job(run_core_message, CronTrigger(hour=18, minute=30, timezone=BEIRUT_TZ), id='core_message')
scheduler.add_job(run_authority,    CronTrigger(hour=21, minute=0,  timezone=BEIRUT_TZ), id='authority')
scheduler.add_job(run_loop_video,   CronTrigger(hour=23, minute=30, timezone=BEIRUT_TZ), id='loop_video')
scheduler.start()
logger.info("✅ Scheduler started — Beirut UTC+3")

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    now = datetime.now(BEIRUT_TZ)
    token_set = '✅ Set' if os.environ.get('TIKTOK_ACCESS_TOKEN') else '❌ Missing — visit /setup'
    return jsonify({
        'status': '🟢 Running',
        'beirut_time': now.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'tiktok_token': token_set,
        'hint': f'Visit /setup to connect TikTok'
    })

@app.route('/setup')
def setup():
    """Redirect to TikTok OAuth login"""
    if not CLIENT_KEY:
        return '<h2>❌ Add TIKTOK_CLIENT_KEY to Railway variables</h2>', 400
    url = (
        f'https://www.tiktok.com/v2/auth/authorize/'
        f'?client_key={CLIENT_KEY}'
        f'&scope=video.upload,video.publish'
        f'&response_type=code'
        f'&redirect_uri={REDIRECT_URI}'
        f'&state=setup'
    )
    return redirect(url)

@app.route('/callback')
def callback():
    """Auto exchange code for access token and display it"""
    code  = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f'<h2>❌ TikTok error: {error}</h2>', 400
    if not code:
        return '<h2>❌ No code received from TikTok</h2>', 400

    resp = requests.post(
        'https://open.tiktokapis.com/v2/oauth/token/',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'client_key':    CLIENT_KEY,
            'client_secret': CLIENT_SECRET,
            'code':          code,
            'grant_type':    'authorization_code',
            'redirect_uri':  REDIRECT_URI,
        },
        timeout=30
    )

    data = resp.json()
    token = data.get('access_token', '')
    refresh = data.get('refresh_token', '')
    expires = data.get('expires_in', 86400)

    if not token:
        return f'<h2>❌ Token exchange failed</h2><pre>{data}</pre>', 400

    return f'''<!DOCTYPE html>
<html>
<body style="font-family:monospace;background:#0a0a0a;color:#00ff88;padding:40px;max-width:800px;margin:auto;">
  <h2>✅ TikTok Connected Successfully!</h2>
  <p style="color:#aaa">Copy the value below and add it to Railway → Variables:</p>

  <div style="background:#1a1a1a;padding:24px;border-radius:10px;margin:20px 0;border:1px solid #00ff88;">
    <div style="color:#888;margin-bottom:8px;">TIKTOK_ACCESS_TOKEN=</div>
    <div style="color:#ffff00;word-break:break-all;font-size:14px;">{token}</div>
  </div>

  <div style="background:#1a1a1a;padding:24px;border-radius:10px;margin:20px 0;border:1px solid #333;">
    <div style="color:#888;margin-bottom:8px;">Save refresh token (expires in 1 year):</div>
    <div style="color:#00ccff;word-break:break-all;font-size:13px;">{refresh}</div>
  </div>

  <p style="color:#888;">Access token expires in {expires//3600} hours (~{expires//86400} day)</p>
  <p style="color:#555;">After adding to Railway, redeploy and your bot will start posting.</p>
</body>
</html>'''

@app.route('/trigger/<video_type>')
def trigger(video_type):
    durations = {
        'short_hook':   (7,  12),
        'core_message': (20, 35),
        'authority':    (40, 60),
        'loop_video':   (15, 25)
    }
    if video_type not in durations:
        return jsonify({'error': f'Unknown. Use: {list(durations.keys())}'}), 400
    threading.Thread(target=generate_and_post, args=(video_type, durations[video_type]), daemon=True).start()
    return jsonify({'status': '🚀 Triggered', 'video_type': video_type})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

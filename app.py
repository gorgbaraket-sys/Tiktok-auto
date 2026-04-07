import os
import re
import json
import subprocess
import threading
import uuid
from flask import Flask, request, jsonify, send_file, Response
import yt_dlp
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

jobs = {}

# ─── YOUTUBE COOKIES SUPPORT ────────────────────────────────
# Set YOUTUBE_COOKIES env var in Railway with the base64-encoded
# contents of a Netscape-format cookies.txt from your browser.
_COOKIE_FILE = '/tmp/yt_cookies.txt'

def _get_cookie_file():
    raw = os.environ.get('YOUTUBE_COOKIES', '').strip()
    if not raw:
        return None
    try:
        import base64
        decoded = base64.b64decode(raw).decode('utf-8')
    except Exception:
        decoded = raw
    with open(_COOKIE_FILE, 'w') as f:
        f.write(decoded)
    return _COOKIE_FILE

def _base_ydl_opts():
    opts = {
        # 'android' bypasses bot-detection for video downloads.
        # NOTE: do NOT set http_headers with an Android UA here — it would
        # also apply to youtube:tab (channel listing) web-scraping requests
        # and cause "unable to extract yt initial data" errors. yt-dlp sets
        # the correct UA for each client internally.
        'extractor_args': {'youtube': {'player_client': ['android', 'mweb']}},
        'socket_timeout': 30,
        'retries': 5,
        'sleep_interval': 2,
        'max_sleep_interval': 6,
    }
    cookie_file = _get_cookie_file()
    if cookie_file:
        opts['cookiefile'] = cookie_file
    return opts


# ─── 4 CLIP STRUCTURES ──────────────────────────────────────
CLIP_TYPES = [
    {
        "key":     "hook",
        "label":   "Short Hook",
        "goal":    "Go viral fast",
        "min_sec": 7,
        "max_sec": 12,
        "emoji":   "⚡",
        "desc":    "Most attention-grabbing opener — bold claim, shocking stat, or strong question"
    },
    {
        "key":     "core",
        "label":   "Core Message",
        "goal":    "Retention + shares",
        "min_sec": 20,
        "max_sec": 35,
        "emoji":   "🎯",
        "desc":    "The central insight or value — the part viewers will save and share"
    },
    {
        "key":     "authority",
        "label":   "Authority",
        "goal":    "Build trust",
        "min_sec": 40,
        "max_sec": 60,
        "emoji":   "👑",
        "desc":    "Credibility moment — expertise, proof, results, or strong confident opinion"
    },
    {
        "key":     "loop",
        "label":   "Loop Video",
        "goal":    "Replay boost",
        "min_sec": 15,
        "max_sec": 25,
        "emoji":   "🔄",
        "desc":    "Segment that feels complete on repeat — satisfying loop, punchline, or visual"
    },
]

# ─── EMBEDDED HTML (no templates folder needed) ──────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>YT → TikTok AI Clipper</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet"/>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:#080808; --s1:#111111; --s2:#181818; --border:#222;
    --gold:#c9a84c; --gold2:#f0d080; --text:#e8e8e8; --muted:#555;
    --font:'Syne',sans-serif; --mono:'DM Mono',monospace;
  }
  body { background:var(--bg); color:var(--text); font-family:var(--font); min-height:100vh; overflow-x:hidden; }
  body::before {
    content:''; position:fixed; inset:0; pointer-events:none; z-index:999;
    background:url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
    opacity:0.5;
  }
  header { padding:1.4rem 2rem; display:flex; align-items:center; gap:0.9rem; border-bottom:1px solid var(--border); }
  .logo {
    width:34px; height:34px; background:var(--gold);
    clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);
    display:flex; align-items:center; justify-content:center; font-size:15px; color:#000; font-weight:800;
  }
  .brand { font-size:0.95rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; }
  .brand span { color:var(--gold); }
  .badge { margin-left:auto; padding:0.25rem 0.75rem; border-radius:99px; border:1px solid var(--border); font-family:var(--mono); font-size:0.65rem; color:var(--muted); }
  main { max-width:860px; margin:0 auto; padding:2.5rem 1.2rem 5rem; }
  .hero { text-align:center; margin-bottom:3rem; }
  .hero h1 { font-size:clamp(1.9rem,5vw,3.2rem); font-weight:800; line-height:1.05; letter-spacing:-0.02em; }
  .hero h1 .g { color:var(--gold); }
  .hero p { margin-top:0.8rem; color:var(--muted); font-family:var(--mono); font-size:0.8rem; letter-spacing:0.04em; }
  .structure-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:0.6rem; margin-bottom:2.5rem; }
  .struct-card { background:var(--s1); border:1px solid var(--border); border-radius:10px; padding:0.9rem 0.75rem; text-align:center; }
  .struct-emoji { font-size:1.3rem; margin-bottom:0.4rem; }
  .struct-label { font-size:0.75rem; font-weight:700; margin-bottom:0.25rem; }
  .struct-range { font-family:var(--mono); font-size:0.62rem; color:var(--gold); margin-bottom:0.2rem; }
  .struct-goal { font-family:var(--mono); font-size:0.6rem; color:var(--muted); }
  .step-label {
    display:inline-flex; align-items:center; gap:0.45rem;
    font-family:var(--mono); font-size:0.68rem; letter-spacing:0.1em;
    color:var(--gold); text-transform:uppercase; margin-bottom:0.7rem;
  }
  .step-label::before {
    content:attr(data-n); width:18px; height:18px; border-radius:50%;
    background:var(--gold); color:#000; display:flex; align-items:center;
    justify-content:center; font-weight:700; font-size:0.6rem;
  }
  .card { background:var(--s1); border:1px solid var(--border); border-radius:12px; padding:1.5rem; margin-bottom:1.2rem; }
  .input-row { display:flex; gap:0.6rem; flex-wrap:wrap; }
  .input-row input {
    flex:1; min-width:180px; background:var(--s2); border:1px solid var(--border);
    border-radius:8px; padding:0.8rem 1rem; font-family:var(--mono); font-size:0.82rem;
    color:var(--text); outline:none; transition:border-color 0.2s;
  }
  .input-row input:focus { border-color:var(--gold); }
  .input-row input::placeholder { color:var(--muted); }
  .hint { margin-top:0.5rem; font-family:var(--mono); font-size:0.67rem; color:var(--muted); }
  .hint code { color:#666; }
  .btn { padding:0.8rem 1.4rem; border-radius:8px; font-family:var(--font); font-weight:700; font-size:0.85rem; letter-spacing:0.04em; cursor:pointer; border:none; transition:all 0.2s; white-space:nowrap; }
  .btn-gold { background:var(--gold); color:#000; }
  .btn-gold:hover { background:var(--gold2); transform:translateY(-1px); }
  .btn:disabled { opacity:0.35; cursor:not-allowed; transform:none !important; }
  .err-box { display:none; margin-top:0.7rem; background:#180808; border:1px solid #3a1010; border-radius:7px; padding:0.8rem 1rem; font-family:var(--mono); font-size:0.75rem; color:#e06060; }
  #video-grid { display:none; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:0.8rem; margin-top:1rem; }
  .v-card { background:var(--s2); border:1px solid var(--border); border-radius:9px; overflow:hidden; cursor:pointer; transition:border-color 0.2s,transform 0.15s; }
  .v-card:hover { border-color:#555; transform:translateY(-2px); }
  .v-card.sel { border-color:var(--gold); box-shadow:0 0 0 2px var(--gold); }
  .v-card img { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; }
  .v-info { padding:0.7rem 0.8rem; }
  .v-title { font-size:0.8rem; font-weight:600; line-height:1.4; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; margin-bottom:0.3rem; }
  .v-meta { font-family:var(--mono); font-size:0.65rem; color:var(--muted); }
  #process-row { display:none; margin-top:1rem; align-items:center; gap:0.8rem; }
  .sel-info { flex:1; font-family:var(--mono); font-size:0.73rem; color:var(--gold); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  #progress-card { display:none; }
  .status-row { display:flex; align-items:center; gap:0.9rem; margin-bottom:0.9rem; }
  .spinner { width:20px; height:20px; border-radius:50%; border:2px solid var(--border); border-top-color:var(--gold); animation:spin 0.8s linear infinite; flex-shrink:0; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .status-text { font-size:0.88rem; color:var(--muted); flex:1; }
  .track { height:3px; background:var(--s2); border-radius:99px; overflow:hidden; margin-bottom:0.5rem; }
  .fill { height:100%; background:linear-gradient(90deg,var(--gold),var(--gold2)); border-radius:99px; width:0%; transition:width 0.7s ease; }
  .stages { display:flex; gap:0.45rem; flex-wrap:wrap; margin-top:0.7rem; }
  .st-dot { font-family:var(--mono); font-size:0.62rem; letter-spacing:0.06em; padding:0.22rem 0.55rem; border-radius:99px; background:var(--s2); border:1px solid var(--border); color:var(--muted); transition:all 0.3s; }
  .st-dot.active { border-color:var(--gold); color:var(--gold); }
  .st-dot.done { background:var(--gold); border-color:var(--gold); color:#000; }
  #clips-card { display:none; }
  .clips-hdr { display:flex; align-items:center; justify-content:space-between; margin-bottom:1.2rem; }
  .clips-hdr h3 { font-size:1.05rem; font-weight:700; }
  .clips-hdr .cnt { font-family:var(--mono); font-size:0.72rem; color:var(--muted); }
  .clip-item { background:var(--s2); border:1px solid var(--border); border-radius:10px; padding:0.95rem 1.1rem; display:flex; align-items:flex-start; gap:0.9rem; margin-bottom:0.7rem; }
  .clip-badge { display:flex; flex-direction:column; align-items:center; gap:0.25rem; min-width:52px; flex-shrink:0; }
  .clip-emoji { font-size:1.4rem; line-height:1; }
  .clip-key { font-family:var(--mono); font-size:0.58rem; letter-spacing:0.08em; text-transform:uppercase; color:var(--gold); }
  .clip-num-badge { width:22px; height:22px; border-radius:50%; background:var(--gold); color:#000; display:flex; align-items:center; justify-content:center; font-size:0.68rem; font-weight:800; }
  .clip-body { flex:1; min-width:0; }
  .clip-label { font-size:0.7rem; font-weight:700; color:var(--gold); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.25rem; }
  .clip-title { font-size:0.88rem; font-weight:600; margin-bottom:0.35rem; line-height:1.35; }
  .clip-meta { font-family:var(--mono); font-size:0.65rem; color:var(--muted); display:flex; gap:0.8rem; flex-wrap:wrap; margin-bottom:0.4rem; }
  .clip-goal { display:inline-block; padding:0.15rem 0.5rem; border-radius:99px; border:1px solid var(--border); font-family:var(--mono); font-size:0.6rem; color:var(--muted); margin-bottom:0.4rem; }
  .clip-reason { font-size:0.73rem; color:#555; line-height:1.45; }
  .btn-dl { padding:0.55rem 1rem; border-radius:7px; background:transparent; border:1px solid var(--gold); color:var(--gold); font-family:var(--font); font-weight:700; font-size:0.75rem; letter-spacing:0.04em; cursor:pointer; transition:all 0.2s; white-space:nowrap; flex-shrink:0; align-self:center; }
  .btn-dl:hover { background:var(--gold); color:#000; }
  .dl-all-row { display:flex; justify-content:center; margin-top:1.2rem; gap:0.7rem; flex-wrap:wrap; }
  @keyframes fadeUp { from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:translateY(0);} }
  .fu { animation:fadeUp 0.35s ease both; }
  footer { text-align:center; padding:1.8rem; font-family:var(--mono); font-size:0.63rem; color:#2a2a2a; border-top:1px solid var(--border); margin-top:3rem; }

  .cookie-bar { margin-bottom:1.4rem; background:var(--s1); border:1px solid #2a2a00; border-radius:12px; overflow:hidden; }
  .cookie-bar-hdr { display:flex; align-items:center; justify-content:space-between; padding:0.8rem 1.2rem; cursor:pointer; user-select:none; }
  .cookie-bar-hdr .cb-title { font-family:var(--mono); font-size:0.72rem; letter-spacing:0.06em; color:#888; }
  .cookie-bar-hdr .cb-status { font-family:var(--mono); font-size:0.65rem; padding:0.2rem 0.55rem; border-radius:99px; border:1px solid var(--border); color:var(--muted); transition:all 0.2s; }
  .cookie-bar-hdr .cb-status.ok { border-color:#4a7; color:#4a7; }
  .cookie-bar-body { display:none; padding:0 1.2rem 1.2rem; }
  .cookie-bar-body textarea { width:100%; height:90px; background:var(--s2); border:1px solid var(--border); border-radius:7px; padding:0.65rem 0.8rem; font-family:var(--mono); font-size:0.65rem; color:#aaa; resize:vertical; outline:none; }
  .cookie-bar-body textarea:focus { border-color:var(--gold); }
  .cookie-row { display:flex; gap:0.6rem; margin-top:0.6rem; align-items:center; }
  .cookie-hint { font-family:var(--mono); font-size:0.62rem; color:var(--muted); flex:1; }
  @media(max-width:600px){
    .structure-grid{grid-template-columns:repeat(2,1fr);}
    .input-row{flex-direction:column;}
    #video-grid{grid-template-columns:1fr 1fr;}
    .clip-item{flex-wrap:wrap;}
    .btn-dl{width:100%;text-align:center;}
    main{padding:1.5rem 0.9rem 4rem;}
  }
</style>
</head>
<body>
<header>
  <div class="logo">▶</div>
  <div class="brand">YT <span>→</span> TikTok</div>
  <div class="badge">Groq + FFmpeg · Manual Upload</div>
</header>
<main>
  <div class="hero fu">
    <h1>4 <span class="g">structured clips</span><br>from any YouTube video</h1>
    <p>Paste channel → Pick video → AI cuts 4 clips → Download → Upload to TikTok yourself</p>
  </div>
  <div class="structure-grid fu">
    <div class="struct-card"><div class="struct-emoji">⚡</div><div class="struct-label">Short Hook</div><div class="struct-range">7–12s</div><div class="struct-goal">Go viral fast</div></div>
    <div class="struct-card"><div class="struct-emoji">🎯</div><div class="struct-label">Core Message</div><div class="struct-range">20–35s</div><div class="struct-goal">Retention + shares</div></div>
    <div class="struct-card"><div class="struct-emoji">👑</div><div class="struct-label">Authority</div><div class="struct-range">40–60s</div><div class="struct-goal">Build trust</div></div>
    <div class="struct-card"><div class="struct-emoji">🔄</div><div class="struct-label">Loop Video</div><div class="struct-range">15–25s</div><div class="struct-goal">Replay boost</div></div>
  </div>
  <div class="cookie-bar" id="cookie-bar">
    <div class="cookie-bar-hdr" onclick="toggleCookies()">
      <span class="cb-title">🍪 YOUTUBE COOKIES (required to bypass bot check)</span>
      <span class="cb-status" id="cb-status">Not set — click to add</span>
    </div>
    <div class="cookie-bar-body" id="cookie-body">
      <textarea id="cookie-input" placeholder="Paste your Netscape-format cookies.txt content here...&#10;&#10;Export via: yt-dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download https://youtube.com&#10;Then open cookies.txt and paste the full contents here." spellcheck="false"></textarea>
      <div class="cookie-row">
        <span class="cookie-hint">Stored in memory only · clears on redeploy · never leaves your server</span>
        <button class="btn btn-gold" onclick="saveCookies()" style="padding:0.5rem 1rem;font-size:0.78rem;">Save Cookies</button>
        <button class="btn" onclick="clearCookies()" style="padding:0.5rem 0.9rem;font-size:0.78rem;background:var(--s2);color:var(--muted);border:1px solid var(--border);">Clear</button>
      </div>
    </div>
  </div>
    <div class="step-label" data-n="1">Paste Channel or Video URL</div>
  <div class="card">
    <div class="input-row">
      <input type="url" id="channel-input" placeholder="https://youtube.com/@ChannelName  or  /watch?v=..." autocomplete="off"/>
      <button class="btn btn-gold" id="fetch-btn" onclick="fetchVideos()">Fetch Videos</button>
    </div>
    <div class="hint">Supports: <code>/@handle</code> · <code>/channel/UCxxx</code> · <code>/c/name</code> · <code>/videos</code> · single video link</div>
    <div id="fetch-err" class="err-box"></div>
    <div id="video-grid"></div>
    <div id="process-row">
      <div class="sel-info" id="sel-info">No video selected</div>
      <button class="btn btn-gold" id="process-btn" onclick="startProcessing()" disabled>✦ Cut 4 TikTok Clips</button>
    </div>
  </div>
  <div class="step-label" data-n="2">AI Processing</div>
  <div class="card" id="progress-card">
    <div class="status-row">
      <div class="spinner" id="spinner"></div>
      <div class="status-text" id="status-text">Starting...</div>
    </div>
    <div class="track"><div class="fill" id="fill"></div></div>
    <div class="stages">
      <span class="st-dot" id="st-downloading">Downloading</span>
      <span class="st-dot" id="st-transcribing">Transcribing</span>
      <span class="st-dot" id="st-analyzing">AI Analysis</span>
      <span class="st-dot" id="st-clipping">Rendering</span>
      <span class="st-dot" id="st-done">Done</span>
    </div>
  </div>
  <div class="step-label" data-n="3">Download Your 4 Clips</div>
  <div class="card" id="clips-card">
    <div class="clips-hdr">
      <h3>TikTok Clips Ready</h3>
      <span class="cnt" id="clips-cnt"></span>
    </div>
    <div id="clips-list"></div>
    <div class="dl-all-row" id="dl-all-row"></div>
  </div>
</main>
<footer>YT→TikTok AI Clipper · Groq Whisper + LLaMA 3.3-70b + FFmpeg · Download & upload manually</footer>
<script>
  let selectedVideo=null,currentJobId=null,pollTimer=null;

  async function fetchVideos(){
    const url=document.getElementById('channel-input').value.trim();
    const btn=document.getElementById('fetch-btn');
    const errBox=document.getElementById('fetch-err');
    const grid=document.getElementById('video-grid');
    if(!url)return;
    btn.disabled=true;btn.textContent='Fetching...';
    errBox.style.display='none';
    grid.style.display='none';grid.innerHTML='';
    document.getElementById('process-row').style.display='none';
    selectedVideo=null;
    try{
      const r=await fetch('/fetch-videos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel_url:url})});
      const d=await r.json();
      if(!r.ok||d.error){showErr(errBox,d.error);return;}
      renderGrid(d.videos);
    }catch(e){showErr(errBox,'Network error: '+e.message);}
    finally{btn.disabled=false;btn.textContent='Fetch Videos';}
  }

  function renderGrid(videos){
    const grid=document.getElementById('video-grid');
    grid.innerHTML='';grid.style.display='grid';
    videos.forEach(v=>{
      const el=document.createElement('div');
      el.className='v-card fu';
      el.innerHTML=`<img src="${v.thumbnail}" loading="lazy" onerror="this.src='https://i.ytimg.com/vi/${v.id}/hqdefault.jpg'"/><div class="v-info"><div class="v-title">${esc(v.title)}</div><div class="v-meta">${v.duration_str}${v.view_count?' · '+fmtV(v.view_count)+' views':''}</div></div>`;
      el.addEventListener('click',()=>pickVideo(v,el));
      grid.appendChild(el);
    });
    document.getElementById('process-row').style.display='flex';
  }

  function pickVideo(video,el){
    document.querySelectorAll('.v-card').forEach(c=>c.classList.remove('sel'));
    el.classList.add('sel');selectedVideo=video;
    document.getElementById('sel-info').textContent='▶ '+video.title;
    document.getElementById('process-btn').disabled=false;
  }

  async function startProcessing(){
    if(!selectedVideo)return;
    const btn=document.getElementById('process-btn');
    btn.disabled=true;btn.textContent='Working...';
    document.getElementById('progress-card').style.display='block';
    document.getElementById('clips-card').style.display='none';
    setStage('downloading');
    try{
      const r=await fetch('/process',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_url:selectedVideo.url,video_title:selectedVideo.title})});
      const d=await r.json();
      if(!r.ok||d.error){alert(d.error);return;}
      currentJobId=d.job_id;
      pollTimer=setInterval(poll,2500);
    }catch(e){alert('Error: '+e.message);btn.disabled=false;btn.textContent='✦ Cut 4 TikTok Clips';}
  }

  async function poll(){
    if(!currentJobId)return;
    try{
      const r=await fetch('/status/'+currentJobId);
      const job=await r.json();
      document.getElementById('status-text').textContent=job.message||'';
      const pct={queued:5,downloading:20,transcribing:45,analyzing:65,clipping:85,done:100,error:0};
      document.getElementById('fill').style.width=(pct[job.status]||5)+'%';
      if(['downloading','transcribing','analyzing','clipping','done'].includes(job.status))setStage(job.status);
      if(job.status==='done'){
        clearInterval(pollTimer);
        document.getElementById('spinner').style.display='none';
        allDone();renderClips(job.clips);
        document.getElementById('process-btn').disabled=false;
        document.getElementById('process-btn').textContent='✦ Cut 4 TikTok Clips';
      }
      if(job.status==='error'){
        clearInterval(pollTimer);
        document.getElementById('spinner').style.borderTopColor='#e63b3b';
        document.getElementById('process-btn').disabled=false;
        document.getElementById('process-btn').textContent='✦ Try Again';
      }
    }catch(e){console.error(e);}
  }

  function renderClips(clips){
    const list=document.getElementById('clips-list');
    const dlRow=document.getElementById('dl-all-row');
    list.innerHTML='';dlRow.innerHTML='';
    document.getElementById('clips-cnt').textContent=clips.length+' clips · upload manually to TikTok';
    clips.forEach(c=>{
      const el=document.createElement('div');
      el.className='clip-item fu';
      el.innerHTML=`<div class="clip-badge"><div class="clip-num-badge">${c.index}</div><div class="clip-emoji">${c.emoji}</div><div class="clip-key">${c.key}</div></div><div class="clip-body"><div class="clip-label">${esc(c.label)}</div><div class="clip-title">${esc(c.title)}</div><div class="clip-meta"><span>⏱ ${c.duration_str}</span><span>${c.start}s → ${c.end}s</span><span>${c.size_mb} MB</span></div><span class="clip-goal">🎯 ${esc(c.goal)}</span>${c.reason?'<div class="clip-reason">'+esc(c.reason)+'</div>':''}</div><button class="btn-dl" onclick="dlClip(${c.index})">↓ Download</button>`;
      list.appendChild(el);
      const btn=document.createElement('button');
      btn.className='btn-dl';btn.textContent=c.emoji+' '+c.label;
      btn.onclick=()=>dlClip(c.index);dlRow.appendChild(btn);
    });
    document.getElementById('clips-card').style.display='block';
    document.getElementById('clips-card').scrollIntoView({behavior:'smooth'});
  }

  function dlClip(idx){window.location.href='/download/'+currentJobId+'/'+idx;}

  const STAGES=['downloading','transcribing','analyzing','clipping','done'];
  function setStage(cur){
    const idx=STAGES.indexOf(cur);
    STAGES.forEach((s,i)=>{
      const el=document.getElementById('st-'+s);if(!el)return;
      el.classList.remove('active','done');
      if(i<idx)el.classList.add('done');
      else if(i===idx)el.classList.add('active');
    });
  }
  function allDone(){STAGES.forEach(s=>{const el=document.getElementById('st-'+s);if(el){el.classList.remove('active');el.classList.add('done');}});}
  function showErr(el,msg){el.textContent='⚠ '+msg;el.style.display='block';}
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  function fmtV(n){if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n;}
  document.getElementById('channel-input').addEventListener('keydown',e=>{if(e.key==='Enter')fetchVideos();});
  // ── Cookie panel ──────────────────────────────────────────
  function toggleCookies(){
    const body=document.getElementById('cookie-body');
    body.style.display=body.style.display==='block'?'none':'block';
  }
  async function saveCookies(){
    const txt=document.getElementById('cookie-input').value.trim();
    if(!txt){alert('Paste your cookies.txt content first.');return;}
    const r=await fetch('/set-cookies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookies:txt})});
    const d=await r.json();
    if(d.ok){
      document.getElementById('cb-status').textContent='✓ Cookies active';
      document.getElementById('cb-status').classList.add('ok');
      document.getElementById('cookie-body').style.display='none';
    } else { alert('Failed: '+d.error); }
  }
  async function clearCookies(){
    await fetch('/set-cookies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookies:''})});
    document.getElementById('cb-status').textContent='Not set — click to add';
    document.getElementById('cb-status').classList.remove('ok');
    document.getElementById('cookie-input').value='';
  }
  // Check cookie status on load
  fetch('/cookie-status').then(r=>r.json()).then(d=>{
    if(d.active){
      document.getElementById('cb-status').textContent='✓ Cookies active';
      document.getElementById('cb-status').classList.add('ok');
    }
  }).catch(()=>{});

</script>
</body>
</html>"""


# ────────────────────────────────────────────────────────────

def _normalize_channel_url(url):
    """Force channel URLs to the /videos tab. youtube:tab fails on bare
    @handle pages (multi-tab layout); /videos is unambiguous and always works."""
    if 'watch?v=' in url or 'youtu.be/' in url:
        return url
    url = url.rstrip('/')
    if re.search(r'/(videos|shorts|streams|playlists|community)$', url, re.I):
        return url
    return url + '/videos'


def get_channel_videos(channel_url, max_videos=10):
    channel_url = _normalize_channel_url(channel_url)
    ydl_opts = {**_base_ydl_opts(), **{
        'quiet': True, 'extract_flat': True,
        'playlist_items': f'1-{max_videos}', 'ignoreerrors': True,
    }}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        if not info:
            raise ValueError("Could not fetch channel. Check the URL.")

        # Channel URLs return tabs (Videos/Shorts/Live) as sub-playlists.
        # Their IDs start with 'UC' (channel IDs) — drill into their entries.
        raw_entries = info.get('entries') or []
        flat_entries = []
        for entry in raw_entries:
            if not entry:
                continue
            eid = entry.get('id') or ''
            if eid.startswith('UC') or entry.get('_type') == 'playlist':
                for sub in (entry.get('entries') or []):
                    if sub and not (sub.get('id') or '').startswith('UC'):
                        flat_entries.append(sub)
            else:
                flat_entries.append(entry)

        videos = []
        for entry in flat_entries[:max_videos]:
            if not entry:
                continue
            vid_id = entry.get('id') or ''
            if not vid_id or vid_id.startswith('UC'):
                continue
            duration = entry.get('duration') or 0
            videos.append({
                'id':           vid_id,
                'title':        entry.get('title', 'Untitled'),
                'url':          f"https://youtube.com/watch?v={vid_id}",
                'duration':     duration,
                'duration_str': fmt_duration(duration),
                'thumbnail':    entry.get('thumbnail') or f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                'view_count':   entry.get('view_count'),
            })
        return videos


def fmt_duration(secs):
    if not secs:
        return '?:??'
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def download_video(video_url, output_dir):
    ydl_opts = {**_base_ydl_opts(), **{
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': True, 'merge_output_format': 'mp4',
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
    }}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(video_url, download=True)
    for f in os.listdir(output_dir):
        if f.endswith('.mp4'):
            return os.path.join(output_dir, f)
    raise FileNotFoundError("Download failed — no mp4 found")


def transcribe_video(video_path, job_id):
    update_job(job_id, message="Extracting & compressing audio...")
    audio_path = video_path.replace('.mp4', '_audio.mp3')
    subprocess.run([
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-ar', '16000', '-ac', '1', '-b:a', '32k', '-t', '600',
        audio_path
    ], check=True, capture_output=True)

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb > 24:
        update_job(job_id, message=f"Audio {size_mb:.1f}MB — trimming for Groq limit...")
        trimmed = audio_path.replace('.mp3', '_trim.mp3')
        subprocess.run(['ffmpeg', '-y', '-i', audio_path, '-t', '480', trimmed],
                       check=True, capture_output=True)
        os.replace(trimmed, audio_path)

    update_job(job_id, message="Transcribing with Groq Whisper...")
    with open(audio_path, 'rb') as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f),
            model="whisper-large-v3",
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    os.remove(audio_path)
    return transcription


def find_structured_clips(transcript_text, duration, job_id):
    update_job(job_id, message="AI finding 4 structured TikTok moments...")

    types_desc = "\n".join([
        f'  "{t["key"]}": {t["label"]} ({t["min_sec"]}–{t["max_sec"]}s) — {t["desc"]}'
        for t in CLIP_TYPES
    ])

    prompt = f"""You are a viral TikTok content strategist. Analyze this transcript and find the BEST segment for each of these 4 clip types:

{types_desc}

Video duration: {int(duration)}s
Transcript:
{transcript_text[:7500]}

Return ONLY a JSON array with exactly 4 objects in this order [hook, core, authority, loop]:
[
  {{"key":"hook","start":5,"end":14,"title":"Short punchy caption (max 8 words)","reason":"Why this is the best hook"}},
  {{"key":"core","start":45,"end":75,"title":"...","reason":"..."}},
  {{"key":"authority","start":120,"end":172,"title":"...","reason":"..."}},
  {{"key":"loop","start":200,"end":220,"title":"...","reason":"..."}}
]

STRICT duration rules:
- hook: 7–12 seconds
- core: 20–35 seconds
- authority: 40–60 seconds
- loop: 15–25 seconds

All timestamps within 0–{int(duration)}s. Pick from different parts of the video.
Return ONLY the JSON array."""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2, max_tokens=900
    )

    raw = resp.choices[0].message.content.strip()
    if '```' in raw:
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    raw = raw.strip().rstrip('`').strip()

    clips = json.loads(raw)

    for clip in clips:
        ct = next((t for t in CLIP_TYPES if t['key'] == clip['key']), None)
        if not ct:
            continue
        dur = clip['end'] - clip['start']
        if dur < ct['min_sec']:
            clip['end'] = clip['start'] + ct['min_sec']
        if dur > ct['max_sec']:
            clip['end'] = clip['start'] + ct['max_sec']
        clip['start'] = max(0, clip['start'])
        clip['end']   = min(clip['end'], duration)

    return clips


def get_video_info(video_path):
    probe = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', '-show_format', video_path
    ], capture_output=True, text=True)
    info = json.loads(probe.stdout)
    w = h = None
    for s in info.get('streams', []):
        if s.get('codec_type') == 'video':
            w, h = s.get('width'), s.get('height')
            break
    duration = float(info.get('format', {}).get('duration', 0))
    return w, h, duration


def create_tiktok_clip(video_path, start, end, title, output_path):
    w, h, _ = get_video_info(video_path)
    duration = max(1, end - start)
    target_w = int(h * 9 / 16) if h else 608
    target_w = min(target_w, w or target_w)
    crop_x   = ((w or target_w) - target_w) // 2

    safe_title = (
        title.replace('\\', '\\\\')
             .replace(':', '\\:')
             .replace("'", "\u2019")[:50]
    )

    vf = (
        f"crop={target_w}:{h}:{crop_x}:0,"
        f"scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"drawtext=text='{safe_title}'"
        f":fontcolor=white:fontsize=46:x=(w-text_w)/2:y=h-180"
        f":box=1:boxcolor=black@0.55:boxborderw=14"
    )

    cmd = [
        'ffmpeg', '-y', '-ss', str(start), '-i', video_path,
        '-t', str(duration), '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-400:]}")


def update_job(job_id, **kwargs):
    if job_id in jobs:
        jobs[job_id].update(kwargs)


def process_job(job_id, video_url, video_title):
    work_dir  = f'/tmp/yt2tiktok/{job_id}'
    clips_dir = os.path.join(work_dir, 'clips')
    os.makedirs(clips_dir, exist_ok=True)

    try:
        update_job(job_id, status='downloading', message='Downloading from YouTube...')
        video_path = download_video(video_url, work_dir)

        w, h, duration = get_video_info(video_path)
        update_job(job_id, message=f"Downloaded · {fmt_duration(duration)} · {w}x{h}")

        transcription = transcribe_video(video_path, job_id)

        transcript_text = ""
        if hasattr(transcription, 'segments') and transcription.segments:
            for seg in transcription.segments:
                transcript_text += f"[{seg.start:.1f}s-{seg.end:.1f}s] {seg.text}\n"
        else:
            transcript_text = getattr(transcription, 'text', '')

        if not transcript_text.strip():
            raise ValueError("Transcription empty — video may have no speech.")

        update_job(job_id, status='analyzing')
        structured = find_structured_clips(transcript_text, duration, job_id)

        update_job(job_id, status='clipping', message="Rendering 4 TikTok clips...")

        clips = []
        for i, seg in enumerate(structured):
            ct    = next((t for t in CLIP_TYPES if t['key'] == seg['key']), CLIP_TYPES[i % 4])
            start = float(seg.get('start', 0))
            end   = float(seg.get('end', start + ct['min_sec']))
            end   = min(end, duration)
            if end - start < 3:
                continue

            title         = seg.get('title', ct['label'])
            clip_filename = f"{i+1}_{ct['key']}.mp4"
            clip_path     = os.path.join(clips_dir, clip_filename)

            update_job(job_id, message=f"Rendering {i+1}/4 — {ct['emoji']} {ct['label']} ({int(end-start)}s)...")

            try:
                create_tiktok_clip(video_path, start, end, title, clip_path)
                size_mb = os.path.getsize(clip_path) / (1024 * 1024)
                clips.append({
                    'index':        i + 1,
                    'key':          ct['key'],
                    'label':        ct['label'],
                    'goal':         ct['goal'],
                    'emoji':        ct['emoji'],
                    'title':        title,
                    'reason':       seg.get('reason', ''),
                    'start':        int(start),
                    'end':          int(end),
                    'duration':     int(end - start),
                    'duration_str': fmt_duration(end - start),
                    'path':         clip_path,
                    'filename':     clip_filename,
                    'size_mb':      round(size_mb, 1),
                })
            except Exception as e:
                print(f"[Clip {i+1}] Error: {e}")

        update_job(job_id,
                   status='done',
                   message='✅ 4 clips ready — download & upload to TikTok manually!',
                   clips=clips)

    except Exception as e:
        update_job(job_id, status='error', message=str(e))
        print(f"[Job {job_id}] FAILED: {e}")


# ─── ROUTES ─────────────────────────────────────────────────

@app.route('/')
def index():
    return Response(HTML, mimetype='text/html')


@app.route('/set-cookies', methods=['POST'])
def set_cookies():
    data = request.get_json(force=True)
    cookie_text = (data.get('cookies') or '').strip()
    if not cookie_text:
        try:
            os.remove(_COOKIE_FILE)
        except FileNotFoundError:
            pass
        return jsonify({'ok': True})
    try:
        with open(_COOKIE_FILE, 'w') as f:
            f.write(cookie_text)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/cookie-status')
def cookie_status():
    active = os.path.exists(_COOKIE_FILE) and os.path.getsize(_COOKIE_FILE) > 0
    return jsonify({'active': active})


@app.route('/fetch-videos', methods=['POST'])
def fetch_videos():
    data = request.get_json(force=True)
    url  = (data.get('channel_url') or '').strip()
    if not url:
        return jsonify({'error': 'Provide a YouTube channel or video URL'}), 400
    try:
        videos = get_channel_videos(url, max_videos=12)
        if not videos:
            return jsonify({'error': 'No videos found. Try the /videos URL.'}), 404
        return jsonify({'videos': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/process', methods=['POST'])
def process():
    data        = request.get_json(force=True)
    video_url   = data.get('video_url', '').strip()
    video_title = data.get('video_title', 'Video')
    if not video_url:
        return jsonify({'error': 'No video URL'}), 400

    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {'status': 'queued', 'message': 'Starting...', 'clips': []}

    t = threading.Thread(target=process_job, args=(job_id, video_url, video_title))
    t.daemon = True
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    safe          = {k: v for k, v in job.items() if k != 'clips'}
    safe['clips'] = [{k2: v2 for k2, v2 in c.items() if k2 != 'path'} for c in job.get('clips', [])]
    return jsonify(safe)


@app.route('/download/<job_id>/<int:clip_index>')
def download_clip(job_id, clip_index):
    job = jobs.get(job_id)
    if not job or job.get('status') != 'done':
        return jsonify({'error': 'Clips not ready'}), 404
    clip = next((c for c in job['clips'] if c['index'] == clip_index), None)
    if not clip or not os.path.exists(clip['path']):
        return jsonify({'error': 'Clip not found'}), 404
    safe_name = f"{clip['index']}_{clip['key']}_{clip['title'][:25].replace(' ', '_').replace('/', '-')}"
    return send_file(clip['path'], as_attachment=True,
                     download_name=f"{safe_name}.mp4", mimetype='video/mp4')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

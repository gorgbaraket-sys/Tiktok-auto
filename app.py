"""
app.py
Flask dashboard — run pipeline, track history, download generated videos.
"""

import os
import threading
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request, send_from_directory
from apscheduler.schedulers.background import BackgroundScheduler

from pipeline import run_pipeline, VIDEOS_DIR
from sheets_logger import log_run

app = Flask(__name__)

# ── State ─────────────────────────────────────────────────────────────────────
run_history: list[dict] = []
is_running:  bool       = False

SCHEDULE_HOURS = int(os.environ.get("SCHEDULE_HOURS", 6))
NICHE          = os.environ.get("VIDEO_NICHE", "")


# ── Runner ────────────────────────────────────────────────────────────────────

def do_run(niche: str = NICHE) -> None:
    global is_running, run_history
    if is_running:
        return
    is_running = True
    try:
        results = run_pipeline(niche=niche)
        log_run(results)
        run_history.insert(0, {"started_at": datetime.now().isoformat(), **results})
        run_history[:] = run_history[:50]
    finally:
        is_running = False


scheduler = BackgroundScheduler()
scheduler.add_job(do_run, "interval", hours=SCHEDULE_HOURS)
scheduler.start()


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Seedance Bot</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0a0c0f; --surface:#111418; --border:#1e2530;
    --amber:#f5a623; --green:#39d353; --red:#f85149; --blue:#58a6ff;
    --muted:#4a5568; --text:#c9d1d9; --heading:#e6edf3;
  }
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:var(--bg);color:var(--text);font-family:'Barlow',sans-serif;
       font-weight:300;min-height:100vh;padding-bottom:60px;}

  /* header */
  header{border-bottom:1px solid var(--border);padding:20px 32px;
         display:flex;align-items:center;gap:14px;
         position:sticky;top:0;background:var(--bg);z-index:10;}
  .logo{width:36px;height:36px;border:2px solid var(--amber);border-radius:8px;
        display:grid;place-items:center;font-family:'Share Tech Mono',monospace;
        font-size:16px;color:var(--amber);}
  header h1{font-size:18px;font-weight:600;color:var(--heading);}
  header .sub{font-size:12px;color:var(--muted);font-family:'Share Tech Mono',monospace;}
  .pill{margin-left:auto;padding:5px 14px;border-radius:20px;font-size:11px;
        font-family:'Share Tech Mono',monospace;letter-spacing:1px;
        text-transform:uppercase;border:1px solid;}
  .pill.idle{color:var(--muted);border-color:var(--muted);}
  .pill.running{color:var(--amber);border-color:var(--amber);
                animation:blink 1.2s ease-in-out infinite;}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}

  main{max-width:1100px;margin:0 auto;padding:36px 24px;}

  /* stat cards */
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px;}
  @media(max-width:640px){.grid{grid-template-columns:1fr;}}
  .card{background:var(--surface);border:1px solid var(--border);
        border-radius:12px;padding:22px 24px;}
  .card .label{font-size:11px;color:var(--muted);text-transform:uppercase;
               letter-spacing:1.5px;font-family:'Share Tech Mono',monospace;margin-bottom:8px;}
  .card .val{font-size:28px;font-weight:700;color:var(--heading);letter-spacing:-1px;}
  .card .val.amber{color:var(--amber);}
  .card .val.green{color:var(--green);}
  .card .hint{font-size:12px;color:var(--muted);margin-top:4px;
              font-family:'Share Tech Mono',monospace;}

  /* trigger bar */
  .trigger{background:var(--surface);border:1px solid var(--border);
           border-radius:12px;padding:22px 24px;margin-bottom:28px;
           display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
  .trigger h2{font-size:15px;font-weight:600;color:var(--heading);flex:1;min-width:160px;}
  input[type=text]{background:var(--bg);border:1px solid var(--border);
                   border-radius:8px;padding:9px 14px;color:var(--text);
                   font-family:'Barlow',sans-serif;font-size:14px;width:200px;
                   outline:none;transition:border-color .2s;}
  input[type=text]:focus{border-color:var(--amber);}
  input::placeholder{color:var(--muted);}
  .btn{padding:10px 22px;border-radius:8px;font-family:'Share Tech Mono',monospace;
       font-size:13px;cursor:pointer;border:none;transition:opacity .2s,transform .1s;}
  .btn:active{transform:scale(.97);}
  .btn:disabled{opacity:.4;cursor:not-allowed;}
  .btn-run{background:var(--amber);color:#000;font-weight:700;}
  .btn-run:hover:not(:disabled){opacity:.85;}
  .fb{font-size:13px;font-family:'Share Tech Mono',monospace;}
  .fb.ok{color:var(--green);}  .fb.err{color:var(--red);}

  /* section */
  .sec-title{font-size:15px;font-weight:600;color:var(--heading);
             margin-bottom:14px;display:flex;align-items:center;gap:10px;}
  .count{font-size:11px;color:var(--muted);font-family:'Share Tech Mono',monospace;
         background:var(--border);padding:2px 8px;border-radius:10px;}

  /* table */
  .table-wrap{background:var(--surface);border:1px solid var(--border);
              border-radius:12px;overflow:hidden;margin-bottom:40px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  thead th{text-align:left;padding:12px 16px;font-size:11px;color:var(--muted);
           text-transform:uppercase;letter-spacing:1px;
           font-family:'Share Tech Mono',monospace;
           border-bottom:1px solid var(--border);font-weight:400;}
  tbody tr{border-bottom:1px solid var(--border);}
  tbody tr:last-child{border-bottom:none;}
  tbody tr:hover{background:rgba(255,255,255,.02);}
  td{padding:12px 16px;vertical-align:middle;}

  .badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;
         font-family:'Share Tech Mono',monospace;text-transform:uppercase;letter-spacing:.5px;}
  .badge.success{background:rgba(57,211,83,.12);color:var(--green);}
  .badge.error{background:rgba(248,81,73,.12);color:var(--red);}
  .badge.running{background:rgba(245,166,35,.12);color:var(--amber);}

  .idea-col{max-width:280px;line-height:1.4;}
  .ts-col{color:var(--muted);font-family:'Share Tech Mono',monospace;font-size:11px;white-space:nowrap;}
  .err-col{color:var(--red);font-size:12px;max-width:180px;}

  /* download button */
  .dl-btn{display:inline-flex;align-items:center;gap:6px;
          padding:6px 14px;border-radius:6px;font-size:12px;
          font-family:'Share Tech Mono',monospace;
          background:rgba(88,166,255,.1);color:var(--blue);
          border:1px solid rgba(88,166,255,.25);
          text-decoration:none;transition:background .2s;}
  .dl-btn:hover{background:rgba(88,166,255,.2);}
  .dl-btn svg{flex-shrink:0;}

  /* video library */
  .lib-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;}
  .vid-card{background:var(--surface);border:1px solid var(--border);
            border-radius:10px;overflow:hidden;}
  .vid-card video{width:100%;display:block;aspect-ratio:9/16;object-fit:cover;background:#000;}
  .vid-info{padding:10px 12px;}
  .vid-name{font-family:'Share Tech Mono',monospace;font-size:10px;
            color:var(--muted);margin-bottom:8px;white-space:nowrap;
            overflow:hidden;text-overflow:ellipsis;}
  .empty{padding:48px;text-align:center;color:var(--muted);
         font-family:'Share Tech Mono',monospace;font-size:13px;}
</style>
</head>
<body>

<header>
  <div class="logo">▶</div>
  <div>
    <h1>Seedance Bot</h1>
    <div class="sub">AI Video Generator · local download</div>
  </div>
  <div class="pill {{ 'running' if is_running else 'idle' }}">
    {{ 'RUNNING' if is_running else 'IDLE' }}
  </div>
</header>

<main>

  <div class="grid">
    <div class="card">
      <div class="label">Total Runs</div>
      <div class="val amber">{{ history|length }}</div>
      <div class="hint">all time</div>
    </div>
    <div class="card">
      <div class="label">Successful</div>
      <div class="val green">{{ history|selectattr('status','eq','success')|list|length }}</div>
      <div class="hint">videos ready</div>
    </div>
    <div class="card">
      <div class="label">Schedule</div>
      <div class="val">{{ schedule_h }}h</div>
      <div class="hint">auto-run interval</div>
    </div>
  </div>

  <!-- Trigger -->
  <div class="trigger">
    <div>
      <h2>Run Pipeline</h2>
    </div>
    <input type="text" id="niche" placeholder="niche (optional)…" value="{{ niche }}">
    <button class="btn btn-run" id="runBtn" onclick="triggerRun()" {{ 'disabled' if is_running }}>
      ▶ RUN NOW
    </button>
    <span class="fb" id="fb"></span>
  </div>

  <!-- Run history -->
  <div class="sec-title">
    Run History <span class="count">{{ history|length }}</span>
  </div>
  <div class="table-wrap">
    {% if history %}
    <table>
      <thead>
        <tr>
          <th>Time</th><th>Status</th><th>Idea</th><th>Download</th><th>Error</th>
        </tr>
      </thead>
      <tbody>
        {% for r in history %}
        <tr>
          <td class="ts-col">{{ r.started_at[:19].replace('T',' ') if r.started_at else '—' }}</td>
          <td><span class="badge {{ r.status }}">{{ r.status }}</span></td>
          <td class="idea-col">{{ (r.idea or '—')[:100] }}{{ '…' if r.idea and r.idea|length > 100 else '' }}</td>
          <td>
            {% if r.filename %}
            <a class="dl-btn" href="/download/{{ r.filename }}" download>
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 12l-4-4h2.5V3h3v5H12L8 12z"/>
                <rect x="2" y="13" width="12" height="1.5" rx=".75"/>
              </svg>
              {{ r.filename[-18:] }}
            </a>
            {% else %}—{% endif %}
          </td>
          <td class="err-col">{{ (r.error or '')[:80] }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="empty">No runs yet — hit ▶ RUN NOW or wait for the scheduler.</div>
    {% endif %}
  </div>

  <!-- Video library -->
  <div class="sec-title">
    Video Library <span class="count">{{ videos|length }} files</span>
  </div>
  {% if videos %}
  <div class="lib-grid">
    {% for v in videos %}
    <div class="vid-card">
      <video src="/videos/{{ v }}" controls preload="metadata" playsinline></video>
      <div class="vid-info">
        <div class="vid-name" title="{{ v }}">{{ v }}</div>
        <a class="dl-btn" href="/download/{{ v }}" download style="width:100%;justify-content:center;">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 12l-4-4h2.5V3h3v5H12L8 12z"/>
            <rect x="2" y="13" width="12" height="1.5" rx=".75"/>
          </svg>
          Download
        </a>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="table-wrap"><div class="empty">No videos yet.</div></div>
  {% endif %}

</main>

<script>
async function triggerRun() {
  const btn   = document.getElementById('runBtn');
  const fb    = document.getElementById('fb');
  const niche = document.getElementById('niche').value.trim();
  btn.disabled = true;
  fb.className = 'fb'; fb.textContent = 'Starting…';
  try {
    const res  = await fetch('/trigger', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({niche})
    });
    const data = await res.json();
    if (res.ok) {
      fb.className = 'fb ok';
      fb.textContent = '✓ Running — page refreshes automatically.';
      setTimeout(() => location.reload(), 4000);
    } else {
      fb.className = 'fb err';
      fb.textContent = '✗ ' + (data.error || 'Unknown error');
      btn.disabled = false;
    }
  } catch(e) {
    fb.className = 'fb err';
    fb.textContent = '✗ ' + e.message;
    btn.disabled = false;
  }
}
{% if is_running %}setTimeout(() => location.reload(), 8000);{% endif %}
</script>
</body>
</html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    # List local video files newest-first
    try:
        videos = sorted(
            [f for f in os.listdir(VIDEOS_DIR) if f.endswith(".mp4")],
            reverse=True,
        )
    except FileNotFoundError:
        videos = []

    return render_template_string(
        DASHBOARD,
        is_running=is_running,
        history=run_history,
        schedule_h=SCHEDULE_HOURS,
        niche=NICHE,
        videos=videos,
    )


@app.route("/trigger", methods=["POST"])
def trigger():
    if is_running:
        return jsonify({"error": "Pipeline already running"}), 409
    body  = request.get_json(silent=True) or {}
    niche = body.get("niche", NICHE)
    thread = threading.Thread(target=do_run, kwargs={"niche": niche}, daemon=True)
    thread.start()
    return jsonify({"message": "Pipeline started", "niche": niche})


@app.route("/download/<filename>")
def download(filename):
    """Serve a video file as a download."""
    return send_from_directory(
        VIDEOS_DIR, filename,
        as_attachment=True,
        mimetype="video/mp4",
    )


@app.route("/videos/<filename>")
def stream_video(filename):
    """Stream a video for in-browser preview."""
    return send_from_directory(VIDEOS_DIR, filename, mimetype="video/mp4")


@app.route("/status")
def status():
    return jsonify({
        "is_running":    is_running,
        "schedule_hours": SCHEDULE_HOURS,
        "total_runs":    len(run_history),
        "last_run":      run_history[0] if run_history else None,
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

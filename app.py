import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, send_from_directory, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from modules.script_generator import generate_script
from modules.video_creator import create_video

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

app = Flask(__name__)

BEIRUT_TZ = pytz.timezone("Asia/Beirut")
VIDEOS_DIR = "videos"
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)

# ── Schedule config ───────────────────────────────────────────────────────────
SCHEDULE = [
    {
        "id": "slot_1",
        "label": "Short Hook",
        "time": "13:00",
        "hour": 13,
        "minute": 0,
        "duration_range": (7, 12),
        "goal": "Go viral fast",
        "style": "hook",
        "emoji": "⚡",
    },
    {
        "id": "slot_2",
        "label": "Core Message",
        "time": "18:30",
        "hour": 18,
        "minute": 30,
        "duration_range": (20, 35),
        "goal": "Retention + shares",
        "style": "core",
        "emoji": "💎",
    },
    {
        "id": "slot_3",
        "label": "Authority",
        "time": "21:00",
        "hour": 21,
        "minute": 0,
        "duration_range": (40, 60),
        "goal": "Build trust",
        "style": "authority",
        "emoji": "🔥",
    },
    {
        "id": "slot_4",
        "label": "Loop Video",
        "time": "23:30",
        "hour": 23,
        "minute": 30,
        "duration_range": (15, 25),
        "goal": "Replay boost",
        "style": "loop",
        "emoji": "🔄",
    },
]

# ── State ─────────────────────────────────────────────────────────────────────
generated_videos = []

def load_video_history():
    history_file = os.path.join(VIDEOS_DIR, "history.json")
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return json.load(f)
    return []

def save_video_history():
    history_file = os.path.join(VIDEOS_DIR, "history.json")
    with open(history_file, "w") as f:
        json.dump(generated_videos[-100:], f, indent=2)  # keep last 100

generated_videos = load_video_history()

# ── Core job ──────────────────────────────────────────────────────────────────
def run_slot(slot: dict):
    slot_id = slot["id"]
    label = slot["label"]
    style = slot["style"]
    dur_range = slot["duration_range"]

    log.info(f"▶ Starting slot [{label}]")
    now = datetime.now(BEIRUT_TZ)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{slot_id}.mp4"
    output_path = os.path.join(VIDEOS_DIR, filename)

    try:
        # 1 — Generate script via Claude
        script = generate_script(style=style, duration_range=dur_range)
        log.info(f"  Script generated ({len(script.get('lines', []))} lines)")

        # 2 — Render video
        create_video(
            script=script,
            output_path=output_path,
            style=style,
            duration_range=dur_range,
        )
        log.info(f"  Video saved → {output_path}")

        # 3 — Log to history
        entry = {
            "id": f"{slot_id}_{timestamp}",
            "slot_id": slot_id,
            "label": label,
            "style": style,
            "goal": slot["goal"],
            "emoji": slot["emoji"],
            "filename": filename,
            "script": script,
            "created_at": now.isoformat(),
            "status": "done",
        }
        generated_videos.append(entry)
        save_video_history()
        log.info(f"✅ Slot [{label}] complete")
        return entry

    except Exception as e:
        log.error(f"❌ Slot [{label}] failed: {e}", exc_info=True)
        entry = {
            "id": f"{slot_id}_{timestamp}",
            "slot_id": slot_id,
            "label": label,
            "style": style,
            "goal": slot["goal"],
            "emoji": slot["emoji"],
            "filename": None,
            "script": None,
            "created_at": now.isoformat(),
            "status": "error",
            "error": str(e),
        }
        generated_videos.append(entry)
        save_video_history()
        return entry

# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=BEIRUT_TZ)

for slot in SCHEDULE:
    scheduler.add_job(
        func=run_slot,
        trigger=CronTrigger(
            hour=slot["hour"],
            minute=slot["minute"],
            timezone=BEIRUT_TZ,
        ),
        kwargs={"slot": slot},
        id=slot["id"],
        name=slot["label"],
        replace_existing=True,
    )

scheduler.start()
log.info("📅 Scheduler started — 4 daily jobs active (Beirut TZ)")

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    now = datetime.now(BEIRUT_TZ)
    # Compute next run for each slot
    jobs_info = []
    for slot in SCHEDULE:
        job = scheduler.get_job(slot["id"])
        next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M") if job and job.next_run_time else "N/A"
        jobs_info.append({**slot, "next_run": next_run})
    return render_template(
        "dashboard.html",
        schedule=jobs_info,
        videos=list(reversed(generated_videos[-20:])),
        now=now.strftime("%Y-%m-%d %H:%M:%S"),
        tz="Beirut (UTC+3)",
    )

@app.route("/api/trigger/<slot_id>", methods=["POST"])
def trigger_slot(slot_id):
    slot = next((s for s in SCHEDULE if s["id"] == slot_id), None)
    if not slot:
        return jsonify({"error": "Unknown slot"}), 404
    import threading
    t = threading.Thread(target=run_slot, args=(slot,))
    t.daemon = True
    t.start()
    return jsonify({"status": "triggered", "slot": slot["label"]})

@app.route("/api/videos")
def api_videos():
    return jsonify(list(reversed(generated_videos[-50:])))

@app.route("/api/status")
def api_status():
    now = datetime.now(BEIRUT_TZ)
    jobs = []
    for slot in SCHEDULE:
        job = scheduler.get_job(slot["id"])
        jobs.append({
            "id": slot["id"],
            "label": slot["label"],
            "time": slot["time"],
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        })
    return jsonify({
        "server_time": now.isoformat(),
        "timezone": "Asia/Beirut",
        "total_videos": len(generated_videos),
        "jobs": jobs,
    })

@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEOS_DIR, filename)

@app.route("/api/logs")
def api_logs():
    try:
        with open("logs/bot.log", "r") as f:
            lines = f.readlines()
        return jsonify({"lines": lines[-100:]})
    except Exception:
        return jsonify({"lines": []})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

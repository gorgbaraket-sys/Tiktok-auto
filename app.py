import os
import json
import subprocess
import threading
import uuid
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

jobs = {}

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
# ─────────────────────────────────────────────────────────────


def get_channel_videos(channel_url, max_videos=10):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'playlist_items': f'1-{max_videos}',
        'ignoreerrors': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        if not info:
            raise ValueError("Could not fetch channel. Check the URL.")
        videos = []
        for entry in (info.get('entries') or []):
            if not entry:
                continue
            vid_id = entry.get('id') or ''
            if not vid_id:
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
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': True,
        'merge_output_format': 'mp4',
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
    }
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

STRICT duration rules (enforce exactly):
- hook: 7–12 seconds
- core: 20–35 seconds
- authority: 40–60 seconds
- loop: 15–25 seconds

All timestamps must be within 0–{int(duration)}s. Pick segments from different parts of the video.
Return ONLY the JSON array."""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=900
    )

    raw = resp.choices[0].message.content.strip()
    if '```' in raw:
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    raw = raw.strip().rstrip('`').strip()

    clips = json.loads(raw)

    # Hard-clamp durations
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
             .replace("'", "\u2019")
             [:50]
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
        'ffmpeg', '-y',
        '-ss', str(start), '-i', video_path,
        '-t', str(duration),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-400:]}")


def update_job(job_id, **kwargs):
    if job_id in jobs:
        jobs[job_id].update(kwargs)


# ─── BACKGROUND WORKER ──────────────────────────────────────

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
    return render_template('index.html')


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
    safe         = {k: v for k, v in job.items() if k != 'clips'}
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

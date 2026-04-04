import os
import json
import random
import logging
import subprocess
import requests

logger = logging.getLogger(__name__)

PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY')

# Luxury + trading background queries for Pexels
BG_QUERIES = [
    'luxury car driving night',
    'stock market trading screen',
    'private jet interior',
    'luxury penthouse city view',
    'forex charts finance',
    'businessman walking city',
    'luxury watch close up',
    'skyscraper city night lights',
    'trading desk multiple screens',
    'yacht ocean luxury',
    'monaco lifestyle',
    'speed luxury sports car',
    'financial district blur',
    'gold bars wealth',
    'luxury hotel lobby',
]

def get_pexels_video(query, min_duration=10):
    """Fetch a portrait background video from Pexels"""
    headers = {'Authorization': PEXELS_API_KEY}
    url = f'https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=portrait'

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        videos = response.json().get('videos', [])
    except Exception as e:
        logger.warning(f"Pexels query '{query}' failed: {e}. Trying fallback.")
        videos = []

    if not videos:
        # Fallback to generic luxury
        try:
            r2 = requests.get(
                'https://api.pexels.com/videos/search?query=luxury lifestyle&per_page=15&orientation=portrait',
                headers=headers, timeout=30
            )
            videos = r2.json().get('videos', [])
        except:
            raise RuntimeError("Pexels API completely failed — check PEXELS_API_KEY")

    # Prefer videos long enough
    suitable = [v for v in videos if v.get('duration', 0) >= min_duration] or videos
    video = random.choice(suitable)

    # Find best portrait file
    files = video.get('video_files', [])
    portrait = [f for f in files if f.get('width', 1) < f.get('height', 0)] or files
    portrait.sort(key=lambda f: f.get('width', 0) * f.get('height', 0), reverse=True)

    return portrait[0]['link']

def download_file(url, path, timeout=90):
    r = requests.get(url, stream=True, timeout=timeout)
    r.raise_for_status()
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return path

def get_audio_duration(audio_path):
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', audio_path],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    for stream in data.get('streams', []):
        if stream.get('codec_type') == 'audio':
            return float(stream.get('duration', 30.0))
    return 30.0

def escape_ffmpeg_text(text):
    """Escape text for FFmpeg drawtext filter"""
    return (text
        .replace('\\', '\\\\')
        .replace("'", "\\'")
        .replace(':', '\\:')
        .replace('%', '\\%')
        .replace('[', '\\[')
        .replace(']', '\\]')
    )

def build_subtitle_filters(script, audio_duration):
    """Build FFmpeg drawtext filters for word-by-word subtitles"""
    words = script.split()
    chunk_size = 4
    chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

    if not chunks:
        return []

    time_per_chunk = audio_duration / len(chunks)
    filters = []

    for i, chunk in enumerate(chunks):
        t_start = round(i * time_per_chunk, 2)
        t_end   = round((i + 1) * time_per_chunk, 2)
        safe    = escape_ffmpeg_text(chunk)

        filters.append(
            f"drawtext="
            f"text='{safe}':"
            f"fontsize=54:"
            f"fontcolor=white:"
            f"bordercolor=black:"
            f"borderw=4:"
            f"x=(w-text_w)/2:"
            f"y=(h*0.72):"
            f"enable='between(t,{t_start},{t_end})'"
        )

    return filters

def create_video(audio_path, script_data, video_type):
    os.makedirs('videos', exist_ok=True)

    uid = os.urandom(4).hex()
    bg_path     = f'videos/bg_{uid}.mp4'
    output_path = f'videos/{video_type}_{uid}_final.mp4'

    # Get audio duration
    audio_dur = get_audio_duration(audio_path)
    target_dur = audio_dur + 0.3  # tiny buffer

    # Download background
    query = random.choice(BG_QUERIES)
    logger.info(f"Fetching Pexels background: '{query}'")
    bg_url = get_pexels_video(query, min_duration=int(target_dur))
    download_file(bg_url, bg_path)
    logger.info(f"Background downloaded: {bg_path}")

    # Build subtitle drawtext filters
    subtitle_filters = build_subtitle_filters(script_data['script'], audio_dur)

    # ── Watermark / branding line ──
    brand_text = escape_ffmpeg_text('TRADING MINDSET')
    brand_filter = (
        f"drawtext="
        f"text='{brand_text}':"
        f"fontsize=30:"
        f"fontcolor=gold:"
        f"bordercolor=black:"
        f"borderw=3:"
        f"x=(w-text_w)/2:"
        f"y=55"
    )

    # ── Video type label (top right) ──
    vtype_text  = escape_ffmpeg_text(video_type.replace('_', ' ').upper())
    vtype_label = (
        f"drawtext="
        f"text='{vtype_text}':"
        f"fontsize=22:"
        f"fontcolor=white@0.6:"
        f"bordercolor=black:"
        f"borderw=2:"
        f"x=w-text_w-20:"
        f"y=55"
    )

    # ── Combine all vf filters ──
    vf_parts = [
        'scale=720:1280:force_original_aspect_ratio=increase',
        'crop=720:1280',
        # Slight dark overlay to make text readable
        'eq=brightness=-0.15:saturation=1.2',
        brand_filter,
        vtype_label,
    ] + subtitle_filters

    vf = ','.join(vf_parts)

    cmd = [
        'ffmpeg', '-y',
        '-stream_loop', '-1',       # loop bg if shorter than audio
        '-i', bg_path,
        '-i', audio_path,
        '-vf', vf,
        '-af', 'volume=1.4',
        '-t', str(target_dur),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '22',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-shortest',
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        output_path
    ]

    logger.info(f"Running FFmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg stderr:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"FFmpeg failed with code {result.returncode}")

    # Cleanup
    for p in [bg_path, audio_path]:
        try:
            os.remove(p)
        except:
            pass

    size_mb = os.path.getsize(output_path) / (1024*1024)
    logger.info(f"Video ready: {output_path} ({size_mb:.1f}MB)")
    return output_path

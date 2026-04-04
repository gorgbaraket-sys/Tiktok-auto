import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

TIKTOK_ACCESS_TOKEN = os.environ.get('TIKTOK_ACCESS_TOKEN')
BASE = 'https://open.tiktokapis.com/v2'

def post_to_tiktok(video_path, caption, hashtags):
    """
    Post a video to TikTok using Content Posting API v2 (Direct File Upload).
    Requires scope: video.upload + video.publish
    """
    if not TIKTOK_ACCESS_TOKEN:
        raise RuntimeError("TIKTOK_ACCESS_TOKEN is not set in environment variables")

    file_size = os.path.getsize(video_path)
    full_title = f"{caption}\n\n{hashtags}"[:2200]

    headers = {
        'Authorization': f'Bearer {TIKTOK_ACCESS_TOKEN}',
        'Content-Type': 'application/json; charset=UTF-8'
    }

    # ── Step 1: Init upload ───────────────────────────────────────────────────
    logger.info("TikTok: Initializing upload...")
    init_payload = {
        'post_info': {
            'title':              full_title,
            'privacy_level':      'PUBLIC_TO_EVERYONE',
            'disable_duet':       False,
            'disable_comment':    False,
            'disable_stitch':     False,
            'video_cover_timestamp_ms': 1000
        },
        'source_info': {
            'source':             'FILE_UPLOAD',
            'video_size':         file_size,
            'chunk_size':         file_size,
            'total_chunk_count':  1
        }
    }

    init_resp = requests.post(
        f'{BASE}/post/publish/video/init/',
        json=init_payload,
        headers=headers,
        timeout=30
    )
    init_resp.raise_for_status()
    init_data = init_resp.json()
    logger.info(f"TikTok init: {init_data}")

    if init_data.get('error', {}).get('code') not in ('ok', 'OK', None, ''):
        raise RuntimeError(f"TikTok init failed: {init_data}")

    upload_url  = init_data['data']['upload_url']
    publish_id  = init_data['data']['publish_id']

    # ── Step 2: Upload file ───────────────────────────────────────────────────
    logger.info(f"TikTok: Uploading {file_size//1024}KB video...")
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    upload_headers = {
        'Content-Type':   'video/mp4',
        'Content-Range':  f'bytes 0-{file_size-1}/{file_size}',
        'Content-Length': str(file_size)
    }

    upload_resp = requests.put(
        upload_url,
        data=video_bytes,
        headers=upload_headers,
        timeout=120
    )
    upload_resp.raise_for_status()
    logger.info(f"TikTok upload status: {upload_resp.status_code}")

    # ── Step 3: Poll publish status ───────────────────────────────────────────
    logger.info("TikTok: Polling publish status...")
    status_headers = {
        'Authorization': f'Bearer {TIKTOK_ACCESS_TOKEN}',
        'Content-Type':  'application/json; charset=UTF-8'
    }

    for attempt in range(10):
        time.sleep(3)
        status_resp = requests.post(
            f'{BASE}/post/publish/status/fetch/',
            json={'publish_id': publish_id},
            headers=status_headers,
            timeout=30
        )
        status_data = status_resp.json()
        status = status_data.get('data', {}).get('status', 'UNKNOWN')
        logger.info(f"TikTok publish status [{attempt+1}]: {status}")

        if status in ('PUBLISH_COMPLETE', 'SUCCESS'):
            logger.info("✅ TikTok: Video published successfully!")
            break
        elif status in ('FAILED', 'ERROR'):
            raise RuntimeError(f"TikTok publish failed: {status_data}")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    try:
        os.remove(video_path)
        logger.info(f"Cleaned up: {video_path}")
    except Exception:
        pass

    return {
        'publish_id': publish_id,
        'status': status,
        'caption': caption
    }

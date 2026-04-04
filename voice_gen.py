import os
import requests
import logging

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
# Default: Adam (deep, confident, masculine) — great for trading/wealth content
# Override with ELEVENLABS_VOICE_ID env var
VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')

# Voice style per video type
VOICE_SETTINGS = {
    'short_hook':    {'stability': 0.35, 'similarity_boost': 0.80, 'style': 0.70, 'speed': 1.05},
    'core_message':  {'stability': 0.50, 'similarity_boost': 0.75, 'style': 0.50, 'speed': 1.0},
    'authority':     {'stability': 0.65, 'similarity_boost': 0.75, 'style': 0.35, 'speed': 0.95},
    'loop_video':    {'stability': 0.55, 'similarity_boost': 0.78, 'style': 0.55, 'speed': 0.98},
}

def generate_voiceover(script, video_type):
    os.makedirs('videos', exist_ok=True)
    uid = os.urandom(4).hex()
    output_path = f'videos/{video_type}_{uid}.mp3'

    settings = VOICE_SETTINGS.get(video_type, VOICE_SETTINGS['core_message'])

    url = f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}'
    headers = {
        'Accept': 'audio/mpeg',
        'Content-Type': 'application/json',
        'xi-api-key': ELEVENLABS_API_KEY
    }

    payload = {
        'text': script,
        'model_id': 'eleven_multilingual_v2',
        'voice_settings': {
            'stability':        settings['stability'],
            'similarity_boost': settings['similarity_boost'],
            'style':            settings['style'],
            'use_speaker_boost': True
        }
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        f.write(response.content)

    logger.info(f"Voiceover saved: {output_path} ({len(response.content)//1024}KB)")
    return output_path

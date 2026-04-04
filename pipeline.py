import logging
from generator.script_gen import generate_script
from generator.voice_gen import generate_voiceover
from generator.video_gen import create_video
from poster.tiktok import post_to_tiktok

logger = logging.getLogger(__name__)

def generate_and_post(video_type, duration_range):
    try:
        logger.info(f"▶ Pipeline start: {video_type} | {duration_range[0]}-{duration_range[1]}s")

        # 1. Script
        script_data = generate_script(video_type, duration_range)
        logger.info(f"✅ Script: {script_data['script'][:60]}...")

        # 2. Voiceover
        audio_path = generate_voiceover(script_data['script'], video_type)
        logger.info(f"✅ Audio: {audio_path}")

        # 3. Video
        video_path = create_video(audio_path, script_data, video_type)
        logger.info(f"✅ Video: {video_path}")

        # 4. Post
        result = post_to_tiktok(video_path, script_data['caption'], script_data['hashtags'])
        logger.info(f"✅ Posted: {result}")

        return result

    except Exception as e:
        logger.error(f"❌ Pipeline error [{video_type}]: {e}", exc_info=True)
        raise

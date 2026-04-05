"""
script_generator.py — Uses Anthropic Claude to generate luxury trading mindset scripts.
"""
import os
import re
import json
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

STYLE_PROMPTS = {
    "hook": {
        "system": (
            "You are a viral TikTok scriptwriter specializing in the luxury trading mindset niche. "
            "Your hooks are bold, provocative, and stop the scroll in the first second. "
            "Write for an audience of ambitious young people who want to escape the 9-5, get rich, and live lavishly. "
            "Tone: cold, elite, alpha energy. Think: Lamborghinis, penthouses, waking up early, beating the market."
        ),
        "user": (
            "Write a SHORT HOOK TikTok script (7-12 seconds when read aloud). "
            "Goal: go viral immediately. "
            "Format as JSON with these fields:\n"
            "- title: string (internal title)\n"
            "- hook_line: string (the first bold statement, max 10 words)\n"
            "- lines: array of strings (all text lines shown on screen, 3-5 lines max)\n"
            "- caption: string (TikTok caption with 5 hashtags)\n"
            "- audio_mood: string (e.g. 'dramatic cinematic', 'dark trap', 'motivational piano')\n\n"
            "Topics to rotate through (pick one randomly): "
            "why most people stay broke, the mindset of the 1%, what losers do on weekends, "
            "trading is the ultimate freedom, why salary is slavery, "
            "silent discipline beats loud motivation, "
            "the market doesn't care about your feelings. "
            "Return ONLY valid JSON, no markdown."
        ),
    },
    "core": {
        "system": (
            "You are a TikTok content strategist for the luxury trading mindset niche. "
            "Your core message videos teach real value: mindset shifts, trading psychology, wealth habits. "
            "Tone: confident mentor, aspirational, data-backed but emotionally charged. "
            "The viewer should share this video immediately."
        ),
        "user": (
            "Write a CORE MESSAGE TikTok script (20-35 seconds when read aloud at normal pace). "
            "Goal: maximum retention and shares. "
            "Format as JSON with these fields:\n"
            "- title: string (internal title)\n"
            "- hook_line: string (opening hook, max 12 words)\n"
            "- lines: array of strings (5-8 text lines shown sequentially on screen)\n"
            "- caption: string (TikTok caption with 5 hashtags)\n"
            "- audio_mood: string\n\n"
            "Topics: trading rules every beginner ignores, the compounding mindset, "
            "3 habits separating rich traders from broke ones, why emotions destroy your portfolio, "
            "the morning routine of top earners, risk management is everything, "
            "how to think like a hedge fund. "
            "Return ONLY valid JSON, no markdown."
        ),
    },
    "authority": {
        "system": (
            "You are a luxury trading authority on TikTok. "
            "Your authority videos position you as the elite expert — someone who trades 7 figures, "
            "lives in penthouses, and shares hard truths. "
            "Tone: raw, real, slightly controversial. You educate but you also challenge. "
            "This video should make people follow immediately."
        ),
        "user": (
            "Write an AUTHORITY TikTok script (40-60 seconds when read aloud). "
            "Goal: build deep trust and gain followers. "
            "Format as JSON with these fields:\n"
            "- title: string (internal title)\n"
            "- hook_line: string (bold authority statement or story opener)\n"
            "- lines: array of strings (8-12 text lines, tell a story or teach a lesson step by step)\n"
            "- caption: string (TikTok caption with 5 hashtags)\n"
            "- audio_mood: string\n\n"
            "Topics: my worst trading loss and what it taught me, "
            "the truth about trading gurus, "
            "I analyzed 500 losing trades — here's the pattern, "
            "what $100k in the market actually looks like, "
            "why the rich don't talk about money, "
            "the psychology behind every winning trade. "
            "Return ONLY valid JSON, no markdown."
        ),
    },
    "loop": {
        "system": (
            "You are a viral loop video creator for the luxury trading mindset niche. "
            "Loop videos are designed so the end seamlessly connects to the beginning — "
            "the viewer watches 3-5 times without realizing. "
            "Tone: mysterious, hypnotic, aesthetic. Use short punchy lines. "
            "Think: wealth quotes, paradoxes, riddles about money."
        ),
        "user": (
            "Write a LOOP TikTok script (15-25 seconds). "
            "Goal: maximum replays — the video should feel like it loops perfectly. "
            "Format as JSON with these fields:\n"
            "- title: string (internal title)\n"
            "- hook_line: string (the opening that also works as the closing)\n"
            "- lines: array of strings (4-6 short lines, last line should connect to first)\n"
            "- caption: string (TikTok caption with 5 hashtags)\n"
            "- audio_mood: string\n\n"
            "Topics: wealth paradoxes (to make money you must stop chasing it), "
            "morning vs night habits of millionaires, "
            "the cycle of the broke vs the rich, "
            "one rule every trader lives by, "
            "what the market teaches you about life. "
            "Ensure the final line naturally leads back to the opening line. "
            "Return ONLY valid JSON, no markdown."
        ),
    },
}


def generate_script(style: str, duration_range: tuple) -> dict:
    """Call Claude and return a parsed script dict."""
    prompt_config = STYLE_PROMPTS.get(style, STYLE_PROMPTS["hook"])

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=prompt_config["system"],
        messages=[{"role": "user", "content": prompt_config["user"]}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        script = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract JSON from somewhere inside the text
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            script = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse Claude response as JSON:\n{raw}")

    # Ensure required fields exist
    script.setdefault("title", f"{style.title()} Video")
    script.setdefault("hook_line", "The market never sleeps.")
    script.setdefault("lines", ["Luxury. Discipline. Freedom."])
    script.setdefault("caption", "#trading #mindset #luxury #wealth #motivation")
    script.setdefault("audio_mood", "dramatic cinematic")
    script["style"] = style
    script["duration_range"] = list(duration_range)

    return script

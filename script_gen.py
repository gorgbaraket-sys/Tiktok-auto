import os
import json
import random
import logging
from groq import Groq

logger = logging.getLogger(__name__)
client = Groq(api_key=os.environ.get('GROQ_API_KEY'))

# ── Topic pools per video type ────────────────────────────────────────────────
TOPICS = {
    'short_hook': [
        "The one mindset shift that separates 7-figure traders from broke ones",
        "Why 90% of traders lose money — and it has nothing to do with strategy",
        "The luxury lifestyle starts with this single trading rule",
        "Most traders quit right before they were about to win",
        "Your emotions are costing you more than your losses",
        "The difference between a Lambo and a loss is your mindset",
        "Discipline is the only strategy that never fails in trading",
        "Rich traders do this ONE thing differently",
        "Stop blaming the market — the problem is in your head",
        "Trading is 20% strategy, 80% psychology",
    ],
    'core_message': [
        "How to kill fear and greed before they kill your account",
        "The trading psychology loop that keeps you poor",
        "Why professional traders never rush a single entry",
        "How discipline creates the luxury life you want",
        "The mindset of a trader who never blows their account",
        "What separates consistent winners from emotional losers in trading",
        "How to detach your ego from your trades",
        "The patience principle behind every wealthy trader",
        "Why revenge trading always ends the same way",
        "How to build a trading routine that creates freedom",
    ],
    'authority': [
        "The complete psychology of a profitable trader — explained",
        "Why the wealthy think about risk in a completely different way",
        "How top traders use journaling to eliminate emotional decisions",
        "The full breakdown of why traders fail despite good strategies",
        "Building a mindset that attracts consistent trading profits",
        "How to think like a hedge fund manager with a $100 account",
        "The 5 psychological traps that destroy trading accounts",
        "Why patience is the rarest and most profitable trading skill",
        "How to build mental resilience that survives any market",
        "The psychology behind position sizing and wealth preservation",
    ],
    'loop_video': [
        "Watch this on repeat until your mindset changes forever",
        "The trading truth that loops in every rich trader's mind",
        "This one principle replays in profitable traders' heads daily",
        "Keep watching this until discipline becomes automatic",
        "One rule. Loop it. Repeat it. Live it.",
    ]
}

# ── Prompt configs per video type ─────────────────────────────────────────────
TYPE_CONFIG = {
    'short_hook': {
        'words': '15-30',
        'style': 'Ultra-punchy. ONE shocking statement or question. Zero fluff. Stops the scroll instantly.',
        'format': 'Single bold statement OR question that creates instant curiosity. No intro. No outro.'
    },
    'core_message': {
        'words': '70-110',
        'style': 'Educational, direct, builds to one key insight. Confident and premium tone.',
        'format': 'Hook (1 line) → Problem → Key truth → What to do → Quick call to action.'
    },
    'authority': {
        'words': '130-190',
        'style': 'Expert-level authority. Deep insight. Positions speaker as a serious trading mentor.',
        'format': 'Strong hook → Deeper insight with reason → Real examples or analogies → Actionable takeaway → Power close.'
    },
    'loop_video': {
        'words': '45-75',
        'style': 'Hypnotic, meditative, repeatable. Ends in a way that makes the viewer hit replay.',
        'format': 'Build-up statement → Core truth → Closing line that echoes the opening or creates a loop feeling.'
    }
}

def generate_script(video_type, duration_range):
    topic = random.choice(TOPICS[video_type])
    cfg = TYPE_CONFIG[video_type]

    prompt = f"""You are an elite TikTok scriptwriter for luxury lifestyle, trading psychology, and wealth mindset content.

Video Type: {video_type.replace('_', ' ').title()}
Topic: {topic}
Duration: {duration_range[0]}–{duration_range[1]} seconds when spoken
Word Count: {cfg['words']} words
Style: {cfg['style']}
Format: {cfg['format']}

Niche context:
- Audience: Ambitious 18-35 year olds who want financial freedom through trading
- Tone: Premium, confident, no-BS — like a successful trader speaking from experience
- Reference luxury touchpoints naturally (freedom, Lamborghini, private jet, penthouse, watches) — but sparingly
- Core themes: discipline, patience, emotional control, risk management, mindset mastery, wealth psychology

Respond ONLY in valid JSON. No markdown. No explanation. No extra text.

{{
  "script": "the full spoken script — natural, energetic, punchy",
  "caption": "TikTok caption under 120 chars — intriguing, drives engagement",
  "hashtags": "#trading #tradingpsychology #mindset #wealthmindset #forex #discipline #luxurylifestyle #richlife #tradinglife #motivation",
  "topic": "{topic}"
}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.88,
        max_tokens=700
    )

    raw = response.choices[0].message.content.strip()

    # Strip code fences if present
    if '```json' in raw:
        raw = raw.split('```json')[1].split('```')[0].strip()
    elif '```' in raw:
        raw = raw.split('```')[1].split('```')[0].strip()

    data = json.loads(raw)
    logger.info(f"Script topic: {data.get('topic','?')}")
    return data

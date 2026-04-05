"""
video_creator.py — Black-and-gold luxury TikTok video renderer using Pillow + MoviePy.
"""
import os
import math
import random
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import (
    ImageClip,
    concatenate_videoclips,
    AudioFileClip,
    CompositeVideoClip,
)

# ── Constants ────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1080, 1920          # TikTok portrait 9:16
FPS = 30

# Luxury color palette
BLACK      = (0, 0, 0)
DEEP_BLACK = (5, 5, 8)
GOLD       = (212, 175, 55)
GOLD_LIGHT = (255, 215, 100)
GOLD_DIM   = (140, 110, 30)
WHITE      = (255, 255, 255)
GREY_DARK  = (30, 30, 35)
GREY_MID   = (60, 60, 65)

# Font paths — uses system fonts, falls back to default
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]

def get_font(size: int):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_gold_line(draw: ImageDraw, y: int, margin: int = 80, thickness: int = 2):
    """Draw a thin gold horizontal divider."""
    draw.line([(margin, y), (WIDTH - margin, y)], fill=GOLD_DIM, width=thickness)


def draw_luxury_background(style: str) -> Image.Image:
    """Create the base background frame for a given style."""
    img = Image.new("RGB", (WIDTH, HEIGHT), DEEP_BLACK)
    draw = ImageDraw.Draw(img)

    if style == "hook":
        # Dramatic diagonal gold beam
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for i in range(0, 60, 4):
            od.line(
                [(WIDTH // 2 - 300 + i, 0), (WIDTH // 2 + 800 + i, HEIGHT)],
                fill=(*GOLD_DIM, 12), width=60,
            )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        # Top and bottom gold bars
        draw.rectangle([(0, 0), (WIDTH, 12)], fill=GOLD)
        draw.rectangle([(0, HEIGHT - 12), (WIDTH, HEIGHT)], fill=GOLD)

    elif style == "core":
        # Subtle grid pattern
        for x in range(0, WIDTH, 120):
            draw.line([(x, 0), (x, HEIGHT)], fill=(20, 20, 25), width=1)
        for y in range(0, HEIGHT, 120):
            draw.line([(0, y), (WIDTH, y)], fill=(20, 20, 25), width=1)
        # Gold corner accents
        L = 80
        for corner, (cx, cy) in enumerate([(0, 0), (WIDTH, 0), (0, HEIGHT), (WIDTH, HEIGHT)]):
            sx = cx if cx == 0 else cx - L
            sy = cy if cy == 0 else cy - L
            draw.rectangle([(sx, sy), (sx + L, sy + 4)], fill=GOLD)
            draw.rectangle([(sx, sy), (sx + 4, sy + L)], fill=GOLD)

    elif style == "authority":
        # Dark vignette with centered gold circle glow
        for r in range(500, 0, -40):
            alpha = max(0, int(40 * (1 - r / 500)))
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            cx, cy = WIDTH // 2, HEIGHT // 2 - 100
            od.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*GOLD_DIM, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (WIDTH, 8)], fill=GOLD)
        draw.rectangle([(0, HEIGHT - 8), (WIDTH, HEIGHT)], fill=GOLD)

    elif style == "loop":
        # Symmetric diamond pattern
        for i in range(8):
            r = 120 + i * 160
            draw.rectangle(
                [(WIDTH // 2 - r, HEIGHT // 2 - r), (WIDTH // 2 + r, HEIGHT // 2 + r)],
                outline=(*GOLD_DIM, 60) if hasattr(draw, 'outline') else GOLD_DIM,
            )
        draw.rectangle([(0, 0), (WIDTH, 6)], fill=GOLD)
        draw.rectangle([(0, HEIGHT - 6), (WIDTH, HEIGHT)], fill=GOLD)
        draw.rectangle([(0, 0), (6, HEIGHT)], fill=GOLD)
        draw.rectangle([(WIDTH - 6, 0), (WIDTH, HEIGHT)], fill=GOLD)

    return img


def make_text_frame(
    text: str,
    style: str,
    line_index: int,
    total_lines: int,
    is_hook: bool = False,
) -> np.ndarray:
    """Render a single text card as numpy array."""
    bg = draw_luxury_background(style)
    draw = ImageDraw.Draw(bg)

    # Watermark / brand
    brand_font = get_font(32)
    draw.text((WIDTH // 2, HEIGHT - 80), "LUXURY MINDSET", font=brand_font,
              fill=GOLD_DIM, anchor="mm")
    draw_gold_line(draw, HEIGHT - 100)

    # Progress dots
    dot_y = HEIGHT - 130
    dot_spacing = 24
    total_dots = total_lines
    start_x = WIDTH // 2 - (total_dots - 1) * dot_spacing // 2
    for i in range(total_dots):
        x = start_x + i * dot_spacing
        color = GOLD if i == line_index else GREY_MID
        r = 7 if i == line_index else 5
        draw.ellipse([(x - r, dot_y - r), (x + r, dot_y + r)], fill=color)

    # Main text area
    if is_hook:
        font_size = 96
        text_y = HEIGHT // 2 - 80
        color = GOLD
        # Gold glow effect — draw same text multiple times in dimmer gold
        glow_font = get_font(font_size + 4)
        for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3)]:
            draw.text((WIDTH // 2 + dx, text_y + dy), text,
                      font=glow_font, fill=(*GOLD_DIM, 120), anchor="mm")
    else:
        font_size = 72
        text_y = HEIGHT // 2 - 60
        color = WHITE

    font = get_font(font_size)

    # Wrap text
    max_chars = 22 if is_hook else 26
    wrapped = textwrap.fill(text.upper() if is_hook else text, width=max_chars)
    lines = wrapped.split("\n")

    line_h = font_size + 20
    total_h = len(lines) * line_h
    start_y = text_y - total_h // 2

    for i, line in enumerate(lines):
        y = start_y + i * line_h
        # Shadow
        draw.text((WIDTH // 2 + 3, y + 3), line, font=font,
                  fill=(0, 0, 0), anchor="mm")
        draw.text((WIDTH // 2, y), line, font=font, fill=color, anchor="mm")

    # Style-specific decorations
    if style == "hook":
        # Side gold arrows
        arrow_font = get_font(48)
        draw.text((120, HEIGHT // 2), "▶", font=arrow_font, fill=GOLD, anchor="mm")
        draw.text((WIDTH - 120, HEIGHT // 2), "◀", font=arrow_font, fill=GOLD, anchor="mm")

    elif style == "authority":
        # Horizontal rules around text
        rule_y_top = start_y - 30
        rule_y_bot = start_y + total_h + 20
        draw_gold_line(draw, rule_y_top, margin=120, thickness=2)
        draw_gold_line(draw, rule_y_bot, margin=120, thickness=2)

    return np.array(bg)


def create_video(
    script: dict,
    output_path: str,
    style: str,
    duration_range: tuple,
):
    """Render all lines into an MP4 and save to output_path."""
    lines = script.get("lines", ["Discipline. Luxury. Freedom."])
    hook_line = script.get("hook_line", lines[0])
    total_lines = len(lines)
    total_dur = random.uniform(*duration_range)
    per_line = total_dur / max(total_lines, 1)

    # For hook style: show hook first, then body lines
    all_lines = []
    if style == "hook":
        all_lines.append({"text": hook_line, "is_hook": True, "idx": 0})
        for i, l in enumerate(lines):
            all_lines.append({"text": l, "is_hook": False, "idx": i + 1})
    else:
        for i, l in enumerate(lines):
            all_lines.append({"text": l, "is_hook": (i == 0), "idx": i})

    total_frames = len(all_lines)
    dur_each = total_dur / total_frames

    clips = []
    for item in all_lines:
        frame = make_text_frame(
            text=item["text"],
            style=style,
            line_index=item["idx"],
            total_lines=total_frames,
            is_hook=item["is_hook"],
        )
        clip = ImageClip(frame, duration=dur_each).set_fps(FPS)
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio=False,
        logger=None,
        preset="ultrafast",
    )
    final.close()

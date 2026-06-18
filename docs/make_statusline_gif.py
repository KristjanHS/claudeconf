#!/usr/bin/env python3
"""Render an animated GIF of the real statusline as context fills toward the cliff.

Drives .claude/statusline.sh with crafted Claude-Code JSON at rising token
counts, parses its ANSI output, and paints each frame in the Windows Terminal
"Campbell" palette (the scheme the docs/statusline*.png screenshots were shot
in). The final frame matches docs/statusline2.png exactly ($8.03 / 77% / 154k).

Reproduce:  python3 docs/make_statusline_gif.py
Output:     docs/statusline.gif
"""
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / ".claude" / "statusline.sh"
OUT = REPO / "docs" / "statusline.gif"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# Campbell palette (sampled from docs/statusline2.png)
BG = (12, 12, 12)
WHITE = (242, 242, 242)
DIM = (128, 128, 128)
ANSI = {31: (197, 15, 31), 32: (19, 161, 14), 33: (193, 156, 0)}

W, H = 1595, 110
FONT_SIZE = 28
PAD_X = 44

# (used_tokens, cost_usd, five_hour_pct) — the story: green -> amber+/clear -> red
FRAMES = [
    (18000, 0.42, 31),
    (55000, 1.75, 36),
    (98000, 3.40, 42),
    (124000, 5.05, 46),
    (134000, 6.20, 48),   # crosses 130k: bar turns amber, "/clear soon" appears
    (154000, 8.03, 50),   # the hero frame (== docs/statusline2.png)
    (168000, 9.30, 53),   # crosses 160k: bar turns red
]
# Per-frame duration (ms); hold the cliff frame longer so the eye lands on it.
DURATIONS = [650, 650, 650, 700, 900, 1900, 1400]


def render_line(used, cost, five_h):
    """Run the real statusline script and return its raw ANSI string."""
    payload = {
        "model": {"display_name": "Opus 4.8 (1M context)"},
        "context_window": {"current_usage": {"input_tokens": used}},
        "cost": {"total_cost_usd": cost},
        "rate_limits": {"five_hour": {"used_percentage": five_h}},
        "workspace": {"current_dir": str(REPO)},
    }
    out = subprocess.run(
        ["bash", str(SCRIPT)], input=json.dumps(payload),
        capture_output=True, text=True, check=True,
    )
    return out.stdout.rstrip("\n")


SGR = re.compile(r"\033\[([0-9;]*)m")


def parse_ansi(s):
    """Yield (text, rgb) spans, resolving SGR color + dim to Campbell RGB."""
    color, dim = 0, False

    def rgb():
        return ANSI[color] if color in ANSI else (DIM if dim else WHITE)

    pos = 0
    for m in SGR.finditer(s):
        text = s[pos:m.start()]
        if text:
            yield text, rgb()
        for code in (int(c) for c in m.group(1).split(";") if c != ""):
            if code == 0:
                color, dim = 0, False
            elif code == 2:
                dim = True
            elif code in ANSI:
                color = code
        pos = m.end()
    tail = s[pos:]
    if tail:
        yield tail, rgb()


def main():
    font = ImageFont.truetype(FONT, FONT_SIZE)
    ascent, descent = font.getmetrics()
    y = (H - (ascent + descent)) // 2
    frames = []
    for used, cost, five_h in FRAMES:
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        x = PAD_X
        for text, rgb in parse_ansi(render_line(used, cost, five_h)):
            draw.text((x, y), text, font=font, fill=rgb)
            x += draw.textlength(text, font=font)
        frames.append(img)
    frames[0].save(
        OUT, save_all=True, append_images=frames[1:],
        duration=DURATIONS, loop=0, optimize=True, disposal=2,
    )
    print(f"wrote {OUT} ({len(frames)} frames)")


if __name__ == "__main__":
    main()

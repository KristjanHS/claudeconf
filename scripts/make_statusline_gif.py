#!/usr/bin/env python3
"""Render an animated GIF of the real statusline as context fills toward the cliff.

Drives .claude/statusline.sh with crafted Claude-Code JSON at rising token
counts, parses its ANSI output, and paints each frame in the Windows Terminal
"Campbell" palette (the scheme the docs/statusline*.png screenshots were shot
in).

The "| $cost" segment is stripped from each frame: once "← /clear soon" appears
it pushes the trailing "5h:" limit off the frame edge, so dropping the spend
keeps the rate-limit indicator visible end-to-end.

Reproduce:  python3 scripts/make_statusline_gif.py
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

# White frame baked around the dark terminal panel (renders on GitHub).
FRAME = (250, 250, 250)
MARGIN = 22       # frame thickness on every side
RADIUS = 16       # rounded corners on the inner dark panel

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
DURATIONS = [1100, 1100, 1100, 1200, 1500, 3000, 2400]


def render_line(used, cost, five_h):
    """Run the real statusline script and return its raw ANSI string."""
    payload = {
        "model": {"display_name": "Opus 4.8"},
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

# The " | $cost" spend segment: leading space, DIM, "| $N.NN", RESET.
COST_SEG = re.compile(r" \033\[2m\| \$[0-9.]+\033\[0m")


def strip_cost(s):
    """Drop the spend segment so the trailing 5h: limit stays on-frame."""
    return COST_SEG.sub("", s)


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
        img = Image.new("RGB", (W + 2 * MARGIN, H + 2 * MARGIN), FRAME)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [MARGIN, MARGIN, MARGIN + W - 1, MARGIN + H - 1], radius=RADIUS, fill=BG,
        )
        x = MARGIN + PAD_X
        for text, rgb in parse_ansi(strip_cost(render_line(used, cost, five_h))):
            draw.text((x, MARGIN + y), text, font=font, fill=rgb)
            x += draw.textlength(text, font=font)
        frames.append(img)
    frames[0].save(
        OUT, save_all=True, append_images=frames[1:],
        # disposal=1 (leave prior frame) keeps the static white border visible:
        # optimize stores only the changed region per frame, so the unchanged
        # border must persist rather than be wiped to background (disposal=2).
        duration=DURATIONS, loop=0, optimize=True, disposal=1,
    )
    print(f"wrote {OUT} ({len(frames)} frames)")


if __name__ == "__main__":
    main()

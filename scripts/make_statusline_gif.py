#!/usr/bin/env python3
"""Render an animated GIF of the real statusline as context fills toward the cliff.

Drives .claude/statusline.sh with crafted Claude-Code JSON at rising token
counts, parses its ANSI output, and paints each frame in the Windows Terminal
"Campbell" palette. The README stills docs/statusline{,2}.png are exported
from the same frames (STILLS) so they always match the GIF.

The "| $cost" segment is stripped from each frame: once "← /clear soon" appears
it pushes the trailing "5h:"/"7d:" limits off the frame edge, so dropping the
spend keeps the rate-limit indicators visible end-to-end.

Reproduce:  python3 scripts/make_statusline_gif.py
Output:     docs/statusline.gif, docs/statusline.png, docs/statusline2.png
"""

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / ".claude" / "statusline.sh"
DOCS = REPO / "docs"
OUT = DOCS / "statusline.gif"
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
MARGIN = 22  # frame thickness on every side
RADIUS = 16  # rounded corners on the inner dark panel

# (used_tokens, cost_usd, five_hour_pct, seven_day_pct) — the story against the
# 300k statusline: green -> amber + "/clear soon" -> red
FRAMES = [
    (27000, 0.42, 31, 14),
    (83000, 1.75, 36, 15),
    (147000, 3.40, 42, 17),
    (186000, 5.05, 46, 18),
    (201000, 6.20, 48, 19),  # crosses 200k: bar turns amber, "/clear soon" appears
    (231000, 8.03, 50, 21),  # the hero frame (== docs/statusline2.png)
    (252000, 9.30, 53, 22),  # crosses 240k: bar turns red
]
RED_FRAME = 6
# Per-frame duration (ms); hold the cliff frame longer so the eye lands on it.
DURATIONS = [1100, 1100, 1100, 1200, 1500, 3000, 2400]
# README stills, exported from these frame indices.
STILLS = {"statusline.png": 2, "statusline2.png": 5}


def render_line(used, cost, five_h, seven_d):
    """Run the real statusline script and return its raw ANSI string."""
    payload = {
        "model": {"display_name": "Opus 5.5"},
        "context_window": {"current_usage": {"input_tokens": used}},
        "cost": {"total_cost_usd": cost},
        "rate_limits": {
            "five_hour": {"used_percentage": five_h},
            "seven_day": {"used_percentage": seven_d},
        },
        "workspace": {"current_dir": str(REPO)},
    }
    out = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.rstrip("\n")


SGR = re.compile(r"\033\[([0-9;]*)m")

# The " | $cost" spend segment: leading space, DIM, "| $N.NN", RESET.
COST_SEG = re.compile(r" \033\[2m\| \$[0-9.]+\033\[0m")


def strip_cost(s):
    """Drop the spend segment so the trailing 5h:/7d: limits stay on-frame."""
    return COST_SEG.sub("", s)


def parse_ansi(s):
    """Yield (text, rgb) spans, resolving SGR color + dim to Campbell RGB."""
    color, dim = 0, False

    def rgb():
        return ANSI[color] if color in ANSI else (DIM if dim else WHITE)

    pos = 0
    for m in SGR.finditer(s):
        text = s[pos : m.start()]
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
    for i, frame in enumerate(FRAMES):
        line = render_line(*frame)
        if i == RED_FRAME:
            assert "\033[31m█" in line and "84%" in line, (
                f"frame {i} not red/84%: {line!r}"
            )
        img = Image.new("RGB", (W + 2 * MARGIN, H + 2 * MARGIN), FRAME)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [MARGIN, MARGIN, MARGIN + W - 1, MARGIN + H - 1],
            radius=RADIUS,
            fill=BG,
        )
        x = MARGIN + PAD_X
        for text, rgb in parse_ansi(strip_cost(line)):
            draw.text((x, MARGIN + y), text, font=font, fill=rgb)
            x += draw.textlength(text, font=font)
        assert x - MARGIN <= W - PAD_X, (
            f"frame {i} clipped: {x - MARGIN:.0f}px > {W - PAD_X}"
        )
        frames.append(img)
    # Lead with the red frame: static renderers (PDF export, previews) show frame 0.
    order = [RED_FRAME, *(i for i in range(len(frames)) if i != RED_FRAME)]
    frames[order[0]].save(
        OUT,
        save_all=True,
        append_images=[frames[i] for i in order[1:]],
        # disposal=1 (leave prior frame) keeps the static white border visible:
        # optimize stores only the changed region per frame, so the unchanged
        # border must persist rather than be wiped to background (disposal=2).
        duration=[DURATIONS[i] for i in order],
        loop=0,
        optimize=True,
        disposal=1,
    )
    for name, i in STILLS.items():
        frames[i].save(DOCS / name)
    print(f"wrote {OUT} ({len(frames)} frames) + {', '.join(STILLS)}")


if __name__ == "__main__":
    main()

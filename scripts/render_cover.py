#!/usr/bin/env python3
"""Render the README's looping, code-drawn cover. Requires Pillow and fonts.

Example (Windows): python scripts/render_cover.py
Other systems: pass --sans and --serif paths to a Chinese-capable sans and a serif font.
"""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, SCALE = 1200, 480, 2
FRAMES, DURATION_MS = 60, 100
BG = '#0d1820'
PAPER = '#f3f0e7'
MUTED = '#95a7a3'
GRID = '#1b3035'
TEAL = '#8fd9c5'
GOLD = '#e8b86a'


def xy(point):
    return tuple(round(v * SCALE) for v in point)


def font(path, size):
    return ImageFont.truetype(str(path), size * SCALE)


def rect(draw, box, fill, outline=None, width=1, radius=0):
    draw.rounded_rectangle(xy(box), radius=radius * SCALE, fill=fill,
                           outline=outline, width=width * SCALE)


def line(draw, points, fill, width=1):
    draw.line([xy(p) for p in points], fill=fill, width=width * SCALE, joint='curve')


def text(draw, position, value, face, color):
    draw.text(xy(position), value, font=face, fill=color)


def dot(draw, x, y, radius, color):
    draw.ellipse(xy((x-radius, y-radius, x+radius, y+radius)), fill=color)


def make_frame(t, faces):
    image = Image.new('RGB', (W * SCALE, H * SCALE), BG)
    d = ImageDraw.Draw(image)

    # Restrained scientific grid; no decorative chart claims to represent data.
    for x in range(0, W + 1, 40):
        line(d, [(x, 0), (x, H)], GRID)
    for y in range(0, H + 1, 40):
        line(d, [(0, y), (W, y)], GRID)
    rect(d, (0, 0, 510, H), BG)
    rect(d, (56, 58, 89, 61), TEAL)
    text(d, (102, 46), 'EXPERIMENTAL REPORT WRITING', faces['label'], MUTED)
    text(d, (54, 107), '让实验', faces['headline'], PAPER)
    text(d, (54, 184), '被读懂', faces['headline'], PAPER)
    line(d, [(58, 288), (440, 288)], '#35484a')
    text(d, (58, 311), '写清设计，也写清结果。', faces['body'], '#c5d1ca')
    text(d, (58, 353), 'CLEAR THINKING  /  CLEAR WRITING', faces['small'], MUTED)

    # Independent plan/result cards. Breathing accents loop continuously.
    cards = [
        {'x': 550, 'accent': TEAL, 'tag': '01  /  PLAN', 'title': '实验设计',
         'subtitle': '问题 · 比较 · 方法', 'phase': 0.0},
        {'x': 850, 'accent': GOLD, 'tag': '02  /  RESULTS', 'title': '实验结果',
         'subtitle': '观察 · 证据 · 边界', 'phase': 0.5},
    ]
    for card in cards:
        x, accent = card['x'], card['accent']
        rect(d, (x, 70, x+260, 409), '#14252b', '#3b5653', 1, 8)
        rect(d, (x+22, 94, x+51, 97), accent)
        text(d, (x+22, 116), card['tag'], faces['small_bold'], accent)
        text(d, (x+22, 157), card['title'], faces['card'], PAPER)
        text(d, (x+22, 208), card['subtitle'], faces['sub'], MUTED)
        line(d, [(x+22, 251), (x+238, 251)], '#3a5050')
        if card['tag'].endswith('PLAN'):
            # Sequential planned actions; markers pulse without changing the text.
            pulse = 0.5 + 0.5 * math.sin(2 * math.pi * t)
            for i, length in enumerate((140, 174, 115)):
                y = 280 + i * 30
                rect(d, (x+23, y, x+32, y+9), BG, accent, 1, 2)
                line(d, [(x+45, y+4), (x+45+length, y+4)], '#526969', 2)
            dot(d, x+27.5, 284.5, 1.5 + pulse, accent)
        else:
            # Static plot geometry is illustrative; the moving highlight is motion only.
            line(d, [(x+27, 355), (x+27, 277)], '#536a66')
            line(d, [(x+27, 355), (x+225, 355)], '#536a66')
            points = [(x+39, 337), (x+79, 321), (x+121, 327),
                      (x+165, 299), (x+213, 287)]
            line(d, points, accent, 2)
            for px, py in points:
                dot(d, px, py, 3, accent)
            position = (0.5 - 0.5 * math.cos(2 * math.pi * t)) * (len(points)-1)
            index = min(int(position), len(points)-2)
            fraction = position - index
            px = points[index][0] * (1-fraction) + points[index+1][0] * fraction
            py = points[index][1] * (1-fraction) + points[index+1][1] * fraction
            dot(d, px, py, 5, PAPER)
    text(d, (1066, 438), 'HUMAN  /  AI', faces['tiny'], MUTED)
    return image.resize((W, H), Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sans', default='C:/Windows/Fonts/msyh.ttc')
    parser.add_argument('--serif', default='C:/Windows/Fonts/georgia.ttf')
    parser.add_argument('--output', type=Path, default=ROOT / 'cover.gif')
    args = parser.parse_args()
    faces = {
        'headline': font(args.sans, 62), 'body': font(args.sans, 19),
        'card': font(args.sans, 30), 'sub': font(args.sans, 16),
        'label': font(args.serif, 12), 'small': font(args.serif, 11),
        'small_bold': font(args.serif, 12), 'tiny': font(args.serif, 10),
    }
    frames = [make_frame(index / FRAMES, faces) for index in range(FRAMES)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(args.output, save_all=True, append_images=frames[1:],
                   duration=DURATION_MS, loop=0, optimize=True, disposal=2)
    print(f'{args.output}: {W}x{H}, {FRAMES} frames, {DURATION_MS} ms/frame, looping')


if __name__ == '__main__':
    main()

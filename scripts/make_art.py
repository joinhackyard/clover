#!/usr/bin/env python3
"""Clover's icon, drawn from code (Pillow) so the art is Hackyard's own. Run: python3 scripts/make_art.py
The README banner and social preview are scripts/banner.html and scripts/social-preview.html."""
import math
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CLOVER, DEEP, MINT, PETAL, INK = (47, 210, 122), (14, 159, 90), (139, 245, 200), (255, 126, 182), (11, 31, 23)


def squircle(size, n=5.0):
    """macOS-style continuous-corner mask."""
    s = size * 4
    mask = Image.new('L', (s, s), 0)
    r = s / 2
    pts = []
    for i in range(720):
        t = 2 * math.pi * i / 720
        c, d = math.cos(t), math.sin(t)
        pts.append((r + r * math.copysign(abs(c) ** (2 / n), c), r + r * math.copysign(abs(d) ** (2 / n), d)))
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def gradient(size, top, bottom):
    g = Image.new('RGB', (1, 256))
    for y in range(256):
        f = y / 255
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3)))
    return g.resize((size, size))


def heart(cx, cy, angle, r, steps=180):
    """A classic heart curve whose point sits at (cx, cy) and whose lobes face outward at angle."""
    pts, a = [], math.radians(angle)
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        y = -(y + 17) / 17   # tip (y=-17) at the origin, lobes pointing "out" (+)
        y = -y
        x, y = x / 17, y
        ox, oy = y, x        # local "out" axis is +y; rotate so out = angle
        pts.append((cx + r * (ox * math.cos(a) - oy * math.sin(a)), cy + r * (ox * math.sin(a) + oy * math.cos(a))))
    return pts


def clover_mark(size, color=(255, 255, 255), face=True):
    s = size * 4
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy, r = s * 0.5, s * 0.45, s * 0.205
    d.line([(cx, cy + r * 0.2), (cx + r * 0.35, cy + r * 1.5), (cx + r * 0.85, cy + r * 2.05)], fill=color, width=int(r * 0.2), joint='curve')
    gap = r * 0.07
    for ang in (-135, -45, 45, 135):
        a = math.radians(ang)
        d.polygon(heart(cx + math.cos(a) * gap, cy + math.sin(a) * gap, ang, r), fill=color)
    if face:   # a tiny happy face on the top-left and top-right leaves' meeting point would be lost: put it centre-low
        fx, fy, e = cx, cy + r * 0.02, r * 0.075
        d.ellipse((cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5), fill=color)
        for side in (-1, 1):
            ex, ey = fx + side * r * 0.2, fy - r * 0.05
            d.ellipse((ex - e, ey - e * 1.3, ex + e, ey + e * 1.3), fill=INK)
            bx, by = fx + side * r * 0.34, fy + r * 0.12
            d.ellipse((bx - e * 1.1, by - e * 0.7, bx + e * 1.1, by + e * 0.7), fill=PETAL)
        d.arc((fx - r * 0.12, fy - r * 0.02, fx + r * 0.12, fy + r * 0.18), 20, 160, fill=INK, width=int(r * 0.045))
    return img.resize((size, size), Image.LANCZOS)


def icon(size=1024):
    pad = int(size * 0.09)   # Apple's grid: the tile sits inside the canvas with room for its shadow
    inner = size - pad * 2
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 110), (pad, pad + int(size * 0.012)), squircle(inner))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size * 0.014)))
    tile = gradient(inner, (64, 226, 140), DEEP).convert('RGBA')
    glow = Image.new('RGBA', (inner, inner), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-inner * 0.3, -inner * 0.7, inner * 1.3, inner * 0.5), fill=MINT + (70,))
    tile.alpha_composite(glow.filter(ImageFilter.GaussianBlur(inner * 0.2)))
    mark = clover_mark(int(inner * 0.86))
    soft = Image.new('RGBA', mark.size, (0, 0, 0, 0)); soft.paste((6, 70, 40, 120), (0, 0), mark)
    o = (inner - mark.size[0]) // 2
    tile.alpha_composite(soft.filter(ImageFilter.GaussianBlur(inner * 0.012)), (o, o + int(inner * 0.015)))
    tile.alpha_composite(mark, (o, o))
    canvas.paste(tile, (pad, pad), squircle(inner))
    rim = Image.new('RGBA', (inner, inner), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle((0, 0, inner - 1, inner - 1), radius=int(inner * 0.225), outline=(255, 255, 255, 60), width=max(1, size // 256))
    canvas.alpha_composite(rim, (pad, pad))
    return canvas


def main():
    os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
    big = icon(1024)
    big.save(os.path.join(ROOT, 'docs', 'icon.png'))
    big.save(os.path.join(ROOT, 'ui', 'AppIcon.icns'), sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])


if __name__ == '__main__':
    main()

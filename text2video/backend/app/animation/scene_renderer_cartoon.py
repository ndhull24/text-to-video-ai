from __future__ import annotations
import math
import random
from PIL import Image, ImageDraw, ImageFilter

from .scene_spec import SceneSpec

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def lerp_rgb(c1, c2, t: float):
    t = clamp01(t)
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )

def _gradient(w: int, h: int, top, bottom) -> Image.Image:
    img = Image.new("RGB", (w, h), top)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = lerp_rgb(top, bottom, t)
        for x in range(w):
            px[x, y] = c
    return img

def _soft_vignette(img: Image.Image, strength: float = 0.25) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    r = int(math.hypot(w, h) * 0.55)
    d.ellipse([w//2 - r, h//2 - r, w//2 + r, h//2 + r], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(80))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    out = Image.composite(img, dark, mask)  # center keeps img, corners darken
    return Image.blend(img, out, strength)

def _glow_circle(base: Image.Image, cx: int, cy: int, r: int, color, glow: int = 45, alpha: int = 120):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r - glow, cy - r - glow, cx + r + glow, cy + r + glow], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(int(0.7 * glow)))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
    out = Image.alpha_composite(base.convert("RGBA"), layer)
    return out.convert("RGB")

def _rounded_hill(base: Image.Image, y: int, color, wobble: float = 0.0):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # big rounded ground
    d.ellipse([-w//2, y - int(h*0.25), w + w//2, h + int(h*0.45)], fill=color + (255,))
    if wobble:
        # subtle highlight band
        d.ellipse([-w//2, y - int(h*0.28), w + w//2, h + int(h*0.40)], fill=(255, 255, 255, 30))
    out = Image.alpha_composite(base.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(2)))
    return out.convert("RGB")

def _cloud(base: Image.Image, x: int, y: int, s: float, alpha: int = 200):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = (255, 255, 255, alpha)
    r = int(34 * s)
    parts = [
        (x, y, r),
        (x + int(0.9*r), y - int(0.35*r), int(1.15*r)),
        (x + int(2.0*r), y, r),
        (x + int(1.0*r), y + int(0.35*r), int(1.25*r)),
    ]
    for cx, cy, rr in parts:
        d.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], fill=c)
    layer = layer.filter(ImageFilter.GaussianBlur(int(6*s)))
    out = Image.alpha_composite(base.convert("RGBA"), layer)
    return out.convert("RGB")

def _bird(base: Image.Image, x: int, y: int, size: int = 16, alpha: int = 200):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = (30, 30, 30, alpha)
    d.arc([x, y, x + size, y + size], start=200, end=340, fill=c, width=3)
    d.arc([x + size, y, x + 2*size, y + size], start=200, end=340, fill=c, width=3)
    out = Image.alpha_composite(base.convert("RGBA"), layer)
    return out.convert("RGB")

def _trees(base: Image.Image, t: float, density: int = 6):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(layer)

    rng = random.Random(1234)  # deterministic
    ground = int(h * 0.70)
    for i in range(density):
        x = int((i + 0.5) * (w / density) + math.sin(t*0.5 + i) * 6)
        trunk_h = rng.randint(60, 90)
        trunk_w = rng.randint(10, 14)
        d.rounded_rectangle([x-trunk_w//2, ground-trunk_h, x+trunk_w//2, ground], radius=6, fill=(90, 60, 40, 255))
        # canopy
        rr = rng.randint(40, 55)
        d.ellipse([x-rr, ground-trunk_h-rr, x+rr, ground-trunk_h+rr], fill=(40, 140, 70, 235))
        d.ellipse([x-rr-18, ground-trunk_h-rr+10, x+rr-18, ground-trunk_h+rr+10], fill=(30, 120, 60, 210))

    out = Image.alpha_composite(base.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(1)))
    return out.convert("RGB")

def _skyline(base: Image.Image, t: float):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    ground = int(h * 0.70)

    rng = random.Random(777)
    x = 0
    while x < w:
        bw = rng.randint(40, 90)
        bh = rng.randint(90, 230)
        # slight parallax drift
        dx = int(math.sin(t*0.2) * 4)
        d.rounded_rectangle([x+dx, ground-bh, x+bw+dx, ground], radius=8, fill=(25, 35, 60, 220))
        # windows
        wx = x + 10 + dx
        wy = ground - bh + 14
        for _ in range(rng.randint(6, 10)):
            d.rectangle([wx, wy, wx+8, wy+10], fill=(255, 230, 140, 140))
            wx += 14
            if wx > x + bw - 12 + dx:
                wx = x + 10 + dx
                wy += 18
        x += bw + rng.randint(6, 14)

    out = Image.alpha_composite(base.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(2)))
    return out.convert("RGB")

def _rain(base: Image.Image, t: float, intensity: int = 120):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    rng = random.Random(999)
    for i in range(intensity):
        x = (rng.randint(0, w) + int(t*240)) % w
        y = (rng.randint(0, h) + int(t*520)) % h
        d.line([x, y, x-10, y+22], fill=(200, 220, 255, 120), width=2)
    out = Image.alpha_composite(base.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(1)))
    return out.convert("RGB")

def _snow(base: Image.Image, t: float, intensity: int = 90):
    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    rng = random.Random(555)
    for i in range(intensity):
        x = (rng.randint(0, w) + int(t*60)) % w
        y = (rng.randint(0, h) + int(t*120)) % h
        r = rng.randint(2, 4)
        d.ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 255, 170))
    out = Image.alpha_composite(base.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(0.5)))
    return out.convert("RGB")

def render_scene_frame_cartoon(spec: SceneSpec, t: float, w: int, h: int, seconds: float) -> Image.Image:
    # normalize progress
    p = clamp01(t / max(0.001, seconds))

    # Sky palettes by theme (Pixar-ish)
    if spec.theme == "sunrise":
        top = lerp_rgb((15, 25, 55), (90, 170, 255), p)
        bottom = lerp_rgb((40, 20, 60), (255, 175, 120), p)
    elif spec.theme == "night":
        top, bottom = (10, 16, 40), (30, 40, 70)
    elif spec.theme == "rainy":
        top, bottom = (70, 90, 120), (120, 140, 170)
    elif spec.theme == "snowy":
        top, bottom = (150, 190, 235), (230, 245, 255)
    elif spec.theme == "beach":
        top, bottom = (90, 180, 255), (255, 210, 170)
    else:  # day/forest/city
        top, bottom = (85, 170, 255), (200, 235, 255)

    img = _gradient(w, h, top, bottom)
    img = _soft_vignette(img, 0.18 * spec.softness)

    horizon = int(h * 0.70)

    # Sun / Moon positions
    if spec.sun and spec.theme != "night":
        # sun rises if sunrise, else gently bob
        sun_x = int(w * 0.25)
        if spec.theme == "sunrise":
            sun_y = int(horizon - lerp(10, h * 0.36, p))
        else:
            sun_y = int(h * 0.24 + math.sin(t * 0.6) * 6)
        img = _glow_circle(img, sun_x, sun_y, int(h * 0.07), (255, 220, 140), glow=int(52 * spec.softness), alpha=120)

    if spec.moon:
        moon_x = int(w * 0.75)
        moon_y = int(h * 0.22 + math.sin(t * 0.3) * 4)
        img = _glow_circle(img, moon_x, moon_y, int(h * 0.055), (220, 230, 255), glow=int(36 * spec.softness), alpha=90)

    # Clouds with parallax drift
    if spec.clouds:
        drift1 = int((t * 24) % (w + 260)) - 260
        drift2 = int((t * 14) % (w + 300)) - 300
        img = _cloud(img, drift1 + 220, int(h * 0.18), 1.25, alpha=210 if spec.weather != "clear" else 190)
        img = _cloud(img, drift2 + 640, int(h * 0.26), 0.95, alpha=200 if spec.weather != "clear" else 170)
        if spec.weather in ("cloudy", "rain", "snow"):
            img = _cloud(img, drift1 + 940, int(h * 0.16), 1.45, alpha=220)

    # Ground layers (rounded, toy-like)
    if spec.theme in ("beach",):
        # sand
        img = _rounded_hill(img, horizon + 20, (235, 210, 155), wobble=1.0)
        # ocean band
        ocean_y = horizon - 10
        d = ImageDraw.Draw(img)
        d.rectangle([0, ocean_y, w, horizon + 20], fill=(60, 150, 220))
        # wave highlights
        wave = Image.new("RGBA", (w, h), (0,0,0,0))
        dw = ImageDraw.Draw(wave)
        for i in range(7):
            yy = ocean_y + 10 + i * 10 + int(math.sin(t*1.2 + i) * 2)
            dw.arc([int(w*0.10), yy, int(w*0.90), yy+24], start=10, end=170, fill=(255,255,255,80), width=3)
        wave = wave.filter(ImageFilter.GaussianBlur(1))
        img = Image.alpha_composite(img.convert("RGBA"), wave).convert("RGB")
    else:
        # grass/ground
        ground_color = (30, 110, 55) if spec.theme != "snowy" else (235, 245, 255)
        img = _rounded_hill(img, horizon + 30, ground_color, wobble=1.0)
        if spec.theme == "forest":
            img = _rounded_hill(img, horizon + 70, (20, 90, 45), wobble=0.0)

    # Extra elements: trees/skyline
    if spec.trees or spec.theme == "forest":
        img = _trees(img, t, density=7)
    if spec.skyline or spec.theme == "city":
        img = _skyline(img, t)

    # Birds
    if spec.birds and spec.theme not in ("rainy", "snowy"):
        bx = int(w * 0.62 + math.sin(t * 1.2) * 55)
        by = int(h * 0.22 + math.cos(t * 1.05) * 18)
        img = _bird(img, bx, by, size=16)
        img = _bird(img, bx + 40, by + 10, size=14, alpha=180)

    # Rain/Snow particles
    if spec.weather == "rain":
        img = _rain(img, t, intensity=150)
    if spec.weather == "snow":
        img = _snow(img, t, intensity=110)

    return img

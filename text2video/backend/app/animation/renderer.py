from __future__ import annotations

import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .plan import AnimationPlan, TextLayer, ShapeLayer


# -----------------------------
# Helpers
# -----------------------------
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


def ease_in_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def ease_out_back(t: float) -> float:
    # A subtle overshoot (nice for title/underline)
    t = clamp01(t)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease(t: float, kind: str) -> float:
    if kind == "in_out_cubic":
        return ease_in_out_cubic(t)
    return clamp01(t)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    # Prefer a clean sans. DejaVuSans is common on many installs.
    for name in ["DejaVuSans.ttf", "Arial.ttf", "Calibri.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    # Robust measurement
    bbox = draw.textbbox((0, 0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])


# -----------------------------
# Background (Gradient + Vignette)
# -----------------------------
def _make_gradient_bg(w: int, h: int, top_rgb, bottom_rgb) -> Image.Image:
    # Vertical gradient
    img = Image.new("RGB", (w, h), top_rgb)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = lerp_rgb(top_rgb, bottom_rgb, t)
        for x in range(w):
            px[x, y] = c
    return img


def _apply_vignette(img: Image.Image, strength: float = 0.65) -> Image.Image:
    # Darken corners subtly
    w, h = img.size
    vignette = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(vignette)

    # radial ellipse gradient via multiple rings (fast enough)
    max_r = int(math.hypot(w, h) * 0.55)
    steps = 40
    for i in range(steps):
        t = i / (steps - 1)
        alpha = int(255 * (t ** 2) * strength)
        r = int(lerp(max_r, 0, t))
        bbox = [w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r]
        d.ellipse(bbox, outline=alpha, width=max(1, int(max_r / steps)))

    vignette = vignette.filter(ImageFilter.GaussianBlur(40))
    # Composite: dark overlay using vignette as mask
    overlay = Image.new("RGB", (w, h), (0, 0, 0))
    out = Image.composite(overlay, img, vignette)  # where vignette=255 -> overlay
    # Mix with original to keep subtle
    return Image.blend(img, out, 0.35)


# -----------------------------
# Drawing primitives
# -----------------------------
def _draw_shadow_text(
    base: Image.Image,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill_rgb,
    shadow_rgb=(0, 0, 0),
    shadow_offset=(2, 2),
    shadow_blur=6,
    shadow_alpha=140,
):
    # Draw shadow on separate layer, blur, then composite
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    sx, sy = shadow_offset
    d.text((x + sx, y + sy), text, font=font, fill=shadow_rgb + (shadow_alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(shadow_blur))

    base_rgba = base.convert("RGBA")
    base_rgba = Image.alpha_composite(base_rgba, layer)

    d2 = ImageDraw.Draw(base_rgba)
    d2.text((x, y), text, font=font, fill=fill_rgb + (255,))
    return base_rgba.convert("RGB")


def _draw_glow_shape(
    base: Image.Image,
    kind: str,
    x: int,
    y: int,
    w: int,
    h: int,
    color_rgb,
    radius: int = 16,
    glow: int = 18,
    glow_alpha: int = 90,
):
    if w <= 0 or h <= 0:
        return base

    # Glow layer
    glow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow_layer)
    bbox = [x, y, x + w, y + h]

    if kind == "circle":
        dg.ellipse(bbox, fill=color_rgb + (glow_alpha,))
    else:
        dg.rounded_rectangle(bbox, radius=radius, fill=color_rgb + (glow_alpha,))

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(glow))

    # Shape layer
    shape_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(shape_layer)
    if kind == "circle":
        ds.ellipse(bbox, fill=color_rgb + (255,))
    else:
        ds.rounded_rectangle(bbox, radius=radius, fill=color_rgb + (255,))

    out = base.convert("RGBA")
    out = Image.alpha_composite(out, glow_layer)
    out = Image.alpha_composite(out, shape_layer)
    return out.convert("RGB")


def _alpha_tint(rgb, alpha: int):
    a = clamp01(alpha / 255.0)
    return (int(rgb[0] * a), int(rgb[1] * a), int(rgb[2] * a))


# -----------------------------
# Text layers
# -----------------------------
def _draw_text_layer(
    img: Image.Image,
    layer: TextLayer,
    t: float,
    auto_center_x: bool = False,
    max_width: int | None = None,
):
    draw = ImageDraw.Draw(img)
    font = _load_font(layer.font_size)

    local = (t - layer.start) / max(layer.duration, 1e-6)
    p = clamp01(local)
    if p <= 0:
        return img

    text = layer.text
    x, y = layer.x, layer.y

    if auto_center_x:
        tw, th = _text_size(draw, text, font)
        if max_width is not None and tw > max_width:
            # If too wide, shrink a bit (simple but effective)
            scale = max_width / max(1, tw)
            font = _load_font(max(14, int(layer.font_size * scale)))
            tw, th = _text_size(draw, text, font)
        x = (img.size[0] - tw) // 2

    if layer.appear == "slide_left":
        x = int(x - (1 - ease_in_out_cubic(p)) * 60)
        alpha = int(255 * p)
        color = _alpha_tint(layer.color, alpha)
        return _draw_shadow_text(img, x, y, text, font, color)

    if layer.appear == "fade":
        alpha = int(255 * p)
        color = _alpha_tint(layer.color, alpha)
        return _draw_shadow_text(img, x, y, text, font, color)

    if layer.appear == "typewriter":
        n = max(1, int(len(text) * p))
        return _draw_shadow_text(img, x, y, text[:n], font, layer.color)

    return _draw_shadow_text(img, x, y, text, font, layer.color)


# -----------------------------
# Main
# -----------------------------
def render_frame(plan: AnimationPlan, t: float) -> Image.Image:
    w, h = plan.width, plan.height

    # Premium background: gradient + vignette
    # If plan.background is set, treat it as top color and create a darker bottom.
    top = plan.background
    bottom = (max(0, top[0] - 20), max(0, top[1] - 25), max(0, top[2] - 30))
    img = _make_gradient_bg(w, h, top, bottom)
    img = _apply_vignette(img, strength=0.7)

    # Safe margins
    margin_x = int(w * 0.08)
    max_text_width = w - 2 * margin_x

    # Shapes (with glow + nicer motion)
    for s in plan.shapes:
        local = (t - s.start) / max(s.duration, 1e-6)
        p = ease(local, s.ease)

        # add gentle drift for life
        drift = int(6 * math.sin((t + s.x * 0.001) * 1.6))

        if s.anim == "fade":
            # fade in: scale alpha by p
            # We'll simulate by tinting toward black via alpha_tint in glow strength
            ww, hh = s.w, s.h
            xx, yy = s.x, s.y + drift
            # glow strength increases with p
            img = _draw_glow_shape(
                img, s.kind, xx, yy, ww, hh, s.color,
                radius=18, glow=20, glow_alpha=int(90 * clamp01(p))
            )

        elif s.anim == "grow_w":
            ww = int(s.w * ease_out_back(p))
            xx, yy = s.x, s.y + drift
            img = _draw_glow_shape(img, s.kind, xx, yy, ww, s.h, s.color, radius=18)

        elif s.anim == "grow_h":
            hh = int(s.h * ease_out_back(p))
            xx, yy = s.x, s.y + drift
            img = _draw_glow_shape(img, s.kind, xx, yy, s.w, hh, s.color, radius=18)

        elif s.anim == "slide_up":
            yy = int(s.y + (1 - ease_in_out_cubic(p)) * 60) + drift
            img = _draw_glow_shape(img, s.kind, s.x, yy, s.w, s.h, s.color, radius=18)

        else:
            img = _draw_glow_shape(img, s.kind, s.x, s.y + drift, s.w, s.h, s.color, radius=18)

    # Title (auto-center)
    if plan.title:
        img = _draw_text_layer(
            img,
            plan.title,
            t,
            auto_center_x=True,
            max_width=max_text_width,
        )

        # Animated underline accent (premium touch)
        # underline timing tracks title appear
        lt = plan.title
        local = (t - lt.start) / max(lt.duration, 1e-6)
        p = clamp01(local)
        if p > 0:
            draw = ImageDraw.Draw(img)
            font = _load_font(lt.font_size)
            tw, th = _text_size(draw, lt.text, font)
            x0 = (w - tw) // 2
            y0 = lt.y + th + 16
            underline_w = int(tw * ease_out_back(p))
            underline_h = 10
            underline_color = (90, 170, 255)

            img = _draw_glow_shape(
                img,
                "rect",
                x0,
                y0,
                underline_w,
                underline_h,
                underline_color,
                radius=12,
                glow=14,
                glow_alpha=110,
            )

    # Subtitles (left aligned within safe margin)
    for layer in plan.subtitles:
        # clamp x to margin for consistency
        layer_x = max(margin_x, layer.x)
        tmp = TextLayer(
            text=layer.text,
            font_size=layer.font_size,
            x=layer_x,
            y=layer.y,
            color=layer.color,
            appear=layer.appear,
            start=layer.start,
            duration=layer.duration,
        )
        img = _draw_text_layer(img, tmp, t, auto_center_x=False, max_width=max_text_width)

    return img

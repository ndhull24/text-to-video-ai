from __future__ import annotations

import textwrap
from .plan import AnimationPlan, TextLayer, ShapeLayer


def text_to_plan(prompt: str) -> AnimationPlan:
    prompt = (prompt or "").strip()
    if not prompt:
        prompt = "Untitled animation"

    first_line = prompt.splitlines()[0].strip()
    title_text = first_line[:70]

    rest = prompt[len(first_line) :].strip()
    if not rest:
        rest = "Turning text into motion graphics…"

    wrapped = textwrap.wrap(rest, width=46)[:3]

    # Palette tuned for the upgraded renderer
    bg = (12, 12, 20)
    title_color = (245, 248, 255)
    subtitle_color = (220, 228, 245)
    accent = (90, 170, 255)

    # Title centered by renderer, x is a fallback
    title = TextLayer(
        text=title_text,
        font_size=74,
        x=120,
        y=160,
        color=title_color,
        appear="slide_left",
        start=0.18,
        duration=1.05,
    )

    subtitles = []
    start_t = 1.25
    for i, line in enumerate(wrapped):
        subtitles.append(
            TextLayer(
                text=line,
                font_size=40,
                x=120,
                y=320 + i * 58,
                color=subtitle_color,
                appear="typewriter" if i == 0 else "fade",
                start=start_t + i * 0.42,
                duration=1.25,
            )
        )

    shapes = [
        # Accent pill near top-right (nice design anchor)
        ShapeLayer(kind="circle", x=1030, y=90, w=110, h=110, color=accent, anim="fade", start=0.25, duration=1.1),
        # Long underline bar (renderer also adds underline; this adds depth)
        ShapeLayer(kind="rect", x=140, y=520, w=1000, h=18, color=accent, anim="grow_w", start=0.75, duration=1.35),
        # Secondary subtle bar
        ShapeLayer(kind="rect", x=140, y=560, w=720, h=12, color=(70, 120, 200), anim="grow_w", start=1.05, duration=1.25),
    ]

    seconds = max(5.0, 2.0 + len(wrapped) * 1.2)

    return AnimationPlan(
        width=1280,
        height=720,
        fps=30,
        seconds=seconds,
        background=bg,
        title=title,
        subtitles=subtitles,
        shapes=shapes,
    )

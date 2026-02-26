from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

Ease = Literal["linear", "in_out_cubic"]

@dataclass
class TextLayer:
    text: str
    font_size: int = 72
    x: int = 120
    y: int = 180
    color: Tuple[int, int, int] = (255, 255, 255)
    appear: Literal["fade", "slide_left", "typewriter"] = "fade"
    start: float = 0.0
    duration: float = 1.0

@dataclass
class ShapeLayer:
    kind: Literal["rect", "circle"] = "rect"
    x: int = 100
    y: int = 500
    w: int = 400
    h: int = 40
    color: Tuple[int, int, int] = (80, 170, 255)
    start: float = 0.3
    duration: float = 1.2
    anim: Literal["grow_w", "grow_h", "slide_up", "fade"] = "grow_w"
    ease: Ease = "in_out_cubic"

@dataclass
class AnimationPlan:
    width: int = 1280
    height: int = 720
    fps: int = 30
    seconds: float = 5.0
    background: Tuple[int, int, int] = (10, 10, 18)
    title: Optional[TextLayer] = None
    subtitles: List[TextLayer] = None
    shapes: List[ShapeLayer] = None

    def __post_init__(self):
        self.subtitles = self.subtitles or []
        self.shapes = self.shapes or []
        if self.seconds <= 0:
            raise ValueError("seconds must be > 0")
        if self.fps <= 0:
            raise ValueError("fps must be > 0")

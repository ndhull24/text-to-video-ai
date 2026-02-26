from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Theme = Literal[
    "sunrise",
    "day",
    "night",
    "rainy",
    "snowy",
    "beach",
    "forest",
    "city",
]

Weather = Literal["clear", "cloudy", "rain", "snow"]

@dataclass
class SceneSpec:
    theme: Theme = "day"
    weather: Weather = "clear"
    clouds: bool = True
    birds: bool = False
    sun: bool = True
    moon: bool = False
    trees: bool = False
    skyline: bool = False
    ocean: bool = False

    # style knobs
    saturation: float = 1.0
    softness: float = 1.0  # blur/glow intensity

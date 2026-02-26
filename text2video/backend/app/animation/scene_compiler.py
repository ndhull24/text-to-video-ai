from __future__ import annotations
import re
from .scene_spec import SceneSpec

def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)

def text_to_scene_spec(text: str) -> SceneSpec:
    t = (text or "").lower().strip()
    spec = SceneSpec()

    # --- Theme detection (priority order) ---
    if _has_any(t, ["snow", "blizzard", "snowing", "snowfall", "frost"]):
        spec.theme = "snowy"
        spec.weather = "snow"
        spec.clouds = True
        spec.sun = False
    elif _has_any(t, ["rain", "raining", "storm", "thunder", "drizzle", "shower"]):
        spec.theme = "rainy"
        spec.weather = "rain"
        spec.clouds = True
        spec.sun = False
    elif _has_any(t, ["sunrise", "sun rising", "dawn", "morning"]):
        spec.theme = "sunrise"
        spec.weather = "clear"
        spec.sun = True
        spec.clouds = True
        spec.birds = True
    elif _has_any(t, ["night", "midnight", "moon", "stars"]):
        spec.theme = "night"
        spec.weather = "clear"
        spec.sun = False
        spec.moon = True
        spec.clouds = False if "clear" in t else True
    elif _has_any(t, ["beach", "ocean", "sea", "waves", "shore"]):
        spec.theme = "beach"
        spec.ocean = True
        spec.sun = True
        spec.clouds = True
        spec.birds = True
    elif _has_any(t, ["forest", "woods", "trees", "jungle", "nature"]):
        spec.theme = "forest"
        spec.trees = True
        spec.sun = True
        spec.clouds = True
        spec.birds = True
    elif _has_any(t, ["city", "downtown", "skyscraper", "buildings", "street"]):
        spec.theme = "city"
        spec.skyline = True
        spec.sun = True
        spec.clouds = True
    else:
        spec.theme = "day"
        spec.sun = True
        spec.clouds = True

    # --- Weather modifiers ---
    if _has_any(t, ["cloudy", "overcast", "gray sky"]):
        spec.weather = "cloudy"
        spec.clouds = True
        spec.sun = False if spec.theme in ("day", "sunrise") else spec.sun

    if _has_any(t, ["clear", "good weather", "sunny", "bright"]):
        if spec.weather in ("cloudy",):
            spec.weather = "clear"
        spec.clouds = False if "no clouds" in t else spec.clouds
        spec.sun = True if spec.theme != "night" else spec.sun

    # explicit toggles
    if "no clouds" in t:
        spec.clouds = False
    if "birds" in t:
        spec.birds = True

    # style adjectives
    if _has_any(t, ["cute", "pixar", "cartoon", "whimsical"]):
        spec.saturation = 1.15
        spec.softness = 1.15

    return spec

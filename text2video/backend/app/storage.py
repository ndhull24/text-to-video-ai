import os
from pathlib import Path
from .config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../text2video

def assets_root() -> Path:
    p = Path(settings.assets_dir)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

def ensure_assets_dir():
    assets_root().mkdir(parents=True, exist_ok=True)

def shot_asset_path(project_id: int, scene_idx: int, shot_idx: int) -> str:
    ensure_assets_dir()
    p = Path(settings.assets_dir) / f"project_{project_id}" / f"scene_{scene_idx}"
    p.mkdir(parents=True, exist_ok=True)
    return str(p / f"shot_{shot_idx}.txt")  # MVP: placeholder artifact

def shot_video_path(project_id: int, scene_idx: int, shot_idx: int) -> str:
    ensure_assets_dir()
    p = assets_root() / f"project_{project_id}" / f"scene_{scene_idx}"
    p.mkdir(parents=True, exist_ok=True)
    return str(p / f"shot_{shot_idx}.mp4")

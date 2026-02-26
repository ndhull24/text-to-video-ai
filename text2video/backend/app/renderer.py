from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
import re
import subprocess

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Scene, Shot


@dataclass
class RenderResult:
    output_path: str


def _project_dir(project_id: int) -> Path:
    out = Path(settings.assets_dir) / f"project_{project_id}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _concat_videos_ffmpeg(mp4_paths: List[str], out_mp4: str) -> None:
    out_mp4_path = Path(out_mp4)
    out_mp4_path.parent.mkdir(parents=True, exist_ok=True)

    list_file = out_mp4_path.with_suffix(".concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in mp4_paths:
            safe = str(Path(p).resolve()).replace("\\", "/")
            f.write(f"file '{safe}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_mp4_path)]
    _run(cmd)


def _mux_audio_ffmpeg(video_mp4: str, audio_wav: str, out_mp4: str) -> None:
    out_path = Path(out_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_mp4,
        "-i", audio_wav,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(out_path),
    ]
    _run(cmd)


_scene_re = re.compile(r"scene_(\d+)", re.IGNORECASE)
_shot_re = re.compile(r"shot_(\d+)", re.IGNORECASE)


def _sort_key_from_path(p: Path) -> Tuple[int, int, str]:
    s = 10**9
    sh = 10**9
    m1 = _scene_re.search(str(p))
    if m1:
        s = int(m1.group(1))
    m2 = _shot_re.search(p.name)
    if m2:
        sh = int(m2.group(1))
    return (s, sh, p.name)


def render_project(project_id: int, db: Session) -> RenderResult:
    out_dir = _project_dir(project_id)

    # 1) Normal path: use DB asset_path if present and files exist
    shots = db.execute(
        select(Shot)
        .join(Scene, Shot.scene_id == Scene.id)
        .where(Scene.project_id == project_id)
        .order_by(Scene.idx.asc(), Shot.idx.asc())
    ).scalars().all()

    mp4_paths: List[str] = []
    for sh in shots:
        if not sh.asset_path:
            continue
        p = Path(sh.asset_path)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.exists() and p.suffix.lower() == ".mp4":
            mp4_paths.append(str(p))

    # 2) Fallback: scan filesystem for shot mp4s and prefer non-base over base
    if not mp4_paths:
        # Prefer shot_X.mp4 over shot_X_base.mp4 if both exist.
        shots_map = {}  # (scene_idx, shot_idx) -> Path

        for p in out_dir.rglob("*.mp4"):
            name = p.name.lower()
            if name.startswith("final_render"):
                continue
            if "shot_" not in name:
                continue

            key = _sort_key_from_path(p)  # (scene, shot, filename)
            scene_i, shot_i, _ = key

            # Skip weird files
            if scene_i == 10**9 or shot_i == 10**9:
                continue

            existing = shots_map.get((scene_i, shot_i))
            if existing is None:
                shots_map[(scene_i, shot_i)] = p
            else:
                # If we already have base, replace with non-base
                if existing.name.lower().endswith("_base.mp4") and not name.endswith("_base.mp4"):
                    shots_map[(scene_i, shot_i)] = p

        ordered_keys = sorted(shots_map.keys())
        mp4_paths = [str(shots_map[k].resolve()) for k in ordered_keys]

    if not mp4_paths:
        raise ValueError("No MP4 shots found on disk to render")

    final_mp4 = out_dir / "final_render.mp4"
    _concat_videos_ffmpeg(mp4_paths, str(final_mp4))

    narration = out_dir / "narration.wav"
    if narration.exists():
        final_with_audio = out_dir / "final_render_with_audio.mp4"
        _mux_audio_ffmpeg(str(final_mp4), str(narration), str(final_with_audio))
        return RenderResult(output_path=str(final_with_audio))

    return RenderResult(output_path=str(final_mp4))

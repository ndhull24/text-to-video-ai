from __future__ import annotations
import subprocess
from pathlib import Path
from PIL import Image

from .scene_spec import SceneSpec
from .scene_renderer_cartoon import render_scene_frame_cartoon

def render_scene_to_mp4(
    spec: SceneSpec,
    out_mp4: str,
    seconds: float = 6.0,
    fps: int = 30,
    w: int = 1280,
    h: int = 720,
) -> str:
    out_path = Path(out_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = out_path.parent / f".frames_{out_path.stem}"
    if tmp_dir.exists():
        for p in tmp_dir.glob("*.png"):
            p.unlink()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    total_frames = int(seconds * fps)
    for i in range(total_frames):
        t = i / fps
        img: Image.Image = render_scene_frame_cartoon(spec, t, w, h, seconds=seconds)
        img.save(tmp_dir / f"frame_{i:06d}.png", "PNG")

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(tmp_dir / "frame_%06d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    for p in tmp_dir.glob("*.png"):
        p.unlink()
    tmp_dir.rmdir()

    return str(out_path)

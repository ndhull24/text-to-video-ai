from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Callable
from PIL import Image
from .plan import AnimationPlan
from .renderer import render_frame

def render_to_mp4(plan: AnimationPlan, out_mp4: str) -> str:
    out_path = Path(out_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = out_path.parent / f".frames_{out_path.stem}"
    if tmp_dir.exists():
        for p in tmp_dir.glob("*.png"):
            p.unlink()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    total_frames = int(plan.seconds * plan.fps)

    for i in range(total_frames):
        t = i / plan.fps
        img: Image.Image = render_frame(plan, t)
        img.save(tmp_dir / f"frame_{i:06d}.png", "PNG")

    # Encode via ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(plan.fps),
        "-i", str(tmp_dir / "frame_%06d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    # Cleanup frames
    for p in tmp_dir.glob("*.png"):
        p.unlink()
    tmp_dir.rmdir()

    return str(out_path)

from pathlib import Path
import subprocess
from sqlalchemy.orm import Session
from .models import Project, Render, ShotStatus
from .config import settings
from .storage import assets_root  # <-- FIXED: was text2video.backend.app.storage

def render_project(project_id: int, db: Session) -> Render:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")

    ordered_assets = []
    for scene in sorted(project.scenes, key=lambda s: s.idx):
        for sh in sorted(scene.shots, key=lambda x: x.idx):
            if sh.status == ShotStatus.SUCCEEDED and sh.asset_path and sh.asset_path.lower().endswith(".mp4"):
                ordered_assets.append(sh.asset_path)

    if not ordered_assets:
        raise ValueError("No successful MP4 shots to render")

    out_dir = Path(settings.assets_dir) / f"project_{project_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    list_file = out_dir / "concat_list.txt"
    out_mp4 = out_dir / "final_render.mp4"

    # IMPORTANT: absolute paths + forward slashes avoid Windows quoting issues
    with open(list_file, "w", encoding="utf-8") as f:
        for asset in ordered_assets:
            p = Path(asset).resolve()
            f.write(f"file '{p.as_posix()}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_mp4),
    ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)

    # If narration exists, mux it into a final mp4 with audio
    narration_wav = out_dir / "narration.wav"
    if narration_wav.exists():
        out_with_audio = out_dir / "final_render_with_audio.mp4"
        cmd2 = [
            "ffmpeg",
            "-y",
            "-i", str(out_mp4),
            "-i", str(narration_wav),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(out_with_audio),
        ]
        subprocess.run(cmd2, check=True, capture_output=True, text=True)
        out_mp4 = out_with_audio

    render = Render(project_id=project_id, output_path=str(out_mp4))
    db.add(render)
    db.commit()
    db.refresh(render)
    return render

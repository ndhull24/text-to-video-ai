from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/projects/{project_id}/video")
def project_video(project_id: int):
    assets_dir = Path(settings.assets_dir)
    project_dir = assets_dir / f"project_{project_id}"

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project dir not found: {project_dir}")

    # Prefer audio version
    mp4_audio = project_dir / "final_render_with_audio.mp4"
    mp4_plain = project_dir / "final_render.mp4"

    if mp4_audio.exists():
        p = mp4_audio
    elif mp4_plain.exists():
        p = mp4_plain
    else:
        raise HTTPException(status_code=404, detail=f"No render found in: {project_dir}")

    return FileResponse(str(p), media_type="video/mp4", filename=p.name)

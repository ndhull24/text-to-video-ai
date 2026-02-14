from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix="/studio", tags=["studio"])


class Voice(BaseModel):
    id: str
    label: str


class NarrateRequest(BaseModel):
    project_id: int
    text: str
    voice_id: str


def _project_dir(project_id: int) -> Path:
    return Path(settings.assets_dir) / f"project_{project_id}"


def _best_video_path(project_id: int) -> Path:
    out_dir = _project_dir(project_id)
    mp4_audio = out_dir / "final_render_with_audio.mp4"
    mp4 = out_dir / "final_render.mp4"

    if mp4_audio.exists():
        return mp4_audio
    if mp4.exists():
        return mp4

    raise FileNotFoundError("No render found")


@router.get("/voices", response_model=List[Voice])
def list_voices():
    """
    Return available voices for the dropdown.
    Replace this list with your real voice inventory later.
    """
    return [
        Voice(id="default", label="Default"),
        Voice(id="female_1", label="Female 1"),
        Voice(id="male_1", label="Male 1"),
    ]


@router.post("/narrate")
def narrate(req: NarrateRequest):
    """
    Creates narration.wav under backend/_assets/project_{id}/narration.wav.
    TODO: Wire to your existing TTS function.
    """
    out_dir = _project_dir(req.project_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # TODO: Replace this with your real narration generator that writes narration.wav
    # Example:
    # generate_narration_wav(text=req.text, voice_id=req.voice_id, out_path=out_dir / "narration.wav")

    raise HTTPException(
        status_code=501,
        detail="Narration generation not wired yet. Connect your TTS function here.",
    )


@router.get("/video/{project_id}")
def get_video(project_id: int):
    try:
        p = _best_video_path(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No render found")

    return FileResponse(str(p), media_type="video/mp4", filename=p.name)


@router.get("/narration/{project_id}")
def get_narration(project_id: int):
    p = _project_dir(project_id) / "narration.wav"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No narration.wav found")
    return FileResponse(str(p), media_type="audio/wav", filename=p.name)

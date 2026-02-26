from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pyttsx3
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Project

router = APIRouter(prefix="/studio", tags=["studio"])


class Voice(BaseModel):
    id: str
    label: str


class NarrateRequest(BaseModel):
    project_id: int
    text: str
    voice_id: Optional[str] = None
    rate: int = 175


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


def _tts_engine() -> pyttsx3.Engine:
    # pyttsx3 selects an OS engine (SAPI5 on Windows, NSSS on macOS, eSpeak on Linux)
    return pyttsx3.init()


@router.get("/voices", response_model=List[Voice])
def list_voices():
    """Return available local TTS voices (pyttsx3)."""
    try:
        engine = _tts_engine()
        voices = engine.getProperty("voices") or []
        out: List[Voice] = []
        for v in voices:
            vid = getattr(v, "id", "") or ""
            name = getattr(v, "name", "") or vid
            if not vid:
                continue
            out.append(Voice(id=vid, label=name))
        if not out:
            out = [Voice(id="default", label="Default")]
        return out
    except Exception:
        return [Voice(id="default", label="Default")]


@router.post("/narrate")
def narrate(req: NarrateRequest, db: Session = Depends(get_db)):
    """Generate narration.wav for a project."""
    project = db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    out_dir = _project_dir(req.project_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = out_dir / "narration.wav"

    try:
        engine = _tts_engine()
        engine.setProperty("rate", int(req.rate or 175))

        if req.voice_id and req.voice_id != "default":
            try:
                engine.setProperty("voice", req.voice_id)
            except Exception:
                pass

        engine.save_to_file(text, str(out_wav))
        engine.runAndWait()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")

    return {"ok": True, "path": str(out_wav), "chars": len(text)}


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

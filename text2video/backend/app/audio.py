from pathlib import Path
import pyttsx3
from sqlalchemy.orm import Session
from .models import Project
from .config import settings

def build_narration_text(project: Project) -> str:
    scenes = sorted(project.scenes, key=lambda s: s.idx)
    parts = []
    for sc in scenes:
        parts.append(f"Scene {sc.idx}. {sc.summary}")
    return "\n\n".join(parts).strip()

def synthesize_narration(project_id: int, db: Session, voice_contains: str | None = None, rate: int = 175):
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")
    if not project.scenes:
        raise ValueError("No scenes found. Run /plan first.")

    text = build_narration_text(project)
    if not text:
        raise ValueError("Narration text is empty.")

    out_dir = Path(settings.assets_dir) / f"project_{project_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = out_dir / "narration.wav"

    engine = pyttsx3.init()
    engine.setProperty("rate", int(rate))

    if voice_contains:
        key = voice_contains.lower()
        for v in engine.getProperty("voices"):
            name = (getattr(v, "name", "") or "").lower()
            vid = (getattr(v, "id", "") or "").lower()
            if key in name or key in vid:
                engine.setProperty("voice", v.id)
                break

    engine.save_to_file(text, str(out_wav))
    engine.runAndWait()

    return {"path": str(out_wav), "chars": len(text)}

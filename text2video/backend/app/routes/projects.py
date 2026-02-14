from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Project, Chapter, Scene, Shot
from ..schemas import ProjectCreate, ProjectOut, ChapterUpload, PlanRequest, SceneOut
from ..planner import simple_plan
from ..tasks import celery_app
from ..audio import synthesize_narration
from pathlib import Path
from fastapi.responses import FileResponse
from ..config import settings

# ✅ ADD
import json
from ..animations import default_animation_plan

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    p = Project(title=payload.title)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.post("/{project_id}/chapter")
def upload_chapter(project_id: int, payload: ChapterUpload, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    if p.chapter:
        p.chapter.raw_text = payload.text
    else:
        db.add(Chapter(project_id=project_id, raw_text=payload.text))
    db.commit()
    return {"ok": True}

@router.post("/{project_id}/plan")
def plan_project(project_id: int, req: PlanRequest, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if not p.chapter:
        raise HTTPException(400, "Upload chapter first")

    # wipe previous plan for MVP
    for sc in list(p.scenes):
        db.delete(sc)
    db.commit()

    scenes_spec = simple_plan(p.chapter.raw_text, req.target_minutes, req.max_scenes)

    for sc in scenes_spec:
        scene = Scene(project_id=project_id, idx=sc["idx"], title=sc["title"], summary=sc["summary"])
        db.add(scene)
        db.flush()
        for sh in sc["shots"]:
            dur = int(sh["duration_s"])
            plan = default_animation_plan(sh.get("prompt", ""), dur)

            shot = Shot(
                scene_id=scene.id,
                idx=sh["idx"],
                duration_s=dur,
                shot_type=sh["shot_type"],
                prompt=sh["prompt"],
                negative_prompt=sh["negative_prompt"],
                animation_json=json.dumps(plan),  # ✅ ADD THIS
            )
            db.add(shot)

    db.commit()
    return {"ok": True, "scenes": len(scenes_spec)}

@router.get("/{project_id}/video")
def get_project_video(project_id: int):
    out_dir = Path(settings.assets_dir) / f"project_{project_id}"

    mp4_audio = out_dir / "final_render_with_audio.mp4"
    mp4_plain = out_dir / "final_render.mp4"

    if mp4_audio.exists():
        p = mp4_audio
    elif mp4_plain.exists():
        p = mp4_plain
    else:
        raise HTTPException(status_code=404, detail=f"No render found in {out_dir}")

    return FileResponse(str(p), media_type="video/mp4", filename=p.name)


@router.get("/{project_id}/scenes", response_model=list[SceneOut])
def get_scenes(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p.scenes

@router.post("/{project_id}/generate")
def generate_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if not p.scenes:
        raise HTTPException(400, "Run /plan first")

    shot_ids = []
    for sc in p.scenes:
        for sh in sc.shots:
            shot_ids.append(sh.id)

    for sid in shot_ids:
        celery_app.send_task("generate_shot", args=[sid])

    return {"ok": True, "enqueued_shots": len(shot_ids)}

from ..renderer import render_project

@router.post("/{project_id}/render")
def render_endpoint(project_id: int, db: Session = Depends(get_db)):
    try:
        render = render_project(project_id, db)
        return {"ok": True, "output_path": render.output_path}
    except ValueError as e:
        raise HTTPException(400, str(e))

from sqlalchemy import select
from ..models import Project, Scene, Shot

@router.get("/{project_id}/status")
def project_status(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    # Query shots directly (more reliable than relationship loading on SQLite)
    shots = db.execute(
        select(Shot).join(Scene, Shot.scene_id == Scene.id).where(Scene.project_id == project_id)
    ).scalars().all()

    by_status = {"PENDING": 0, "RUNNING": 0, "SUCCEEDED": 0, "FAILED": 0}
    for sh in shots:
        key = sh.status.value if hasattr(sh.status, "value") else str(sh.status)
        key = key.upper()
        if key not in by_status:
            by_status[key] = 0
        by_status[key] += 1

    total = len(shots)
    scenes_count = db.execute(select(Scene).where(Scene.project_id == project_id)).scalars().all()

    return {
        "project_id": project_id,
        "scenes": len(scenes_count),
        "shots_total": total,
        "shots_by_status": by_status,
        "done_pct": (by_status.get("SUCCEEDED", 0) / total * 100) if total else 0.0,
    }

@router.post("/{project_id}/audio")
def create_audio(project_id: int, voice: str | None = None, rate: int = 175, db: Session = Depends(get_db)):
    try:
        result = synthesize_narration(project_id, db, voice_contains=voice, rate=rate)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(400, str(e))

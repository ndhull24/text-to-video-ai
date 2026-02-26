from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..animations import default_animation_plan
from ..audio import synthesize_narration
from ..config import settings
from ..db import get_db
from ..models import Chapter, Project, Scene, Shot
from ..planner import simple_plan
from ..renderer import render_project
from ..schemas import ChapterUpload, PlanRequest, ProjectCreate, ProjectOut, SceneOut
from ..tasks import celery_app, generate_shot

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

    # clear existing plan
    for sc in list(p.scenes):
        db.delete(sc)
    db.commit()

    scenes_spec = simple_plan(p.chapter.raw_text, req.target_minutes, req.max_scenes, req.style)
    if not scenes_spec:
        raise HTTPException(400, "Planner produced 0 scenes (chapter may be empty)")

    for sc in scenes_spec:
        scene = Scene(project_id=project_id, idx=sc["idx"], title=sc["title"], summary=sc["summary"])
        db.add(scene)
        db.flush()

        for sh in sc["shots"]:
            dur = max(1, int(sh.get("duration_s", 6)))

            # ✅ Ensure we store animation plan JSON on the shot
            plan = default_animation_plan(sh.get("prompt", ""), dur)
            # Embed the NLP concept text so FFMPEG draws it, not the visual prompt
            plan["caption"] = sc.get("summary", "")

            shot = Shot(
                scene_id=scene.id,
                idx=int(sh["idx"]),
                duration_s=dur,
                shot_type=sh.get("shot_type", "STANDARD"),
                prompt=sh.get("prompt", ""),
                negative_prompt=sh.get("negative_prompt", ""),
                animation_json=json.dumps(plan),
            )
            db.add(shot)

    db.commit()
    return {"ok": True, "scenes": len(scenes_spec)}


@router.get("/{project_id}/scenes", response_model=list[SceneOut])
def get_scenes(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p.scenes


@router.post("/{project_id}/generate")
def generate_project(project_id: int, db: Session = Depends(get_db)):
    """Enqueue all shots for generation.

    Dev-friendly behavior:
    - If a Celery worker is alive, enqueue.
    - If no worker responds, run inline (so UI never gets stuck at 0%).
    """
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if not p.scenes:
        raise HTTPException(400, "Run /plan first")

    shots = db.execute(
        select(Shot).join(Scene, Shot.scene_id == Scene.id).where(Scene.project_id == project_id)
    ).scalars().all()

    if not shots:
        raise HTTPException(400, "No shots found. Run /plan first")

    # ✅ Detect if a worker is actually alive
    worker_alive = False
    try:
        replies = celery_app.control.ping(timeout=1.0)
        worker_alive = bool(replies)
    except Exception:
        worker_alive = False

    enqueued = 0
    ran_inline = 0

    for sh in shots:
        if worker_alive:
            try:
                celery_app.send_task("generate_shot", args=[sh.id])
                enqueued += 1
                continue
            except Exception:
                # if enqueue fails mid-way, fall back inline
                pass

        generate_shot(sh.id)
        ran_inline += 1

    return {"ok": True, "worker_alive": worker_alive, "enqueued_shots": enqueued, "ran_inline": ran_inline}


@router.get("/{project_id}/status")
def project_status(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    shots = db.execute(
        select(Shot).join(Scene, Shot.scene_id == Scene.id).where(Scene.project_id == project_id)
    ).scalars().all()

    by_status = {"PENDING": 0, "RUNNING": 0, "SUCCEEDED": 0, "FAILED": 0}
    for sh in shots:
        key = sh.status.value if hasattr(sh.status, "value") else str(sh.status)
        key = key.upper()
        by_status[key] = by_status.get(key, 0) + 1

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


@router.post("/{project_id}/render")
def render_endpoint(project_id: int, db: Session = Depends(get_db)):
    try:
        render = render_project(project_id, db)
        return {"ok": True, "output_path": render.output_path}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}/video")
def get_project_video(project_id: int, download: bool = False):
    out_dir = Path(settings.assets_dir) / f"project_{project_id}"

    mp4_audio = out_dir / "final_render_with_audio.mp4"
    mp4_plain = out_dir / "final_render.mp4"

    if mp4_audio.exists():
        p = mp4_audio
    elif mp4_plain.exists():
        p = mp4_plain
    else:
        raise HTTPException(status_code=404, detail=f"No render found in {out_dir}")

    if download:
        return FileResponse(str(p), media_type="video/mp4", filename=f"project_{project_id}.mp4")
    return FileResponse(str(p), media_type="video/mp4", content_disposition_type="inline")

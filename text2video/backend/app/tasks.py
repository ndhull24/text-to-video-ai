from celery import Celery
from sqlalchemy.orm import Session
from .config import settings
from .db import SessionLocal
from .models import Shot, ShotStatus
from .storage import shot_video_path
import subprocess
import json

from .animations import apply_animations_ffmpeg, default_animation_plan


celery_app = Celery("t2v", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="generate_shot")
def generate_shot(shot_id: int):
    db: Session = SessionLocal()
    shot = None
    try:
        shot = db.get(Shot, shot_id)
        if not shot:
            return {"ok": False, "error": "Shot not found"}

        shot.status = ShotStatus.RUNNING
        db.commit()

        scene = shot.scene
        project_id = scene.project_id

        # Keep duration within a sane range
        dur = max(1, int(shot.duration_s or 6))

        # Paths
        out_mp4 = shot_video_path(project_id, scene.idx, shot.idx)
        base_mp4 = out_mp4.replace(".mp4", "_base.mp4")

        # 1) generate base clip
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", "testsrc=size=1280x720:rate=24",
            "-t", str(dur),
            "-pix_fmt", "yuv420p",
            base_mp4,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        # 2) load or create animation plan
        plan = None
        if getattr(shot, "animation_json", None):
            try:
                plan = json.loads(shot.animation_json)
            except Exception:
                plan = None

        if not plan:
            plan = default_animation_plan(shot.prompt or "", dur)

        # 3) burn animated overlays onto final mp4
        apply_animations_ffmpeg(base_mp4, out_mp4, plan)

        # Finalize
        shot.asset_path = out_mp4
        shot.status = ShotStatus.SUCCEEDED
        db.commit()
        return {"ok": True, "shot_id": shot_id, "asset_path": out_mp4}

    except Exception as e:
        if shot is not None:
            shot.status = ShotStatus.FAILED
            shot.error = str(e)
            db.commit()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()

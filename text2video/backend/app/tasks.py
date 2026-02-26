from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from celery import Celery
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import Shot, ShotStatus
from .storage import shot_video_path
from .animations import (
    apply_animations_ffmpeg,
    default_animation_plan,
    parse_plan,
)
from .providers.wan2_client import wan_generate_mp4

# ✅ NEW: scene-spec compiler/encoder (drives visuals from text)
from app.animation.scene_compiler import text_to_scene_spec
from app.animation.scene_encode import render_scene_to_mp4


celery_app = Celery(
    "t2v",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


def _make_test_pattern(out_mp4: str, duration_s: int = 6):
    """
    Very fast dummy video used for debugging.
    Deterministic: smptebars.
    (Kept for optional debugging, but no longer used as the core fallback.)
    """
    Path(out_mp4).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "smptebars=size=1280x720:rate=24",
        "-t",
        str(max(1, int(duration_s))),
        "-pix_fmt",
        "yuv420p",
        out_mp4,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _make_animation_base_clip(shot: Shot, scene, dur: int, out_mp4: str) -> str:
    """
    Core generator used by UI fallback: procedural cartoon scene based on text.
    """
    Path(out_mp4).parent.mkdir(parents=True, exist_ok=True)

    # ✅ Step-2 spec order: prompt -> text -> scene.summary -> scene.title
    anim_text = (
        (getattr(shot, "prompt", None) or "").strip()
        or (getattr(shot, "text", None) or "").strip()
        or (getattr(scene, "summary", None) or "").strip()
        or (getattr(scene, "title", None) or "").strip()
    )
    if not anim_text:
        anim_text = f"Scene {scene.idx} shot {shot.idx}"

    spec = text_to_scene_spec(anim_text)
    final_mp4 = render_scene_to_mp4(
        spec,
        out_mp4,
        seconds=float(dur),
        fps=30,
        w=1280,
        h=720,
    )
    return final_mp4


@celery_app.task(name="generate_shot")
def generate_shot(shot_id: int):
    db: Session = SessionLocal()
    shot = None

    try:
        shot = db.get(Shot, shot_id)
        if not shot:
            return {"ok": False, "error": "Shot not found"}

        # Mark as running
        shot.status = ShotStatus.RUNNING
        shot.error = None
        db.commit()

        scene = shot.scene
        if not scene:
            shot.status = ShotStatus.FAILED
            shot.error = "Scene not found"
            db.commit()
            return {"ok": False, "error": "Scene not found"}

        project_id = scene.project_id

        # Keep duration sane
        dur = max(1, int(shot.duration_s or 6))

        # Paths
        out_mp4 = shot_video_path(project_id, scene.idx, shot.idx)
        base_mp4 = out_mp4.replace(".mp4", "_base.mp4")

        Path(out_mp4).parent.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------
        # 0️⃣ Provider selection
        # --------------------------------------------------
        provider = (os.getenv("VIDEO_PROVIDER") or "").upper().strip()
        is_cinematic = "cinematic" in (shot.prompt or "").lower()
        use_wan = provider == "WAN2" or bool(os.getenv("WAN2_COLAB_URL")) or is_cinematic

        # --------------------------------------------------
        # 1️⃣ REAL GENERATION (WAN2)
        # --------------------------------------------------
        if use_wan:
            prompt = (shot.prompt or "").strip()
            if not prompt:
                prompt = f"Scene {scene.idx} shot {shot.idx}, cinematic, high quality"

            try:
                wan_generate_mp4(
                    prompt=prompt,
                    out_path=out_mp4,
                    width=1280,
                    height=704,
                )
                
                if not Path(out_mp4).exists():
                    shot.status = ShotStatus.FAILED
                    shot.error = "WAN2 did not produce an mp4"
                    db.commit()
                    return {"ok": False, "error": shot.error}

                shot.asset_path = str(Path(out_mp4).resolve())
                shot.status = ShotStatus.SUCCEEDED
                db.commit()
                return {
                    "ok": True,
                    "shot_id": shot_id,
                    "asset_path": shot.asset_path,
                    "provider": "WAN2",
                }
            except Exception as e:
                # If WAN2 fails (e.g. no colab URL configured), fall back to procedural text animation.
                shot.error = f"WAN2 cinematic generation failed, falling back to procedural text-animation. {e}"
                # Exception caught. Execution will continue to the text-animation fallback.

        # --------------------------------------------------
        # 2️⃣ CORE FALLBACK BASE CLIP = TEXT ANIMATION
        # (This replaces smptebars as the default generator.)
        # --------------------------------------------------
        try:
            # ✅ Step-2 requirement: fallback calls _make_animation_base_clip(...)
            base_final = _make_animation_base_clip(shot, scene, dur, base_mp4)
        except Exception as e:
            # Emergency fallback (only if animation renderer fails)
            _make_test_pattern(base_mp4, duration_s=dur)
            shot.error = f"Animation base generation failed; used test pattern. {e}"
            base_final = base_mp4

        # base_final should exist
        if not Path(base_final).exists():
            shot.status = ShotStatus.FAILED
            shot.error = "Base mp4 not found after fallback generation"
            db.commit()
            return {"ok": False, "error": shot.error}

        # --------------------------------------------------
        # 3️⃣ Load or create ffmpeg animation plan (optional)
        # If you still want your ffmpeg filter animations on top, keep this.
        # Otherwise you can skip straight to success using base_final.
        # --------------------------------------------------
        plan = parse_plan(getattr(shot, "animation_json", None))

        if not plan:
            plan = default_animation_plan(shot.prompt or "", dur)
            try:
                shot.animation_json = json.dumps(plan)
                db.commit()
            except Exception:
                pass

        # --------------------------------------------------
        # 4️⃣ Apply ffmpeg animations -> final mp4 (optional)
        # --------------------------------------------------
        try:
            apply_animations_ffmpeg(
                base_final,
                out_mp4,
                dur,
                plan,
                prompt_for_text=shot.prompt or "",
            )
            final_path = out_mp4
            provider_name = "TEXT_ANIMATION_FALLBACK+FFMPEG"
        except Exception as e:
            # Salvage mode — still succeed with base animation
            shot.error = f"FFMPEG animation overlay failed; used base animation. {e}"
            final_path = base_final
            provider_name = "TEXT_ANIMATION_FALLBACK"

        # --------------------------------------------------
        # 5️⃣ Mark success
        # --------------------------------------------------
        if not Path(final_path).exists():
            shot.status = ShotStatus.FAILED
            shot.error = "Final mp4 not found after generation"
            db.commit()
            return {"ok": False, "error": shot.error}

        shot.asset_path = str(Path(final_path).resolve())
        shot.status = ShotStatus.SUCCEEDED
        db.commit()

        return {
            "ok": True,
            "shot_id": shot_id,
            "asset_path": shot.asset_path,
            "provider": provider_name,
        }

    except Exception as e:
        if shot is not None:
            shot.status = ShotStatus.FAILED
            shot.error = str(e)
            db.commit()
        return {"ok": False, "error": str(e)}

    finally:
        db.close()

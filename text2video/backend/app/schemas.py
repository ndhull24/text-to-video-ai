from pydantic import BaseModel
from typing import Optional, List


class ProjectCreate(BaseModel):
    title: str


class ProjectOut(BaseModel):
    id: int
    title: str

    class Config:
        from_attributes = True


class ChapterUpload(BaseModel):
    text: str


class PlanRequest(BaseModel):
    """Planning defaults tuned for an MVP demo, extended for long lectures.

    The previous defaults (90 minutes / 120 scenes) created huge plans and made
    local SQLite + ffmpeg testing feel "stuck". Support added for 60+ min videos
    using lecture mode.
    """

    target_minutes: int = 60
    style: str = "lecture"
    max_scenes: int = 120


class ShotOut(BaseModel):
    id: int
    idx: int
    duration_s: int
    shot_type: str
    status: str
    asset_path: Optional[str] = None

    class Config:
        from_attributes = True


class SceneOut(BaseModel):
    id: int
    idx: int
    title: str
    summary: str
    shots: List[ShotOut]

    class Config:
        from_attributes = True

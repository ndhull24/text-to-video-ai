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
    target_minutes: int = 90  # 60-120
    style: str = "cinematic, realistic"
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

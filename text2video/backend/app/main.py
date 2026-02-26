from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import Base, engine
from .routes.media import router as media_router
from .routes.projects import router as projects_router
from .routes.studio import router as studio_router

app = FastAPI(title="Text2Video MVP")

# ✅ Dev CORS (fixes "OPTIONS ... 400" + "Failed to fetch")
# Allow ANY origin on localhost/127.0.0.1 on ANY port.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Ad-hoc "text → animation mp4"
# -----------------------------
animate_router = APIRouter()


class AnimateReq(BaseModel):
    text: str


@animate_router.post("/animate")
def animate(req: AnimateReq):
    # Lazy imports so the app doesn't fail to start if these modules aren't present yet.
    from .animation.compiler import text_to_plan
    from .animation.encode import render_to_mp4
    from .storage_paths import project_file_path  # adjust if your helper name differs

    plan = text_to_plan(req.text)
    out_mp4 = project_file_path("adhoc", "animation.mp4")  # replace with your path helper
    render_to_mp4(plan, out_mp4)
    return {"mp4_path": out_mp4}


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(animate_router)
app.include_router(projects_router)
app.include_router(studio_router)
app.include_router(media_router)


@app.get("/")
def health():
    return {"ok": True, "service": "text2video-backend"}

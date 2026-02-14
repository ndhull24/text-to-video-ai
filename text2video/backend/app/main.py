from .db import engine, Base
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from .routes.projects import router as projects_router
from .routes.studio import router as studio_router
from .routes.media import router as media_router

app.include_router(projects_router)
app.include_router(studio_router)
app.include_router(media_router)



app = FastAPI(title="Text2Video MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

app.include_router(projects_router)

@app.get("/")
def health():
    return {"ok": True}

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: text2video/
ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"


def _resolve_under_root(p: str) -> str:
    """Resolve ASSETS_DIR-like paths relative to repo root unless already absolute."""
    if not p:
        return str((ROOT / "_assets").resolve())
    path = Path(p)
    if path.is_absolute():
        return str(path)
    return str((ROOT / path).resolve())


class Settings(BaseSettings):
    database_url: str = "sqlite:///./text2video.db"
    redis_url: str = "redis://localhost:6379/0"

    # IMPORTANT: always absolute path so backend works no matter where it's launched from
    assets_dir: str = str((ROOT / "_assets").resolve())

    # NEW: Windows font path for text rendering
    font_path: str = r"C:\Windows\Fonts\segoeui.ttf"

    model_config = SettingsConfigDict(env_file=str(ENV_PATH), extra="ignore")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.assets_dir = _resolve_under_root(self.assets_dir)


settings = Settings()

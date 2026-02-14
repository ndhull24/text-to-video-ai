from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .../text2video
ENV_PATH = ROOT / ".env"

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    assets_dir: str = "./_assets"

    model_config = SettingsConfigDict(env_file=str(ENV_PATH), extra="ignore")

settings = Settings()

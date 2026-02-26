from __future__ import annotations

import os
from pathlib import Path
import requests


def _wan_url() -> str:
    url = (os.getenv("WAN2_COLAB_URL") or "").strip().rstrip("/")
    if not url:
        raise RuntimeError("WAN2_COLAB_URL is not set")
    return url


def wan_generate_mp4(
    prompt: str,
    out_path: str,
    width: int = 1280,
    height: int = 704,
    timeout_s: int = 60 * 60,
):
    """
    Calls Colab FastAPI /generate endpoint that returns MP4 bytes.
    Saves to out_path.
    """
    url = _wan_url()

    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
    }

    r = requests.post(f"{url}/generate", json=payload, stream=True, timeout=timeout_s)
    r.raise_for_status()

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    return out_path

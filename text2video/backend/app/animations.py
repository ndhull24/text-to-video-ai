from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import settings


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def default_animation_plan(prompt: str, duration_s: int) -> Dict[str, Any]:
    # Motion type based on simple keyword heuristics
    p = (prompt or "").lower()
    if any(k in p for k in ["fast", "urgent", "quick", "run", "chase", "explode", "action"]):
        motion = "pan"
        intensity = 0.22
    elif any(k in p for k in ["calm", "slow", "quiet", "peace", "soft", "gentle"]):
        motion = "kenburns"
        intensity = 0.10
    else:
        motion = "kenburns"
        intensity = 0.18

    return {
        "type": motion,
        "intensity": intensity,    # how strong the motion is
        "fps": 30,
        "text": "auto",            # enable auto text overlay
    }


def parse_plan(animation_json: Optional[str]) -> Dict[str, Any]:
    if not animation_json:
        return {}
    try:
        return json.loads(animation_json)
    except Exception:
        return {}


def _extract_title_sub(prompt: str) -> Tuple[str, str]:
    """
    Turn the shot prompt into a short, readable on-screen caption.
    Heuristic:
    - Title: first sentence / first ~7 words
    - Subline: next clause trimmed
    """
    s = (prompt or "").strip()
    s = re.sub(r"\s+", " ", s)
    if not s:
        return ("", "")

    # split on sentence boundaries
    parts = re.split(r"[.!?]\s+", s)
    first = parts[0].strip()
    rest = " ".join(parts[1:]).strip()

    words = first.split(" ")
    title = " ".join(words[:7]).strip()
    if len(words) > 7:
        title = title + "…"

    sub = rest[:80].strip()
    if len(rest) > 80:
        sub = sub + "…"

    # if no "rest", take remaining from first
    if not sub and len(words) > 7:
        sub = " ".join(words[7:])[:80].strip()
        if len(" ".join(words[7:])) > 80:
            sub += "…"

    return (title, sub)


# --- SAFE text escaping for ffmpeg drawtext ---
def _escape_drawtext_text(s: str) -> str:
    """
    Escape text for ffmpeg drawtext.
    - Escape backslashes first
    - Escape single quotes because we wrap text='...'
    - Escape colon because ffmpeg uses it as key/value separator
    - Escape comma because ffmpeg uses it to separate filters
    """
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace(":", "\\:")
    s = s.replace(",", "\\,")
    return s


def apply_animations_ffmpeg(
    input_mp4: str,
    output_mp4: str,
    duration_s: int,
    plan: Dict[str, Any],
    prompt_for_text: str = "",
) -> None:
    """
    Apply:
    - motion (zoom/pan)
    - text overlay (animated lower-third)
    """
    inp = Path(input_mp4)
    out = Path(output_mp4)
    out.parent.mkdir(parents=True, exist_ok=True)

    fps = int(plan.get("fps", 30))
    dur = max(1, int(duration_s))
    motion_type = (plan.get("type") or "kenburns").lower()
    intensity = float(plan.get("intensity", 0.18))

    # ----- Motion filter -----
    if motion_type == "kenburns":
        # zoom from 1 -> 1+intensity across duration
        vf_motion = (
            f"trim=duration={dur},setpts=PTS-STARTPTS,"
            f"scale=iw*1.35:ih*1.35,"
            f"zoompan=z='1+{intensity}*on/({dur}*{fps})':"
            f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s=iwxih:fps={fps}"
        )
    else:
        # pan to the right
        pan_px = intensity  # use intensity as fraction of width
        vf_motion = (
            f"trim=duration={dur},setpts=PTS-STARTPTS,"
            f"scale=iw*1.20:ih*1.20,"
            f"crop=iw:ih:x='(iw*{pan_px})*t/{dur}':y='0',fps={fps}"
        )

    # ----- Text overlay filter -----
    # Prioritize the explicitly stored educational caption over the visual generation prompt
    display_text = plan.get("caption") or prompt_for_text
    title, sub = _extract_title_sub(display_text)
    fontfile = settings.font_path.replace("\\", "/")

    safe_title = _escape_drawtext_text(title)
    safe_sub = _escape_drawtext_text(sub)

    # lower-third box position
    # animate slide-up in first 0.5s and fade out last 0.5s
    # y(t) from h to h-160, and alpha fades in/out
    box_h = 160
    pad = 28
    box_y_expr = f"h-{box_h}-({pad}) + (1 - min(t/0.5\\,1))*50"  # slides up 50px
    alpha_expr = f"if(lt(t\\,0.35)\\, t/0.35\\, if(gt(t\\,{dur}-0.35)\\, ({dur}-t)/0.35\\, 1))"

    draw_title = (
        f"drawtext=fontfile='{fontfile}':"
        f"text='{safe_title}':"
        f"fontsize=44:"
        f"fontcolor=white@{alpha_expr}:"
        f"x={pad+22}:"
        f"y=({box_y_expr})+20:"
        f"shadowcolor=black@0.55:"
        f"shadowx=2:"
        f"shadowy=2"
    )

    draw_sub = (
        f"drawtext=fontfile='{fontfile}':"
        f"text='{safe_sub}':"
        f"fontsize=28:"
        f"fontcolor=white@{alpha_expr}:"
        f"x={pad+22}:"
        f"y=({box_y_expr})+78:"
        f"shadowcolor=black@0.45:"
        f"shadowx=2:"
        f"shadowy=2"
    )

    # Use a semi-transparent box + two lines of text
    vf_text = (
        f"drawbox=x={pad}:y=h-{box_h}-{pad}:w=w-{pad*2}:h={box_h}:color=black@0.45:t=fill,"
        f"{draw_title},"
        f"{draw_sub}"
    )

    # Combine all
    vf = f"{vf_motion},{vf_text},format=yuv420p"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(inp),
        "-vf",
        vf,
        "-t",
        str(dur),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out),
    ]
    _run(cmd)

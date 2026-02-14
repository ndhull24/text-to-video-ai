import json
import re
import subprocess
from pathlib import Path

def _safe_text(s: str) -> str:
    # keep it simple: remove weird chars that break ffmpeg drawtext
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = s.replace(":", "\\:")  # ffmpeg drawtext uses ':' as separator
    s = s.replace("'", "\\'")
    return s[:120]  # cap length for readability

def default_animation_plan(text: str, dur: int) -> dict:
    """
    Minimal plan:
    - show one line of text in lower third
    - fade in, slide slightly, then fade out
    """
    t = _safe_text(text) or " "
    dur = max(1, int(dur or 6))
    start = 0.3
    end = max(start + 1.2, dur - 0.4)

    return {
        "version": 1,
        "overlays": [
            {
                "type": "text",
                "text": t,
                "start": start,
                "end": end,
                "style": "lower_third",
                "anim": "slide_fade",
            }
        ],
    }

def apply_animations_ffmpeg(
    input_mp4: str,
    output_mp4: str,
    plan: dict,
    font_path: str | None = None,
) -> None:
    """
    Burns animated text overlays onto video using ffmpeg drawtext.
    """
    overlays = (plan or {}).get("overlays", [])
    if not overlays:
        # no overlays: just copy
        Path(output_mp4).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-i", input_mp4, "-c", "copy", output_mp4], check=True)
        return

    # pick a default font (Windows-friendly)
    # You can pass settings.font_path later; for now hardcode a safe default if missing.
    if not font_path:
        # common Windows font path
        candidate = r"C:\Windows\Fonts\arial.ttf"
        font_path = candidate if Path(candidate).exists() else ""

    filters = []
    for ov in overlays:
        if ov.get("type") != "text":
            continue

        text = _safe_text(ov.get("text", ""))
        start = float(ov.get("start", 0.0))
        end = float(ov.get("end", 2.0))

        # Lower third position baseline
        # x moves slightly from left (slide in), y fixed near bottom
        # alpha fades in/out using expressions
        # enable only between start/end
        x_expr = "w*0.08 + (1 - min(1,(t-{s})/0.6))*40".format(s=start)  # slides from +40px to 0
        y_expr = "h*0.78"

        # fade: ramp up 0.4s, ramp down last 0.4s
        alpha_expr = (
            "if(lt(t,{s}),0,"
            " if(lt(t,{s}+0.4),(t-{s})/0.4,"
            "  if(lt(t,{e}-0.4),1,"
            "   if(lt(t,{e}),( {e}-t)/0.4,0)"
            "  )"
            " )"
            ")"
        ).format(s=start, e=end)

        draw = (
            "drawtext="
            f"fontfile='{font_path}':"
            f"text='{text}':"
            "fontsize=48:"
            "fontcolor=white:"
            "borderw=3:bordercolor=black@0.6:"
            f"x='{x_expr}':y='{y_expr}':"
            f"alpha='{alpha_expr}':"
            f"enable='between(t,{start},{end})'"
        )
        filters.append(draw)

    vf = ",".join(filters) if filters else "null"

    Path(output_mp4).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_mp4,
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_mp4,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

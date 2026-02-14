import math

def simple_plan(chapter_text: str, target_minutes: int, max_scenes: int):
    """
    MVP planner:
    - Splits text into N scenes based on target length
    - Creates a few shots per scene
    """
    # crude heuristic: scenes scale with target duration
    scene_count = min(max_scenes, max(20, target_minutes))  # e.g. 90 min -> ~90 scenes cap
    # make summaries from chunks
    chunk_size = max(500, math.ceil(len(chapter_text) / scene_count))
    scenes = []

    for i in range(scene_count):
        chunk = chapter_text[i*chunk_size:(i+1)*chunk_size].strip()
        if not chunk:
            break
        title = f"Scene {i+1}"
        summary = (chunk[:280] + "...") if len(chunk) > 280 else chunk

        # shots: 3 per scene for MVP
        shots = [
            {
                "idx": 1,
                "duration_s": 6,
                "shot_type": "STANDARD",
                "prompt": f"{title}: establishing shot. {summary}",
                "negative_prompt": "text, watermark, logo, distorted hands"
            },
            {
                "idx": 2,
                "duration_s": 6,
                "shot_type": "HERO" if (i % 7 == 0) else "STANDARD",
                "prompt": f"{title}: main action moment, cinematic camera, {summary}",
                "negative_prompt": "text, watermark, logo, low quality"
            },
            {
                "idx": 3,
                "duration_s": 8,
                "shot_type": "BRIDGE",
                "prompt": f"{title}: dialogue coverage / reaction shot, subtle motion, {summary}",
                "negative_prompt": "text, watermark, logo, flicker"
            },
        ]
        scenes.append({"idx": i+1, "title": title, "summary": summary, "shots": shots})

    return scenes

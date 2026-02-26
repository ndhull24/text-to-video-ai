import math


def simple_plan(chapter_text: str, target_minutes: int, max_scenes: int, style: str = "lecture"):
    """Planner supporting different styles like lecture and cinematic.

    Goals:
    - generate a reasonable number of scenes for local testing
    - differentiate between high-density short videos and long video lectures

    Heuristic for Lecture:
    - ~1 scene per 2-5 minutes, maxing at `max_scenes`.
    - Shots have much longer durations (15-60s or more) so 60m takes far fewer shots.
    
    Heuristic for Cinematic (default MVP):
    - ~3 scenes per minute.
    - Shots have short durations (4-8s).
    """

    chapter_text = (chapter_text or "").strip()
    if not chapter_text:
        return []

    is_lecture = "lecture" in style.lower()
    is_cinematic_nlp = "cinematic_nlp" in style.lower() or "nlp" in style.lower()

    if is_cinematic_nlp or is_lecture:
        # For lectures, maybe 1 scene per 2 minutes.
        scene_count = max(1, min(int(max_scenes), max(1, target_minutes // 2)))
    else:
        # Roughly 3 scenes per minute; never less than 1.
        scene_count = max(1, min(int(max_scenes), int(max(1, target_minutes)) * 3))

    # chunk text evenly; keep chunk sizes large enough to produce meaningful summaries
    chunk_size = max(300, math.ceil(len(chapter_text) / scene_count))

    scenes = []
    for i in range(scene_count):
        chunk = chapter_text[i * chunk_size: (i + 1) * chunk_size].strip()
        if not chunk:
            break

        title = f"Scene {i + 1}"
        summary = (chunk[:280] + "...") if len(chunk) > 280 else chunk
        
        if is_cinematic_nlp:
            shots = [
                {
                    "idx": 1,
                    "duration_s": 20,
                    "shot_type": "STANDARD",
                    "prompt": f"Cinematic 3D visualization, photorealistic, highly detailed render explaining natural language processing concepts. Visualizing: {summary}. Glowing data streams, neural network nodes, volumetric lighting, 8k resolution.",
                    "negative_prompt": "cartoon, 2d, animated, text, watermark, logo, low quality, flat",
                },
                {
                    "idx": 2,
                    "duration_s": 40,
                    "shot_type": "HERO" if (i % 3 == 0) else "STANDARD",
                    "prompt": f"Photorealistic cinematic b-roll showcasing AI and machine learning architecture. Context: {summary}. Deep depth of field, slow pan, realistic lighting, masterful cinematography.",
                    "negative_prompt": "cartoon, 2d, animated, text, watermark, logo, distracting elements, poorly drawn",
                },
            ]
        elif is_lecture:
            # Generate fewer, longer shots for a lecture.
            # E.g., a single 60-second shot per scene, or one 20s and one 40s shot.
            shots = [
                {
                    "idx": 1,
                    "duration_s": 20,
                    "shot_type": "STANDARD",
                    "prompt": f"{title}: establishing shot, professor teaching, clean background. {summary}",
                    "negative_prompt": "text, watermark, logo, fast motion",
                },
                {
                    "idx": 2,
                    "duration_s": 40,
                    "shot_type": "HERO" if (i % 3 == 0) else "STANDARD",
                    "prompt": f"{title}: instructional presentation, slow camera movement, {summary}",
                    "negative_prompt": "text, watermark, logo, distracting elements",
                },
            ]
        else:
            shots = [
                {
                    "idx": 1,
                    "duration_s": 6,
                    "shot_type": "STANDARD",
                    "prompt": f"{title}: establishing shot. {summary}",
                    "negative_prompt": "text, watermark, logo, distorted hands",
                },
                {
                    "idx": 2,
                    "duration_s": 6,
                    "shot_type": "HERO" if (i % 6 == 0) else "STANDARD",
                    "prompt": f"{title}: main action moment, cinematic camera, {summary}",
                    "negative_prompt": "text, watermark, logo, low quality",
                },
                {
                    "idx": 3,
                    "duration_s": 8,
                    "shot_type": "BRIDGE",
                    "prompt": f"{title}: dialogue coverage / reaction shot, subtle motion, {summary}",
                    "negative_prompt": "text, watermark, logo, flicker",
                },
            ]

        scenes.append({"idx": i + 1, "title": title, "summary": summary, "shots": shots})

    return scenes

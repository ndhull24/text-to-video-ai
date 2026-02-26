import sys
sys.path.append('.')
from app.animations import apply_animations_ffmpeg
try:
    apply_animations_ffmpeg('_assets/project_23/scene_001/shot_001_base.mp4', '_assets/test_overlay2.mp4', 6, {'type':'kenburns', 'intensity':0.18, 'fps':30}, 'Natural Language Processing, or NLP, is the fascinating intersection of linguistics and artificial intelligence.')
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()

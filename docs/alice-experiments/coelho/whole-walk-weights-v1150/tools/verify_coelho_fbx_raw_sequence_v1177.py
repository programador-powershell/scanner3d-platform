"""Read immutable whole FBX payload sequentially, without authoring/render memory."""
from pathlib import Path
import gc
T = Path('F:/Alice/SharedProduction/Tools')
for name in ['verify_coelho_distinct_walk_fbx_normals_v1152.py', 'verify_coelho_distinct_walk_fbx_materials_v1154.py']:
    p = T / name
    namespace = {'__name__': '__main__', '__file__': str(p)}
    exec(compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec'), namespace)
    namespace.clear()
    gc.collect()
print('WHOLE_FBX_RAW_NORMAL_AND_EMBEDDED_MATERIAL_SEQUENCE_COMPLETE', flush=True)

from pathlib import Path
import gc
T=Path('F:/Alice/SharedProduction/Tools')
for name in ['verify_coelho_left_patch_glb_normals_v1208.py','reimport_coelho_whole_left_patch_glb_v1206.py']:
    p=T/name;namespace={'__name__':'__main__','__file__':str(p)}
    exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),namespace);namespace.clear();gc.collect()
print('WHOLE_GLB_RAW_NORMAL_AND_ACTUAL_REIMPORT_PIPELINE_COMPLETE',flush=True)

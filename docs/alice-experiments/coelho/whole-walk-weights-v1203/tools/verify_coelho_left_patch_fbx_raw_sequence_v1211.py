from pathlib import Path
import gc
T=Path('F:/Alice/SharedProduction/Tools')
for name in ['verify_coelho_left_patch_fbx_normals_v1209.py','verify_coelho_left_patch_fbx_materials_v1211.py']:
    p=T/name;namespace={'__name__':'__main__','__file__':str(p)}
    exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),namespace);namespace.clear();gc.collect()
print('CURRENT_FULL_FBX_RAW_NORMAL_AND_EMBEDDED_MATERIAL_CHECKS_COMPLETE',flush=True)

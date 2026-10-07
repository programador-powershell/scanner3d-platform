from pathlib import Path
import gc
T=Path('F:/Alice/SharedProduction/Tools')
for name in ['verify_coelho_corset_fbx_normals_v1237.py', 'verify_coelho_corset_fbx_materials_v1239.py', 'reimport_coelho_whole_corset_fbx_v1235.py']:
 p=T/name;ns={'__name__':'__main__','__file__':str(p)};exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),ns);del ns;gc.collect()

from pathlib import Path
import gc
T=Path('F:/Alice/SharedProduction/Tools')
for name in ['verify_coelho_corset_glb_normals_v1236.py', 'reimport_coelho_whole_corset_glb_v1234.py']:
 p=T/name;ns={'__name__':'__main__','__file__':str(p)};exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),ns);del ns;gc.collect()

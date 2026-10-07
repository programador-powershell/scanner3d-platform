from pathlib import Path
T=Path('F:/Alice/SharedProduction/Tools')
for name in ['capture_coelho_left_patch_true_motion_v1204.py','export_coelho_whole_left_patch_weights_v1202.py']:
    p=T/name;exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),{'__name__':'__main__','__file__':str(p)})

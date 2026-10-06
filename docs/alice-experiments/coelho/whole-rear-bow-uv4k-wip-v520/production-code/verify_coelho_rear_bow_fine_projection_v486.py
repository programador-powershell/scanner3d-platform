from pathlib import Path
p=Path('F:/Alice/SharedProduction/Tools/verify_coelho_rear_bow_projection_visibility_v478.py');code=p.read_text(encoding='utf-8-sig').replace('v475','v482').replace('v478','v486').replace('BOW478','BOW486');exec(compile(code,str(p.with_name('verify_coelho_rear_bow_fine_projection_v486.py')),'exec'))

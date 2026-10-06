from pathlib import Path
p=Path('F:/Alice/SharedProduction/Tools/verify_render_coelho_rear_bow_paint_v469.py');code=p.read_text(encoding='utf-8-sig').replace('v467','v492').replace('v466','v471').replace('v469','v493').replace('BOW469','BOW493').replace('RearBow.Atlas4K.v471','RearBow.Atlas4K.ABF.v471');exec(compile(code,str(p.with_name('verify_render_coelho_rear_bow_thin_ink_v493.py')),'exec'))

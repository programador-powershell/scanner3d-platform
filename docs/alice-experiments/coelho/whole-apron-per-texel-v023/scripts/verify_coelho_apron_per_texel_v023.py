from pathlib import Path
R=Path('F:/Alice/SharedProduction');p=R/'Tools/verify_coelho_apron_single_uv_v013.py';code=p.read_text().replace('_v013','_v023').replace('V013','V023').replace('apron_single_uv_checkpoint','apron_per_texel_checkpoint');exec(compile(code,str(p),'exec'))

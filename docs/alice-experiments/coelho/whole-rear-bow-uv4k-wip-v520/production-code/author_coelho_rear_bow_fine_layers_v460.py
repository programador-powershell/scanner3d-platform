"""Board8 loop pleats with thinner inner textile spacing; strict guard remains."""
from pathlib import Path
p=Path('F:/Alice/SharedProduction/Tools/author_coelho_rear_bow_pleats_v459.py')
script=p.read_text(encoding='utf-8-sig').replace('459','460')
needle='exec(compile(script'
script=script.replace(needle,"script=script.replace(\"code=code.replace('y=.112\", \"code=code.replace('-.0014','-.0005').replace('-.0027','-.00075').replace('.00045','.00012')\\ncode=code.replace('y=.112\",1)\n"+needle,1)
exec(compile(script,str(p.with_name('author_coelho_rear_bow_fine_layers_v460.py')),'exec'))

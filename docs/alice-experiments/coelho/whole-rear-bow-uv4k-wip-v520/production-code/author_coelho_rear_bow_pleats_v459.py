"""Refine the board8 radiating loop pleats; retain454 and the published Alice."""
from pathlib import Path
p=Path('F:/Alice/SharedProduction/Tools/author_coelho_rear_bow_curvature_layers_v454.py')
script=p.read_text(encoding='utf-8-sig').replace('454','459')
needle="code=code.replace('y=.112"
script=script.replace(needle,"code=code.replace('.006*math.cos(3*math.pi*(v+1)/2+.30*s)', '.012*math.cos(5*math.pi*(v+1)/2+.30*s)')\n"+needle,1)
script=script.replace("code=code.replace(\"report=dict(smoothParametricBowAndTailShapes\", \"report=dict(","code=code.replace(\"report=dict(smoothParametricBowAndTailShapes\", \"report=dict(referenceBoard8RadiatingPleatsRefined=True,pleatAmplitudeM=.012,pleatCyclesAcrossWidth=2.5,prior454Preserved=True,")
exec(compile(script,str(p.with_name('author_coelho_rear_bow_pleats_v459.py')),'exec'))

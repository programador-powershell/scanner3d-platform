"""Independent saved-mesh all-kind audit of candidate v177, including the net."""
from pathlib import Path
R=Path('F:/Alice/SharedProduction')
code=(R/'Tools/verify_coelho_neighbor_sections_v174.py').read_text(encoding='utf-8-sig').replace('v174','v178').replace('v173','v177')
code=code.replace("report.update(independentSavedFloat32Reopen", "assert not [r for r in rows if r['kindA']==r['kindB']=='ivory_diamond_net'], 'New net contacts remain in saved geometry'\nreport.update(allDiamondNetPairsChecked=True,diamondNetSATTrianglePairs=0,independentSavedFloat32Reopen")
exec(compile(code,__file__,'exec'))

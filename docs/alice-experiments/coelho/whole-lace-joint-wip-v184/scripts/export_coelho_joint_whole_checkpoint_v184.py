"""Export the whole verified local source v181; this remains an intermediate checkpoint."""
from pathlib import Path
import json
R=Path('F:/Alice/SharedProduction'); O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
review=json.loads((O/'apron_joint_whole_review_decision_v183.json').read_text(encoding='utf-8-sig'))
assert review['allFiveWholeViewsActuallyInspected'] and review['acceptedForLocalWholeExportReimportReview'] and not review['productionComplete']
code=(R/'Tools/export_coelho_whole_apron_checkpoint_v147.py').read_text(encoding='utf-8-sig')
code=code.replace('v147','v184').replace('v145','v181').replace('Export147.','Export184.').replace('Triangles.147','Triangles.184').replace('apron_tip_chain_cord_checkpoint','apron_lace_joint_checkpoint')
exec(compile(code,__file__,'exec'))

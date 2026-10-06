"""Record actual stage-photo comparison alongside geometric motion diagnostics."""
from pathlib import Path
import json,hashlib,datetime
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));index=read(O/'layer_reference_index_v008.json')
rows=[]
for number in [2,4]:
 row=next(r for r in index['references'] if r['board']==number);p=Path(row['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'];rows.append(dict(row,actualPhotoInspected=True))
c=read(O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/manifest.json');assert len(c['renders'])==4
for r in c['renders']:assert hashlib.sha256((R/r['path']).read_bytes()).hexdigest()==r['sha256']
review=dict(version='v1167',source='v1146',stageReferences=rows,actualFourNativeWholeMotionRendersInspected=True,geometryUVNormalsMaterialsUnchanged=True,findings=['striped existing stockings retain their source pattern during the viewed poses; this does not approve complete foundation layers hidden under the skirt','sleeve puff/cuff volume remains in the whole renders, but shoulder/cuff transitions and hanging details do not yet match the clean construction shown in board4','the stage4 photo requires gathered caps, sleeve bands, two cuff ruffles/lace and independent trims; no approval of those hidden layers or final deformation is made','solid Tripo hair and canonical face/body integration remain visibly unfinished; unchanged UV4K alone does not establish fidelity'],staticFidelityApproved=False,allStageLayersComplete=False,clothPhysicsApproved=False,gameplayApproved=False,productionComplete=False,createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
(O/'native_stage_photo_review_v1167.json').write_text(json.dumps(review,indent=2,ensure_ascii=False),encoding='utf-8');print('ACTUAL_STAGE2_STAGE4_PHOTO_REVIEW_RECORDED_NOT_FINAL_FIDELITY')

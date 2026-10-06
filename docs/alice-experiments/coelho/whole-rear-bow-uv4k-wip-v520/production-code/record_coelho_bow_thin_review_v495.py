import json
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
a=read(O/'rear_bow_paint_saved_audit_v493.json')
assert a['allElevenSavedGeometriesUVWeightsAndTenWholeObjectsExactlyVerified']
assert len(a['maps'])==2 and all(m['packedPNGBytesExact'] for m in a['maps'])
decision=dict(version='v495',sourceCandidate='v492',allSixActualRenders493Inspected=True,nativeBoardComparison494Inspected=True,acceptedForWholeStaticWIPIntegrationReview=True,acceptedForPublication=False,fidelityApproved=False,productionComplete=False,observations=['Six actual saved-file renders inspected: whole back, whole rear threequarter, close back, both profiles, layers-only back. Fine chain paths are more continuous than482; the same three-dimensional cloth folds remain.','Native board8 comparison inspected. Printed motif density/scale is not approved as final fidelity. Clock medallion, chains, upper drapes, ruffle and ivory cascade remain missing.','Profile views show layered cloth and actual thickness. Back ink and auxiliary hidden pattern are not a complete validated multiview material.','Original Tripo hair remains a solid mass and has345 static contacts at waist. No rig/physics/sewn attachment was approved.'],sourceHashes=dict(savedBlend=a['sourceSHA256']),additionalTripoCredits=0,next='Create whole dressed497 with exact source copies; independent reopen, export and reimport both formats before claiming a publication checkpoint.')
(O/'rear_bow_thin_ink_review_decision_v495.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
print('BOW495_LOCAL_WHOLE_STATIC_WIP_REVIEW_ACCEPTED_NOT_FIDELITY_OR_PUBLICATION')

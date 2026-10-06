"""Apply the actually reviewed491 thin-chain classification, with unchanged certified visibility."""
from pathlib import Path
import json,numpy as np
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';diagnostic=json.loads((O/'rear_bow_thin_ink_classification_diagnostic_v491.json').read_text(encoding='utf-8-sig'))
diagnostic.update(actualDiagnosticPanelInspected=True,thinChainsAndCirclesMoreComplete=True,neutralHighlightsRemainExcludedInsideCloth=True,skinOutsideClothWouldBeWarmButGeometryVisibilityMaskPreventsTransfer=True,acceptedForLocalChromaProjectionOnly=True);(O/'rear_bow_thin_ink_classification_diagnostic_v491.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf-8')
RGB=np.asarray([[.075,.098,.145],[.3,.34,.4],[.2,.2,.2],[1,1,1],[.6,.4,.2]]);warm=(RGB[:,0]-RGB[:,2]*1.05)/(RGB[:,0]+RGB[:,2]+.015);alpha=np.clip((warm-.015)/.13,0,1);assert (alpha[:4]==0).all() and alpha[4]==1
p=R/'Tools/project_coelho_rear_bow_chroma_detail_v489.py';code=p.read_text(encoding='utf-8-sig').replace('v489','v492').replace('BOW489','BOW492').replace('Detail489','Detail492')
code=code.replace('exec(compile(code',"code=code.replace('RGB[...,2]*1.35)/(RGB', 'RGB[...,2]*1.05)/(RGB')\ncode=code.replace('chromaRatioInsteadOfAbsoluteGoldBrightness=True,','chromaRatioInsteadOfAbsoluteGoldBrightness=True,chromaBlueSuppressionFactor=1.05,thinChainDiagnostic491ActuallyReviewed=True,neutralBlueAndWhiteHighlightUnitSamplesPassed=True,')\nexec(compile(code",1)
exec(compile(code,str(p.with_name('project_coelho_rear_bow_thin_ink_v492.py')),'exec'))

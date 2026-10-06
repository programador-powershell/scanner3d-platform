"""Record limited visual/42-frame weight improvement, never final gameplay approval."""
from pathlib import Path
import json,hashlib,datetime
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
c=read(O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/manifest.json');a=read(O/'walk_continuity_independent_REVIEW_v1147/audit.json')
assert c['allFourSameCameraRendersComplete'] and c['sourceAndLibraryUnchanged'] and len(c['renders'])==4
for row in c['renders']:assert sha(R/row['path'])==row['sha256']
assert len(a['baseline']['frames'])==len(a['candidate']['frames'])==42
assert a['candidate']['sourceSHA256']==c['blendSHA256'] and a['candidate']['maxSeamSeparationM']<2e-6
stats={label:{key:max(f['edgeStatistics'][key]['shortRestEdgesExpandedBeyond12cm'] for f in a[label]['frames']) for key in ['all','boots','forearm','sleeve','bootBoundary']} for label in ['baseline','candidate']}
assert stats['candidate']['boots']==0 and stats['candidate']['forearm']==0
assert stats['candidate']['all']<stats['baseline']['all'] and stats['candidate']['bootBoundary']==0
assert sha(Path(c['blend']))==c['blendSHA256']
r=dict(version='v1157',sourceWorkingVersion='v1146',sourceBlend=c['blend'],sourceBlendSHA256=c['blendSHA256'],acceptedForLimitedWholeWeightCheckpointExport=True,allFourNativeRendersActuallyInspected=True,all42FramesIndependentlyEvaluated=True,diagnosticShortEdgeCounts=stats,diagnosticThreshold='rest edge <3cm expanding >12cm; not a fidelity score',physicalSurfaceSeamsVerified=True,differentTouchingLayersMustNotShareWeights=True,geometryAllUVNormalsMaterialsPreserved=True,noCutWeldOrNewAnatomy=True,visualFindings=['previous long boot and forearm strips disappeared in the inspected front/profile study poses','stocking and navy garment weight fields now separate without editing their geometry','remaining shoulder/massive hair distortion and provisional pelvis-bound dress persist'],acceptedForPublication=False,requiresWholeGLBFBXReimportAndActualReview=True,rigFinalApproved=False,canonicalIdentityApproved=False,anatomical168cmVerified=False,hairStrandsComplete=False,clothPhysicsApproved=False,gameplayMotionApproved=False,productionComplete=False,additionalTripoCredits=0,VercelUsed=False,createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
p=O/'native_distinct_walk_visual_review_v1157.json';assert not p.exists();p.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(stats));print('LIMITED_WHOLE_WEIGHT_EXPORT_ACCEPTED_NOT_GAMEPLAY_FINAL')

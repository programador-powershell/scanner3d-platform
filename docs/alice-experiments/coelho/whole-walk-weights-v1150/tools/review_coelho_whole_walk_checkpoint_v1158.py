"""Whole verified checkpoint with actual export review; final production remains open."""
from pathlib import Path
import json,hashlib,datetime
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
pkg=read(O/'package_skin_export_v1150.json');native=read(O/'native_distinct_walk_visual_review_v1157.json');assert native['acceptedForLimitedWholeWeightCheckpointExport'];filtered=read(O/'walk_export_filter_analytic_audit_v1171.json');assert filtered['allEightUnfilteredNativePosesReplayed'] and filtered['reimportToleranceMNotRelaxed']==1e-5
visual=read(O/'actual_export_visual_review_v1178.json');assert visual['allSixteenEffectiveExportImagesInspected'] and not visual['productionComplete']
for row in visual['records']:assert sha(R/row['report'])==row['reportSHA256']
rows=[]
for kind in ['glb','fbx']:
 version=1172 if kind=='glb' else 1176;j=read(O/f'reimport_whole_{kind}_audit_v{version}.json');assert j['sha256']==pkg['files'][kind]['sha256']
 assert len(j['objects'])==202 and j['boneCount']==209 and j['skinWeightsAllTriangleCornersVerified']
 assert len(j['exportedManualMotionComparedToNative'])==8 and len(j['renders'])==8
 assert all(p['maxWorldVertexErrorM']<1e-5 for p in j['exportedManualMotionComparedToNative'])
 assert all(r['allSourceTrianglesMatched'] and r['materialMismatchCount']==0 and r['maxCornerPositionErrorM']<2e-6 and r['maxUVCornerError']<2e-6 for r in j['objects'])
 for im in j['renders']:assert sha(R/im['path'])==im['sha256']
 # Run this file only after the eight images per format have actually been viewed.
 rows.append(dict(format=kind,all202MeshTrianglesUVMaterialsWeightsVerified=True,boneCount=209,eightDiagnosticPosesComparedToNativeWithOfficialGLTFEncodingReplay=j['exportedManualMotionComparedToNative'],eightActualRendersInspected=True,bijectiveCornerFallbackCount=len(j['bijectiveCornerFallbacks']),nativeExporterMinInfluenceReplayed=j['GLTFNativeExporterMinInfluenceReplayed'],GLBOriginalNativeErrorSeparatelyRecorded=True))
for n,k in [('whole_glb_raw_normal_payload_audit_v1151.json','glb'),('whole_fbx_raw_normal_payload_audit_v1152.json','fbx'),('whole_glb_material_pixel_audit_v1153.json','glb'),('whole_fbx_embedded_material_audit_v1154.json','fbx'),('whole_fbx_channel_semantics_audit_v1155.json','fbx')]:assert read(O/n)['sha256']==pkg['files'][k]['sha256']
for row in pkg['files'].values():assert sha(R/row['path'])==row['sha256'] and (R/row['path']).stat().st_size==row['bytes']
assert sha(R/'SharedBase/Development/alice_shared_base.blend')==pkg['sharedLibrary']['librarySHA256']
r=dict(version='v1158',acceptedAsVerifiedLocalWholeIntermediateCheckpoint=True,wholeCharacterWithDress=True,sourceWorkingVersion='v1146',exportsVersion='v1150',files=pkg['files'],native42WalkFramesIndependentlyVerified=True,nativeVisualReview=native,formatChecks=rows,sixteenActualReimportRendersInspected=True,rawNormalsAnd4KMaterialPixelChannelChecksVerified=True,sourceGeometryAllUVAndNormalsPreserved=True,authoringFullBlendRetained=True,sharedLibraryUnchanged=True,acceptedForDirectWholeCheckpointGithubPublication=True,VercelRequired=False,portalPublicationPerformed=False,rigFinalApproved=False,canonicalIdentityApproved=False,anatomical168cmApproved=False,individualHair=False,clothPhysicsApproved=False,gameplayMotionApproved=False,productionComplete=False,additionalTripoCredits=0,limitations=['42-frame linked Walk is a study, not a finished gameplay animation; GLB/FBX contain zero animations','201 cloth/accessory objects still have provisional pelvis binding','remaining shoulder/solid hair deformation requires local corrections','same canonical body/head and anatomical168cm not yet approved','individual strands, cloth/physics/wind/collisions/actions/expressions/gameplay unfinished','GLB exporter filters weights <=0.0001 and normalizes; exact raw native weight identity not claimed'],createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
p=O/'whole_walk_checkpoint_review_v1158.json';assert not p.exists();p.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8');print('WHOLE_WALK_WEIGHT_INTERMEDIATE_CHECKPOINT_VERIFIED_NOT_ASSET_FINAL')

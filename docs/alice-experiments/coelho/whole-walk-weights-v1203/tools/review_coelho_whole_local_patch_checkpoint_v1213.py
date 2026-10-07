"""Run after twenty current reimport renders have actually been inspected."""
from pathlib import Path
import json,hashlib,datetime
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
pkg=read(O/'package_skin_export_v1203.json');native=read(O/'native_left_patch_whole_visual_review_v1201.json');filtered=read(O/'walk_export_filter_analytic_audit_v1205.json');assert native['acceptedForLimitedWholeWeightCheckpointExport'] and filtered['allEightUnfilteredNativePosesReplayed'] and filtered['reimportToleranceMNotRelaxed']==1e-5
rows=[];actualImages=[]
for kind,version in [('glb',1206),('fbx',1207)]:
    p=O/f'reimport_whole_{kind}_audit_v{version}.json';j=read(p);assert j['sha256']==pkg['files'][kind]['sha256'] and len(j['objects'])==202 and j['boneCount']==209
    assert j['skinWeightsAllTriangleCornersVerified'] and j['allSourceTrianglesMatchedStillMandatory'] and j['allImporterNormalEncodingReplaysVerified']
    assert len(j['exportedManualMotionComparedToNative'])==8 and len(j['renders'])==10
    assert all(p['maxWorldVertexErrorM']<1e-5 for p in j['exportedManualMotionComparedToNative'])
    assert all(r['allSourceTrianglesMatched'] and r['materialMismatchCount']==0 and r['maxCornerPositionErrorM']<2e-6 and r['maxUVCornerError']<2e-6 for r in j['objects'])
    for im in j['renders']:assert sha(R/im['path'])==im['sha256'];actualImages.append(im)
    rows.append(dict(format=kind,report=p.relative_to(R).as_posix(),reportSHA256=sha(p),all202MeshesVerified=True,eightActualDiagnosticPoses=j['exportedManualMotionComparedToNative'],tenActualWholeRendersInspected=True,officialGLTFEncodingFilterAccountedFor=True))
raw=[('whole_glb_raw_normal_payload_audit_v1208.json','glb'),('whole_fbx_raw_normal_payload_audit_v1209.json','fbx'),('whole_glb_material_pixel_audit_v1210.json','glb'),('whole_fbx_embedded_material_audit_v1211.json','fbx'),('whole_fbx_channel_semantics_audit_v1212.json','fbx')]
for n,k in raw:assert read(O/n)['sha256']==pkg['files'][k]['sha256']
for row in pkg['files'].values():assert sha(R/row['path'])==row['sha256'] and (R/row['path']).stat().st_size==row['bytes']
assert sha(R/'SharedBase/Development/alice_shared_base.blend')==pkg['sharedLibrary']['librarySHA256']
n=read(O/'left_patch_weights_whole_CANDIDATE_v1200/manifest.json');assert n['allFiveSameCameraRendersComplete'] and n['all42NativeFramesVerified']
for row in n['renders']:assert sha(R/row['path'])==row['sha256']
visual=dict(version='v1213',allTwentyCurrentReimportImagesActuallyInspected=True,allFiveNativeWholeImagesActuallyInspected=True,records=rows,actualImages=actualImages,observation='Local source fragments behind both sleeves have improved weight continuity. Remaining solid hair/upper shoulder spikes and provisional cloth binding visible; same canonical body/head, anatomical168cm, individual hair and physics/gameplay unapproved.',productionComplete=False)
(O/'actual_export_visual_review_v1213.json').write_text(json.dumps(visual,indent=2),encoding='utf-8')
review=dict(version='v1213',acceptedAsVerifiedLocalWholeIntermediateCheckpoint=True,acceptedForDirectWholeCheckpointGithubPublication=True,wholeCharacterWithDress=True,sourceWorkingVersion='v1200',exportsVersion='v1203',files=pkg['files'],nativeVisualReview=native,native42WalkFramesIndependentlyVerified=True,twentyActualReimportRendersInspected=True,fiveActualNativeWholeRendersInspected=True,formatChecks=rows,rawNormalsAnd4KMaterialPixelChannelChecksVerified=True,sourceGeometryAllUVAndNormalsPreserved=True,authoringFullBlendRetained=True,sharedLibraryUnchanged=True,VercelRequired=False,portalPublicationPerformed=False,productionComplete=False,additionalTripoCredits=0,limitations=['42-frame linked Walk is a study; exports contain zero animations','201 garment/accessory objects still have provisional pelvis binding','Other solid hair/shoulder deformation remains: global sum681 and max116 in the native Walk diagnostic','Canonical common body/head and anatomical168cm not approved','Individual strands, cloth/physics/wind/collisions/actions/expressions/gameplay unfinished','GLB native exporter filters tiny weights; effect independently reproduced without relaxing tolerance'],createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
(O/'whole_local_patch_checkpoint_review_v1213.json').write_text(json.dumps(review,indent=2,ensure_ascii=False),encoding='utf-8');print('CURRENT_WHOLE_CHECKPOINT_REIMPORT_AND_VISUAL_REVIEW_VERIFIED_NOT_FINAL_ASSET')

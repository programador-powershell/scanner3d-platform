from pathlib import Path
import json,hashlib,datetime
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v417.json');q=read(O/'apron_ornament_pbr_atlas_reopen_audit_v419.json');u=read(O/'apron_ornament_continuous_uv_audit_v418.json');g=read(O/'apron_ornament_front_corner_review_decision_v415.json')
assert sha(R/a['path'])==a['sha256'] and a['sourceCandidate']=='v411' and a['allGeometryPositionsAndFacesPreserved'] and g['acceptedForOwnUVPBRBake']
assert q['sourceSHA256']==u['sourceSHA256']==a['sha256'] and q['geometryAndGroupsExactlyPreservedFromStaticallyVerified411']
assert len(q['preservation'])==5 and all(x['positionsFacesGroupsSmoothAndMaterialIndicesExactlyPreserved'] and x['ownUVExactlyMatchesSavedAuthorAudit'] for x in q['preservation'])
assert u['continuousUVOverlapPairs']==0 and u['unitTestsPassed'] and q['ownImages4KVerified'] and len(q['packedMaps'])==4
assert len(q['renders'])==5
for row in q['renders']:assert sha(R/row['path'])==row['sha256'];row['actualImageInspected']=True
r=dict(version='v420',createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),sourceCandidate='v417',sourceCandidateSHA256=a['sha256'],allImagesActuallyInspected=True,inspectedSavedRenders=q['renders'],continuousUVOverlapPairs=0,ownPackedPBR4KReopenedAndVerified=True,geometryExactlyPreservedFrom411=True,staticSavedTopology412AndContacts413ApplicableBecauseExact411Geometry=True,acceptedForWholeStaticWIPIntegrationReview=True,actualGLBFBXFormatsStillRequireWholeExportReimport=True,newPhotoProjectionPerformed=False,newHighPolyNormalDetailCreated=False,opaqueBlueApproximationNotPhysicalSapphire=True,acceptedForFinalAssetOrGameplay=False,referenceFidelityApproved=False,rigged=False,physicsVerified=False,notIntegrated=True,notPublished=True,productionComplete=False,publicWholeCheckpointRemains='v382')
(O/'apron_ornament_atlas_review_decision_v420.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print('LOCAL417_REVIEW420_ACCEPTS_WHOLE_INTEGRATION_ONLY')

from pathlib import Path
import json,hashlib,datetime
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';H=R/'Handoff/alice_coelho_apron_per_texel_v023';A=R/'Assets/Characters/alice_coelho'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v370.json');q=read(O/'apron_ornament_pbr_atlas_reopen_audit_v371.json');u=read(O/'apron_ornament_continuous_uv_audit_v372.json');e=read(O/'apron_ornament_material_format_payload_v373.json');f=read(O/'apron_ornament_material_actual_reimport_audit_v374.json');c=read(O/'apron_ornament_material_packed_channel_audit_v375.json');g=read(O/'apron_ornament_compact_review_decision_v366.json')
assert sha(R/a['path'])==a['sha256']
assert all(d['sourceSHA256']==a['sha256'] for d in [q,u,e,f,c])
assert a['sourceCandidate']=='v361' and a['allGeometryPositionsAndFacesPreserved'] and g['acceptedForOwnUVPBRBake']
assert len(q['preservation'])==5 and all(x['positionsFacesGroupsSmoothAndMaterialIndicesExactlyPreserved'] and x['ownUVExactlyMatchesSavedAuthorAudit'] for x in q['preservation'])
assert u['continuousUVOverlapPairs']==0 and u['unitTestsPassed'] and c['GLBPackedMetalRoughChannelsExactlyMatchSource']
assert f['geometryAndUVJointCornerCorrespondencePassed'] and f['images4KBoundAfterBothActualReimports'] and e['FBXAllEmbeddedImagesExact']
assert len(q['renders'])==5 and len(f['renders'])==3
for row in q['renders']+f['renders']:assert sha(R/row['path'])==row['sha256'];row['actualImageInspected']=True
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
d=dict(version='v376',createdAt=now,sourceCandidate='v370',sourceCandidateSHA256=a['sha256'],allImagesActuallyInspected=True,inspectedSavedRenders=q['renders'],inspectedActualFormatReimportRenders=f['renders'],continuousUVOverlapPairs=0,ownPackedPBR4KAndActualFormatReimportVerified=True,geometryExactlyPreservedFrom361=True,staticSavedTopology362AndContacts364ApplicableBecauseExact361Geometry=True,legacy371Key267CorrectedByAuthorAndActualPreservationTo361=True,compactCornerGeometryAndBlueMaterialChangedSincePublished323=True,newPhotoProjectionPerformed=False,newHighPolyNormalDetailCreated=False,opaqueBlueApproximationNotPhysicalSapphire=True,acceptedForWholeStaticWIPIntegrationReview=True,acceptedForFinalAssetOrGameplay=False,referenceFidelityApproved=False,rigged=False,physicsVerified=False,notIntegrated=True,notPublished=True,productionComplete=False,publicWholeCheckpointRemains='v323')
write(O/'apron_ornament_atlas_review_decision_v376.json',d)
study=dict(version='v370_review376',path=a['path'],sha256=a['sha256'],bytes=a['bytes'],maps=a['maps'],newObjects=[x['object'] for x in a['newObjects']],review='Blender/Work/alice_coelho/tripo_h31_budget55_v001/apron_ornament_atlas_review_decision_v376.json',ownUVAndPackedPBR4KVerified=True,continuousUVOverlapPairs=0,staticGeometryPreservedFrom361=True,actualGLBFBXMaterialReimportVerified=True,notIntegrated=True,notPublished=True,rigged=False,physicsVerified=False,productionComplete=False)
for p in [H/'manifest.json',O/'Dress/quad_authoring_current.json']:
 v=read(p);v.update(latestLocalOrnamentStudy=study,latestLocalOrnamentStudyPending=None,lastLocalProgressAt=now);write(p,v)
w=read(A/'working_checkpoint.json');w.update(latestLocalOrnamentStudy=study,latestLocalOrnamentStudyPending=None,manifest=read(H/'manifest.json'),updatedAt=now);write(A/'working_checkpoint.json',w)
v=read(O/'continuation_state_v023.json');v.update(latestLocalOrnamentStudy=study,latestLocalCandidatePendingReview=None,activeOwnBlenderJobs=[],updatedAt=now,nextLocalOrnamentStep='Integrate370 into complete dressed Alice, reopen/render whole, export/reimport full GLB/FBX and publish whole checkpoint before another part/movement. Continue production, no new Tripo.');write(O/'continuation_state_v023.json',v)
print('COELHO370_REVIEW376_WHOLE_INTEGRATION_ONLY_NOT_FINAL')

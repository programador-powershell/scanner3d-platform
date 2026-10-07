from pathlib import Path
import json,hashlib
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';T=R/'Tools';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
c=read(R/'COELHO_CURRENT_WHOLE_SKIN_CHECKPOINT.json');assert c['version']=='v1216' and c['GitEvidenceByteIntegrity']['allTrackedFileBytesVerified']
d=read(O/'remaining_patch_original_uv_REVIEW_v1222/audit.json');assert len(d['renders'])==20
for r in d['renders']:assert hashlib.sha256((R/r['path']).read_bytes()).hexdigest()==r['sha256']
review=dict(version='v1225',allTwentyActualImagesInspected=True,acceptedForLimitedTopologyWeightContinuityStudy=True,selectedUVRoot=75839,identification='Blue/gold corset side with cream front panel below left breast; identified in isolated original UV and four exact-source contextual views.',mixedUpperRootsNotClassifiedAsEntireHair=[31911,50222,76235,78840],noHairFaceNeckRemovalAuthorizedByThisStudy=True,noGeometryUVNormalsMaterialsEdited=True,finalCorsetFidelityOrClothRigApproved=False,productionComplete=False)
(O/'corset_patch_weight_review_v1225.json').write_text(json.dumps(review,indent=2),encoding='utf-8')
s=(T/'study_coelho_left_patch_topology_weights_v1199.py').read_text(encoding='utf-8-sig').replace('1199','1225')
s=s.replace("c['version']=='v1182'","c['version']=='v1216'")
s=s.replace('whole_skin_export_source_character_v1148.npz','whole_skin_export_source_character_v1202.npz').replace('whole_skin_walk_world_matrices_v1170.npz','whole_skin_walk_world_matrices_v1204.npz').replace('package_skin_export_v1150.json','package_skin_export_v1203.json')
s=s.replace('remaining_walk_regions_REVIEW_v1196','remaining_walk_regions_REVIEW_v1221').replace('actual_weights_walk_frame31_v1196.npz','actual_weights_walk_frame31_v1221.npz')
s=s.replace('selectedRoots=np.asarray([75585,77234,77809,81623,81651,85800])','selectedRoots=np.asarray([75839])')
marker="eligibleVertex=np.isin(roots,selectedRoots)"
insert="""# Include the observed peak corset frame27, rather than relying only on frame31.
boneIndexSeed={n:i for i,n in enumerate(pkg['boneNames'])};js=np.argsort(W,axis=1)[:,-4:];idsSeed=np.asarray([boneIndexSeed[str(n)] for n in names])[js];restSeed=np.asarray([b['matrixWorld'] for b in pkg['bones']]);deltaSeed=(walk['worldPose'][26]@np.linalg.inv(restSeed))[idsSeed];q27=np.sum(np.einsum('nvij,nj->nvi',deltaSeed,np.column_stack([P,np.ones(len(P))]))[:,:,:3]*np.take_along_axis(W,js,axis=1)[:,:,None],axis=1);bad27=(rest>1e-5)&(rest<.03)&(np.linalg.norm(q27[edges[:,0]]-q27[edges[:,1]],axis=1)>.12);v27=np.unique(edges[bad27]);seedVertices=np.unique(np.concatenate([seedVertices,v27[np.isin(roots[v27],selectedRoots)]]));seedGroups=np.unique(groups[seedVertices]);assert len(seedVertices)==5
"""
assert marker in s;s=s.replace(marker,insert+marker)
s=s.replace('left_patch_weight_review_v1225.json','corset_patch_weight_review_v1225.json').replace("review['allEightActualImagesInspected']","review['allTwentyActualImagesInspected']")
s=s.replace('sourceDomainIsNotYetIdentifiedVisually=True','surfaceIsVisuallyIdentifiedCorset=True').replace('previousRightPatch1191Preserved=True','previousWhole1200OutsideDomainPreserved=True').replace('sameOriginalWalkReference1170=True','sameActualOriginalWalk1204Reference=True').replace('local_patch_weights_whole_CANDIDATE_v1191/manifest.json','left_patch_weights_whole_CANDIDATE_v1200/manifest.json')
check="assert sum(r['baseline']['allBad'] for r in records)==read(O/'remaining_walk_regions_REVIEW_v1221/audit.json')['totalBadEdgeOccurrences']\n"
s=s.replace("report=dict(version='v1225'",check+"report=dict(version='v1225'")
(T/'study_coelho_corset_patch_topology_weights_v1225.py').write_text(s,encoding='utf-8')
print('VISUAL_CLOTHING_DOMAIN_REVIEW_AND_LOCAL_STUDY_PREPARED_NO_GEOMETRY_EDIT')

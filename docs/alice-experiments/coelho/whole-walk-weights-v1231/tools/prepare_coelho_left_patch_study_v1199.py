from pathlib import Path
import json,hashlib
R=Path('F:/Alice/SharedProduction');T=R/'Tools';O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
r=read(O/'left_patch_original_uv_REVIEW_v1197/audit.json');assert len(r['renders'])==8
for row in r['renders']:assert hashlib.sha256((R/row['path']).read_bytes()).hexdigest()==row['sha256']
review=dict(version='v1199',allEightActualImagesInspected=True,roots=r['roots'],acceptedForLimitedTopologyWeightContinuityStudy=True,observation='Six narrow dark source fragments lie below solid hair beside left puff sleeve. In actual Walk31, adjacent vertices pull apart into long triangles. UV is original and too dark to certify cloth-versus-hair ownership. Study changes only existing weights along actual triangle topology, not geometry, materials, semantic final classification or final hairstyle.',semanticHairOrClothFinalClassificationApproved=False,finalPhysicsApproved=False,productionComplete=False)
(O/'left_patch_weight_review_v1199.json').write_text(json.dumps(review,indent=2),encoding='utf-8')
s=(T/'study_coelho_local_patch_topology_weights_v1189.py').read_text(encoding='utf-8-sig').replace('v1189','v1199')
old="P=M['positions'].astype(np.float64);W=M['weights'].astype(np.float64);names=M['boneNames'];"
new="""P=M['positions'].astype(np.float64);names=M['boneNames'];raw=np.load(O/'remaining_walk_regions_REVIEW_v1196/actual_weights_walk_frame31_v1196.npz');W=raw['weights'].astype(np.float64);assert W.shape==M['weights'].shape;"""
assert old in s;s=s.replace(old,new)
s=s.replace("bad=read(O/'remaining_walk_edge_regions_v1164.json')['edges'];seedVertices=np.unique([v for e in bad for v in e['vertices']]);seedGroups=np.unique(groups[seedVertices]);assert all(roots[seedVertices]==38212)","selectedRoots=np.asarray([75585,77234,77809,81623,81651,85800]);bad=read(O/'remaining_walk_regions_REVIEW_v1196/audit.json')['all42Frames'][30]['edges'];seedVertices=np.unique([v for e in bad for v in e['vertices'] if roots[v] in selectedRoots]);seedGroups=np.unique(groups[seedVertices]);assert len(seedVertices)>0")
s=s.replace("eligibleVertex=(roots==38212)&np.isin(roles,[0,2,3])&(np.abs(P[:,0])>.075)&(P[:,2]>1.035)&(P[:,2]<1.29)&~M['boots']&~M['positiveHand']&~M['negativeHand']","eligibleVertex=np.isin(roots,selectedRoots)&np.isin(roles,[0,2,3])&~M['boots']&~M['positiveHand']&~M['negativeHand']")
s=s.replace("review=read(O/'local_patch_weight_review_v1188.json');assert review['acceptedForLimitedWeightContinuityStudy'] and review['allNineActualDiagnosticViewsInspected'];assert len(ids)==95","review=read(O/'left_patch_weight_review_v1199.json');assert review['acceptedForLimitedTopologyWeightContinuityStudy'] and review['allEightActualImagesInspected'];assert 50<len(ids)<500")
s=s.replace("assert np.abs(new-new[first[groups]]).max()<1e-7","assert np.abs(new-new[first[groups]]).max()<1e-7")
s=s.replace("if int(f)==11:","if int(f)==31:").replace("true=np.load(O/'whole_skin_motion_walk_study_frame11_v1170.npz')['positions'];","true=raw['positions'];")
s=s.replace('frame11_topology_comparison_v1199','frame31_topology_comparison_v1199').replace('baselineFrame11ReproducedMaxM','baselineFrame31ReproducedMaxM')
s=s.replace("currentWholeGitCheckpoint=c['GitHubCheckpoint']['sourceCommit'],sourceBlend=c['files']['blend']","currentWholeGitCheckpoint=c['GitHubCheckpoint']['sourceCommit'],sourceBlend=read(O/'local_patch_weights_whole_CANDIDATE_v1191/manifest.json')['blend'],previousRightPatch1191Preserved=True")
p=T/'study_coelho_left_patch_topology_weights_v1199.py';assert not p.exists();p.write_text(s,encoding='utf-8');print('LEFT_PATCH_STUDY_PREPARED_NO_SOURCE_EDIT')

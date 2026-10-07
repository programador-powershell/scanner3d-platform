from pathlib import Path
import json
R=Path('F:/Alice/SharedProduction');T=R/'Tools';O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
a=read(O/'shoulder_topology_weight_STUDY_v1199/audit.json');assert len(a['all42Frames'])==42 and a['outsideDomainWeightsExactlyPreserved'] and all(r['candidate']['localBad']==0 for r in a['all42Frames'])
s=(T/'author_coelho_local_patch_weights_whole_v1191.py').read_text(encoding='utf-8-sig')
s=s.replace("D=O/'local_patch_weights_whole_CANDIDATE_v1191'","D=O/'left_patch_weights_whole_CANDIDATE_v1200'")
s=s.replace("source=R/c['currentBlend'];assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==c['files']['blend']['sha256']","sourceManifest=read(O/'local_patch_weights_whole_CANDIDATE_v1191/manifest.json');source=Path(sourceManifest['blend']);assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==sourceManifest['blendSHA256']")
s=s.replace("trial=read(O/'shoulder_topology_weight_STUDY_v1189/audit.json');review=read(O/'local_patch_weight_review_v1188.json');assert review['allNineActualDiagnosticViewsInspected']","trial=read(O/'shoulder_topology_weight_STUDY_v1199/audit.json');review=read(O/'left_patch_weight_review_v1199.json');assert review['allEightActualImagesInspected']")
s=s.replace("N=np.load(O/'shoulder_topology_weight_STUDY_v1189/character_weights_v1189.npz')","N=np.load(O/'shoulder_topology_weight_STUDY_v1199/character_weights_v1199.npz')")
start=s.index("raw=np.load(O/'whole_skin_export_source_character_v1148.npz')");end=s.index('for group in ob.vertex_groups:',start)
replacement="""raw=np.load(O/'remaining_walk_regions_REVIEW_v1196/actual_weights_walk_frame31_v1196.npz');rawDense=raw['weights'];assert np.array_equal(old,rawDense),'Actual1191 native weights differ from independently reconstructed raw1148 plus108 reviewed changes'
selected=N['changed'];assert int(selected.sum())==trial['changedVertices']
new=old.copy();new[selected]=N['weights'][selected];assert np.array_equal(new[~selected],old[~selected])
changed=np.any(np.abs(new-old)>1e-7,axis=1);ids=np.flatnonzero(changed);assert int(changed.sum())==trial['changedVertices']
assert np.abs(new-new[np.unique(N['physicalSurfaceGroup'],return_index=True)[1][N['physicalSurfaceGroup']]]).max()<1e-7
"""
s=s[:start]+replacement+s[end:]
s=s.replace('alice_coelho_complete_local_patch_weight_CANDIDATE_v1191.blend','alice_coelho_complete_left_patch_weight_CANDIDATE_v1200.blend').replace("version='v1191'","version='v1200'")
s=s.replace("sourceSHA256=c['files']['blend']['sha256']","sourceSHA256=sourceManifest['blendSHA256']")
s=s.replace('primaryPatchVertices=95,samePositionPhysicalRoleUVSeamCounterparts=13,actualNativeWeightsExactlyMatchRawSource1148=True,diagnosticNPZMaximumDifferenceFromActualNativeWeights=diagnosticNPZDifference,',"previousRightPatch1191Preserved=True,actualNativeWeightsExactlyMatchIndependentRaw1191=True,selectedRoots=review['roots'],")
s=s.replace('if frame==11:', 'if frame==31:').replace("O/'shoulder_topology_weight_STUDY_v1189/frame11_topology_comparison_v1189.npz'","O/'shoulder_topology_weight_STUDY_v1199/frame31_topology_comparison_v1199.npz'").replace('nativeFrame11MatchesIndependentAnalyticCandidateMaxM','nativeFrame31MatchesIndependentAnalyticCandidateMaxM')
s=s.replace("sha(source)==c['files']['blend']['sha256']","sha(source)==sourceManifest['blendSHA256']").replace("frame{frame}_v1191.png","frame{frame}_v1200.png")
# Preserve the four previous camera/frame choices and add left-profile31 for the local target.
s=s.replace("(11,'profile_quarter',(-4,0,0))]", "(11,'profile_quarter',(-4,0,0)),(31,'left_profile_threequarter',(4,0,0))]")
s=s.replace('allFourSameCameraRendersComplete','allFiveSameCameraRendersComplete')
p=T/'author_coelho_left_patch_weights_whole_v1200.py';assert not p.exists();p.write_text(s,encoding='utf-8');print('NATIVE_WHOLE_CANDIDATE_PREPARED_ONLY_SCOPED_WEIGHTS')

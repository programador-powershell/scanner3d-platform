from pathlib import Path
R=Path('F:/Alice/SharedProduction');T=R/'Tools'
s=(T/'audit_coelho_remaining_walk_regions_v1196.py').read_text(encoding='utf-8-sig')
s=s.replace('1196','1221').replace('after local1191 weights','on actual whole1200 native weights')
s=s.replace("whole_skin_export_source_character_v1148.npz","whole_skin_export_source_character_v1202.npz").replace('whole_skin_walk_world_matrices_v1170.npz','whole_skin_walk_world_matrices_v1204.npz').replace('package_skin_export_v1150.json','package_skin_export_v1203.json')
s=s.replace(";N=np.load(O/'shoulder_topology_weight_STUDY_v1189/character_weights_v1189.npz')",'')
s=s.replace("changed=N['changed'];W[changed]=N['weights'][changed]","assert np.array_equal(M['positions'],ex['positions']);assert len(pkg['boneNames'])==209")
s=s.replace("nativeCandidate='local_patch_weights_whole_CANDIDATE_v1191',authoritativeOutsideWeightsFromRaw1148=True,localPatch1189NotGlobalZero=True","nativeCandidate='left_patch_weights_whole_CANDIDATE_v1200',allAuthoritativeWeightsFromCurrentRaw1202=True,referenceWorldMatricesFromCurrentNative1204=True,globalZeroNotClaimed=True")
assert 'N[' not in s and 'package_skin_export_v1150' not in s
(T/'audit_coelho_actual_remaining_walk_regions_v1221.py').write_text(s,encoding='utf-8')
print('READONLY_CURRENT_RAW_WEIGHT_AUDIT_PREPARED')

from pathlib import Path
import json,numpy as np,hashlib
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';T=R/'Tools';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
pkg=read(O/'package_skin_export_v1203.json');m=read(O/'whole_skin_motion_reference_v1204.json');assert m['walkReferenceMatchesIndependentCandidateSourceFrame31MaxM']<2e-6;walk=np.load(O/'whole_skin_walk_world_matrices_v1204.npz');assert np.array_equal(walk['boneNames'],np.asarray(pkg['boneNames']))
poses={r['label']:np.load(R/r['path'])['worldPose'].tolist() for r in m['poses']}
for i,f in enumerate(walk['frames']):poses['walk_frame_'+str(int(f))]=walk['worldPose'][i].tolist()
data=dict(names=pkg['boneNames'],rest=[b['matrixWorld'] for b in pkg['bones']],poses=poses,frameRate=float(walk['frameRate']),walkFrames=42,sourceBlendSHA256=pkg['files']['blend']['sha256'],manualAndOriginalLinkedWalkStudyOnly=True,gameplayApproved=False,clothPhysicsApproved=False,hairStrandsComplete=False)
p=O/'browser_pose_data_v1219.json';assert not p.exists();p.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
s=(T/'serve_coelho_exact_matrix_preview_v1179.cjs').read_text(encoding='utf-8-sig').replace('v1179','v1219').replace('v1150','v1203').replace('v1146','v1200').replace('browser_pose_data_v1175','browser_pose_data_v1219')
s=s.replace('Pesos corrigidos nas botas e punhos.','Pesos corrigidos em fragmentos próximos às mangas, botas e punhos.')
p=T/'serve_coelho_current_whole_preview_v1219.cjs';assert not p.exists();p.write_text(s,encoding='utf-8');print('CURRENT_WHOLE_PREVIEW_PREPARED_SOURCE1200_EXPORT1203_NOT_YET_BROWSER_VERIFIED')

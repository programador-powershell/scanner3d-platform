"""Actual whole GLB preview with original native bone matrices; no game/physics claim."""
from pathlib import Path
import json,numpy as np,hashlib
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';T=R/'Tools';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
pkg=read(O/'package_skin_export_v1150.json');m=read(O/'whole_skin_motion_reference_v1170.json');assert m['walkReferenceMatchesIndependentOriginalSourceFrame11MaxM']==0;walk=np.load(O/'whole_skin_walk_world_matrices_v1170.npz');assert np.array_equal(walk['boneNames'],np.asarray(pkg['boneNames']))
poses={r['label']:np.load(R/r['path'])['worldPose'].tolist() for r in m['poses']}
for i,f in enumerate(walk['frames']):poses['walk_frame_'+str(int(f))]=walk['worldPose'][i].tolist()
data=dict(names=pkg['boneNames'],rest=[b['matrixWorld'] for b in pkg['bones']],poses=poses,frameRate=float(walk['frameRate']),walkFrames=42,sourceBlendSHA256=pkg['files']['blend']['sha256'],manualAndOriginalLinkedWalkStudyOnly=True,gameplayApproved=False,clothPhysicsApproved=False,hairStrandsComplete=False)
p=O/'browser_pose_data_v1175.json';assert not p.exists();p.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
s=(T/'serve_coelho_semantic_skin_preview_v1122.cjs').read_text(encoding='utf-8-sig').replace('v1102','v1150').replace('v1097','v1146').replace('v1122','v1175').replace('browser_pose_data_v1119','browser_pose_data_v1175')
s=s.replace('Teste parcial dos pesos. Fios individuais, tecido, ações e física ainda pendentes.','Pesos corrigidos nas botas e punhos. Estudo Walk original; corpo/rosto canônicos, 168 cm, fios, tecido e gameplay ainda pendentes.')
s=s.replace('</nav><p id="pose-status">','</nav><nav><button data-pose="walk_study_frame1">Walk 1</button><button data-pose="walk_study_frame11">Walk 11</button><button data-pose="walk_study_frame31">Walk 31</button><button data-pose="walk_study_frame42">Walk 42</button><button id="play-walk">Reproduzir estudo Walk</button></nav><p id="pose-status">')
s=s.replace("left:[-4,0,0],right:[4,0,0]","left:[4,0,0],right:[-4,0,0]")
s=s.replace("renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera)});", "let playing=false,walkStarted=0,lastWalkFrame=0;renderer.setAnimationLoop(()=>{if(playing&&model&&poseData){const frame=1+Math.floor((performance.now()-walkStarted)/1000*poseData.frameRate)%42;if(frame!==lastWalkFrame){lastWalkFrame=frame;applyPose('walk_frame_'+frame)}}controls.update();renderer.render(scene,camera)});")
s=s.replace("b.onclick=()=>applyPose(b.dataset.pose)","b.onclick=()=>{playing=false;document.getElementById('play-walk').textContent='Reproduzir estudo Walk';applyPose(b.dataset.pose)}")
s=s.replace("manualPoseTestsOnly:true","manualAndOriginalLinkedWalkStudyOnly:true,walkFrames:42,canonicalIdentityApproved:false,anatomical168cmVerified:false,individualHairComplete:false,clothPhysicsApproved:false,gameplayApproved:false")
s=s.replace("poseQA[label]={changedJointWorldMatrices:moved,maxJointMatrixDifference:max};", "let desiredError=0;for(const[n,b]of bones)desiredError=Math.max(desiredError,...b.matrixWorld.elements.map((x,i)=>Math.abs(x-desired.get(n).elements[i])));poseQA[label]={changedJointWorldMatrices:moved,maxJointMatrixDifference:max,maxDesiredJointWorldComponentError:desiredError};")
s=s.replace("fetch('/poses.json')", "document.getElementById('play-walk').onclick=()=>{playing=!playing;walkStarted=performance.now();lastWalkFrame=0;document.getElementById('play-walk').textContent=playing?'Pausar estudo Walk':'Reproduzir estudo Walk'};fetch('/poses.json')")
p=T/'serve_coelho_true_walk_preview_v1175.cjs';assert not p.exists();p.write_text(s,encoding='utf-8');print('TRUE_WALK_LOCAL_PREVIEW_PREPARED_NOT_STARTED_NOT_GAMEPLAY')

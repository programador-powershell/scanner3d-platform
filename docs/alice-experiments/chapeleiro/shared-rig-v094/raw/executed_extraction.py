import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
rpath=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v093/generation.json');r=json.loads(rpath.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(r['editableBlend'])==r['editableBlendSha256'];out=rpath.parent/'ivory_cloth_bake_seed_v001';assert not out.exists();out.mkdir()
bpy.ops.wm.open_mainfile(filepath=r['editableBlend']);rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');names=[b.name for b in rig.data.bones]
probe=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/ivory_cloth_thin_colliders_v001');j=json.loads((probe/'actual_continuous_solver_motion.json').read_text(encoding='utf-8'));a=np.load(j['dataFile']);assert a['bone_names'].tolist()==names
cage=bpy.data.objects[j['clothCage']];points=np.array([cage.matrix_world@v.co for v in cage.data.vertices],np.float32);assert np.abs(points-a['rest_points']).max()<1e-7
weights=np.zeros((len(points),len(names)),np.float32);lookup={g.index:names.index(g.name) for g in cage.vertex_groups if g.name in names}
for v in cage.data.vertices:
 for g in v.groups:
  if g.group in lookup:weights[v.index,lookup[g.group]]=g.weight
assert np.abs(weights.sum(1)-1).max()<1e-5
world=np.asarray(rig.matrix_world);inv=np.linalg.inv(world);hom=np.c_[points,np.ones(len(points))];errors=[]
for f in [0,11,19,28]:
 mats=np.array([world@m@inv for m in a['rig_deformations'][f]]);posed=np.zeros((len(points),3))
 for k in range(len(names)):
  ids=np.flatnonzero(weights[:,k]>0)
  if len(ids):posed[ids]+=(hom[ids]@mats[k].T)[:,:3]*weights[ids,k,None]
 errors.append(float(np.abs(posed-a['actual_skin_targets'][f]).max()))
assert max(errors)<1e-6
file=out/'actual_ivory_skin_seed.npz';np.savez_compressed(file,rest_points=points,weights=weights,bone_names=np.array(names),bind_matrices=np.array([np.asarray(b.matrix_local) for b in rig.data.bones]),rig_world=world,ivory_bone_indices=np.array([i for i,n in enumerate(names) if n.startswith('IvoryCloth_')]),bone_parents=np.array([names.index(b.parent.name) if b.parent else -1 for b in rig.data.bones]))
record={'parentEditableSha256':r['editableBlendSha256'],'sourcePhotoSha256':j['sourcePhotoSha256'],'actualPhysicsDataSha256':j['dataSha256'],'actualCageVertices':len(points),'actualRigBones':len(names),'actualIvoryBones':sum(n.startswith('IvoryCloth_') for n in names),'actualSkinTargetReconstructionErrors':errors,'dataFile':str(file),'dataSha256':sha(file),'sourceEditableUnchanged':sha(r['editableBlend'])==r['editableBlendSha256'],'responseFitted':False,'responseBaked':False,'finalFbxExported':False}
(out/'seed.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n');print('ACTUAL_IVORY_BAKE_SEED',len(points),max(errors),flush=True)

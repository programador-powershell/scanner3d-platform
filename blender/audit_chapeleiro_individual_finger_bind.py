"""Verify actual editable finger bones and exported joint heads, without saving."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--measurement-data',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
path=Path(args.generation);g=json.loads(path.read_text(encoding='utf-8'))
guides=json.loads((path.parent/'native_individual_finger_targets.json').read_text())
assert sha(g['editableBlend'])==g['editableBlendSha256']
assert sha(path.parent/'native_individual_finger_targets.json')==g['nativeIndividualFingerGuideSha256']
assert sha(g['exports']['whole']['sourcePhoto'])==guides['sourcePhotoSha256']
data=np.load(args.measurement_data);points=data['points'];faces=data['faces'];classes=data['arm_classes']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
rig=rigs[0];assert len(rig.data.bones)==173
skin=json.loads((path.parent/'skin_audit.json').read_text())
obj=bpy.data.objects[next(p['mesh'] for p in skin['pieces'] if p['role']=='whole_native')]
xyz=np.empty(len(obj.data.vertices)*3,np.float32);obj.data.vertices.foreach_get('co',xyz)
matrix=np.asarray(obj.matrix_world)
actual_points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
loops=np.empty(len(obj.data.loops),np.int32);obj.data.loops.foreach_get('vertex_index',loops)
assert actual_points.shape==points.shape and np.array_equal(loops.reshape(-1,3),faces)
surface_error=float(np.max(np.abs(actual_points-points)))
assert surface_error<1e-8,'The measured native hand surface changed.'
rows=[];actual_bones={}
for side,sign in [('Left',1),('Right',-1)]:
    triangles=actual_points[faces[np.all(classes[faces]==sign,axis=1)]]
    for name,target in guides['boneTargets'].items():
        if not name.startswith(side):continue
        bone=rig.data.bones[name]
        head=np.asarray(rig.matrix_world@bone.head_local)
        tail=np.asarray(rig.matrix_world@bone.tail_local)
        target_error=max(float(np.linalg.norm(head-target['head'])),float(np.linalg.norm(tail-target['tail'])))
        assert target_error<2e-6,'The actual saved finger bone differs from its measured guide.'
        values=[]
        for fraction in np.linspace(0,1,5):
            q=head+(tail-head)*fraction
            x,y,z=triangles[:,0]-q,triangles[:,1]-q,triangles[:,2]-q
            nx,ny,nz=(np.linalg.norm(v,axis=1) for v in [x,y,z])
            numerator=np.einsum('ij,ij->i',x,np.cross(y,z))
            denominator=nx*ny*nz+np.einsum('ij,ij->i',x,y)*nz+np.einsum('ij,ij->i',y,z)*nx+np.einsum('ij,ij->i',z,x)*ny
            values.append(float(np.arctan2(numerator,denominator).sum()/(2*np.pi)))
        actual_bones[name]={'head':head.tolist(),'tail':tail.tolist()}
        rows.append({'bone':name,'maximumGuidePositionError':target_error,'windingSamples':values,
            'allFiveSamplesInside':all(abs(value)>.5 for value in values)})
assert len(rows)==40
outside=[r['bone'] for r in rows if not r['allFiveSamplesInside']]
assert not outside,'A saved finger bone sample lies outside the unchanged native surface.'
assert sha(g['editableBlend'])==g['editableBlendSha256']
bpy.ops.wm.read_factory_settings(use_empty=True)
model=g['exports']['whole']['model'];assert sha(model)==g['exports']['whole']['modelSha256']
bpy.ops.import_scene.gltf(filepath=model)
rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
rig=rigs[0];exported=[]
for name,actual in actual_bones.items():
    point=np.asarray(rig.matrix_world@rig.data.bones[name].head_local)
    error=float(np.linalg.norm(point-actual['head']))
    assert error<2e-6,'An actual glTF joint head differs from the saved native bind.'
    exported.append({'joint':name,'position':point.tolist(),'editableJointPositionError':error})
report={'editableSha256':g['editableBlendSha256'],'modelSha256':g['exports']['whole']['modelSha256'],
    'sourcePhotoSha256':guides['sourcePhotoSha256'],'measurementDataSha256':sha(args.measurement_data),
    'nativeSurfaceMaximumPositionError':surface_error,
    'method':'actual reopened bone heads/tails: five solid-angle winding samples each on unchanged original hand triangles; actual reimported glTF joint heads compared to editable',
    'actualBoneSamples':200,'actualExportedJointHeads':40,'editableBoneChecks':rows,'exportedJointChecks':exported,
    'outsideSampleBones':outside,'importerBoneTailsUsed':False,'reopenedWithoutSaving':True,
    'anatomyVerified':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,
    'limitation':'Surface containment at sampled points and exact joint export do not establish anatomy, finger bending, intermediate pose safety or cloth behavior.'}
Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ACTUAL_SAVED_AND_EXPORTED_FINGER_BIND_CHECKED',len(rows),len(exported),flush=True)

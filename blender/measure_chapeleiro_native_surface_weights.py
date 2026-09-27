"""Measure intact native topology, atlas, weights and actual poses without saving."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
path=Path(args.generation);record=json.loads(path.read_text(encoding='utf-8'))
assert sha(record['editableBlend'])==record['editableBlendSha256']
out=Path(args.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=record['editableBlend'])
scene=bpy.context.scene;rigs=[o for o in scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
rig=rigs[0];assert len(rig.data.bones)==173
audit=json.loads((path.parent/'skin_audit.json').read_text(encoding='utf-8'))
obj=bpy.data.objects[next(p['mesh'] for p in audit['pieces'] if p['role']=='whole_native')]
assert [m.type for m in obj.modifiers]==['ARMATURE']
for other in scene.objects:
    if other not in [rig,obj]:other.hide_viewport=True
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None;rig.data.pose_position='REST'
mesh=obj.data
xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
world=np.asarray(obj.matrix_world);points=xyz.reshape(-1,3)@world[:3,:3].T+world[:3,3]
edges=np.empty(len(mesh.edges)*2,np.int32);mesh.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
loops=np.empty(len(mesh.loops),np.int32);mesh.loops.foreach_get('vertex_index',loops)
counts=np.empty(len(mesh.polygons),np.int32);mesh.polygons.foreach_get('loop_total',counts);assert np.all(counts==3)
faces=loops.reshape(-1,3)
raw_geometry=hashlib.sha256(xyz.tobytes()+loops.tobytes()+counts.tobytes()).hexdigest()
assert raw_geometry==record['sourceWholeGeometrySha256']
uv=np.empty(len(mesh.loops)*2,np.float32);mesh.uv_layers.active.data.foreach_get('uv',uv);uv=uv.reshape(-1,2)
face_material=np.empty(len(mesh.polygons),np.int32);mesh.polygons.foreach_get('material_index',face_material)
vertices,first=np.unique(loops,return_index=True);assert len(vertices)==len(mesh.vertices)
slots=np.repeat(face_material,counts)[first];vertex_uv=uv[first]
colors=np.full((len(points),3),np.nan,np.float32);images=[]
for slot,material in enumerate(mesh.materials):
    node=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    links=list(node.inputs['Base Color'].links);assert len(links)==1 and links[0].from_node.type=='TEX_IMAGE'
    image=links[0].from_node.image;width,height=image.size[:]
    pixels=np.empty(width*height*image.channels,np.float32);image.pixels.foreach_get(pixels)
    pixels=pixels.reshape(height,width,image.channels);selected=slots==slot;coord=vertex_uv[selected]%1
    x=np.clip((coord[:,0]*width).astype(int),0,width-1);y=np.clip((coord[:,1]*height).astype(int),0,height-1)
    colors[selected]=pixels[y,x,:3]
    images.append({'material':material.name,'image':image.name,'size':[width,height],
        'packedImageSha256':hashlib.sha256(bytes(image.packed_file.data)).hexdigest()})
assert np.isfinite(colors).all()
names=[b.name for b in rig.data.bones];indexed={name:i for i,name in enumerate(names)}
groups={g.index:indexed[g.name] for g in obj.vertex_groups if g.name in indexed}
weights=np.zeros((len(points),len(names)),np.float32)
for v in mesh.vertices:
    for group in v.groups:
        if group.group in groups:weights[v.index,groups[group.group]]=group.weight
assert np.max(np.abs(weights.sum(1)-1))<1e-7
bones=[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(rig.matrix_world@b.head_local),
    'tail':list(rig.matrix_world@b.tail_local)} for b in rig.data.bones]
rig.data.pose_position='POSE';matrices=[];actual_points=[];poses=[]
for label,fraction in [('Walk',.33),('Run',.66),('Attack',.18),('Attack',.50),('Attack',.78)]:
    actions=[a for a in bpy.data.actions if a.name.startswith(label+' /')];assert len(actions)==1
    action=actions[0];rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    first,last=action.frame_range;frame=first+(last-first)*fraction
    scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
    matrices.append(np.stack([np.asarray(rig.matrix_world@rig.pose.bones[name].matrix@rig.data.bones[name].matrix_local.inverted()@rig.matrix_world.inverted()) for name in names]))
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());posed_mesh=evaluated.to_mesh()
    assert len(posed_mesh.vertices)==len(points)
    posed=np.empty(len(points)*3,np.float32);posed_mesh.vertices.foreach_get('co',posed)
    transform=np.asarray(evaluated.matrix_world);posed=posed.reshape(-1,3)@transform[:3,:3].T+transform[:3,3]
    evaluated.to_mesh_clear();actual_points.append(posed)
    poses.append({'clip':action.name,'fraction':fraction,'frame':frame})
    print('ACTUAL_NATIVE_SURFACE_POSE_MEASURED',label,fraction,flush=True)
file=out/'native_surface_weights.npz'
np.savez_compressed(file,points=points,edges=edges,faces=faces,colors=colors,weights=weights,
    bone_deformations=np.stack(matrices),actual_posed_points=np.stack(actual_points))
report={'parentEditableSha256':record['editableBlendSha256'],'parentWholeModelSha256':record['exports']['whole']['modelSha256'],
    'sourcePhotoSha256':record['exports']['whole']['sourcePhotoSha256'],'rawGeometrySha256':raw_geometry,
    'dataFile':str(file),'dataSha256':sha(file),'actualVertices':len(points),'actualEdges':len(edges),'actualFaces':len(faces),
    'bones':bones,'poses':poses,'actualAtlasImages':images,'scriptSha256':sha(__file__),
    'method':'actual reopened intact original surface, UV atlas samples and weights; actual evaluated one-armature poses',
    'geometryChanged':False,'sourceEditableUnchanged':sha(record['editableBlend'])==record['editableBlendSha256'],
    'anatomicalRegionsVerified':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False}
(out/'measurement.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ACTUAL_NATIVE_SURFACE_MEASUREMENT_SAVED',len(points),flush=True)

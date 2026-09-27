"""Read-only diagnosis of the actual whole exported skin's stretched edges."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
record=json.loads(Path(args.generation).read_text(encoding='utf-8'))
file=Path(record['model']);expected=record['modelSha256']
assert hashlib.sha256(file.read_bytes()).hexdigest()==expected
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(file))
scene=bpy.context.scene
rigs=[o for o in scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
rig=rigs[0]
meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
assert len(meshes)==1
obj=meshes[0]
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None
rig.data.pose_position='REST';bpy.context.view_layer.update()

def coordinates():
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
    matrix=np.asarray(evaluated.matrix_world)
    points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
    edges=np.empty(len(mesh.edges)*2,np.int32);mesh.edges.foreach_get('vertices',edges)
    evaluated.to_mesh_clear()
    return points,edges.reshape(-1,2)

rest,edges=coordinates()
lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
valid=lengths>1e-5
rig.data.pose_position='POSE'
bone_names={b.name for b in rig.data.bones}
groups={g.index:g.name for g in obj.vertex_groups if g.name in bone_names}
def weights(index):
    return {groups[g.group]:g.weight for g in obj.data.vertices[index].groups if g.group in groups and g.weight>0}

poses=[]
for label,fraction in [('Walk',.33),('Run',.66),('Attack',.18),('Attack',.50),('Attack',.78)]:
    actions=[a for a in bpy.data.actions if a.name.startswith(label+' /')];assert len(actions)==1
    action=actions[0];rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    first,last=action.frame_range;frame=first+(last-first)*fraction
    scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
    points,actual_edges=coordinates()
    assert np.array_equal(edges,actual_edges) and np.isfinite(points).all()
    posed=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1)
    ratio=np.ones(len(edges));ratio[valid]=posed[valid]/lengths[valid]
    rows=[]
    for edge_index in np.argsort(ratio)[-8:][::-1]:
        pair=edges[edge_index]
        rows.append({'edgeIndex':int(edge_index),'vertexIndices':pair.tolist(),'stretchRatio':float(ratio[edge_index]),
                     'restLength':float(lengths[edge_index]),'posedLength':float(posed[edge_index]),
                     'restEndpointsSourceBlender':rest[pair].tolist(),'posedEndpointsSourceBlender':points[pair].tolist(),
                     'actualEndpointWeights':[weights(int(v)) for v in pair]})
    pose={'clip':action.name,'fraction':fraction,'frame':frame,'worstActualEdges':rows}
    poses.append(pose)
    print(json.dumps({'clip':label,'fraction':fraction,'worstActualEdge':rows[0]}),flush=True)

report={'model':str(file),'modelSha256':expected,'method':'actual reimported one-mesh skin; same topology and exact endpoint weights',
        'poses':poses,'geometryChanged':False,'fidelityVerified':False,'motionVerified':False,'clothCollisionVerified':False,
        'limitation':'A numeric edge diagnosis does not approve movement, geometry, or physical cloth.'}
Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')

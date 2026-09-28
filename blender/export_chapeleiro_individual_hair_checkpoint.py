"""Export the whole Chapeleiro with disconnected, Head-rigged individual fiber ribbons."""
import argparse, hashlib, json, shutil, struct, sys
from pathlib import Path
import bpy, bmesh, numpy as np
from mathutils import Matrix
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
p.add_argument('--draco',action='store_true',help='Measure whole-character geometry compression for future individual-fiber checkpoint')
p.add_argument('--image-format',choices=['AUTO','WEBP','JPEG'],default='AUTO')
p.add_argument('--image-quality',type=int,default=100)
p.add_argument('--fiber-count',type=int,default=-1,help='Bounded full-character export probe; -1 means every fiber')
p.add_argument('--samples',type=int,default=24)
p.add_argument('--chunk-size',type=int,default=2048)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
g=json.loads(Path(a.generation).read_text());assert sha(g['editableBlend'])==g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
whole=bpy.data.objects['Chapeleiro / intact whole exterior / skin study']
rig=next(m.object for m in whole.modifiers if m.type=='ARMATURE')
mask=whole.data.attributes['alice_original_hair_review_mask'];hair_faces={i for i,v in enumerate(mask.data) if v.value}
original_faces=len(whole.data.polygons);original_vertices=len(whole.data.vertices)
whole.name='Alice / complete body and dress / individual hair checkpoint'
for mod in list(whole.modifiers):
    if mod.type!='ARMATURE':whole.modifiers.remove(mod)
bm=bmesh.new();bm.from_mesh(whole.data);bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[face for i,face in enumerate(bm.faces) if i in hair_faces],context='FACES')
isolated=[v for v in bm.verts if not v.link_faces]
if isolated:bmesh.ops.delete(bm,geom=isolated,context='VERTS')
bm.to_mesh(whole.data);bm.free();whole.data.update()
assert len(whole.data.polygons)+len(hair_faces)==original_faces

source_hair=next(o for o in bpy.context.scene.objects if o.type=='CURVES' and 'individual hair fibers' in o.name)
C=len(source_hair.data.curves);N=len(source_hair.data.points)//C
assert 8<=a.samples<=N and a.chunk_size>0 and (a.fiber_count==-1 or 1<=a.fiber_count<=C)
v=np.empty(len(source_hair.data.points)*3,np.float32);source_hair.data.attributes['position'].data.foreach_get('vector',v);v=v.reshape(C,N,3)
r=np.empty(len(source_hair.data.points),np.float32);source_hair.data.attributes['radius'].data.foreach_get('value',r);r=r.reshape(C,N)
selected_fiber_ids=np.arange(C) if a.fiber_count==-1 else np.linspace(0,C-1,a.fiber_count,dtype=int)
sample=np.linspace(0,N-1,a.samples).round().astype(int)
mat=bpy.data.materials.new('Alice / individual dark hair ribbons / checkpoint');mat.use_nodes=True
bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.025,.020,.019,1);bs.inputs['Roughness'].default_value=.42
mat.use_backface_culling=False
hair_chunks=[]
for chunk_start in range(0,len(selected_fiber_ids),a.chunk_size):
    fibers=selected_fiber_ids[chunk_start:chunk_start+a.chunk_size]
    verts=[];faces=[];uv=[]
    for fid in fibers:
        path=v[fid,sample];radius=r[fid,sample]
        tangent=np.gradient(path,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1,keepdims=True),1e-9)
        radial=path-np.array([0,.012,.82],np.float32);radial[:,2]=0
        radial/=np.maximum(np.linalg.norm(radial,axis=1,keepdims=True),1e-9)
        side=np.cross(tangent,radial);side/=np.maximum(np.linalg.norm(side,axis=1,keepdims=True),1e-9)
        first=len(verts)
        for i in range(a.samples):
            width=max(float(radius[i]),.000012)
            verts.extend([tuple(path[i]-side[i]*width),tuple(path[i]+side[i]*width)])
        for i in range(a.samples-1):
            faces.append((first+2*i,first+2*i+1,first+2*i+3,first+2*i+2))
            t0=i/(a.samples-1);t1=(i+1)/(a.samples-1)
            uv.extend([(0,t0),(1,t0),(1,t1),(0,t1)])
    mesh=bpy.data.meshes.new('Alice separated fiber ribbons '+str(chunk_start//a.chunk_size));mesh.from_pydata(verts,[],faces);mesh.update()
    layer=mesh.uv_layers.new(name='Hair UV')
    for loop,coordinate in zip(layer.data,uv):loop.uv=coordinate
    mesh.materials.append(mat)
    obj=bpy.data.objects.new('Alice / individual hair fibers / '+str(chunk_start//a.chunk_size),mesh)
    bpy.context.scene.collection.objects.link(obj);obj.parent=rig;obj.matrix_world=source_hair.matrix_world.copy()
    group=obj.vertex_groups.new(name='Head');group.add(list(range(len(mesh.vertices))),1.0,'REPLACE')
    modifier=obj.modifiers.new('Alice Head skin','ARMATURE');modifier.object=rig
    obj['aliceRole']='hair';obj['hairFiberCount']=len(fibers);obj['hairRepresentation']='separate mesh ribbon per source fiber; static Head skin, runtime dynamics pending'
    hair_chunks.append(obj)
    print('HAIR_RIBBON_CHUNK',len(hair_chunks),len(fibers),flush=True)
    del verts,faces,uv
selected=[whole,rig]+hair_chunks+[bpy.data.objects[name] for name in g['posteriorBodice']['objects']]
selected += [bpy.data.objects[g['posteriorBodice']['underlyingSkinObject']],bpy.data.objects['Chapeleiro / reconstructed closed head interior / review'],bpy.data.objects['Chapeleiro / reconstructed neck interior / review']]
assert not any(o.get('alice_collision_proxy') for o in selected)
if rig.animation_data:rig.animation_data.action=None
rig.data.pose_position='POSE'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
for track in list(rig.animation_data.nla_tracks):
    if track.name.split(' /')[0] in ('Walk','Run','Jump','Attack'):track.mute=False
    else:rig.animation_data.nla_tracks.remove(track)
for col in bpy.data.collections:col.hide_render=col.hide_viewport=False
for obj in bpy.context.scene.objects:
    obj.hide_render=obj not in selected;obj.hide_viewport=obj not in selected;obj.hide_set(obj not in selected);obj.select_set(obj in selected)
bpy.context.view_layer.objects.active=rig;bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
unweighted={}
for obj in selected:
    if obj.type=='MESH' and any(m.type=='ARMATURE' for m in obj.modifiers):
        empty=[v.index for v in obj.data.vertices if not any(w.weight>1e-8 for w in v.groups)]
        if empty:unweighted[obj.name]=len(empty)
assert not unweighted,unweighted
model=out/'alice_chapeleiro_complete_individual_hair_checkpoint.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_yup=True,export_extras=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_all_influences=True,export_draco_mesh_compression_enable=a.draco,export_draco_mesh_compression_level=6,export_image_format=a.image_format,export_image_quality=a.image_quality)
with model.open('rb') as f:
    magic,version,total=struct.unpack('<4sII',f.read(12));length,kind=struct.unpack('<II',f.read(8));data=json.loads(f.read(length))
assert magic==b'glTF' and total==model.stat().st_size
names=[x['name'] for x in data['animations']];assert len(names)==4
assert {name.split(' /')[0] for name in names}=={'Walk','Run','Jump','Attack'}
assert sum(n.get('extras',{}).get('hairFiberCount',0) for n in data['nodes'])==len(selected_fiber_ids)
assert any('finished posterior bodice' in n.get('name','') for n in data['nodes'])
report=dict(sourceGeneration=a.generation,sourceBlend=g['editableBlend'],sourceBlendSha256=g['editableBlendSha256'],sourceEditableUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],model=str(model),modelSha256=sha(model),modelBytes=model.stat().st_size,wholeCharacterWithDress=True,sourceFaceCount=original_faces,sourceVertices=original_vertices,sourceHairFacesExcluded=len(hair_faces),originalTripoHairIncluded=False,hairRepresentation='One disconnected mesh ribbon per source fiber; Head skin only; independent wind dynamics remain Blender authoring',exportedFiberCount=len(selected_fiber_ids),sourceFiberCount=C,fiberSamples=a.samples,hairRibbonMeshCount=len(hair_chunks),meshCount=len(data['meshes']),skinCount=len(data['skins']),animations=names,posteriorBodiceObjects=g['posteriorBodice']['objects'],collisionProxiesExcluded=True,allRiggedVerticesWeighted=True,characterFinished=False,physicsApproved=False,published=False,dracoEnabled=a.draco,imageFormat=a.image_format,imageQuality=a.image_quality)
(out/'export.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_export.py')
print('WHOLE_INDIVIDUAL_HAIR_CHECKPOINT_EXPORTED',json.dumps({k:v for k,v in report.items() if k!='posteriorBodiceObjects'}),flush=True)

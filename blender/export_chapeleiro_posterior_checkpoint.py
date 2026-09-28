"""Export a whole-character checkpoint; retain gallery Tripo hair, separable for back inspection."""
import argparse, hashlib, json, shutil, struct, sys
from pathlib import Path
import bpy, bmesh
from mathutils import Matrix
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
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
hair=whole.copy();hair.data=whole.data.copy();hair.name='Alice / Tripo hair / checkpoint';bpy.context.scene.collection.objects.link(hair)
hair['aliceRole']='hair';hair['checkpointHair']='Original gallery Tripo surface; individual fibers remain in full Blender authoring for further refinement.'
whole.name='Alice / complete body and dress / posterior checkpoint'
for obj,keep_hair in [(whole,False),(hair,True)]:
    for mod in list(obj.modifiers):
        if mod.type!='ARMATURE':obj.modifiers.remove(mod)
    bm=bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
    delete=[face for i,face in enumerate(bm.faces) if (i in hair_faces)!=keep_hair]
    bmesh.ops.delete(bm,geom=delete,context='FACES')
    isolated=[v for v in bm.verts if not v.link_faces]
    if isolated:bmesh.ops.delete(bm,geom=isolated,context='VERTS')
    bm.to_mesh(obj.data);bm.free();obj.data.update()
assert len(whole.data.polygons)+len(hair.data.polygons)==original_faces
selected=[whole,hair,rig]+[bpy.data.objects[name] for name in g['posteriorBodice']['objects']]
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
model=out/'alice_chapeleiro_complete_posterior_checkpoint.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_yup=True,export_extras=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_all_influences=True)
with model.open('rb') as f:
    magic,version,total=struct.unpack('<4sII',f.read(12));length,kind=struct.unpack('<II',f.read(8));data=json.loads(f.read(length))
assert magic==b'glTF' and total==model.stat().st_size
names=[x['name'] for x in data['animations']];assert len(names)==4
assert {name.split(' /')[0] for name in names}=={'Walk','Run','Jump','Attack'}
assert any(n.get('extras',{}).get('aliceRole')=='hair' for n in data['nodes'])
assert any('finished posterior bodice' in n.get('name','') for n in data['nodes'])
report=dict(sourceGeneration=a.generation,sourceBlend=g['editableBlend'],sourceBlendSha256=g['editableBlendSha256'],sourceEditableUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],model=str(model),modelSha256=sha(model),modelBytes=model.stat().st_size,wholeCharacterWithDress=True,sourceFacesPreserved=original_faces,sourceVertices=original_vertices,hairFacesSeparated=len(hair_faces),hairRestoredByDefault=True,hairRepresentation='Original gallery Tripo surface; new individual-strand authoring is retained locally and not claimed as exported',meshCount=len(data['meshes']),skinCount=len(data['skins']),animations=names,posteriorBodiceObjects=g['posteriorBodice']['objects'],collisionProxiesExcluded=True,allRiggedVerticesWeighted=True,characterFinished=False,physicsApproved=False,published=False)
(out/'export.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_export.py')
print('WHOLE_POSTERIOR_CHECKPOINT_EXPORTED',json.dumps({k:v for k,v in report.items() if k!='posteriorBodiceObjects'}),flush=True)

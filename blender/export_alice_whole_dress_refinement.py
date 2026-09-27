"""Export the entire clothed character for local 3D review, preserving its source."""
import argparse,hashlib,json,shutil,struct,sys
from pathlib import Path
import bpy
from mathutils import Matrix
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);g=json.loads(Path(a.generation).read_text());sha=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest()
assert sha(g['editableBlend'])==g['editableBlendSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);whole=bpy.data.objects[g['nativeWholeObject']]
rig=next(m.object for m in whole.modifiers if m.type=='ARMATURE' and m.object)
rig.animation_data.action=None;rig.data.pose_position='POSE'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
tracks=[]
for track in list(rig.animation_data.nla_tracks):
    keep=track.name.split(' /')[0] in ('Walk','Run','Jump','Attack')
    if keep:
        track.mute=False;tracks.append(track.name)
    else:
        # NLA export includes muted tracks. Exclude unapproved cloth study
        # tracks from this temporary export scene; never save these changes.
        rig.animation_data.nla_tracks.remove(track)
assert {s.split(' /')[0] for s in tracks}=={'Walk','Run','Jump','Attack'}
for collection in bpy.data.collections:collection.hide_viewport=collection.hide_render=False
for obj in bpy.context.scene.objects:
    obj.hide_viewport=obj not in (whole,rig);obj.hide_render=obj!=whole;obj.hide_set(obj not in (whole,rig));obj.select_set(False)
whole.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
groups={q.index:q.name for q in whole.vertex_groups};max_influences=max(sum(q.weight>1e-6 and groups[q.group] in rig.data.bones for q in v.groups) for v in whole.data.vertices)
model=out/'alice_chapeleiro_whole_dress_uv4k.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_yup=True,
    export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_all_influences=True)
blob=model.read_bytes();magic,version,total=struct.unpack_from('<4sII',blob);length,kind=struct.unpack_from('<II',blob,12)
assert magic==b'glTF' and version==2 and total==len(blob) and kind==0x4e4f534a
data=json.loads(blob[20:20+length]);names=[q['name'] for q in data['animations']]
assert len(names)==4 and {s.split(' /')[0] for s in names}=={'Walk','Run','Jump','Attack'}
assert len(data['skins'])==1 and len(data['meshes'])==1
materials=data['materials'];dress=[m for m in materials if 'dress UV 4K' in m.get('name','')];assert len(dress)==1
base=dress[0]['pbrMetallicRoughness']['baseColorTexture'];assert base.get('texCoord',0)==1
assert dress[0]['normalTexture'].get('texCoord',0)==0
assert dress[0]['pbrMetallicRoughness']['metallicRoughnessTexture'].get('texCoord',0)==0
report=dict(sourceGeneration=a.generation,sourceGenerationSha256=sha(a.generation),sourceBlend=g['editableBlend'],sourceBlendSha256=g['editableBlendSha256'],sourceEditableUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],
    model=str(model),modelSha256=sha(model),modelBytes=len(blob),wholeCharacterWithDress=True,meshCount=1,skinCount=1,skinJoints=len(data['skins'][0]['joints']),animations=names,
    sourceMaximumBoneInfluences=max_influences,allBoneInfluencesExported=True,
    primitiveAttributes=[list(q['attributes']) for q in data['meshes'][0]['primitives']],garmentBasecolorTexCoord=1,garmentNormalTexCoord=0,garmentRoughnessMetallicTexCoord=0,
    fullAuthoringLayersPreservedInSource=True,localReviewOnly=True,roundtripRendersPending=True,fullDressCoverageApproved=False,characterFidelityVerified=False,clothMotionVerified=False,published=False,fbxFinalExported=False,additionalTripoCreditsConsumed=0,scriptSha256=sha(__file__))
(out/'export.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_whole_export.py')
print('WHOLE_DRESS_GLB_LOCAL_EXPORT',json.dumps(report),flush=True)

"""Locate actual problematic95-vertex source patch in disposable native renders."""
import bpy,numpy as np,json,sys
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'residual_patch_geometry_REVIEW_v1185';D.mkdir(exist_ok=True);sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,audit_link
c=json.loads((R/'COELHO_CURRENT_WHOLE_SKIN_CHECKPOINT.json').read_text(encoding='utf-8-sig'));source=R/c['currentBlend'];assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==c['files']['blend']['sha256'];link=audit_link(R/'SharedBase/Development/alice_shared_base.blend')
ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];original=ob.data;ob.data=original.copy();m=ob.data;G=np.load(O/'semantic_weight_masks_v1082/hip_garment_protection_mask_v1083.npz');root=G['indexedComponents'];assert int((root==38212).sum())==95
mat=bpy.data.materials.new('DIAGNOSTIC_ONLY_SourcePatch38212_Cyan');mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');em=n.new('ShaderNodeEmission');em.inputs['Color'].default_value=(0.,1.,1.,1.);em.inputs['Strength'].default_value=1.;mat.node_tree.links.new(em.outputs[0],out.inputs['Surface']);m.materials.append(mat);slot=len(m.materials)-1;faceIDs=[]
for p in m.polygons:
    if (root[list(p.vertices)]==38212).all():p.material_index=slot;faceIDs.append(p.index)
assert faceIDs
rig=bpy.data.objects['Alice.Shared.Rig'];action=next(s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action and s.action.name.startswith('Walk /'));rig.animation_data.action=action;rig.animation_data.use_nla=False;rig.animation_data.action_influence=1.;rig.animation_data.action_blend_type='REPLACE';rig.animation_data.action_extrapolation='HOLD'
if len(action.slots):rig.animation_data.action_slot=action.slots[0]
s=bpy.context.scene;s.frame_set(11);bpy.context.view_layer.update()
# Resource cleanup affects only this process and preserves every visible material at4K.
used=set();visited=set()
def visit(tree):
    if not tree or tree.as_pointer() in visited:return
    visited.add(tree.as_pointer())
    for n in tree.nodes:
        im=getattr(n,'image',None)
        if im:used.add(im.as_pointer())
        visit(getattr(n,'node_tree',None))
for x in s.objects:
    if x.type=='MESH' and not x.hide_render:
        for ma in x.data.materials:
            if ma:visit(ma.node_tree)
    if x.type=='LIGHT':visit(x.data.node_tree)
visit(s.world.node_tree)
for im in list(bpy.data.images):
    if im.as_pointer() not in used and im.type not in {'RENDER_RESULT','COMPOSITING'}:bpy.data.images.remove(im,do_unlink=True)
s.render.use_persistent_data=False;s.cycles.device='CPU';s.render.threads_mode='FIXED';s.render.threads=6;s.cycles.samples=16;s.cycles.use_denoising=True;s.render.resolution_x=900;s.render.resolution_y=1000;s.render.resolution_percentage=100;cam=s.camera;cam.data.ortho_scale=.65;target=Vector((0,.01,1.25));renders=[]
for view,direction in [('front',(0,-4,0)),('back',(0,4,0)),('right_profile',(-4,0,0))]:
    cam.location=target+Vector(direction);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();p=D/f'actual_source_patch_{view}_frame11_v1185.png';assert not p.exists();s.render.filepath=str(p);bpy.ops.render.render(write_still=True);renders.append(dict(view=view,path=p.relative_to(R).as_posix(),sha256=sha(p)))
assert sha(source)==c['files']['blend']['sha256'] and sha(R/'SharedBase/Development/alice_shared_base.blend')==link['librarySHA256']
report=dict(version='v1185',disposableColorHighlightOnly=True,actualSourceWholeBlend=source.relative_to(R).as_posix(),sourceUnchanged=True,sharedLibraryUnchanged=True,UVRoot=38212,vertices=95,faces=faceIDs,frame=11,originalLinkedWalkRotationModesNotModified=True,noBlendOrExportSaved=True,allVisible4KMapsRetained=True,renders=renders,classificationNotYetVisuallyApproved=True,productionComplete=False)
(D/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ACTUAL_PATCH_THREE_VIEWS_COMPLETE_REQUIRES_IDENTIFICATION',flush=True)

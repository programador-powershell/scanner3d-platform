"""Whole native candidate: only reviewed corset weight continuity, independently evaluated."""
import bpy,numpy as np,json,sys,time
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'corset_patch_weights_whole_CANDIDATE_v1226';D.mkdir(exist_ok=True);sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,array_hash,audit_link
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));c=read(R/'COELHO_CURRENT_WHOLE_SKIN_CHECKPOINT.json');sourceManifest=read(O/'left_patch_weights_whole_CANDIDATE_v1200/manifest.json');source=Path(sourceManifest['blend']);assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==sourceManifest['blendSHA256'];claim=read(R/'Coordination/Claims/alice_coelho.json');assert claim['owner']=='root_coelho_refinement_20261003' and claim['nonce']=='f88f8d53fab24a619579580190e6207a'
trial=read(O/'shoulder_topology_weight_STUDY_v1225/audit.json');review=read(O/'corset_patch_weight_review_v1225.json');assert review['allTwentyActualImagesInspected'] and trial['outsideDomainWeightsExactlyPreserved'] and len(trial['all42Frames'])==42
N=np.load(O/'shoulder_topology_weight_STUDY_v1225/character_weights_v1225.npz');oldN=np.load(O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/character_weights_v1146.npz');ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=bpy.data.objects['Alice.Shared.Rig'];link=audit_link(R/'SharedBase/Development/alice_shared_base.blend');names=[g.name for g in ob.vertex_groups];assert names==N['boneNames'].tolist()
def signature():return dict(positions=array_hash(ob.data.vertices,'co',3),indices=array_hash(ob.data.loops,'vertex_index',1,np.int32),uv={u.name:array_hash(u.data,'uv',2) for u in ob.data.uv_layers},normals=array_hash(ob.data.corner_normals,'vector',3),materials=[m.name for m in ob.data.materials])
before=signature();assert before==read(O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/manifest.json')['sourceGeometrySignature'];old=np.zeros_like(N['weights'])
for v in ob.data.vertices:
    for g in v.groups:old[v.index,g.group]=g.weight
raw=np.load(O/'remaining_walk_regions_REVIEW_v1221/actual_weights_walk_frame31_v1221.npz');rawDense=raw['weights'];assert np.array_equal(old,rawDense),'Actual1200 native weights differ from authoritative current raw1202 reconstruction'
selected=N['changed'];assert int(selected.sum())==trial['changedVertices']
new=old.copy();new[selected]=N['weights'][selected];assert np.array_equal(new[~selected],old[~selected])
changed=np.any(np.abs(new-old)>1e-7,axis=1);ids=np.flatnonzero(changed);assert int(changed.sum())==trial['changedVertices']
assert np.abs(new-new[np.unique(N['physicalSurfaceGroup'],return_index=True)[1][N['physicalSurfaceGroup']]]).max()<1e-7
for group in ob.vertex_groups:group.remove(ids.tolist())
for j,group in enumerate(ob.vertex_groups):
    for v in np.flatnonzero(changed&(new[:,j]>0)):group.add([int(v)],float(new[v,j]),'REPLACE')
assert signature()==before
out=D/'alice_coelho_complete_corset_patch_weight_CANDIDATE_v1226.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=True,check_existing=False)
report=dict(version='v1226',wholeCharacterWithDress=True,blend=str(out),blendSHA256=sha(out),bytes=out.stat().st_size,sourceBlend=str(source),sourceSHA256=sourceManifest['blendSHA256'],sharedLibrary=link,sourceGeometrySignature=before,geometryUVNormalsMaterialsExactlyPreserved=True,onlyChangedSkinWeights=True,changedWeightVertices=len(ids),previousWhole1200OutsideDomainPreserved=True,actualNativeWeightsExactlyMatchIndependentRaw1202=True,selectedRoots=[review['selectedUVRoot']],allOtherCharacterWeightsExactlyPreserved=True,originalAuthoringRetained=True,sourceAndLibraryUnchanged=False,all42NativeFramesVerified=False,allFiveSameCameraRendersComplete=False,acceptedForPublication=False,canonicalIdentityApproved=False,anatomical168cmApproved=False,individualHairComplete=False,clothPhysicsApproved=False,rigComplete=False,gameplayMotionApproved=False,productionComplete=False,VercelUsed=False,additionalTripoCredits=0,renders=[],nativeFrames=[])
save=lambda:(D/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');save();print('WHOLE_LOCAL_WEIGHT_CANDIDATE_SAVED_RENDER_AND_NATIVE_REVIEW_PENDING',flush=True)
action=next(s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action and s.action.name.startswith('Walk /'));modes={p.name:p.rotation_mode for p in rig.pose.bones};rig.animation_data.action=action;rig.animation_data.use_nla=False;rig.animation_data.action_influence=1.;rig.animation_data.action_blend_type='REPLACE';rig.animation_data.action_extrapolation='HOLD'
if len(action.slots):rig.animation_data.action_slot=action.slots[0]
P=oldN['positions'].astype(np.float64);ex=np.load(O/'whole_skin_export_source_character_v1202.npz');tri=ex['triangles'];edges=np.unique(np.sort(np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),axis=1),axis=0);rest=np.linalg.norm(P[edges[:,0]]-P[edges[:,1]],axis=1);groups=N['physicalSurfaceGroup'];_,first=np.unique(groups,return_index=True);s=bpy.context.scene
# Baseline is the actual1200 native weights, restored only in this disposable process.
def assign_selected(weights):
    for group in ob.vertex_groups:group.remove(ids.tolist())
    for j,group in enumerate(ob.vertex_groups):
        for v in np.flatnonzero(changed&(weights[:,j]>0)):group.add([int(v)],float(weights[v,j]),'REPLACE')
assign_selected(old);s.frame_set(27);bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();co=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',co);Q=co.reshape(-1,3).astype(float);matrix=np.asarray(ev.matrix_world);Q=Q@matrix[:3,:3].T+matrix[:3,3];ev.to_mesh_clear();expected27=np.load(O/'shoulder_topology_weight_STUDY_v1225/frame27_topology_comparison_v1225.npz')['baseline'];baselineError=float(np.linalg.norm(Q-expected27,axis=1).max());assert baselineError<2e-6;report['nativeBaselineFrame27MaxErrorM']=baselineError;report['baselineRenders']=[]
s.render.use_persistent_data=False;s.cycles.device='CPU';s.render.threads_mode='FIXED';s.render.threads=6;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=16;s.cycles.use_denoising=True;cam=s.camera
for view,direction in [('front',(0,-4,0)),('left_profile',(4,0,0))]:
    target=Vector((0,0,.88));cam.data.ortho_scale=2.04;cam.location=target+Vector(direction);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();p=D/f'whole_walk_baseline1200_{view}_frame27_v1226.png';assert not p.exists();s.render.filepath=str(p);bpy.ops.render.render(write_still=True);report['baselineRenders'].append(dict(frame=27,view=view,path=p.relative_to(R).as_posix(),sha256=sha(p),sourceWeights1200=True));save()
assign_selected(new)
for frame in range(1,43):
    s.frame_set(frame);bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();co=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',co);Q=co.reshape(-1,3).astype(np.float64);matrix=np.asarray(ev.matrix_world);Q=Q@matrix[:3,:3].T+matrix[:3,3];ev.to_mesh_clear();length=np.linalg.norm(Q[edges[:,0]]-Q[edges[:,1]],axis=1);bad=(rest>1e-5)&(rest<.03)&(length>.12);seam=float(np.linalg.norm(Q-Q[first[groups]],axis=1).max());assert seam<2e-6
    expected=trial['all42Frames'][frame-1]['candidate'];assert int(bad.sum())==expected['allBad'],(frame,int(bad.sum()),expected['allBad'])
    if frame==27:
        prediction27=np.load(O/'shoulder_topology_weight_STUDY_v1225/frame27_topology_comparison_v1225.npz')['candidate'];error27=float(np.linalg.norm(Q-prediction27,axis=1).max());assert error27<2e-6;report['nativeFrame27MatchesIndependentAnalyticCandidateMaxM']=error27
    if frame==31:
        prediction=np.load(O/'shoulder_topology_weight_STUDY_v1225/frame31_topology_comparison_v1225.npz')['candidate'];error=float(np.linalg.norm(Q-prediction,axis=1).max());assert error<2e-6,error;report['nativeFrame31MatchesIndependentAnalyticCandidateMaxM']=error
    report['nativeFrames'].append(dict(frame=frame,shortRestEdgesExpandedBeyond12cm=int(bad.sum()),samePhysicalSeamMaxM=seam));print('NATIVE_LOCAL_PATCH_WALK',frame,'badEdges',int(bad.sum()),'seam',seam,flush=True)
assert modes=={p.name:p.rotation_mode for p in rig.pose.bones};report['all42NativeFramesVerified']=True;save()
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
s.render.use_persistent_data=False;s.cycles.device='CPU';s.render.threads_mode='FIXED';s.render.threads=6;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=16;s.cycles.use_denoising=True;cam=s.camera
for frame,view,direction in [(1,'front_start',(0,-4,0)),(11,'front_quarter',(0,-4,0)),(31,'front_threequarter',(0,-4,0)),(27,'corset_peak',(0,-4,0)),(27,'corset_peak_left_profile',(4,0,0))]:
    s.frame_set(frame);bpy.context.view_layer.update();target=Vector((0,0,.88));cam.data.ortho_scale=2.04;cam.location=target+Vector(direction);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();p=D/f'whole_walk_{view}_frame{frame}_v1226.png';assert not p.exists();s.render.filepath=str(p);bpy.ops.render.render(write_still=True);report['renders'].append(dict(frame=frame,view=view,path=p.relative_to(R).as_posix(),sha256=sha(p)));save()
assert signature()==before and sha(source)==sourceManifest['blendSHA256'] and sha(out)==report['blendSHA256'] and sha(R/'SharedBase/Development/alice_shared_base.blend')==link['librarySHA256'];assert len(report['baselineRenders'])==2 and len(report['renders'])==5;report['allFiveSameCameraRendersComplete']=True;report['twoSameCameraNativeBeforeAfterPairsComplete']=True;report['sourceAndLibraryUnchanged']=True;save();print('WHOLE_LOCAL_PATCH_NATIVE42_AND_FOUR_RENDERS_COMPLETE_VISUAL_REVIEW_REQUIRED',flush=True)

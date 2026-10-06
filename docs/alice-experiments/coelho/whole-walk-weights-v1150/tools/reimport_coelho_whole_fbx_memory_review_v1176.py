"""Whole GLB/FBX audit: every triangle/corner UV/material/normal, plus actual renders."""
import bpy,numpy as np,json,hashlib,sys,time
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';sys.path.insert(0,str(R/'Tools/PythonDeps/mesh_repair'));from scipy.spatial import cKDTree
start=time.time();kind=sys.argv[sys.argv.index('--')+1];assert kind=='fbx';pkg=json.loads((O/'package_skin_export_v1150.json').read_text(encoding='utf-8-sig'));file=R/pkg['files'][kind]['path'];assert hashlib.sha256(file.read_bytes()).hexdigest()==pkg['files'][kind]['sha256'];s=bpy.context.scene;cam=s.camera;world=s.world.copy();world.use_fake_user=True;lightData=[(x.name,x.data.copy(),x.matrix_world.copy()) for x in s.objects if x.type=='LIGHT'];camLoc=cam.location.copy();camRot=cam.rotation_euler.copy();camData=cam.data.copy()
sheenMaterial=bpy.data.materials['Alice.Coelho.RearBow.VisibleInk.RimPaddingCandidate592'];sheenPrincipled=next(n for n in sheenMaterial.node_tree.nodes if n.type=='BSDF_PRINCIPLED');assert not sheenPrincipled.inputs['Sheen Weight'].is_linked and abs(sheenPrincipled.inputs['Sheen Weight'].default_value-.08)<1e-7;assert list(sheenPrincipled.inputs['Sheen Tint'].default_value)==[1.,1.,1.,1.]
compat=json.loads((O/'whole_skin_glb_sheen_compatibility_v1150.json').read_text(encoding='utf-8-sig'));compat.update(sourceWeightIndependentlyVerifiedFromWhole1041=True,sourceWeightMustBeIndependentlyVerifiedBeforeApproval=False);assert compat['onlyOneJSONMaterialFieldChanged'] and compat['binaryChunkExactlyPreserved'] # Read-only shared compatibility record; avoid parallel writers.
for x in list(bpy.data.objects):bpy.data.objects.remove(x,do_unlink=True)
# Reproduce importer encoding from exactly captured raw inputs, on disposable copies.
import importlib
captured={}
if kind=='glb':
 imp=importlib.import_module('io_scene_gltf2.blender.imp.mesh');original=imp.set_poly_smoothing
 def capture(gltf,pymesh,mesh,vert_normals,loop_vidxs):
  original(gltf,pymesh,mesh,vert_normals,loop_vidxs);cp=mesh.copy();cp.update(calc_edges=True,calc_edges_loose=False);cp.validate();cp.normals_split_custom_set_from_vertices(vert_normals.copy());captured[mesh.name]=cp
 imp.set_poly_smoothing=capture
else:
 imp=importlib.import_module('io_scene_fbx.import_fbx');original=imp.blen_read_geom_layer_normal
 def capture(fbx_obj,mesh,xform=None):
  result=original(fbx_obj,mesh,xform)
  if result:
   n=np.zeros(len(mesh.loops)*3,np.float32);mesh.attributes['temp_custom_normals'].data.foreach_get('vector',n);cp=mesh.copy();cp.validate(clean_customdata=False);cp.normals_split_custom_set(n.reshape(-1,3).tolist());captured[mesh.name]=cp
  return result
 imp.blen_read_geom_layer_normal=capture
if kind=='glb':bpy.ops.import_scene.gltf(filepath=str(file),disable_bone_shape=True)
else:bpy.ops.import_scene.fbx(filepath=str(file),use_custom_normals=True)

armatures=[x for x in s.objects if x.type=='ARMATURE'];assert len(armatures)==1
rig=armatures[0];names=pkg['boneNames'];assert set(names)==set(rig.data.bones.keys()),(len(names),len(rig.data.bones));boneIndex={n:i for i,n in enumerate(names)};vertexMappings={};cornerFallbacks=[];importRest={n:rig.matrix_world@rig.data.bones[n].matrix_local for n in names};nativeRest=np.asarray([b['matrixWorld'] for b in pkg['bones']]);sourceMotion=json.loads((O/'whole_skin_motion_reference_v1170.json').read_text(encoding='utf-8-sig'));assert sourceMotion['boneNames']==names
def skin_arrays(ob):
 J=np.full((len(ob.data.vertices),4),-1,np.int32);W=np.zeros((len(ob.data.vertices),4),np.float32)
 for v in ob.data.vertices:
  groups=sorted((boneIndex[ob.vertex_groups[g.group].name],g.weight) for g in v.groups if g.weight>0 and ob.vertex_groups[g.group].name in boneIndex);assert 1<=len(groups)<=4,(ob.name,v.index,groups)
  assert abs(sum(w for _,w in groups)-1)<1e-5
  for c,(j,w) in enumerate(groups):J[v.index,c]=j;W[v.index,c]=w
 return J,W

obs=[x for x in s.objects if x.type=='MESH'];assert len(obs)==len(pkg['objects']),[(x.name,len(x.data.vertices)) for x in obs];records=[]
for row in pkg['objects']:
 expectedImportedName=imp.validate_blend_names(row['name'].encode('utf-8')) if kind=='fbx' else row['name'];matches=[x for x in obs if x.name==expectedImportedName or x.name.startswith(expectedImportedName+'.')];assert len(matches)==1,(row['role'],[x.name for x in obs]);ob=matches[0];m=ob.data;m.calc_loop_triangles();assert len(m.loop_triangles)==row['triangles'] and len(m.uv_layers)==1;expected=np.load(O/f'whole_skin_export_source_{row["role"]}_v1148.npz');P=expected['positions'].astype(np.float64);tr=expected['triangles'];UV=expected['loopUV'];loops=expected['triangleLoops'];normals=expected['loopNormals'];mat=expected['materials'];assert len(mat)==len(tr)
 Q=np.array([ob.matrix_world@v.co for v in m.vertices]);actualTri=np.array([t.vertices[:] for t in m.loop_triangles]);actualLoops=np.array([t.loops[:] for t in m.loop_triangles]);actualUV=np.array([u.uv[:] for u in m.uv_layers[0].data]);actualN=np.array([n.vector[:] for n in m.corner_normals])@np.linalg.inv(np.array(ob.matrix_world)[:3,:3]);actualN/=np.maximum(np.linalg.norm(actualN,axis=1)[:,None],1e-20);actualM=np.array([t.material_index for t in m.loop_triangles]);materialMap=[];actualJ,actualW=skin_arrays(ob);sourceJ=expected['joints'];sourceW=expected['weights'];vertexMap=np.full(len(Q),-1,np.int32)
 if kind=='glb':
  exporter=Path('F:/Programas/5.2/scripts/addons_core/io_scene_gltf2/blender/exp/primitive_extract.py');assert 'min_influence = 0.0001' in exporter.read_text(encoding='utf-8');keep=sourceW>0.0001;filteredJ=np.full_like(sourceJ,-1);filteredW=np.zeros_like(sourceW)
  for vertex in range(len(sourceJ)):
   groups=sorted((int(j),float(w)) for j,w,k in zip(sourceJ[vertex],sourceW[vertex],keep[vertex]) if k);assert groups
   total=sum(w for _,w in groups)
   for slot,(j,w) in enumerate(groups):filteredJ[vertex,slot]=j;filteredW[vertex,slot]=w/total
  sourceJ,sourceW=filteredJ,filteredW

 for ma in m.materials:
  candidates=[i for i,n in enumerate(row['materialNames']) if ma.name==n or ma.name.startswith(n+'.')];assert candidates,(row['role'],ma.name,row['materialNames']);materialMap.append(max(candidates,key=lambda i:len(row['materialNames'][i])))
 actualM=np.array(materialMap)[actualM];tree=cKDTree(P[tr].mean(1));matched=np.zeros(len(tr),bool);maxPos=maxUV=maxAngle=0.;materialMismatch=0
 if kind=='fbx' and np.array_equal(actualTri,tr):
  # Stronger FBX match: importer preserved the literal source vertex indices and
  # triangle order. Avoid nearest-centroid ambiguity for coincident ornaments.
  matched[:]=True;assert np.array_equal(actualJ,sourceJ);assert float(np.abs(actualW-sourceW).max())<1e-5;vertexMap[:]=np.arange(len(Q))
  corners=Q[actualTri];expectedCorners=P[tr];maxPos=float(np.linalg.norm(corners-expectedCorners,axis=2).max());maxUV=float(np.abs(actualUV[actualLoops]-UV[loops]).max());materialMismatch=int(np.sum(actualM!=mat));assert maxPos<2e-6 and maxUV<2e-6 and materialMismatch==0,(row['role'],maxPos,maxUV,materialMismatch)
  expectedN=normals[loops];gotN=actualN[actualLoops];dot=np.clip(np.sum(expectedN*gotN,axis=2)/np.maximum(np.linalg.norm(expectedN,axis=2),1e-20),-1,1);maxAngle=float(np.degrees(np.arccos(dot)).max());print('WHOLE_FBX_LITERAL_IMPORTED_TRIANGLE_ORDER_VERIFIED',row['role'],flush=True)
 else:
  for base in range(0,len(actualTri),4096):
   end=min(len(actualTri),base+4096);AT=Q[actualTri[base:end]];dist,index=tree.query(AT.mean(1),k=8);SP=P[tr[index]];delta=np.linalg.norm(AT[:,None,:,None,:]-SP[:,:,None,:,:],axis=-1);order=delta.argmin(-1);corner=np.take_along_axis(delta,order[...,None],-1)[...,0];unique=(order[:,:,0]!=order[:,:,1])&(order[:,:,0]!=order[:,:,2])&(order[:,:,1]!=order[:,:,2]);eUV=UV[loops[index]];eUV=np.take_along_axis(eUV,order[...,None],axis=2);uvError=np.abs(actualUV[actualLoops[base:end]][:,None,:,:]-eUV).max(axis=(2,3));valid=unique&(corner.max(-1)<2e-6)&(uvError<2e-6)&(mat[index]==actualM[base:end,None]);eJ=np.take_along_axis(sourceJ[tr[index]],order[...,None],axis=2);eW=np.take_along_axis(sourceW[tr[index]],order[...,None],axis=2);valid&=(eJ==actualJ[actualTri[base:end]][:,None,:,:]).all(axis=(2,3))&(np.abs(eW-actualW[actualTri[base:end]][:,None,:,:]).max(axis=(2,3))<1e-5);score=np.where(valid,uvError+corner.max(-1),np.inf);
   for failed in np.flatnonzero(~np.isfinite(score.min(1))):
    from itertools import permutations
    best=None
    for c in range(index.shape[1]):
     if mat[index[failed,c]]!=actualM[base+failed]:continue
     for perm in permutations(range(3)):
      perm=np.asarray(perm);pe=float(delta[failed,c,np.arange(3),perm].max());ue=float(np.abs(actualUV[actualLoops[base+failed]]-UV[loops[index[failed,c]]][perm]).max());sj=sourceJ[tr[index[failed,c]]][perm];sw=sourceW[tr[index[failed,c]]][perm]
      if pe<2e-6 and ue<2e-6 and np.array_equal(sj,actualJ[actualTri[base+failed]]) and float(np.abs(sw-actualW[actualTri[base+failed]]).max())<1e-5:
       candidate=(pe+ue,c,perm.copy(),pe,ue)
       if best is None or candidate[0]<best[0]:best=candidate
    if best is not None:
     cost,c,perm,pe,ue=best;score[failed,c]=cost;order[failed,c]=perm;corner[failed,c]=delta[failed,c,np.arange(3),perm];uvError[failed,c]=ue;cornerFallbacks.append(dict(role=row['role'],actualTriangle=int(base+failed),sourceTriangle=int(index[failed,c]),permutation=perm.tolist(),positionMaxM=pe,UVMax=ue,strictMaterialAndBoneWeightMatch=True))
   choice=score.argmin(1);assert np.isfinite(score[np.arange(end-base),choice]).all(),('Triangle correspondence failed',row['role'],base,np.flatnonzero(~np.isfinite(score.min(1))).tolist()[:20]);indices=index[np.arange(end-base),choice];ord=order[np.arange(end-base),choice];matched[indices]=True;vertexMap[actualTri[base:end]]=np.take_along_axis(tr[indices],ord,axis=1);maxPos=max(maxPos,float(corner[np.arange(end-base),choice].max()));maxUV=max(maxUV,float(uvError[np.arange(end-base),choice].max()));expectedN=normals[loops[indices]];expectedN=np.take_along_axis(expectedN,ord[...,None],axis=1);gotN=actualN[actualLoops[base:end]];dot=np.clip(np.sum(expectedN*gotN,axis=2)/np.maximum(np.linalg.norm(expectedN,axis=2),1e-20),-1,1);maxAngle=max(maxAngle,float(np.degrees(np.arccos(dot)).max()))
   if base%131072==0:print('WHOLE_TRIANGLE_REIMPORT',kind,row['role'],base,'of',len(tr),'UV',maxUV,flush=True)
 assert (vertexMap>=0).all();vertexMappings[row['role']]=vertexMap;assert len([m for m in ob.modifiers if m.type=='ARMATURE' and m.object==rig])==1;assert matched.all(),('Not all source triangles matched',row['role'],int((~matched).sum()));assert m.name in captured,(m.name,list(captured));cp=captured[m.name];rawDecoded=np.array([n.vector[:] for n in cp.corner_normals]);importLocal=np.array([n.vector[:] for n in m.corner_normals]);assert rawDecoded.shape==importLocal.shape;decodeMaxError=float(np.abs(rawDecoded-importLocal).max());assert decodeMaxError<1e-7,('Independent importer encoding replay mismatch',row['role'],decodeMaxError);bpy.data.meshes.remove(cp);records.append(dict(role=row['role'],sourceExportObjectName=row['name'],actualImportedObjectName=ob.name,expectedImportedObjectName=expectedImportedName,importerNameSanitizationApplied=expectedImportedName!=row['name'],vertices=len(Q),triangles=len(tr),allSourceTrianglesMatched=True,literalImportedTriangleOrderExactlyPreserved=bool(kind=='fbx' and np.array_equal(actualTri,tr)),maxCornerPositionErrorM=maxPos,maxUVCornerError=maxUV,maxNormalAngleDegrees=maxAngle,materialMismatchCount=materialMismatch,maxImporterEncodingReplayComponentError=decodeMaxError,rawPayloadPreservationAuditedSeparately=False,materialNames=[x.name for x in m.materials]));print('WHOLE_ROLE_VERIFIED',kind,row['role'],records[-1]['maxCornerPositionErrorM'],records[-1]['maxUVCornerError'],flush=True)

# Orient every imported joint through the native world delta, accounting for importer rest orientation.
from mathutils import Matrix
ordered=sorted(names,key=lambda n:len(rig.data.bones[n].parent_recursive));inverseRig=rig.matrix_world.inverted();motionChecks=[];character=next(x for x in obs if x.name==pkg['objects'][0]['name'] or x.name.startswith(pkg['objects'][0]['name']+'.'));characterMapping=vertexMappings['character'];poseMatrices={}
# Every mesh/corner was verified above. Pose positions are compared only for character.
# Exclude 201 unrelated meshes from temporary viewport evaluation, retaining all bones.
poseHidden=[(o,o.hide_get()) for o in obs if o!=character]
for o,state in poseHidden:o.hide_set(True)
for poseRow in sourceMotion['poses']:
 path=R/poseRow['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==poseRow['sha256'];ref=np.load(path);desired={n:inverseRig@Matrix((ref['worldPose'][i]@np.linalg.inv(nativeRest[i])).tolist())@importRest[n] for i,n in enumerate(names)};poseMatrices[poseRow['label']]=desired
 for n in ordered:rig.pose.bones[n].matrix=desired[n];bpy.context.view_layer.update()
 ev=character.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();Q=np.asarray([ev.matrix_world@v.co for v in mesh.vertices]);originalNative=ref['positions'][characterMapping];originalError=float(np.linalg.norm(Q-originalNative,axis=1).max());expectedPose=originalNative
 if kind=='glb':
  filterAudit=json.loads((O/'walk_export_filter_analytic_audit_v1171.json').read_text(encoding='utf-8-sig'));assert filterAudit['allEightUnfilteredNativePosesReplayed'] and filterAudit['reimportToleranceMNotRelaxed']==1e-5;filterRow=next(r for r in filterAudit['poses'] if r['label']==poseRow['label']);assert filterRow['unfilteredReplayMaxErrorM']<2e-6;filteredPath=R/filterRow['filteredReferencePath'];assert hashlib.sha256(filteredPath.read_bytes()).hexdigest()==filterRow['filteredReferenceSHA256'];expectedPose=np.load(filteredPath)['positions'][characterMapping]
 error=float(np.linalg.norm(Q-expectedPose,axis=1).max());assert error<1e-5,('Skinned exported pose differs from independent encoding replay',kind,poseRow['label'],error);ev.to_mesh_clear();motionChecks.append(dict(label=poseRow['label'],maxWorldVertexErrorM=error,maxOriginalUnfilteredNativePoseErrorM=originalError,comparisonReference='source_native_plus_independently_replayed_official_glTF_filter' if kind=='glb' else 'source_native_unfiltered',toleranceMNotRelaxed=1e-5,allCharacterVerticesCompared=True));print('ACTUAL_EXPORTED_POSE_VERIFIED',kind,poseRow['label'],'encodingError',error,'originalNativeError',originalError,flush=True)
for p in rig.pose.bones:p.matrix_basis.identity()
for o,state in poseHidden:o.hide_set(state)
assert len(obs)==202 and all(not o.hide_get() for o in obs)
bpy.context.view_layer.update()

# Disposable process-only resource cleanup before actual Cycles renders.
used_materials={m.as_pointer() for ob in obs for m in ob.data.materials if m}
for old_material in list(bpy.data.materials):
 if old_material.as_pointer() not in used_materials:bpy.data.materials.remove(old_material,do_unlink=True)
for old_mesh in list(bpy.data.meshes):
 if old_mesh.users==0:bpy.data.meshes.remove(old_mesh)
for old_image in list(bpy.data.images):
 if old_image.users==0 and old_image.type not in {'RENDER_RESULT','COMPOSITING'}:bpy.data.images.remove(old_image)
# Factory review process only: no source/library saves, no texture downscaling.
usedMeshes={o.data.as_pointer() for o in obs};usedImages=set();visitedTrees=set()
def keep_images(tree):
 if not tree or tree.as_pointer() in visitedTrees:return
 visitedTrees.add(tree.as_pointer())
 for n in tree.nodes:
  image=getattr(n,'image',None)
  if image:usedImages.add(image.as_pointer())
  keep_images(getattr(n,'node_tree',None))
for ma in bpy.data.materials:
 if ma.as_pointer() in used_materials:keep_images(ma.node_tree)
keep_images(world.node_tree)
for name,data,matrix in lightData:keep_images(data.node_tree if data.use_nodes else None)
for mesh in list(bpy.data.meshes):
 if mesh.as_pointer() not in usedMeshes:bpy.data.meshes.remove(mesh,do_unlink=True)
for image in list(bpy.data.images):
 if image.as_pointer() not in usedImages and image.type not in {'RENDER_RESULT','COMPOSITING'}:bpy.data.images.remove(image,do_unlink=True)
for curve in list(bpy.data.curves):bpy.data.curves.remove(curve,do_unlink=True)
for ar in list(bpy.data.armatures):
 if ar!=rig.data:bpy.data.armatures.remove(ar,do_unlink=True)
assert len(obs)==202 and len(rig.data.bones)==209 and all(m.as_pointer() in usedMeshes for m in [o.data for o in obs])
assert all(any(im.as_pointer()==ptr for im in bpy.data.images) for ptr in usedImages)
s.render.use_persistent_data=False;s.cycles.device='CPU'
import gc;gc.collect()
print('UNUSED_AUTHORING_FAKE_USER_DATA_RELEASED_IMPORTED_GEOMETRY_AND_4K_IMAGES_PRESERVED',len(usedImages),flush=True)
s.render.threads_mode='FIXED';s.render.threads=6
s.world=world
for name,data,matrix in lightData:light=bpy.data.objects.new(name,data);s.collection.objects.link(light);light.matrix_world=matrix
cam=bpy.data.objects.new('WholeReimportExactCamera658',camData);s.collection.objects.link(cam);s.camera=cam;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=24;s.cycles.use_denoising=True;P=np.load(O/'whole_skin_export_source_character_v1148.npz')['positions'];target=(P.min(0)+P.max(0))/2;target[1]=0;renderRows=[]
for view,dir in [('front',(0,-4,0)),('back',(0,4,0)),('rear_threequarter',(1.7,4,.04))]:
 cam.location=target+np.array(dir);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.05;previous=E/f'whole_reimport_{kind}_{view}_v1173.png';assert previous.exists();s.render.filepath=str(previous);renderRows.append(dict(view=view,path=Path(s.render.filepath).relative_to(R).as_posix(),sha256=hashlib.sha256(Path(s.render.filepath).read_bytes()).hexdigest()))
# A close rear view checks the newly added clock and actual exported material display.
target=np.asarray([0,.17,1.02]);cam.location=target+np.asarray([0,4,.04]);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.22;s.render.resolution_x=s.render.resolution_y=1000;s.render.filepath=str(E/f'whole_reimport_{kind}_rear_clock_close_v1176.png');assert not Path(s.render.filepath).exists();bpy.ops.render.render(write_still=True);renderRows.append(dict(view='rear_clock_close',path=Path(s.render.filepath).relative_to(R).as_posix(),sha256=hashlib.sha256(Path(s.render.filepath).read_bytes()).hexdigest()))

def set_diagnostic_pose(label):
 hidden=[(o,o.hide_get()) for o in obs if o!=character]
 for o,state in hidden:o.hide_set(True)
 for n in ordered:rig.pose.bones[n].matrix=poseMatrices[label][n];bpy.context.view_layer.update()
 for o,state in hidden:o.hide_set(state)
 assert len(obs)==202 and all(not o.hide_get() for o in obs)
 bpy.context.view_layer.update()

for label in ['right_elbow','left_elbow']:
 set_diagnostic_pose(label)
 target=np.array([0.,0.,.88]);cam.location=target+np.array([0,-4,0]);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.04;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.filepath=str(E/f'whole_reimport_{kind}_{label}_v1176.png');bpy.ops.render.render(write_still=True);renderRows.append(dict(view=label,path=Path(s.render.filepath).relative_to(R).as_posix(),sha256=hashlib.sha256(Path(s.render.filepath).read_bytes()).hexdigest(),manualDiagnosticPose=True))
for label,direction in [('walk_study_frame11',(0,-4,0)),('walk_study_frame11_profile',(-4,0,0))]:
 key='walk_study_frame11'
 set_diagnostic_pose(key)
 target=np.array([0.,0.,.88]);cam.location=target+np.array(direction);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.04;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.filepath=str(E/f'whole_reimport_{kind}_{label}_v1176.png');assert not Path(s.render.filepath).exists();bpy.ops.render.render(write_still=True);renderRows.append(dict(view=label,path=Path(s.render.filepath).relative_to(R).as_posix(),sha256=hashlib.sha256(Path(s.render.filepath).read_bytes()).hexdigest(),linkedWalkStudyNotGameplayApproved=True))
for p in rig.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update()

assert hashlib.sha256(file.read_bytes()).hexdigest()==pkg['files'][kind]['sha256'];report=dict(version='v1176',unusedAuthoringDataDiscardedOnlyInDisposableProcess=True,importedGeometryAndAllImported4KImagesPreserved=True,threePreviouslyCompletedRestImagesFrom1173ReusedByExactFileSHA=True,CPUDeviceAndPersistentDataDisabledForMemory=True,format=kind,sha256=pkg['files'][kind]['sha256'],independentReimport=True,wholeCharacterWithDress=True,coordinateUVTolerancesNotRelaxed=True,allSourceTrianglesMatchedStillMandatory=True,bijectiveCornerFallbacks=cornerFallbacks,literalIndexedCornerCorrespondenceUsedForExactFBXTriangleOrder=True,failed942957PreparationsPreserved=True,previousVerified897ImporterNameAndLiteralTriangleSupportRestored=True,objects=records,totalTriangles=sum(x['triangles'] for x in records),allTriangleUVMaterialAssignmentsVerified=True,allImporterNormalEncodingReplaysVerified=True,rawNormalAudits=[],rawNormalAuditRequiredBeforePublication=True,rawSourceNormalIdentityInBlenderNotClaimed=True,FBXImporterExactValidateBlendNamesFunctionUsed=(kind=='fbx'),FBXImporterSourceSHA256=hashlib.sha256(Path(imp.__file__).read_bytes()).hexdigest(),renders=renderRows,sameCameraLightsWorldAndColorManagement=True,skinWeightsAllTriangleCornersVerified=True,GLTFNativeExporterMinInfluenceReplayed=(0.0001 if kind=='glb' else None),exactUnfilteredNativeWeightIdentityClaimed=(kind=='fbx'),exporterEncodingReplayToleranceM=1e-5,unfilteredNativeToleranceNotAssertedForGLB=True,officialFilterAnalyticAudit1165Used=(kind=='glb'),boneCount=len(names),exportedManualMotionComparedToNative=motionChecks,rigged=True,rigComplete=False,animations=0,canonicalIdentityApproved=False,physicsVerified=False,productionComplete=False,notPublished=True,elapsedSeconds=time.time()-start);(O/f'reimport_whole_{kind}_audit_v1176.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WHOLE_REIMPORT_VERIFIED',kind,flush=True)

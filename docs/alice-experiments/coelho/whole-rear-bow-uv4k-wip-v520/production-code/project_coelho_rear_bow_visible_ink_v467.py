"""Blender UV paint: classify reference ink, not lighting; ray-test EVERY painted texel.

Tail edging follows the actual textile pattern, not the distorted AI border.
Occluded printed areas keep a separately identified art-directed flat fallback.
No whole-character modification, rig, garment mounting or physics approval.
"""
import bpy,numpy as np,json,hashlib,time,gc
from pathlib import Path
from mathutils.bvhtree import BVHTree
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';W=4096;start=time.time()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'rear_bow_uv_authoring_audit_v466.json');source=R/a['path'];assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==a['sha256'];assert a['continuousUVOverlapPairs']==0
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
original=read(O/'rear_bow_layer_authoring_audit_v460.json');registration=read(O/'rear_bow_plate_registration_v465.json');assert read(O/'rear_bow_plate_review_decision_v465.json')['blanketProjectionRejected']
assert read(O/'rear_bow_uv_saved_audit_v468.json')['allGeometryUVWeightsAndWholeSourcesVerified']
def image_raw(path):
 image=bpy.data.images.load(str(path),check_existing=False);image.colorspace_settings.name='Non-Color';width,height=image.size;buf=np.empty(width*height*4,np.float32);image.pixels.foreach_get(buf);pixels=buf.reshape(height,width,4)[::-1,:,:3].copy();bpy.data.images.remove(image);return pixels
platePath=R/registration['platePath'];assert sha(platePath)==registration['plateSHA256'];plate=image_raw(platePath)
flatPath=O/'Textures/rear_bow_sources_v455/navy_gold_flat_albedo_candidate_v455.png';assert sha(flatPath)=='e743bd2df9a83306d571a67bac1a7e30e24a3d1fe5b216d35eeb096f3d306302';flat=image_raw(flatPath)
def ink(RGB):
 # Warm gold chroma is separated from luminance. Fold shadows and white
 # highlights cannot become permanent albedo through this classification.
 d=RGB[...,0]-RGB[...,2]*1.35;return np.clip((d-.035)/.075,0,1)*np.clip((RGB[...,0]-.14)/.10,0,1)
flatInk=ink(flat);navy=np.median(flat[flatInk<.01],axis=0);gold=np.median(flat[flatInk>.95],axis=0);assert len(flat[flatInk>.95])>1000
print('BOW467_REFERENCE_PALETTE_SRGB',navy.tolist(),gold.tolist(),flush=True)
def sample(pixels,X,Y):
 X=np.clip(X,0,pixels.shape[1]-1.001);Y=np.clip(Y,0,pixels.shape[0]-1.001);ix=X.astype(int);iy=Y.astype(int);fx=(X-ix)[:,None];fy=(Y-iy)[:,None]
 return pixels[iy,ix]*(1-fx)*(1-fy)+pixels[iy,ix+1]*fx*(1-fy)+pixels[iy+1,ix]*(1-fx)*fy+pixels[iy+1,ix+1]*fx*fy
deps=bpy.context.evaluated_depsgraph_get();allP=[];allF=[];ranges={};offset=0;faceOffset=0
for name in [r['name'] for r in a['newObjects']]+list(original['wholeSourceSignatures']):
 ob=bpy.data.objects[name];ev=ob.evaluated_get(deps);m=ev.to_mesh();m.calc_loop_triangles();P=np.asarray([ob.matrix_world@v.co for v in m.vertices],np.float32);T=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32);allP.extend(map(tuple,P));allF.extend(map(tuple,T+offset));ranges[name]=(faceOffset,faceOffset+len(T));offset+=len(P);faceOffset+=len(T);ev.to_mesh_clear();print('BOW467_OCCLUDER',name,len(T),flush=True)
tree=BVHTree.FromPolygons(allP,allF,all_triangles=True);del allP,allF;gc.collect();print('BOW467_ALL_ELEVEN_LAYERS_AND_TEN_WHOLE_OCCLUDERS_BVH',faceOffset,flush=True)
base=np.zeros((W,W,4),np.float32);base[:,:,:3]=navy;base[:,:,3]=1;rough=np.full((W,W),.46,np.float32);owner=np.full((W,W),-1,np.int16);visibleMask=np.zeros((W,W),np.uint8);edgeMask=np.zeros((W,W),np.uint8);stats=[];M=np.asarray(registration['targetPixelToPlateNormalizedPixelAffine']);plateScale=np.array([plate.shape[1]/900,plate.shape[0]/1000]);uvName=a['UVMapName']
for objIndex,row in enumerate(a['newObjects']):
 ob=bpy.data.objects[row['name']];m=ob.data;m.calc_loop_triangles();P=np.asarray([ob.matrix_world@v.co for v in m.vertices],float);U=np.asarray([x.uv[:] for x in m.uv_layers[uvName].data],float);pattern=np.asarray([x.uv[:] for x in m.uv_layers['RearBow.PatternUV460'].data],float);printed=row['role'] in {'base_loop','printed_tail','center_wrap'};counts=dict(covered=0,testedProjection=0,visible=0,rejectedOcclusion=0,rejectedOutsideCamera=0,geometryTailEdge=0,projectedGoldTexels=0);loFace,hiFace=ranges[ob.name]
 for triangle in m.loop_triangles:
  loops=list(triangle.loops);uv=U[loops];A=np.column_stack((uv[1]-uv[0],uv[2]-uv[0]));lo=np.maximum(np.floor(uv.min(0)*W).astype(int),0);hi=np.minimum(np.ceil(uv.max(0)*W).astype(int),W-1)
  if (hi<lo).any():continue
  xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5);points=np.column_stack((xx.ravel(),yy.ravel()))/W;b=(points-uv[0])@np.linalg.inv(A).T;weights=np.column_stack((1-b.sum(1),b));inside=weights.min(1)>1e-7;weights=weights[inside];pixels=(points[inside]*W).astype(int);x=pixels[:,0];y=pixels[:,1]
  if not len(x):continue
  assert (owner[y,x]<0).all(),('pixel overlap despite continuous audit',objIndex);owner[y,x]=objIndex;counts['covered']+=len(x)
  if not printed:rough[y,x]=.65 if row['role']=='structured_interfacing' else .33;continue
  Q=P[list(triangle.vertices)];world=weights@Q;parameter=weights@pattern[loops]
  # Flat auxiliary pattern for unobserved surfaces; explicitly not a projection
  # through the character and not evidence for hidden motif alignment.
  fallback=sample(flat,parameter[:,0]*(flat.shape[1]-1),parameter[:,1]*(flat.shape[0]-1));amount=ink(fallback)
  metricA=np.column_stack((pattern[loops][1]-pattern[loops][0],pattern[loops][2]-pattern[loops][0]));edgeDistance=np.full(len(x),np.inf)
  if abs(np.linalg.det(metricA))>1e-12:
   J=np.column_stack((Q[1]-Q[0],Q[2]-Q[0]))@np.linalg.inv(metricA);G=J.T@J
   if np.linalg.det(G)>1e-20:
    Ginv=np.linalg.inv(G);edgeDistance=np.minimum(np.minimum(parameter[:,0],1-parameter[:,0])/np.sqrt(Ginv[0,0]),np.minimum(parameter[:,1],1-parameter[:,1])/np.sqrt(Ginv[1,1]))
  if row['role']=='printed_tail':amount[edgeDistance<.010]=0
  cameraPixels=np.column_stack((450-world[:,0]*1000/.83,500-(world[:,2]-.985)*1000/.83));mapped=(cameraPixels@M[:,:2].T+M[:,2])*plateScale;inCamera=(cameraPixels[:,0]>=0)&(cameraPixels[:,0]<900)&(cameraPixels[:,1]>=0)&(cameraPixels[:,1]<1000)&(mapped[:,0]>=0)&(mapped[:,0]<plate.shape[1]-1)&(mapped[:,1]>=0)&(mapped[:,1]<plate.shape[0]-1)
  counts['rejectedOutsideCamera']+=int((~inCamera).sum());indices=np.flatnonzero(inCamera);counts['testedProjection']+=len(indices);visible=[]
  for k in indices:
   point=world[k];hit=tree.ray_cast(Vector((float(point[0]),3.14,float(point[2]))),Vector((0,-1,0)),6.)
   if hit[0] is not None and loFace<=hit[2]<hiFace and abs(float(hit[0].y)-point[1])<=2e-6:visible.append(k)
  ids=np.asarray(visible,np.int32);counts['visible']+=len(ids);counts['rejectedOcclusion']+=len(indices)-len(ids)
  if len(ids):
   incoming=ink(sample(plate,mapped[ids,0],mapped[ids,1]));
   if row['role']=='printed_tail':incoming[edgeDistance[ids]<.010]=0
   amount[ids]=incoming;visibleMask[y[ids],x[ids]]=1;counts['projectedGoldTexels']+=int((incoming>.5).sum())
  if row['role']=='printed_tail':
   # Technical printed-edge correction. Real sewn piping is still pending.
   edging=np.clip((.0016-edgeDistance)/.00035,0,1);amount=np.maximum(amount,edging);edgeMask[y[edging>.5],x[edging>.5]]=1;counts['geometryTailEdge']+=int((edging>.5).sum())
  base[y,x,:3]=navy+(gold-navy)*amount[:,None];rough[y,x]=.46-.075*amount
 stats.append(dict(name=ob.name,role=row['role'],**counts));print('BOW467_TEXEL_PAINT',ob.name,json.dumps(counts),flush=True)
 # Persist progress, so a slow bake is not mistaken for a hung job.
 (O/'rear_bow_projection_progress_v467.json').write_text(json.dumps(dict(completedObjects=stats,elapsedSeconds=time.time()-start),indent=2),encoding='utf-8')
# Extend each object's 4K chart a small number of texels without crossing chart
# ownership. This is sampling padding, never additional visible photo coverage.
coverage=owner>=0;paddingOwner=owner.copy()
for iteration in range(3):
 oldMask=paddingOwner>=0;newMask=oldMask.copy()
 for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
  shifted=np.roll(oldMask,(dy,dx),(0,1));ids=(~newMask)&shifted
  if dy>0:ids[:dy]=False
  if dy<0:ids[dy:]=False
  if dx>0:ids[:,:dx]=False
  if dx<0:ids[:,dx:]=False
  sourceBase=np.roll(base,(dy,dx),(0,1));sourceRough=np.roll(rough,(dy,dx),(0,1));sourceOwner=np.roll(paddingOwner,(dy,dx),(0,1));base[ids]=sourceBase[ids];rough[ids]=sourceRough[ids];paddingOwner[ids]=sourceOwner[ids];newMask[ids]=True
textureDir=O/'Textures/rear_bow_atlas_v467';textureDir.mkdir(exist_ok=True);maps={}
for label in ['basecolor','roughness']:
 pixels=base if label=='basecolor' else np.repeat(rough[:,:,None],4,axis=2);pixels[:,:,3]=1;image=bpy.data.images.new('Alice.Coelho.RearBow.'+label+'.4096.v467',W,W,alpha=False);image.colorspace_settings.name='Non-Color';image.pixels.foreach_set(pixels.ravel());image.file_format='PNG';p=textureDir/('alice_coelho_rear_bow_'+label+'_4096_v467.png');image.filepath_raw=str(p);image.save();bpy.data.images.remove(image);image=bpy.data.images.load(str(p),check_existing=False);image.name='Alice.Coelho.RearBow.'+label+'.4096.v467';image.colorspace_settings.name='sRGB' if label=='basecolor' else 'Non-Color';image.pack();maps[label]=dict(path=p.relative_to(R).as_posix(),sha256=sha(p),dimensions=[W,W],packed=True,colorSpace=image.colorspace_settings.name);print('BOW467_MAP_SAVED',label,flush=True)
mat=bpy.data.materials.new('Alice.Coelho.RearBow.VisibleInk.PBR4K.v467');mat.use_nodes=True;nodes=mat.node_tree.nodes;links=mat.node_tree.links;bs=nodes.get('Principled BSDF');bs.inputs['Metallic'].default_value=0;bs.inputs['Specular IOR Level'].default_value=.35;bs.inputs['Sheen Weight'].default_value=.08;uv=nodes.new('ShaderNodeUVMap');uv.uv_map=uvName
for label,socket in [('basecolor','Base Color'),('roughness','Roughness')]:
 tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images['Alice.Coelho.RearBow.'+label+'.4096.v467'];links.new(uv.outputs['UV'],tex.inputs['Vector']);links.new(tex.outputs['Color'],bs.inputs[socket])
rows=[];normalRecords=[]
for row in a['newObjects']:
 old=bpy.data.objects[row['name']];ob=old.copy();ob.data=old.data.copy();ob.name=old.name.replace('UV466','Paint467');bpy.data.collections[a['collection']].objects.link(ob);ob.data.materials.clear();ob.data.materials.append(mat)
 for poly in ob.data.polygons:poly.material_index=0
 # Retain the evaluated procedural460 corner normals when thickness quads were
 # triangulated. UV changes must not introduce a different rim shading model.
 originalObject=bpy.data.objects[row['sourceObject']];evaluated=originalObject.evaluated_get(deps);referenceMesh=evaluated.to_mesh();referenceMesh.calc_loop_triangles();sourceNormals=np.asarray([n.vector[:] for n in referenceMesh.corner_normals],float);reference={}
 for triangle in referenceMesh.loop_triangles:
  ids=list(triangle.vertices);first=int(np.argmin(ids));key=tuple(np.roll(ids,-first));reference[key]={int(v):sourceNormals[l] for v,l in zip(triangle.vertices,triangle.loops)}
 ob.data.calc_loop_triangles();normals=np.zeros((len(ob.data.loops),3),float)
 for triangle in ob.data.loop_triangles:
  ids=list(triangle.vertices);key=tuple(np.roll(ids,-int(np.argmin(ids))));record=reference[key]
  for v,l in zip(triangle.vertices,triangle.loops):normals[l]=record[int(v)]
 ob.data.normals_split_custom_set(normals.tolist());actualNormals=np.asarray([n.vector[:] for n in ob.data.corner_normals],float);error=np.linalg.norm(actualNormals-normals,axis=1);assert error.max()<.0003;normalRecords.append(dict(object=ob.name,sourceProcedural460=originalObject.name,maximumCornerNormalError=float(error.max()),tolerance=.0003));evaluated.to_mesh_clear()
 ob.hide_render=True;ob.hide_set(True);ob['scope']='Local UV4K paint candidate. Per-texel visible ink projection; hidden pattern is separately authored fallback. Printed trim is not sewn piping. Rig, hair contacts, mounting, physics remain pending.';rows.append(dict(row,name=ob.name,sourceObject=old.name))
np.savez_compressed(O/'rear_bow_projection_masks_v467.npz',covered=coverage,visiblePhotoProjection=visibleMask,geometryTailPrintedEdge=edgeMask,owner=owner,paddingOwner=paddingOwner)
del tree;gc.collect();out=O/'Dress/alice_coelho_rear_bow_visible_ink_candidate_v467.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==a['sha256']
report=dict(version='v467',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),sourcePath=a['path'],sourceSHA256=a['sha256'],newObjects=rows,maps=maps,procedural460CornerNormalsPreserved=normalRecords,paletteEncodedSRGB=dict(navy=navy.tolist(),gold=gold.tolist()),plateSHA256=registration['plateSHA256'],flatSourceSHA256=sha(flatPath),registrationVersion='v465',everyTransferredTexelIndividuallyRayTested=True,allElevenBowLayersAndTenWholeObjectsIncludedAsOccluders=True,rayDepthToleranceM=2e-6,coverageTexels=int(coverage.sum()),visibleProjectedTexels=int(visibleMask.sum()),printedTailEdgeTexels=int(edgeMask.sum()),paddingTexels=int(((paddingOwner>=0)&~coverage).sum()),records=stats,foldIlluminationDiscardedByChromaInkClassification=True,hiddenAreasUseExplicitFlatAuxiliaryPatternNotPhotoProjection=True,tailGeneratedBorderExcludedWithin10mmAndReplacedByPatternEdge=True,printedEdgingIsNotSewn3DPiping=True,onlyBackPlateUsedOtherViewsNotYetProjected=True,normalMicroWeaveNotBaked=True,allObjectsDefaultHidden=True,geometryUVAndPinGroupsRequireIndependentReopenVerification=True,canonicalIdentityAnd168cmNotApproved=True,remainingSourceContacts345NotResolved=True,rigged=False,physicsVerified=False,fidelityApproved=False,notIntegrated=True,notPublished=True,productionComplete=False,additionalTripoCredits=0,elapsedSeconds=time.time()-start)
(O/'rear_bow_visible_ink_authoring_audit_v467.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('BOW467_PAINT_SAVED_REQUIRE_REOPEN_AND_SAME_CAMERA_REVIEW',flush=True)

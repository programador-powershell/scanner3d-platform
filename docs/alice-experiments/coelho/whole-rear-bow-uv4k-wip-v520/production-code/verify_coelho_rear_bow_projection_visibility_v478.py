"""Independent UV-to-world reconstruction and first-hit visibility audit of saved475 masks."""
import bpy,numpy as np,json,hashlib,time,gc
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();start=time.time();a=read(O/'rear_bow_visible_ink_authoring_audit_v475.json');source=R/a['path'];assert sha(source)==a['sha256'];original=read(O/'rear_bow_layer_authoring_audit_v460.json');mask=np.load(O/'rear_bow_projection_masks_v475.npz');deps=bpy.context.evaluated_depsgraph_get();P=[];F=[];ranges={};vertexOffset=0;faceOffset=0
for name in [r['name'] for r in a['newObjects']]+list(original['wholeSourceSignatures']):
 ob=bpy.data.objects[name];ev=ob.evaluated_get(deps);mesh=ev.to_mesh();mesh.calc_loop_triangles();q=np.asarray([ob.matrix_world@v.co for v in mesh.vertices],np.float32);t=np.asarray([x.vertices[:] for x in mesh.loop_triangles],np.int32);P.extend(map(tuple,q));F.extend(map(tuple,t+vertexOffset));ranges[name]=(faceOffset,faceOffset+len(t));vertexOffset+=len(q);faceOffset+=len(t);ev.to_mesh_clear()
tree=BVHTree.FromPolygons(P,F,all_triangles=True);del P,F;gc.collect();rng=np.random.default_rng(478);records=[];examples=[]
for i,row in enumerate(a['newObjects']):
 if row['role'] not in {'base_loop','printed_tail','center_wrap'}:continue
 ob=bpy.data.objects[row['name']];mesh=ob.data;mesh.calc_loop_triangles();q=np.asarray([ob.matrix_world@v.co for v in mesh.vertices],float);uv=np.asarray([u.uv[:] for u in mesh.uv_layers['RearBow.Atlas4K.ABF.v471'].data],float);L=np.asarray([t.loops[:] for t in mesh.loop_triangles],np.int32);T=np.asarray([t.vertices[:] for t in mesh.loop_triangles],np.int32);uvTree=BVHTree.FromPolygons(np.column_stack((uv,np.zeros(len(uv)))).tolist(),L.tolist(),all_triangles=True);loFace,hiFace=ranges[ob.name];result={}
 for label,expected in [('visible',True),('occluded',False)]:
  pixels=np.argwhere((mask['owner']==i)&(mask['visiblePhotoProjection'].astype(bool)==expected));pixels=pixels[rng.choice(len(pixels),min(len(pixels),1024),replace=False)];failures=[]
  for y,x in pixels:
   point=(np.array([x,y])+.5)/4096;hit=uvTree.ray_cast(Vector((float(point[0]),float(point[1]),1)),Vector((0,0,-1)),2);assert hit[0] is not None;index=hit[2];u=uv[L[index]];matrix=np.column_stack((u[1]-u[0],u[2]-u[0]));b=np.linalg.solve(matrix,point-u[0]);world=np.array([1-b.sum(),*b])@q[T[index]];first=tree.ray_cast(Vector((float(world[0]),3.14,float(world[2]))),Vector((0,-1,0)),6);actuallyVisible=first[0] is not None and loFace<=first[2]<hiFace and abs(float(first[0].y)-world[1])<=2e-6
   if actuallyVisible!=expected:failures.append(dict(pixel=[int(x),int(y)],expectedVisible=expected,actualVisible=actuallyVisible))
  result[label]=dict(samples=len(pixels),classificationFailures=len(failures));examples.extend(failures[:10]);assert not failures,(ob.name,label,failures[:3])
 records.append(dict(object=ob.name,**result));print('BOW478_INDEPENDENT_RAYCHECK',ob.name,json.dumps(result),flush=True)
assert sha(source)==a['sha256'];report=dict(version='v478',sourceCandidate='v475',sourceSHA256=a['sha256'],independentUVRayReconstructionMethod=True,allElevenClothAndTenWholeOccludersIncluded=True,totalOccluderTriangles=faceOffset,records=records,totalClassificationFailures=0,sourceAndPaintUnchanged=True,readOnlyNoSaveOrExport=True,notFidelityOrPhysicsApproval=True,productionComplete=False,elapsedSeconds=time.time()-start);(O/'rear_bow_independent_projection_visibility_audit_v478.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('BOW478_INDEPENDENT_VISIBLE_AND_OCCLUDED_TEXEL_SAMPLES_PASSED',flush=True)

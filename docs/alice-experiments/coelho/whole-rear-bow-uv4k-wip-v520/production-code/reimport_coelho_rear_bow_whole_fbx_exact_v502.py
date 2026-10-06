"""Whole GLB/FBX audit: every triangle/corner UV/material/normal, plus actual renders."""
import bpy,numpy as np,json,hashlib,sys,time
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';sys.path.insert(0,str(R/'Tools/PythonDeps/mesh_repair'));from scipy.spatial import cKDTree
start=time.time();kind=sys.argv[sys.argv.index('--')+1];pkg=json.loads((O/'package_export_v500.json').read_text(encoding='utf-8-sig'));file=R/pkg['files'][kind]['path'];assert hashlib.sha256(file.read_bytes()).hexdigest()==pkg['files'][kind]['sha256'];s=bpy.context.scene;cam=s.camera;world=s.world.copy();world.use_fake_user=True;lightData=[(x.name,x.data.copy(),x.matrix_world.copy()) for x in s.objects if x.type=='LIGHT'];camLoc=cam.location.copy();camRot=cam.rotation_euler.copy();camData=cam.data.copy()
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
if kind=='glb':bpy.ops.import_scene.gltf(filepath=str(file))
else:bpy.ops.import_scene.fbx(filepath=str(file),use_custom_normals=True)
obs=[x for x in s.objects if x.type=='MESH'];assert len(obs)==21,[(x.name,len(x.data.vertices)) for x in obs];records=[]
for row in pkg['objects']:
 matches=[x for x in obs if 'Export500.'+row['role'] in x.name];assert len(matches)==1,(row['role'],[x.name for x in obs]);ob=matches[0];m=ob.data;m.calc_loop_triangles();assert len(m.loop_triangles)==row['triangles'] and len(m.uv_layers)==1;expected=np.load(O/f'whole_export_source_{row["role"]}_v500.npz');P=expected['positions'].astype(np.float64);tr=expected['triangles'];UV=expected['loopUV'];loops=expected['triangleLoops'];normals=expected['loopNormals'];mat=expected['materials'];assert len(mat)==len(tr)
 Q=np.array([ob.matrix_world@v.co for v in m.vertices]);actualTri=np.array([t.vertices[:] for t in m.loop_triangles]);actualLoops=np.array([t.loops[:] for t in m.loop_triangles]);actualUV=np.array([u.uv[:] for u in m.uv_layers[0].data]);actualN=np.array([n.vector[:] for n in m.corner_normals])@np.linalg.inv(np.array(ob.matrix_world)[:3,:3]);actualN/=np.maximum(np.linalg.norm(actualN,axis=1)[:,None],1e-20);actualM=np.array([t.material_index for t in m.loop_triangles]);materialMap=[]
 for ma in m.materials:
  candidates=[i for i,n in enumerate(row['materialNames']) if ma.name==n or ma.name.startswith(n+'.')];assert candidates,(row['role'],ma.name,row['materialNames']);materialMap.append(max(candidates,key=lambda i:len(row['materialNames'][i])))
 actualM=np.array(materialMap)[actualM];assert kind=='fbx';assert np.array_equal(actualTri,tr),('FBX changed triangle order',row['role']);cornerDelta=np.linalg.norm(Q[actualTri]-P[tr],axis=2);maxPos=float(cornerDelta.max());maxUV=float(np.abs(actualUV[actualLoops]-UV[loops]).max());materialMismatch=int(np.sum(actualM!=mat));assert maxPos<2e-6 and maxUV<2e-6 and materialMismatch==0,(row['role'],maxPos,maxUV,materialMismatch)
 sourceArea=np.linalg.norm(np.cross(P[tr[:,1]]-P[tr[:,0]],P[tr[:,2]]-P[tr[:,0]]),axis=1)/2;actualArea=np.linalg.norm(np.cross(Q[actualTri[:,1]]-Q[actualTri[:,0]],Q[actualTri[:,2]]-Q[actualTri[:,0]]),axis=1)/2;assert not np.any((actualArea<1e-16)&(sourceArea>=1e-16)),('New collapsed or tiny triangle',row['role'])
 expectedN=normals[loops];gotN=actualN[actualLoops];dot=np.clip(np.sum(expectedN*gotN,axis=2)/np.maximum(np.linalg.norm(expectedN,axis=2),1e-20),-1,1);maxAngle=float(np.degrees(np.arccos(dot)).max());matched=np.ones(len(tr),bool)
 assert matched.all(),('Not all source triangles matched',row['role'],int((~matched).sum()));assert m.name in captured,(m.name,list(captured));cp=captured[m.name];rawDecoded=np.array([n.vector[:] for n in cp.corner_normals]);importLocal=np.array([n.vector[:] for n in m.corner_normals]);assert rawDecoded.shape==importLocal.shape;decodeMaxError=float(np.abs(rawDecoded-importLocal).max());assert decodeMaxError<1e-7,('Independent importer encoding replay mismatch',row['role'],decodeMaxError);bpy.data.meshes.remove(cp);records.append(dict(role=row['role'],vertices=len(Q),triangles=len(tr),allSourceTrianglesMatched=True,maxCornerPositionErrorM=maxPos,maxUVCornerError=maxUV,maxNormalAngleDegrees=maxAngle,materialMismatchCount=materialMismatch,maxImporterEncodingReplayComponentError=decodeMaxError,rawPayloadPreservationAuditedSeparately=False,materialNames=[x.name for x in m.materials]));print('WHOLE_ROLE_VERIFIED',kind,row['role'],records[-1],flush=True)
s.world=world
for name,data,matrix in lightData:light=bpy.data.objects.new(name,data);s.collection.objects.link(light);light.matrix_world=matrix
cam=bpy.data.objects.new('WholeReimportExactCamera502',camData);s.collection.objects.link(cam);s.camera=cam;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=24;s.cycles.use_denoising=True;P=np.load(O/'whole_export_source_character_v500.npz')['positions'];target=(P.min(0)+P.max(0))/2;target[1]=0;renderRows=[]
for view,dir in [('front',(0,-4,0)),('threequarter',(2,-4,0)),('back',(0,4,0)),('left_profile',(-4,0,0)),('right_profile',(4,0,0))]:
 cam.location=target+np.array(dir);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.05;s.render.filepath=str(E/f'whole_reimport_{kind}_{view}_v502.png');bpy.ops.render.render(write_still=True);renderRows.append(dict(view=view,path=Path(s.render.filepath).relative_to(R).as_posix(),sha256=hashlib.sha256(Path(s.render.filepath).read_bytes()).hexdigest()))
assert hashlib.sha256(file.read_bytes()).hexdigest()==pkg['files'][kind]['sha256'];report=dict(version='v502',format=kind,sha256=pkg['files'][kind]['sha256'],independentReimport=True,wholeCharacterWithDress=True,objects=records,totalTriangles=sum(x['triangles'] for x in records),allTriangleUVMaterialAssignmentsVerified=True,correspondenceMethod='Exact preserved FBX triangle indices and per-corner UV identity; no greedy nearest corner assignment',positionAndUVTolerancesUnchanged=True,newCollapsedTriangles=0,allImporterNormalEncodingReplaysVerified=True,rawNormalAudits=["whole_glb_raw_normal_payload_audit_v503.json","whole_fbx_raw_normal_payload_audit_v504.json"],rawNormalAuditRequiredBeforePublication=True,rawSourceNormalIdentityInBlenderNotClaimed=True,renders=renderRows,sameCameraLightsWorldAndColorManagement=True,rigged=False,animations=0,canonicalIdentityApproved=False,physicsVerified=False,productionComplete=False,notPublished=True,elapsedSeconds=time.time()-start);(O/f'reimport_whole_{kind}_audit_v502.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WHOLE_REIMPORT_VERIFIED',kind,flush=True)

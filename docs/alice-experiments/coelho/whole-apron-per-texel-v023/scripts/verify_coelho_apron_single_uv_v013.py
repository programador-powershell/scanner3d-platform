import bpy,sys,json,hashlib,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';X=R/'Assets/Characters/alice_coelho/Exports/apron_single_uv_checkpoint_v013'
kind=sys.argv[sys.argv.index('--')+1];source=bpy.data.objects['Alice.Coelho.Complete.GameCandidate'];source.data.calc_loop_triangles();s=bpy.context.scene
srcP=np.array([source.matrix_world@v.co for v in source.data.vertices],float);srcUV=np.array([u.uv[:] for u in source.data.uv_layers[0].data],float)
srcT=[(np.array(t.vertices),np.array(t.loops),t.material_index) for t in source.data.loop_triangles];assert len(srcT)==150000
sourceTris=len(srcT);used=sorted({int(i) for t,l,mi in srcT for i in t});points=srcP[used];sourceUnused=len(srcP)-len(used)
sourceShader={}
def shader_info(mat):
 nt=mat.node_tree;bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED');result={}
 for label in ['Base Color','Roughness','Metallic','Normal']:
  visited=set();found=[]
  def visit(node):
   if node in visited:return
   visited.add(node)
   if node.type=='TEX_IMAGE' and node.image:found.append(dict(image=node.image.name,size=list(node.image.size),packed=node.image.packed_file is not None))
   for inp in node.inputs:
    for link in inp.links:visit(link.from_node)
  for link in bs.inputs[label].links:visit(link.from_node)
  result[label]=found
 return result
for mat in source.data.materials:sourceShader[mat.name]=shader_info(mat)
cameraState=dict(location=list(s.camera.location),rotation=list(s.camera.rotation_euler),type=s.camera.data.type,ortho_scale=s.camera.data.ortho_scale)
settings=dict(engine=s.render.engine,samples=s.cycles.samples,resolution_x=s.render.resolution_x,resolution_y=s.render.resolution_y,resolution_percentage=s.render.resolution_percentage,view_transform=s.view_settings.view_transform,look=s.view_settings.look,exposure=s.view_settings.exposure,gamma=s.view_settings.gamma)
worldName=s.world.name;world=s.world.copy();world.use_fake_user=True
lightData=[]
for light in s.objects:
 if light.type=='LIGHT':
  d=light.data.copy();d.use_fake_user=True;lightData.append((light.name,d,light.matrix_world.copy()))
report=dict(format=kind,sourceTriangleCount=sourceTris,sourceUnusedVertices=sourceUnused,wholeCharacterWithDress=True,rigged=False,fidelityApproved=False,anatomicalHeightVerified=False,additionalTripoCredits=0)
if kind=='blend':
 high=bpy.data.objects['Alice.Coelho.Complete.High.SourcePreserved'];assert len(high.data.polygons)==1892694
 assert len(source.data.uv_layers)==1 and len(source.data.materials)==2
 assert hashlib.sha256(np.array([v.co[:] for v in source.data.vertices],np.float32).tobytes()).hexdigest()=='75636cc438501d8d08910894b2f3479afea5ddd3c482299840d5bf1f054ab486'
 imgs=[dict(name=i.name,size=list(i.size),packed=i.packed_file is not None) for i in bpy.data.images if i.type=='IMAGE' and i.size[0]]
 assert not bpy.data.libraries and all(i['packed'] for i in imgs)
 report.update(independentReopen=True,highFaces=len(high.data.polygons),UVLayers=1,materials=sourceShader,images=imgs,portableNoExternalLibraries=True)
else:
 # Keep exact camera, world and light copies while clearing the scene only.
 for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
 file=X/f'alice_coelho_complete_apron_single_uv_checkpoint_v013.{kind}'
 if kind=='glb':bpy.ops.import_scene.gltf(filepath=str(file))
 else:bpy.ops.import_scene.fbx(filepath=str(file))
 obs=[o for o in s.objects if o.type=='MESH'];assert len(obs)==1
 ob=obs[0];ob.data.calc_loop_triangles();assert len(ob.data.loop_triangles)==sourceTris and len(ob.data.uv_layers)==1
 actual=np.array([ob.matrix_world@v.co for v in ob.data.vertices],float)
 tree=KDTree(len(points))
 for i,p in enumerate(points):tree.insert(Vector(p),i)
 tree.balance();reverse=KDTree(len(actual))
 for i,p in enumerate(actual):reverse.insert(Vector(p),i)
 reverse.balance();error=max(tree.find(Vector(p))[2] for p in actual);reverseError=max(reverse.find(Vector(p))[2] for p in points)
 assert error<2e-6 and reverseError<2e-6,(error,reverseError)
 # Match triangles by centroid and then corners by position; audit UV and
 # material assignment, including all apron faces, across format conversion.
 faceTree=KDTree(len(srcT))
 for i,(vi,li,mi) in enumerate(srcT):faceTree.insert(Vector(srcP[vi].mean(0)),i)
 faceTree.balance();actualUV=np.array([u.uv[:] for u in ob.data.uv_layers[0].data],float);matched=set();maxUV=0.;mismatches=0;apron=0
 for t in ob.data.loop_triangles:
  vi=np.array(t.vertices);li=np.array(t.loops);p=actual[vi];cent=p.mean(0);candidates=faceTree.find_range(Vector(cent),2e-6);best=None
  for _,idx,dist in candidates:
   svi,sli,smi=srcT[idx];d=np.linalg.norm(p[:,None,:]-srcP[svi][None,:,:],axis=2);order=d.argmin(1)
   if len(set(order))!=3 or d[np.arange(3),order].max()>2e-6:continue
   err=np.abs(actualUV[li]-srcUV[sli[order]]).max()
   if best is None or err<best[0]:best=(err,idx,smi)
  assert best is not None,t.index
  err,idx,smi=best;matched.add(idx);maxUV=max(maxUV,float(err))
  isApron='DedicatedPhotoUV4K' in ob.data.materials[t.material_index].name
  mismatches+=int(isApron!=(smi==1));apron+=int(isApron)
 assert len(matched)==sourceTris and maxUV<2e-6 and mismatches==0 and apron==2270,(len(matched),maxUV,mismatches,apron)
 materials={mat.name:shader_info(mat) for mat in ob.data.materials}
 assert len(materials)==2
 for name,info in materials.items():
  for channel in ['Base Color','Normal','Roughness','Metallic']:
   assert info[channel] and all(i['size']==[4096,4096] for i in info[channel]),(name,channel,info)
 report.update(independentReimport=True,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),triangles=len(ob.data.loop_triangles),maxImportedToSourceDistanceM=error,maxSourceToImportedDistanceM=reverseError,UVLayers=1,allTriangleUVAndMaterialAssignmentsVerified=True,maxUVCornerError=maxUV,materialMismatchCount=mismatches,apronFaces=apron,materials=materials)
 s.world=world
 for name,data,matrix in lightData:
  light=bpy.data.objects.new(name,data);s.collection.objects.link(light);light.matrix_world=matrix
 data=bpy.data.cameras.new('CoelhoExactReviewCamera');cam=bpy.data.objects.new('CoelhoExactReviewCamera',data);s.collection.objects.link(cam);s.camera=cam
 cam.location=cameraState['location'];cam.rotation_euler=cameraState['rotation'];data.type=cameraState['type'];data.ortho_scale=cameraState['ortho_scale']
 s.render.engine=settings['engine'];s.cycles.samples=settings['samples'];s.cycles.use_denoising=True
 for key in ['resolution_x','resolution_y','resolution_percentage']:setattr(s.render,key,settings[key])
 for key in ['view_transform','look','exposure','gamma']:setattr(s.view_settings,key,settings[key])
 s.render.image_settings.file_format='PNG';z=cameraState['location'][2]
 for name,loc,scale,targetZ in [('front',(0,-4,z),data.ortho_scale,z),('right',(4,0,z),data.ortho_scale,z),('back',(0,4,z),data.ortho_scale,z),('detail',(0,-4,.83),.72,.83)]:
  cam.location=loc;data.ortho_scale=scale;cam.rotation_euler=(Vector((0,0,targetZ))-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(E/f'reimport_{kind}_{name}_v013.png');bpy.ops.render.render(write_still=True)
 report.update(sameCameraLightsWorldAndColorManagement=True,renderSettings=settings,camera=cameraState)
(O/f'reimport_{kind}_audit_v013.json').write_text(json.dumps(report,indent=2));print('COELHO_V013_VERIFIED',kind,json.dumps(report),flush=True)

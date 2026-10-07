"""Fresh full-quality render of a numerically verified entire FBX importer scene."""
import bpy,json,hashlib,time,gc
from pathlib import Path
from mathutils import Matrix,Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';D=O/'fbx_reimport_resource_isolation_v1252';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
start=time.time();j=read(D/'numerical_reimport_audit_v1252.json');pkg=read(O/'package_skin_export_v1231.json');assert j['sha256']==pkg['files']['fbx']['sha256'] and sha(R/pkg['files']['fbx']['path'])==j['sha256'];assert sha(R/j['qaBlend']['path'])==j['qaBlend']['sha256'];assert len(j['objects'])==202 and len(j['exportedManualMotionComparedToNative'])==9 and j['boneCount']==209
s=bpy.context.scene;rig=bpy.data.objects[j['rigName']];character=bpy.data.objects[j['characterName']];cam=bpy.data.objects[j['cameraName']];obs=[bpy.data.objects[n] for n in j['meshNames']];assert len(obs)==202 and all(not ob.hide_get() for ob in obs);assert len(rig.data.bones)==209
# Exact duplicate resource deduplication only. No pixel changes, resampling or color-space changes.
imageRows=[];duplicates=[];canonical={}
for im in list(bpy.data.images):
 if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
 row=dict(name=im.name,size=list(im.size),channels=im.channels,colorSpace=im.colorspace_settings.name,alphaMode=im.alpha_mode,isFloat=im.is_float,isDirty=im.is_dirty)
 if im.packed_file:encoded=bytes(im.packed_file.data);row['encodedSHA256']=hashlib.sha256(encoded).hexdigest()
 elif im.filepath and im.source=='FILE':
  f=Path(bpy.path.abspath(im.filepath));assert f.is_file(),('missing full resolution image',im.name,str(f));row['externalPath']=str(f);row['encodedSHA256']=sha(f)
 else:row['encodedSHA256']=None
 imageRows.append(row)
 if row['encodedSHA256'] and not im.is_dirty:
  key=(row['encodedSHA256'],tuple(row['size']),row['channels'],row['colorSpace'],row['alphaMode'],row['isFloat'],im.source)
  if key in canonical:duplicates.append((im,canonical[key],row))
  else:canonical[key]=im
changes=[];trees=set()
def replace(tree):
 if not tree or tree.as_pointer() in trees:return
 trees.add(tree.as_pointer())
 for node in tree.nodes:
  if hasattr(node,'image') and node.image:
   for old,new,row in duplicates:
    if node.image==old:node.image=new;changes.append(dict(tree=tree.name,node=node.name,oldImage=old.name,newImage=new.name,encodedSHA256=row['encodedSHA256'],sameSizeColorSpaceAlphaModeAndSource=True))
  replace(getattr(node,'node_tree',None))
for ma in bpy.data.materials:replace(ma.node_tree)
replace(s.world.node_tree)
for light in bpy.data.lights:replace(light.node_tree)
for old,new,row in duplicates:
 if old.users==0 or (old.users==1 and old.use_fake_user):old.use_fake_user=False;bpy.data.images.remove(old)
gc.collect();print('FULL_RESOLUTION_IDENTICAL_RESOURCE_DEDUP',len(duplicates),'refs',len(changes),flush=True)
s.render.use_persistent_data=False;s.render.use_simplify=False;s.render.threads_mode='FIXED';s.render.threads=2;s.cycles.device='CPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.camera=cam
assert s.render.engine=='CYCLES';poseMatrices={label:{n:Matrix(m) for n,m in matrices.items()} for label,matrices in j['poseMatrices'].items()};ordered=sorted(rig.data.bones.keys(),key=lambda n:len(rig.data.bones[n].parent_recursive))
def pose(label):
 hidden=[(o,o.hide_get()) for o in obs if o!=character]
 for o,v in hidden:o.hide_set(True)
 for n in ordered:rig.pose.bones[n].matrix=poseMatrices[label][n];bpy.context.view_layer.update()
 for o,v in hidden:o.hide_set(v)
 bpy.context.view_layer.update();assert len(obs)==202 and all(not o.hide_get() for o in obs)
rows=[]
def render(label,target,direction,scale,close=False):
 target=Vector(target);cam.location=target+Vector(direction);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;s.render.resolution_x=1000 if close else 900;s.render.resolution_y=1000 if close else 1100;s.render.resolution_percentage=100;out=E/f'whole_reimport_fbx_{label}_v1235.png';assert not out.exists();s.render.filepath=str(out);bpy.ops.render.render(write_still=True);rows.append(dict(view=label,path=out.relative_to(R).as_posix(),sha256=sha(out),freshFactoryRenderProcess=True,manualDiagnosticPose=label in ['right_elbow','left_elbow'],linkedWalkStudyNotGameplayApproved=label.startswith('walk_')));gc.collect();print('FRESH_WHOLE_FBX_RENDER_DONE',label,flush=True)
for view,direction in [('front',(0,-4,0)),('back',(0,4,0)),('rear_threequarter',(1.7,4,.04))]:render(view,j['renderTarget'],direction,2.05)
render('rear_clock_close',(0,.17,1.02),(0,4,.04),.22,True)
for label in ['right_elbow','left_elbow']:
 pose(label);render(label,(0,0,.88),(0,-4,0),2.04)
for label,direction in [('walk_study_frame11',(0,-4,0)),('walk_study_frame11_profile',(-4,0,0)),('walk_study_frame31',(0,-4,0)),('walk_study_frame31_left_profile',(4,0,0)),('walk_study_frame27',(0,-4,0)),('walk_study_frame27_left_profile',(4,0,0))]:
 key='walk_study_frame31' if '31' in label else 'walk_study_frame27' if '27' in label else 'walk_study_frame11';pose(key);render(label,(0,0,.88),direction,2.04)
assert len(rows)==12 and sha(R/pkg['files']['fbx']['path'])==j['sha256'] and sha(R/j['qaBlend']['path'])==j['qaBlend']['sha256'] and sha(R/pkg['files']['blend']['path'])==pkg['files']['blend']['sha256'];report=dict(j,version='v1235',renders=rows,freshRenderProcessResourceAudit=dict(version='v1253',all202MeshesAnd209BonesRetained=True,allOriginalImageResolutionRetained=True,onlyExactDuplicateImageResourcePointersReused=True,imageResourcesBefore=imageRows,reusedImageReferences=changes,pixelOrGeometryReduction=False,sourceAndFBXAndVerifiedQASceneUnchanged=True,samples=24,threads=2,textureResolutionLimitUsed=False),elapsedSeconds=time.time()-start,productionComplete=False);(O/'reimport_whole_fbx_audit_v1235.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WHOLE_REIMPORT_VERIFIED_FBX_FRESH_RENDER_ALL202_9POSES_12IMAGES',flush=True)

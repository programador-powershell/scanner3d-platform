import bpy,numpy as np,json,hashlib,time,struct
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';T=O/'Textures';W=4096;start=time.time();s=bpy.context.scene;ob=bpy.data.objects['Alice.Coelho.Complete.GameCandidate'];m=ob.data;m.calc_loop_triangles();P=np.array([v.co[:] for v in m.vertices],np.float32);UV=np.array([v.uv[:] for v in m.uv_layers[0].data],np.float32);ghash=hashlib.sha256(P.tobytes()).hexdigest();uhash=hashlib.sha256(UV.tobytes()).hexdigest()
def facekey(mesh,t):return tuple(sorted(struct.pack('<5f',*mesh.vertices[vi].co[:],*mesh.uv_layers[0].data[li].uv[:]) for vi,li in zip(t.vertices,t.loops)))
lookup={facekey(m,t):t.polygon_index for t in m.loop_triangles};assert len(lookup)==150000
dress=O/'Dress/alice_coelho_vestido_autoria_parcial_v013.blend';assert hashlib.sha256(dress.read_bytes()).hexdigest()=='9575a35bc28b13a24431d0fc133d206225b64d5b950fc375d177263710375621'
with bpy.data.libraries.load(str(dress),link=False) as (src,dst):dst.objects=['Alice.Coelho.FrontApron.UV.WorkSurface.v013']
patch=dst.objects[0];patch.data.calc_loop_triangles();ids={lookup[facekey(patch.data,t)] for t in patch.data.loop_triangles};assert len(ids)==8427;patchData=patch.data;bpy.data.objects.remove(patch,do_unlink=True)
if patchData.users==0:bpy.data.meshes.remove(patchData)
for library in list(bpy.data.libraries):
 references=[]
 for prop in bpy.data.bl_rna.properties:
  if prop.type!='COLLECTION':continue
  for item in getattr(bpy.data,prop.identifier):
   if getattr(item,'library',None)==library:references.append(item.name)
   override=getattr(item,'override_library',None)
   if override and getattr(override.reference,'library',None)==library:references.append(item.name+' override reference')
 print('TEMPORARY_APPEND_LIBRARY_REFERENCES',library.filepath,references,flush=True)
 assert not references,'Appended own surface still contains external linked IDs'
 bpy.data.libraries.remove(library)
assert not bpy.data.libraries
c=json.loads((O/'photo_calibration_front_apron_v007.json').read_text());mask=np.load(O/'photo_plate_front_apron_v007.npz')['mask'];reference=bpy.data.images.load(str(E/'front_apron_dedicated_photo_4096_v011.png'),check_existing=False);photo=np.empty(W*W*4,np.float32);reference.pixels.foreach_get(photo);photo=photo.reshape(W,W,4)
mat=m.materials[0];bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');tex=bs.inputs['Base Color'].links[0].from_node;original=tex.image;before=np.empty(W*W*4,np.float32);original.pixels.foreach_get(before);before=before.reshape(W,W,4);after=before.copy();paint=np.zeros((W,W),bool);tree=BVHTree.FromPolygons([Vector(p) for p in P],[t.vertices[:] for t in m.loop_triangles],all_triangles=True);tested=0;hidden=0;ownerRejected=0;candidateFaces=0;maskRejected=0
for t in m.loop_triangles:
 if t.polygon_index not in ids or t.material_index!=0:continue
 candidateFaces+=1;u=UV[list(t.loops)].astype(float);M=np.column_stack((u[1]-u[0],u[2]-u[0]));lo=np.maximum(np.floor(u.min(0)*W).astype(int),0);hi=np.minimum(np.ceil(u.max(0)*W).astype(int),W-1);xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5);samples=np.column_stack((xx.ravel()/W,yy.ravel()/W));b=(samples-u[0])@np.linalg.inv(M).T;b=np.column_stack((1-b.sum(1),b));inside=b.min(1)>1e-5
 if not inside.any():continue
 samples=samples[inside];b=b[inside];points=b@P[list(t.vertices)];photoX=c['centerX']+points[:,0]*c['pixelsPerM'];photoY=np.interp(points[:,2],c['worldZ'],c['photoY']);px=np.floor(photoX).astype(int);py=np.floor(photoY).astype(int);gate=(points[:,2]>.58)&(points[:,2]<1.065)&(px>=0)&(px+1<mask.shape[1])&(py>=0)&(py+1<mask.shape[0]);allowed=np.flatnonzero(gate);gate[allowed]&=mask[py[allowed],px[allowed]]&mask[py[allowed]+1,px[allowed]]&mask[py[allowed],px[allowed]+1]&mask[py[allowed]+1,px[allowed]+1];maskRejected+=int((~gate).sum());visible=[]
 for i in np.flatnonzero(gate):
  loc,normal,index,distance=tree.ray_cast(Vector((points[i,0],-3,points[i,2])),Vector((0,1,0)),4);tested+=1
  if index!=t.index:ownerRejected+=1;continue
  if loc is None or (loc-Vector(points[i])).length>.000035:hidden+=1;continue
  visible.append(i)
 if not visible:continue
 ii=np.array(visible);su=np.clip((photoX[ii]-308)/222*W-.5,0,W-1.000001);sv=np.clip((1-(photoY[ii]-120)/455)*W-.5,0,W-1.000001);sx=np.floor(su).astype(int);sy=np.floor(sv).astype(int);fx=(su-sx)[:,None];fy=(sv-sy)[:,None];rgb=photo[sy,sx,:3]*(1-fx)*(1-fy)+photo[sy,sx+1,:3]*fx*(1-fy)+photo[sy+1,sx,:3]*(1-fx)*fy+photo[sy+1,sx+1,:3]*fx*fy;ix=(samples[ii,0]*W).astype(int);iy=(samples[ii,1]*W).astype(int);after[iy,ix,:3]=rgb;paint[iy,ix]=True
assert paint.sum()>100 and np.array_equal(after[~paint],before[~paint]);bpy.data.images.remove(reference)
cam=s.camera;loc=cam.location.copy();rot=cam.rotation_euler.copy();scale=cam.data.ortho_scale;cam.location=(0,-4,.83);cam.rotation_euler=(Vector((0,0,.83))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.72;s.cycles.samples=16;s.render.filepath=str(E/'apron_both_atlases_before_v020.png');bpy.ops.render.render(write_still=True)
im=bpy.data.images.new('alice_coelho_apron_fallback_photo_4096_v020',width=W,height=W,alpha=True);im.colorspace_settings.name=original.colorspace_settings.name;im.pixels.foreach_set(after.ravel());im.filepath_raw=str(T/(im.name+'.png'));im.file_format='PNG';im.save();im.pack();tex.image=im;s.render.filepath=str(E/'apron_both_atlases_after_v020.png');bpy.ops.render.render(write_still=True);cam.data.ortho_scale=scale
for name,cloc in [('front',(0,-4,loc.z)),('right',(4,0,loc.z)),('back',(0,4,loc.z))]:
 cam.location=cloc;cam.rotation_euler=(Vector((0,0,loc.z))-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(E/f'apron_both_atlases_{name}_v020.png');bpy.ops.render.render(write_still=True)
cam.location=loc;cam.rotation_euler=rot;assert ghash==hashlib.sha256(np.array([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest() and uhash==hashlib.sha256(np.array([v.uv[:] for v in m.uv_layers[0].data],np.float32).tobytes()).hexdigest();out=O/'alice_coelho_complete_apron_both_atlases_candidate_v020.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);np.savez_compressed(O/'apron_fallback_projection_mask_v020.npz',painted=paint)
report=dict(source='alice_coelho_complete_apron_per_texel_photo_candidate_v019.blend',candidate=str(out.relative_to(R)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),matchedOwnApronWorkSurfaceFaces=len(ids),candidateMaterial0Faces=candidateFaces,noOtherAssetOrOldMeshImported=True,geometryExactlyPreserved=True,UVExactlyPreserved=True,actualWorldPointPhotoLookup=True,sourcePhotoOriginalNotEdited=True,firstHitMustBeSameTriangle=True,testedDepthRays=tested,rejectedOtherOwner=ownerRejected,rejectedDepth=hidden,rejectedPhotoMask=maskRejected,paintedTexels=int(paint.sum()),outsideMaterial0ProjectionPixelsExactlyPreserved=True,material1FromV019Preserved=True,normalRoughnessMetallicUnchanged=True,triangleEdgesSubpixelVisibilityNotProven=True,rigged=False,fidelityApproved=False,exportVerified=False,additionalTripoCredits=0,elapsedSeconds=time.time()-start)
(O/'apron_fallback_projection_audit_v020.json').write_text(json.dumps(report,indent=2));print('APRON_BOTH_ATLASES_CANDIDATE_FINISHED',json.dumps(report),flush=True)

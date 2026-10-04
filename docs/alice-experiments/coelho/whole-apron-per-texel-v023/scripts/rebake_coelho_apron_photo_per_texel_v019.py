import bpy,numpy as np,json,hashlib,time
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';T=O/'Textures';W=4096;start=time.time();s=bpy.context.scene;ob=bpy.data.objects['Alice.Coelho.Complete.GameCandidate'];m=ob.data;m.calc_loop_triangles()
P=np.array([v.co[:] for v in m.vertices],np.float32);UV=np.array([v.uv[:] for v in m.uv_layers[0].data],np.float32);gHash=hashlib.sha256(P.tobytes()).hexdigest();uvHash=hashlib.sha256(UV.tobytes()).hexdigest();c=json.loads((O/'photo_calibration_front_apron_v007.json').read_text());mask=np.load(O/'photo_plate_front_apron_v007.npz')['mask'];accepted=set(np.load(O/'apron_dedicated_uv_faces_v011.npz')['accepted'].tolist())
mat=m.materials[1];bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');tex=bs.inputs['Base Color'].links[0].from_node;source=tex.image;before=np.empty(W*W*4,np.float32);source.pixels.foreach_get(before);before=before.reshape(W,W,4);after=before.copy();paint=np.zeros((W,W),bool);tree=BVHTree.FromPolygons([Vector(p) for p in P],[t.vertices[:] for t in m.loop_triangles],all_triangles=True)
errorMax=0.;errorSum=0.;errorCount=0;clockErrorMax=0.;tested=0;hidden=0;outsideMask=0
for k,t in enumerate(m.loop_triangles):
 if t.polygon_index not in accepted:continue
 u=UV[list(t.loops)].astype(float);M=np.column_stack((u[1]-u[0],u[2]-u[0]));lo=np.maximum(np.floor(u.min(0)*W).astype(int),0);hi=np.minimum(np.ceil(u.max(0)*W).astype(int),W-1);xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5);samples=np.column_stack((xx.ravel()/W,yy.ravel()/W));b=(samples-u[0])@np.linalg.inv(M).T;b=np.column_stack((1-b.sum(1),b));inside=b.min(1)>1e-5
 if not inside.any():continue
 samples=samples[inside];b=b[inside];points=b@P[list(t.vertices)];photoX=c['centerX']+points[:,0]*c['pixelsPerM'];photoY=np.interp(points[:,2],c['worldZ'],c['photoY']);uvPhotoY=120+(1-samples[:,1])*455;errors=np.abs(photoY-uvPhotoY);errorMax=max(errorMax,float(errors.max()));errorSum+=float(errors.sum());errorCount+=len(errors);inClock=(photoY>294)&(photoY<436)&(photoX>340)&(photoX<495)
 if inClock.any():clockErrorMax=max(clockErrorMax,float(errors[inClock].max()))
 px=np.floor(photoX).astype(int);py=np.floor(photoY).astype(int);valid=mask[py,px]&mask[py+1,px]&mask[py,px+1]&mask[py+1,px+1];outsideMask+=int((~valid).sum());ids=np.flatnonzero(valid);visible=[]
 for i in ids:
  loc=tree.ray_cast(Vector((points[i,0],-3,points[i,2])),Vector((0,1,0)),4)[0];tested+=1
  if loc is not None and (loc-Vector(points[i])).length<=.000035:visible.append(i)
  else:hidden+=1
 if not visible:continue
 ii=np.array(visible);su=(photoX[ii]-308)/222*W-.5;sv=(1-(photoY[ii]-120)/455)*W-.5;su=np.clip(su,0,W-1.000001);sv=np.clip(sv,0,W-1.000001);sx=np.floor(su).astype(int);sy=np.floor(sv).astype(int);fx=(su-sx)[:,None];fy=(sv-sy)[:,None];rgb=before[sy,sx,:3]*(1-fx)*(1-fy)+before[sy,sx+1,:3]*fx*(1-fy)+before[sy+1,sx,:3]*(1-fx)*fy+before[sy+1,sx+1,:3]*fx*fy
 ix=(samples[ii,0]*W).astype(int);iy=(samples[ii,1]*W).astype(int);after[iy,ix,:3]=rgb;paint[iy,ix]=True
 if k%10000==0:print('PHOTO_REBAKE_PROGRESS',k,tested,round(time.time()-start,1),flush=True)
assert tested>100000 and hidden==0 and np.array_equal(after[~paint],before[~paint]);assert errorMax>.1,'No meaningful non-linear UV interpolation error was found'
cam=s.camera;oldloc=cam.location.copy();oldrot=cam.rotation_euler.copy();oldscale=cam.data.ortho_scale;cam.location=(0,-4,.83);cam.rotation_euler=(Vector((0,0,.83))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.72;s.cycles.samples=16;s.render.filepath=str(E/'apron_photo_per_texel_before_v019.png');bpy.ops.render.render(write_still=True)
im=bpy.data.images.new('alice_coelho_apron_photo_per_texel_4096_v019',width=W,height=W,alpha=True);im.colorspace_settings.name=source.colorspace_settings.name;im.pixels.foreach_set(after.ravel());im.filepath_raw=str(T/(im.name+'.png'));im.file_format='PNG';im.save();im.pack();tex.image=im;s.render.filepath=str(E/'apron_photo_per_texel_after_v019.png');bpy.ops.render.render(write_still=True);cam.data.ortho_scale=oldscale
for name,loc in [('front',(0,-4,oldloc.z)),('right',(4,0,oldloc.z)),('back',(0,4,oldloc.z))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,0,oldloc.z))-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(E/f'apron_photo_per_texel_{name}_v019.png');bpy.ops.render.render(write_still=True)
cam.location=oldloc;cam.rotation_euler=oldrot;assert hashlib.sha256(np.array([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest()==gHash and hashlib.sha256(np.array([u.uv[:] for u in m.uv_layers[0].data],np.float32).tobytes()).hexdigest()==uvHash
out=O/'alice_coelho_complete_apron_per_texel_photo_candidate_v019.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);np.savez_compressed(O/'apron_per_texel_projection_mask_v019.npz',painted=paint)
report=dict(source='alice_coelho_complete_apron_single_uv_checkpoint_v013.blend',candidate=str(out.relative_to(R)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),geometryExactlyPreserved=True,UVExactlyPreserved=True,noNewArtOrFontsOrGlyphComposition=True,actualBarycentricWorldPointUsedForPhotoLookup=True,nonlinearVertexUVApproximationErrorMaxNativePhotoPixels=errorMax,nonlinearVertexUVApproximationErrorMeanNativePhotoPixels=errorSum/errorCount,clockInterpolationErrorMaxNativePhotoPixels=clockErrorMax,testedFirstHitDepthRays=tested,rejectedForDepth=hidden,rejectedForTruePhotoMask=outsideMask,paintedTexels=int(paint.sum()),depthToleranceM=.000035,outsideProjectionPixelsExactlyPreserved=True,normalRoughnessMetallicAndMaterial0Unchanged=True,sourcePhotoNativeSize=[222,455],triangleEdgesAndSubpixelVisibilityNotProven=True,rigged=False,fidelityApproved=False,exportVerified=False,additionalTripoCredits=0,elapsedSeconds=time.time()-start)
(O/'apron_per_texel_projection_audit_v019.json').write_text(json.dumps(report,indent=2));print('APRON_PER_TEXEL_CANDIDATE_FINISHED',json.dumps(report),flush=True)

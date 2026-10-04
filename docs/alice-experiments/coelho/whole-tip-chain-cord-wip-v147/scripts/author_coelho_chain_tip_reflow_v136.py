"""Recount/reflow rigid rings on corrected apron arc, preserving their UV/normal bake."""
import bpy,bmesh,numpy as np,json,hashlib,time,sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';start=time.time();sys.path.insert(0,str(R/'Tools/PythonDeps/mesh_repair'));from scipy.ndimage import gaussian_filter1d,minimum_filter1d
a=json.loads((O/'apron_lace_local_weave_authoring_audit_v129.json').read_text(encoding='utf-8-sig'));src=R/a['path'];assert hashlib.sha256(src.read_bytes()).hexdigest()==a['sha256'];old=bpy.data.objects['Alice.Coelho.Apron.ChainLOD.Candidate.v066'];d=json.loads((O/'apron_chain_links_v059.json').read_text(encoding='utf-8-sig'));original=d['links'];apron=bpy.data.objects[a['clothObject']];Q=np.array([v.co[:] for v in apron.data.shape_keys.key_blocks['StaticRestFit_REVIEW_NotRuntimePhysics'].data]);assert len(Q)==2101
ev=apron.evaluated_get(bpy.context.evaluated_depsgraph_get());em=ev.to_mesh();em.calc_loop_triangles();tri=np.array([t.vertices[:] for t in em.loop_triangles if em.polygons[t.polygon_index].material_index==0]);ev.to_mesh_clear();tree=BVHTree.FromPolygons([Vector(q) for q in Q],[tuple(t) for t in tri],all_triangles=True);normals=np.zeros_like(Q);area=np.cross(Q[tri[:,1]]-Q[tri[:,0]],Q[tri[:,2]]-Q[tri[:,0]])
for j in range(3):np.add.at(normals,tri[:,j],area)
normals/=np.linalg.norm(normals,axis=1)[:,None]
def norm(v):return v/np.linalg.norm(v)
def nearest(p):
 hit,n,idx,dist=tree.find_nearest(Vector(p));ids=tri[idx];v=np.linalg.lstsq(np.stack([Q[ids[1]]-Q[ids[0]],Q[ids[2]]-Q[ids[0]]],1),np.array(hit)-Q[ids[0]],rcond=None)[0];w=np.maximum(np.r_[1-v.sum(),v],0);w/=w.sum();return w@Q[ids],norm(w@normals[ids]),int(idx),ids,w
def at(path,arc,s):return np.array([np.interp(s,arc,path[:,c]) for c in range(3)])
P=np.array([v.co[:] for v in old.data.vertices]);newPositions=[];sourceIDs=[];links=[];pathRows=[]
for side in ['left','right']:
 edgeIDs=[j*25+(0 if side=='left' else 24) for j in range(84)]+[2100];innerIDs=[j*25+(1 if side=='left' else 23) for j in range(84)]+[2100];raw=[]
 for e,i in zip(edgeIDs,innerIDs):
  delta=Q[i]-Q[e];length=np.linalg.norm(delta);raw.append(Q[e]+delta/max(length,1e-20)*min(.003,length*.5))
 raw=np.array(raw);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(raw,axis=0),axis=1))];samples=np.linspace(0,arc[-1],int(np.ceil(arc[-1]/.001))+1);path=np.column_stack([np.interp(samples,arc,raw[:,c]) for c in range(3)]);path=gaussian_filter1d(path,3,axis=0,mode='nearest');path=np.array([nearest(p)[0]+nearest(p)[1]*.0023 for p in path]);path=gaussian_filter1d(path,10,axis=0,mode='nearest');constraints=[]
 for p in path:
  depths=[]
  for dx in [-.004,0,.004]:
   for dz in [-.004,0,.004]:
    hit,n,i,dist=tree.ray_cast(Vector((float(p[0]+dx),-3,float(p[2]+dz))),Vector((0,1,0)),4)
    if hit is not None:depths.append(hit.y)
  assert depths;constraints.append(min(depths)-.0041)
 constraints=np.array(constraints);path[:,1]=np.minimum(path[:,1],np.minimum(constraints,gaussian_filter1d(minimum_filter1d(constraints,size=21,mode='nearest'),5,mode='nearest')));arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(path,axis=0),axis=1))];count=round((arc[-1]-.036)/.0061)+1;available=[x for x in original if x['side']==side];assert 2<count<=len(available),(side,count,len(available));pitch=(arc[-1]-.036)/(count-1);pathRows.append(dict(side=side,arcLengthM=float(arc[-1]),previousCount=len(available),newCount=count,pitchM=float(pitch),endMarginM=.018,referenceCountsWereInferredNotPhotographicallyMeasured=True));prevT=prevN=None
 for k in range(count):
  dist=.018+k*pitch;center=at(path,arc,dist);tangent=norm(at(path,arc,dist+.001)-at(path,arc,dist-.001));root,surfaceN,idx,ids,w=nearest(center);normal=norm(surfaceN-tangent*np.dot(surfaceN,tangent))
  if prevT is not None:
   axis=np.cross(prevT,tangent);si=np.linalg.norm(axis);co=np.clip(np.dot(prevT,tangent),-1,1)
   if si>1e-10:axis/=si;normal=prevN*co+np.cross(axis,prevN)*si+axis*np.dot(axis,prevN)*(1-co)
   else:normal=prevN.copy()
   normal=norm(normal-tangent*np.dot(normal,tangent))
  prevT=tangent.copy();prevN=normal.copy();transverse=norm(np.cross(normal,tangent)) if k%2==0 else normal;plane=norm(np.cross(tangent,transverse));ref=available[k];rid=ref['id'];oldT=np.array(ref['tangent']);oldN=np.array(ref['planeNormal']);oldB=np.cross(oldN,oldT);basisOld=np.stack([oldT,oldB,oldN]);basisNew=np.stack([tangent,transverse,plane]);rotation=basisOld.T@basisNew;local=P[rid*144:(rid+1)*144]-np.array(ref['center']);positions=local@rotation+center;newPositions.extend(positions);sourceIDs.append(rid);link=dict(id=rid,newOrdinal=len(links),side=side,localID=k,center=center.tolist(),tangent=tangent.tolist(),planeNormal=plane.tolist(),clothNormal=surfaceN.tolist(),clothRootTriangle=idx,clothRootVertices=ids.tolist(),clothRootBarycentric=w.tolist(),clothRootPosition=root.tolist(),clothRootOffset=(center-root).tolist(),rigidGeometryAndNormalBakeCellPreserved=True);links.append(link)
newPositions=np.array(newPositions);faces=[];uvs=[];faceIDs=[]
for newID,rid in enumerate(sourceIDs):
 for p in old.data.polygons[rid*144:(rid+1)*144]:faces.append(tuple(newID*144+(v-rid*144) for v in p.vertices));uvs.extend([old.data.uv_layers[0].data[i].uv[:] for i in p.loop_indices]);faceIDs.append(rid)
m=bpy.data.meshes.new('Alice.Coelho.Chain.Reflow.v136');m.from_pydata(newPositions.tolist(),[],faces);m.update();uv=m.uv_layers.new(name=old.data.uv_layers[0].name);uv.data.foreach_set('uv',np.array(uvs,np.float32).ravel());att=m.attributes.new('stable_chain_link_id','INT','FACE');att.data.foreach_set('value',np.array(faceIDs,np.int32));att=m.attributes.new('cloth_root_triangle','INT','POINT');att.data.foreach_set('value',np.repeat([x['clothRootTriangle'] for x in links],144).astype(np.int32))
for p in m.polygons:p.use_smooth=True
for mat in old.data.materials:m.materials.append(mat)
ob=bpy.data.objects.new('Alice.Coelho.Apron.ChainReflow.Candidate.v136',m);bpy.context.scene.collection.objects.link(ob);ob.hide_render=True;ob.hide_set(True);ob['scope']='Rigid rings recounted at original pitch on corrected cloth arc; source rings/UV/normal bake preserved. Await linkage/contact/appearance, sew roots, rig/physics and full release.'
out=O/'Dress/alice_coelho_apron_chain_reflow_candidate_v136.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert hashlib.sha256(src.read_bytes()).hexdigest()==a['sha256'];d.update(version='v136',sourceApron=a['clothObject'],links=links,paths=pathRows,productionComplete=False);(O/'apron_chain_links_v136.json').write_text(json.dumps(d,indent=2),encoding='utf-8');report=dict(version='v136',source=src.relative_to(R).as_posix(),sourceSHA256=a['sha256'],path=out.relative_to(R).as_posix(),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),object=ob.name,clothObject=a['clothObject'],parts=[dict(role='chain',object=ob.name,referenceObject=old.name)]+a['parts'][1:],links=len(links),paths=pathRows,stableSourceRingIDs=sourceIDs,rigidIndividualRingGeometryUVNormalMapsPreserved=True,sourceWholeAndOtherCandidatesPreserved=True,requiresIndependentContactLinkageAndAppearanceReview=True,rigged=False,physicsVerified=False,productionComplete=False,notIntegrated=True,notPublished=True,elapsedSeconds=time.time()-start);(O/'apron_chain_reflow_authoring_audit_v136.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('CHAIN_REFLOW_SAVED',len(links),pathRows,flush=True)

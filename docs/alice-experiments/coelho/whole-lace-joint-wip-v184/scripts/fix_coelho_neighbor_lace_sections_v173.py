"""Local finite-radius separation at actual cross-motif intersections; no global depth shifts."""
import bpy, numpy as np, json, hashlib, sys, time
from pathlib import Path
R=Path('F:/Alice/SharedProduction'); O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'; sys.path.insert(0,str(R/'Tools'))
from coelho_neighbor_lace_contact_helper_v173 import audit_neighbors
from coelho_lace_triangle_audit_v091 import sat_intersects
from audit_coelho_lace_self_subset_v113 import audit_self_subset
from mathutils import Vector
from mathutils.bvhtree import BVHTree
start=time.time(); state=json.loads((R/'Assets/Characters/alice_coelho/working_checkpoint.json').read_text(encoding='utf-8-sig')); source=R/state['currentBlend']; expected=state['currentLocalAuthoringCandidate']['sha256']
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()
assert sha(source)==expected; assert json.loads((R/'Coordination/Claims/alice_coelho.json').read_text())['owner']=='root_coelho_refinement_20261003'
paths=json.loads((O/'apron_dense_lace_paths_v129.json').read_text(encoding='utf-8-sig'))['paths']; old=bpy.data.objects['Alice.Coelho.WholeCheckpoint145.lace']; mesh=old.data; mesh.calc_loop_triangles()
P=np.asarray([v.co[:] for v in mesh.vertices]); original=P.copy(); triangles=np.asarray([t.vertices[:] for t in mesh.loop_triangles],np.int32); facepath=np.asarray([mesh.attributes['stable_dense_lace_path_id'].data[t.polygon_index].value for t in mesh.loop_triangles],np.int32); offsets=np.r_[0,np.cumsum([p['pointsCount']*6 for p in paths])]
new=old.copy(); new.data=mesh.copy(); new.name='Alice.Coelho.Apron.LaceNeighborSections.Candidate.v173'; bpy.context.scene.collection.objects.link(new); new.hide_render=True; new.hide_set(True)
modified=set(); steps=[]
for iteration in range(20):
    audit,constraints=audit_neighbors(P,triangles,facepath,paths,offsets); audit['iteration']=iteration; steps.append(audit)
    progress=dict(version='v173',sourceSHA256=expected,steps=steps,notSaved=True,productionComplete=False); (O/'apron_neighbor_sections_progress_v173.json').write_text(json.dumps(progress,indent=2)+'\n',encoding='utf-8')
    print('LOCAL_NEIGHBOR_SECTIONS',iteration,'motifPairs',audit['intersectingMotifPairs'],'triangles',audit['SATTrianglePairs'],'seconds',round(time.time()-start,1),flush=True)
    if iteration==0: assert audit['SATTrianglePairs']==1431
    if audit['SATTrianglePairs']==0: break
    for aid,ia,bid,ib in constraints:
        ablocks=P[offsets[aid]:offsets[aid+1]].reshape(-1,6,3); bblocks=P[offsets[bid]:offsets[bid+1]].reshape(-1,6,3)
        anext=(ia+1)%len(ablocks); bnext=(ib+1)%len(bblocks); A=ablocks[[ia,anext]].mean(1); B=bblocks[[ib,bnext]].mean(1)
        d1=A[1]-A[0]; d2=B[1]-B[0]; r=A[0]-B[0]; aa=np.dot(d1,d1); ee=np.dot(d2,d2); ff=np.dot(d2,r); cc=np.dot(d1,r); bb=np.dot(d1,d2); denominator=aa*ee-bb*bb
        ss=float(np.clip((bb*ff-cc*ee)/denominator,0,1)) if denominator>1e-28 else 0.; tt=(bb*ss+ff)/max(ee,1e-30)
        if tt<0: tt=0.; ss=float(np.clip(-cc/max(aa,1e-30),0,1))
        elif tt>1: tt=1.; ss=float(np.clip((bb-cc)/max(aa,1e-30),0,1))
        pa=A[0]+ss*d1; pb=B[0]+tt*d2; difference=pa-pb; distance=float(np.linalg.norm(difference)); target=paths[aid]['radius']+paths[bid]['radius']+.000015
        if distance>=target: continue
        if distance>1e-10: normal=difference/distance
        else:
            normal=np.cross(d1,d2)
            if np.linalg.norm(normal)<1e-15: normal=np.cross(d1,np.eye(3)[np.argmin(np.abs(d1))])
            normal/=np.linalg.norm(normal)
            if normal[1]>0: normal=-normal
        chooseA=pa[1]<=pb[1]; pid=aid if chooseA else bid; station=ia if chooseA else ib; blocks=ablocks if chooseA else bblocks; vector=normal*min(target-distance,.00008)*(1 if chooseA else -1)
        ids=np.arange(len(blocks)); weights=np.zeros(len(blocks))
        for center in [station,(station+1)%len(blocks)]:
            delta=np.abs(ids-center)
            if paths[pid]['closedCenterline']: delta=np.minimum(delta,len(blocks)-delta)
            weights=np.maximum(weights,np.exp(-.5*(delta/2.5)**2)*(delta<=8))
        blocks+=weights[:,None,None]*vector; modified.add(pid)
    assert np.linalg.norm(P-original,axis=1).max()<.0005, 'Local movement cap exceeded; no save'
else: raise AssertionError('Local cross-motif contacts remain; no save')
new.data.vertices.foreach_set('co',P.astype(np.float32).ravel()); new.data.update(); selfQA=audit_self_subset(new.data,paths,modified); assert not selfQA,('New self-folds; no save',selfQA)
tree=BVHTree.FromPolygons([Vector(p) for p in P],[tuple(t) for t in triangles],all_triangles=True); targetcounts={}
for name in ['Alice.Coelho.WholeCheckpoint145.apron','Alice.Coelho.WholeCheckpoint145.character','Alice.Coelho.WholeCheckpoint145.chain','Alice.Coelho.WholeCheckpoint145.cord']:
    ob=bpy.data.objects[name]; ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); em=ev.to_mesh(); em.calc_loop_triangles(); Q=np.asarray([ev.matrix_world@v.co for v in em.vertices]); tri=np.asarray([t.vertices[:] for t in em.loop_triangles],np.int32); tbvh=BVHTree.FromPolygons([Vector(p) for p in Q],[tuple(t) for t in tri],all_triangles=True); pairs=tree.overlap(tbvh); n=0
    for k in range(0,len(pairs),4096):
        chunk=np.asarray(pairs[k:k+4096],np.int32); n+=int(sat_intersects(P[triangles[chunk[:,0]]],Q[tri[chunk[:,1]]]).sum())
    targetcounts[name]=n; ev.to_mesh_clear()
assert not any(targetcounts.values()),('New external contact; no save',targetcounts)
radial=0.
for pid in modified:
    a=P[offsets[pid]:offsets[pid+1]].reshape(-1,6,3); b=original[offsets[pid]:offsets[pid+1]].reshape(-1,6,3); radial=max(radial,float(np.abs((a-a.mean(1)[:,None,:])-(b-b.mean(1)[:,None,:])).max()))
assert radial<1e-12
for pid in set(range(len(paths)))-modified: assert np.array_equal(P[offsets[pid]:offsets[pid+1]],original[offsets[pid]:offsets[pid+1]])
for u,v in zip(mesh.uv_layers,new.data.uv_layers): assert np.array_equal(np.asarray([x.uv[:] for x in u.data]),np.asarray([x.uv[:] for x in v.data]))
out=O/'Dress/alice_coelho_apron_lace_neighbor_sections_candidate_v173.blend'; assert not out.exists(); bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True); assert sha(source)==expected
newpaths=[]
for p in paths:
    rec=dict(p); rec['worldCenterline']=np.asarray([v.co[:] for v in new.data.vertices[offsets[p['id']]:offsets[p['id']+1]]]).reshape(-1,6,3).mean(1).tolist(); newpaths.append(rec)
(O/'apron_dense_lace_paths_v173.json').write_text(json.dumps(dict(version='v173',paths=newpaths,productionComplete=False),indent=2)+'\n',encoding='utf-8')
report=dict(version='v173',source=source.relative_to(R).as_posix(),sourceSHA256=expected,path=out.relative_to(R).as_posix(),sha256=sha(out),bytes=out.stat().st_size,object=new.name,clothObject='Alice.Coelho.WholeCheckpoint145.apron',oldObject=old.name,modifiedPaths=sorted(modified),maxLocalVertexDisplacementM=float(np.linalg.norm(P-original,axis=1).max()),maxFrontalXZDisplacementM=float(np.linalg.norm((P-original)[:,[0,2]],axis=1).max()),maxRigidSectionRadialErrorM=radial,unchangedPathsExactlyPreserved=True,UVTopologyMaterialsPreserved=True,allModifiedSelfTrianglesChecked=True,modifiedSelfIntersectionPaths=0,steps=steps,interMotifSATTrianglePairs=0,actualTargetSATCounts=targetcounts,intraMotifContactsRemainNotSewApproved=True,sourceWholePreserved=True,notIntegrated=True,notPublished=True,independentFloat32ReopenAndReferenceComparisonPending=True,rigged=False,physicsVerified=False,productionComplete=False,elapsedSeconds=time.time()-start)
(O/'apron_neighbor_sections_authoring_audit_v173.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); print('LOCAL_NEIGHBOR_SECTIONS_SAVED',report['maxLocalVertexDisplacementM'],len(modified),flush=True)

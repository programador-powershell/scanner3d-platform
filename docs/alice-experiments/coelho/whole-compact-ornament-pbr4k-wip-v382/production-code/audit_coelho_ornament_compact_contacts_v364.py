"""Saved ornament actual-triangle contacts, using visible evaluated whole surfaces.

BVH broadphase plus double precision triangle SAT. Does not prove containment,
mechanical link interlocking, sewn mount dynamics or animated collisions.
"""
import bpy,numpy as np,json,hashlib,time,sys,gc
from pathlib import Path
from collections import Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';sys.path.insert(0,str(R/'Tools'));from coelho_lace_triangle_audit_v091 import sat_intersects
start=time.time()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
a=read(O/'apron_ornament_compact_corner_authoring_audit_v361.json');source=R/a['path'];assert digest(source)==a['sha256'];qa=read(O/'apron_ornament_component_audit_v362.json');assert qa['totalInwardComponents']==0 and qa['originalTenWholeMeshSignaturesExactlyPreserved']
assert all(c['boundaryEdges']==c['nonManifoldEdges']==c['inconsistentWindingEdges']==c['zeroAreaTriangles']==0 for r in qa['records'] for c in r['components'])
ornaments=[];records=[];npz={}
for row in a['newObjects']:
 ob=bpy.data.objects[row['object']];m=ob.data;m.calc_loop_triangles();P=np.asarray([ob.matrix_world@v.co for v in m.vertices]);tri=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32);startIDs=np.array([c['firstVertex'] for c in row['components']]);component=np.searchsorted(startIDs,tri.min(1),side='right')-1
 assert all(np.all((t>=row['components'][cid]['firstVertex'])&(t<row['components'][cid]['firstVertex']+row['components'][cid]['vertices'])) for t,cid in zip(tri,component))
 tree=BVHTree.FromPolygons([Vector(p) for p in P],[tuple(t) for t in tri],all_triangles=True);ornaments.append(dict(row=row,P=P,tri=tri,tp=P[tri],tree=tree,component=component));records.append(dict(id=row['id'],object=ob.name,targets={},selfContacts={}))
def narrow(pairs,A,B):
 pairs=np.asarray(pairs,np.int32).reshape((-1,2));chunks=[]
 for k in range(0,len(pairs),65536):
  chunk=pairs[k:k+65536];chunks.append(chunk[sat_intersects(A[chunk[:,0]],B[chunk[:,1]])])
 return np.concatenate(chunks) if chunks else np.empty((0,2),np.int32)
deps=bpy.context.evaluated_depsgraph_get()
for role in ['character','apron','chain','cord','lace']:
 ob=bpy.data.objects['Alice.Coelho.WholeCheckpoint318.'+role];ev=ob.evaluated_get(deps);m=ev.to_mesh();m.calc_loop_triangles();P=np.asarray([ob.matrix_world@v.co for v in m.vertices]);tri=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32);tp=P[tri];tree=BVHTree.FromPolygons([Vector(p) for p in P],[tuple(t) for t in tri],all_triangles=True)
 for data,record in zip(ornaments,records):
  broad=data['tree'].overlap(tree);hits=narrow(broad,data['tp'],tp);ids=data['component'][hits[:,0]];counts=Counter(data['row']['components'][int(cid)]['type'] for cid in ids);record['targets'][role]=dict(BVHPairs=len(broad),SATTrianglePairs=len(hits),contactsByComponentType=dict(counts),componentIDs=sorted(set(int(x) for x in ids)),targetObject=ob.name,targetEvaluatedTriangles=len(tri));npz[record['id']+'__'+role+'__pairs']=hits
  print('ORNAMENT_TRIANGLE_CONTACTS261',record['id'],role,len(hits),flush=True)
 ev.to_mesh_clear();del P,tri,tp,tree;gc.collect()
for data,record in zip(ornaments,records):
 pairs=np.array([(i,j) for i,j in data['tree'].overlap(data['tree']) if i<j],np.int32).reshape((-1,2));A=data['tri'][pairs[:,0]];B=data['tri'][pairs[:,1]];adjacent=np.any(A[:,:,None]==B[:,None,:],axis=(1,2));pairs=pairs[~adjacent];hits=narrow(pairs,data['tp'],data['tp']);ca=data['component'][hits[:,0]];cb=data['component'][hits[:,1]];counts=Counter(tuple(sorted((data['row']['components'][int(x)]['type'],data['row']['components'][int(y)]['type']))) for x,y in zip(ca,cb));record['selfContacts']=dict(BVHPairsAfterSharedVertexExclusion=len(pairs),SATTrianglePairs=len(hits),sameClosedComponentPairs=int(np.sum(ca==cb)),interComponentPairs=int(np.sum(ca!=cb)),byComponentTypes=[dict(types=list(k),SATTrianglePairs=n) for k,n in sorted(counts.items())],manufacturedSettingContactsNotAutomaticallyApproved=True);npz[record['id']+'__self__pairs']=hits;npz[record['id']+'__triangles']=data['tri'];npz[record['id']+'__componentIDs']=data['component'];print('ORNAMENT_SELF261',record['id'],len(hits),flush=True)
between=[]
for i,data in enumerate(ornaments):
 for j in range(i+1,len(ornaments)):
  other=ornaments[j];broad=data['tree'].overlap(other['tree']);hits=narrow(broad,data['tp'],other['tp']);between.append(dict(idA=data['row']['id'],idB=other['row']['id'],BVHPairs=len(broad),SATTrianglePairs=len(hits)));npz[data['row']['id']+'__'+other['row']['id']+'__pairs']=hits
np.savez_compressed(O/'apron_ornament_actual_triangle_contacts_v364.npz',**npz);assert digest(source)==a['sha256']
report=dict(version='v364',sourceCandidateVersion='v361',sourcePath=a['path'],sourceSHA256=a['sha256'],independentSavedReopen=True,visibleEvaluatedTargets=True,records=records,betweenOrnaments=between,totalWholeSurfaceSATTrianglePairs=sum(t['SATTrianglePairs'] for r in records for t in r['targets'].values()),totalSelfSATTrianglePairs=sum(r['selfContacts']['SATTrianglePairs'] for r in records),totalBetweenOrnamentsSATTrianglePairs=sum(r['SATTrianglePairs'] for r in between),actualTrianglePairsNPZ='Blender/Work/alice_coelho/tripo_h31_budget55_v001/apron_ornament_actual_triangle_contacts_v364.npz',toleranceM=1e-9,adjacentSharedVertexPairsExcludedFromSelfAudit=True,closedVolumeContainmentNotVerified=True,mechanicalLinkageNotVerified=True,sewMountsNotApplied=True,readOnlyNoBlendSaveOrExport=True,staticOnly=True,physicsVerified=False,fidelityApproved=False,productionComplete=False,notIntegrated=True,notPublished=True,elapsedSeconds=time.time()-start)
(O/'apron_ornament_triangle_contact_audit_v364.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ORNAMENT_CONTACT261_COMPLETE',report['totalWholeSurfaceSATTrianglePairs'],report['totalSelfSATTrianglePairs'],flush=True)

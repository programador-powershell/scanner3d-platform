"""Local inward lateral spacing of diagnosed inner gold cords; rigid section translations."""
import bpy,numpy as np,json,hashlib,time,sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';start=time.time();a=json.loads((O/'apron_chain_reflow_authoring_audit_v136.json').read_text(encoding='utf-8-sig'));src=R/a['path'];assert hashlib.sha256(src.read_bytes()).hexdigest()==a['sha256'];diag=json.loads((O/'apron_cord_contact_diagnostic_v141.json').read_text(encoding='utf-8-sig'));old=bpy.data.objects[a['parts'][1]['object']];ob=old.copy();ob.data=old.data.copy();old.users_collection[0].objects.link(ob);ob.name='Alice.Coelho.Apron.Cords.LocalSpacing.Candidate.v142';m=ob.data;m.calc_loop_triangles();ctris=np.array([t.vertices[:] for t in m.loop_triangles]);CP=np.array([v.co[:] for v in m.vertices]);initial=CP.copy();faceIDs=np.array([m.attributes['stable_lace_cord_path_id'].data[t.polygon_index].value for t in m.loop_triangles]);groups={x['pathID']:x for x in diag['groups']};sys.path.insert(0,str(R/'Tools'));from coelho_lace_triangle_audit_v091 import sat_intersects
template=(R/'Tools/verify_coelho_fitted_chain_v054.py').read_text(encoding='utf-8-sig');exec(template[template.index('def intersections('):template.index('clothContact=intersections(')].replace('stable_chain_link_id','stable_lace_cord_path_id'));targets=[]
for name,evaluate in [(a['clothObject'],True),('Alice.Coelho.Complete.GameCandidate',False),(a['object'],False),(a['parts'][2]['object'],False)]:
 x=bpy.data.objects[name];x=x.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluate else x;mesh=x.to_mesh() if evaluate else x.data;mesh.calc_loop_triangles();P=np.array([v.co[:] for v in mesh.vertices]);tri=np.array([t.vertices[:] for t in mesh.loop_triangles]);tree=BVHTree.FromPolygons([Vector(p) for p in P],[tuple(t) for t in tri],all_triangles=True);targets.append((name,tree,P,tri))
 if evaluate:x.to_mesh_clear()
iterations=[]
for iteration in range(26):
 chainBVH=BVHTree.FromPolygons([Vector(p) for p in CP],[tuple(t) for t in ctris],all_triangles=True);pairs=[(i,j) for i,j in chainBVH.overlap(chainBVH) if i<j and not set(ctris[i]).intersection(ctris[j])];selfPairs=[]
 for k in range(0,len(pairs),4096):
  chunk=np.array(pairs[k:k+4096]);bad=sat_intersects(CP[ctris[chunk[:,0]]],CP[ctris[chunk[:,1]]]);selfPairs.extend(chunk[bad].tolist())
 contacts={name:intersections(tree,P,tri,name) for name,tree,P,tri in targets};counts={name:x['SATIntersectionPairs'] for name,x in contacts.items()};iterations.append(dict(iteration=iteration,selfSATTrianglePairs=len(selfPairs),contacts=counts));print('LOCAL_CORD_SPACING',iteration,'SELF',len(selfPairs),counts,flush=True)
 if not selfPairs and not any(counts.values()):break
 if iteration==25:raise RuntimeError('Bounded local cord spacing did not converge; no candidate saved')
 weights={};forward={}
 def mark(store,pid,triIDs):
  group=groups[pid];base=group['firstVertex']//6;end=(group['lastVertex']+1)//6;arr=store.setdefault(pid,np.zeros(end-base));nodes=np.unique(ctris[triIDs]//6)-base
  for node in nodes:
   for j in range(max(0,node-6),min(len(arr),node+7)):arr[j]=max(arr[j],np.exp(-.5*((j-node)/2.5)**2))
 for i,j in selfPairs:
  pa,pb=int(faceIDs[i]),int(faceIDs[j]);assert pa!=pb,('New fold within a cord; require curvature repair',pa,i,j);pid=1 if set([pa,pb])=={0,1} else 395 if set([pa,pb])=={394,395} else None;assert pid is not None,('Unexpected cord pair',pa,pb);mark(weights,pid,[i if pa==pid else j])
 for name,record in contacts.items():
  for pid in set(x['linkID'] for x in record['intersectionPairs']):
   triangles=[x['chainTriangle'] for x in record['intersectionPairs'] if x['linkID']==pid]
   if name in [a['clothObject'],'Alice.Coelho.Complete.GameCandidate']:mark(forward,pid,triangles)
   else:mark(weights,pid,triangles)
 for store,axis in [(weights,0),(forward,1)]:
  for pid,w in store.items():
   group=groups[pid];blocks=CP[group['firstVertex']:group['lastVertex']+1].reshape(-1,6,3);amount=.00012*(1 if pid in [0,1] else -1) if axis==0 else -.00015;blocks[:,:,axis]+=amount*w[:,None]
 assert np.linalg.norm(CP-initial,axis=1).max()<.003,'Route exceeded3mm; no save'
for v,p in zip(m.vertices,CP):v.co=p
m.update();ob.hide_render=True;ob.hide_set(True);ob['scope']='Only diagnosed cord sections translated locally toward panel center, with camera-forward corrections if actual contact. Same radius/UV/topology/materials. Static, not sewn or rigged.';out=O/'Dress/alice_coelho_apron_cord_spacing_candidate_v142.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert hashlib.sha256(src.read_bytes()).hexdigest()==a['sha256'];parts=a['parts'].copy();parts[1]=dict(role='cord',object=ob.name,referenceObject=old.name);report=dict(version='v142',source=src.relative_to(R).as_posix(),sourceSHA256=a['sha256'],path=out.relative_to(R).as_posix(),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),object=ob.name,clothObject=a['clothObject'],chainObject=a['object'],parts=parts,iterations=iterations,maxLocalSectionTranslationM=float(np.linalg.norm(CP-initial,axis=1).max()),UVTopologyMaterialsAndSectionRadiusPreserved=True,clothChainLaceWholeSourcePreserved=True,selfSATTrianglePairs=0,actualTargetSATCounts=counts,independentReopenAndVisualReviewPending=True,rigged=False,physicsVerified=False,notIntegrated=True,notPublished=True,productionComplete=False,elapsedSeconds=time.time()-start);(O/'apron_cord_spacing_authoring_audit_v142.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('CORD_SPACING_SAVED',out,flush=True)

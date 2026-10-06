"""Sufficient return curvature for real nested fabrics; whole Alice stays untouched."""
from pathlib import Path
T=Path('F:/Alice/SharedProduction/Tools')
code=(T/'author_coelho_rear_bow_smooth_layers_v447.py').read_text(encoding='utf-8-sig').replace('447','454')
helper='''def normal_offsets(P,F,amount):
 tmp=bpy.data.meshes.new('Temporary.Layer.Normal.Compute');tmp.from_pydata(P,[],F);tmp.update()
 normals=np.asarray([v.normal[:] for v in tmp.vertices],float);bpy.data.meshes.remove(tmp)
 assert np.all(np.linalg.norm(normals,axis=1)>.99)
 return (np.asarray(P,float)+float(amount)*normals).tolist()
'''
code=code.replace('for side,sign in',helper+'\nfor side,sign in',1)
code=code.replace('p=[(x,y+offset,z) for x,y,z in P]','p=normal_offsets(P,F,offset)')
code=code.replace("[(x,y+offset,z) for x,y,z in P],F,UV,mat,role,side,.00050,pins)","normal_offsets(P,F,offset),F,UV,mat,role,side,.00050,pins)")
code=code.replace('y=.112+.030*s+.012*math.cos(math.pi*u)', 'y=.130+.030*s+.028*math.cos(math.pi*u)')
code=code.replace('center=sign*(.025+.058*t)','center=sign*(.027+.058*t)')
code=code.replace('nu,nv=48,9;rootY=.118','nu,nv=49,9;rootY=.132')
code=code.replace('u=i/nu;a=2*math.pi*u','u=i/(nu-1);a=-math.pi/2+.55+(2*math.pi-1.10)*u')
code=code.replace('rootY+.020*math.cos(a),z0+.036*math.sin(a)','rootY+.041*math.cos(a),z0+.046*math.sin(a)')
code=code.replace('for i in range(nu):\n for j in range(nv-1):a=i*nv+j;b=((i+1)%nu)*nv+j','for i in range(nu-1):\n for j in range(nv-1):a=i*nv+j;b=(i+1)*nv+j')
code=code.replace('periodicCenterWrapWeldedBySharedVertexIndices=True','periodicCenterWrapWeldedBySharedVertexIndices=False,openTextileBandUnderTailRootsWithClosedThicknessEdges=True')
code=code.replace("report=dict(smoothParametricBowAndTailShapes", "report=dict(returnSemiDepthM=.028,prior449RejectedFor2271SelfContactsAnd3064InterlayerPairs=True,layerOffsetsFollowNormalsWithLargerCurvatureRadius=True,tailRootsSeparated2mm=True,bandOpeningIsAuthoredPatternNotCutOriginalDress=True,smoothParametricBowAndTailShapes")
guard='''# Actual local triangle tests, before an expensive save, without changing tolerances.
import sys
sys.path.insert(0,str(R/'Tools'));from coelho_lace_triangle_audit_v091 import sat_intersects
from mathutils.bvhtree import BVHTree
local=[];checks=[]
def narrow_count(pairs,A,B):
 pairs=np.asarray(pairs,np.int32).reshape((-1,2));count=0
 for k in range(0,len(pairs),65536):
  part=pairs[k:k+65536];count+=int(sat_intersects(A[part[:,0]],B[part[:,1]]).sum())
 return count
for row in rows:
 ob=bpy.data.objects[row['name']];m=bpy.data.meshes.new_from_object(ob.evaluated_get(deps));m.calc_loop_triangles();P=np.asarray([v.co[:] for v in m.vertices],float);Q=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32);tree=BVHTree.FromPolygons([Vector(p) for p in P],[tuple(t) for t in Q],all_triangles=True);bpy.data.meshes.remove(m)
 pairs=np.asarray([(i,j) for i,j in tree.overlap(tree) if i<j],np.int32).reshape((-1,2));qa=Q[pairs[:,0]];qb=Q[pairs[:,1]];pairs=pairs[~np.any(qa[:,:,None]==qb[:,None,:],axis=(1,2))];n=narrow_count(pairs,P[Q],P[Q]);checks.append(dict(name=row['name'],selfPairs=n));print('CURVATURE454_SELF',row['name'],n,flush=True);local.append((row,P[Q],tree))
for i,(row,A,ta) in enumerate(local):
 for other,B,tb in local[i+1:]:
  if row['role'] in {'base_loop','structured_interfacing','satin_lining'} and other['role'] in {'base_loop','structured_interfacing','satin_lining'} and row['side']==other['side']:
   n=narrow_count(ta.overlap(tb),A,B);checks.append(dict(nameA=row['name'],nameB=other['name'],betweenNestedLoopPairs=n));print('CURVATURE454_NEST',row['name'],other['name'],n,flush=True)
(O/'rear_bow_local_curvature_guard_v454.json').write_text(json.dumps(dict(checks=checks,toleranceM=1e-9,actualTriangles=True,requiresIndependentWholeContactsAndReferenceReview=True),indent=2),encoding='utf-8')
assert all(r.get('selfPairs',r.get('betweenNestedLoopPairs',0))==0 for r in checks),'Local curvature still intersects; do not save/promote'
'''
code=code.replace('assert signatures()==before and not bpy.data.libraries',guard+'\nassert signatures()==before and not bpy.data.libraries')
exec(compile(code,str(T/'author_coelho_rear_bow_curvature_layers_v454.py'),'exec'))

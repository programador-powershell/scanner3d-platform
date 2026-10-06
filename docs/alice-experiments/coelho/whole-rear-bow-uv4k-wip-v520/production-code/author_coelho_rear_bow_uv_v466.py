"""Separate both textile surfaces and thickness rims into a shared nonoverlapping 4K atlas.

The evaluated460 geometry is copied exactly. Original procedural mid-surfaces,
waist pin groups and all ten whole421 objects remain recoverable and unchanged.
This is UV authoring, not a rig or a final character approval.
"""
import bpy,numpy as np,json,hashlib,time,sys
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';W=4096;start=time.time()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'rear_bow_layer_authoring_audit_v460.json');source=R/a['path'];assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==a['sha256']
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
assert read(O/'rear_bow_review_decision_v464.json')['acceptedForLocalUVDevelopmentOnly']
col=bpy.data.collections.new('COELHO_REAR_BOW_UV_V466_LOCAL_NOT_APPROVED');bpy.context.scene.collection.children.link(col);deps=bpy.context.evaluated_depsgraph_get();rows=[];arrays={};triangles=[];rimIndex=0
for objIndex,row in enumerate(a['newObjects']):
 old=bpy.data.objects[row['name']];m=bpy.data.meshes.new_from_object(old.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps);m.name=old.data.name+'.EvaluatedUV466';m.calc_loop_triangles();P=np.asarray([v.co[:] for v in m.vertices],np.float32);F=[list(p.vertices) for p in m.polygons];N=len(old.data.vertices);assert len(P)==2*N
 ob=old.copy();ob.data=m;ob.name=old.name.replace('Candidate460','UV466');col.objects.link(ob)
 for modifier in list(ob.modifiers):ob.modifiers.remove(modifier)
 assert len(ob.vertex_groups)==len(old.vertex_groups)
 sourceUV=np.asarray([x.uv[:] for x in m.uv_layers.active.data],float);uv=np.zeros((len(m.loops),2),float);surfaceCharts=[];rimPolygons=[]
 # Estimate the pattern's median intrinsic metric rather than stretch every tail
 # into the same rectangular aspect as a wing. This does not prove conformality.
 oldUV=np.zeros((N,2),float)
 for loop,datum in zip(old.data.loops,old.data.uv_layers.active.data):oldUV[loop.vertex_index]=datum.uv[:]
 oldP=np.asarray([v.co[:] for v in old.data.vertices]);metric=[]
 for axis in [0,1]:
  measurements=[]
  for e in old.data.edges:
   i,j=e.vertices;delta=abs(oldUV[j]-oldUV[i])
   if delta[axis]>1e-8 and delta[1-axis]<1e-8:measurements.append(np.linalg.norm(oldP[j]-oldP[i])/delta[axis])
  assert measurements;metric.append(float(np.median(measurements)))
 rotate=metric[1]>metric[0];metricOriented=np.asarray(metric[::-1] if rotate else metric);fit=min(976/metricOriented[0],528/metricOriented[1]);size=metricOriented*fit
 for side in [0,1]:
  chart=objIndex*2+side;origin=np.array([(chart%4)*1024+24,(chart//4)*576+640+24])+(np.array([976,528])-size)/2;polygons=[]
  for poly in m.polygons:
   ids=np.asarray(poly.vertices)
   if bool((ids<N).all())!=(side==0) or not ((ids<N).all() or (ids>=N).all()):continue
   loops=list(poly.loop_indices);U=sourceUV[loops];U=U[:,::-1] if rotate else U;uv[loops]=(origin+U*size)/W;polygons.append(poly.index)
  assert len(polygons)==len(old.data.polygons)
  surfaceCharts.append(dict(index=chart,side=side,originPixels=origin.tolist(),sizePixels=size.tolist(),patternAxesSwapped=bool(rotate),medianPatternMetricM=metric,polygons=polygons))
 for poly in m.polygons:
  ids=np.asarray(poly.vertices)
  if (ids<N).all() or (ids>=N).all():continue
  rimPolygons.append(poly.index)
 # Every rim TRIANGLE gets a chart. Splitting a folded quad by its actual Blender
 # diagonal avoids an assumed planar quad fold. Thin rims receive explicit local
 # aspect regularization; they are not evidence of new photographic detail.
 rimTriangles=[t for t in m.loop_triangles if t.polygon_index in set(rimPolygons)]
 # UV loop sharing would prevent independent diagonal charts: rebuild only rim
 # polygons into their existing triangles, preserving exact surface and winding.
 newF=[];newUV=[];materials=[];smooth=[];rimRecords=[]
 for poly in m.polygons:
  if poly.index not in set(rimPolygons):
   newF.append(list(poly.vertices));newUV.extend(uv[list(poly.loop_indices)]);materials.append(poly.material_index);smooth.append(poly.use_smooth)
 for t in rimTriangles:
  q=P[list(t.vertices)].astype(float);e=q[1]-q[0];e/=np.linalg.norm(e);normal=np.cross(q[1]-q[0],q[2]-q[0]);normal/=np.linalg.norm(normal);v=np.cross(normal,e);plane=np.column_stack(((q-q[0])@e,(q-q[0])@v));plane-=plane.min(0);span=plane.max(0);assert (span>1e-12).all();cell=np.array([(rimIndex%256)*16,(rimIndex//256)*16]);assert cell[1]+16<=640
  u=(cell+3+plane/span*10)/W;newF.append(list(t.vertices));newUV.extend(u);materials.append(m.polygons[t.polygon_index].material_index);smooth.append(m.polygons[t.polygon_index].use_smooth);rimRecords.append(dict(triangleVertices=list(t.vertices),cellPixels=cell.tolist(),physicalPlaneSpanM=span.tolist()));rimIndex+=1
 # Triangulation and coordinates must remain exact even though rim polygon layout changes.
 final=bpy.data.meshes.new(ob.name+'.Mesh');final.from_pydata(P.tolist(),[],newF);final.update()
 for mat in m.materials:final.materials.append(mat)
 for poly,mi,sm in zip(final.polygons,materials,smooth):poly.material_index=mi;poly.use_smooth=sm
 # Deform weights live on the old evaluated mesh. Copy them AFTER replacing data.
 groupNames=[g.name for g in ob.vertex_groups];weights=[[(g.group,g.weight) for g in vertex.groups] for vertex in m.vertices];ob.data=final
 for g in list(ob.vertex_groups):ob.vertex_groups.remove(g)
 for name in groupNames:ob.vertex_groups.new(name=name)
 for i,groups in enumerate(weights):
  for group,weight in groups:ob.vertex_groups[group].add([i],weight,'REPLACE')
 pattern=final.uv_layers.new(name='RearBow.PatternUV460')
 # Recover pattern per evaluated vertex; rim duplication uses the original surface parameter.
 patternVertex=np.zeros((len(P),2),float)
 for l,U in zip(m.loops,sourceUV):patternVertex[l.vertex_index]=U
 pattern.data.foreach_set('uv',patternVertex[np.asarray([l.vertex_index for l in final.loops])].astype(np.float32).ravel())
 atlas=final.uv_layers.new(name='RearBow.Atlas4K.v466');atlas.data.foreach_set('uv',np.asarray(newUV,np.float32).ravel());atlas.active_render=True;final.uv_layers.active=atlas
 final.calc_loop_triangles();T=np.asarray([t.vertices[:] for t in final.loop_triangles],np.int32);oldT=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32)
 def canonical(Q):
  Q=np.minimum.reduce([Q,np.roll(Q,1,axis=1),np.roll(Q,2,axis=1)]) if False else Q
  Z=np.asarray([np.roll(t,-int(np.argmin(t))) for t in Q]);return Z[np.lexsort((Z[:,2],Z[:,1],Z[:,0]))]
 assert np.array_equal(P,np.asarray([v.co[:] for v in final.vertices],np.float32));assert np.array_equal(canonical(T),canonical(oldT)),ob.name
 U=np.asarray([u.uv[:] for u in atlas.data],np.float64);L=np.asarray([t.loops[:] for t in final.loop_triangles],np.int32);triangles.extend(U[L]);arrays[f'object{objIndex}_positions']=P;arrays[f'object{objIndex}_triangles']=T;arrays[f'object{objIndex}_uv']=U;arrays[f'object{objIndex}_loops']=L
 old.hide_render=True;old.hide_set(True);ob.hide_render=True;ob.hide_set(True);ob['scope']='UV authoring only. Exact460 evaluated cloth; original procedural pattern retained. No rig or physics approval.'
 rows.append(dict(name=ob.name,sourceObject=old.name,role=row['role'],side=row['side'],positionsSHA256=hashlib.sha256(P.tobytes()).hexdigest(),trianglesSHA256=hashlib.sha256(T.tobytes()).hexdigest(),UVSHA256=hashlib.sha256(U.astype(np.float32).tobytes()).hexdigest(),vertices=len(P),triangles=len(T),surfaceCharts=surfaceCharts,rimTriangles=len(rimTriangles),rimCharts=rimRecords,groups=[g.name for g in ob.vertex_groups],evaluatedGeometryExactlyPreserved=True,rimQuadsTriangulatedWithoutGeometryChange=True,rigged=False));bpy.data.meshes.remove(m)
 print('BOW466_UV_OBJECT',ob.name,len(T),len(rimTriangles),flush=True)
sys.path.insert(0,str(R/'Tools'));from coelho_uv_triangle_sat import overlaps,unit_tests
assert unit_tests();Q=np.asarray(triangles,float);det=np.cross(Q[:,1]-Q[:,0],Q[:,2]-Q[:,0]);assert (abs(det)>1e-16).all();pairs,broad=overlaps(Q);assert len(pairs)==0,('continuous UV overlap',len(pairs));print('BOW466_CONTINUOUS_UV_PASS',len(Q),broad,flush=True)
for name,before in a['wholeSourceSignatures'].items():
 ob=bpy.data.objects[name];m=ob.data;actual=dict(positions=hashlib.sha256(np.asarray([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.asarray([u.uv[:] for u in l.data],np.float32).tobytes()).hexdigest() for l in m.uv_layers],matrix=[list(r) for r in ob.matrix_world],materials=[mat.name for mat in m.materials]);assert actual==before
out=O/'Dress/alice_coelho_rear_bow_uv_candidate_v466.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==a['sha256'];np.savez_compressed(O/'rear_bow_uv_arrays_v466.npz',**arrays)
report=dict(version='v466',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),sourcePath=a['path'],sourceSHA256=a['sha256'],collection=col.name,newObjects=rows,allTenWholeSourceObjectsExactlyPreserved=True,allElevenEvaluatedClothGeometriesExactlyPreserved=True,originalProceduralMidSurfacesAndPinGroupsRetained=True,UVMapName='RearBow.Atlas4K.v466',resolution=[W,W],continuousUVOverlapPairs=0,continuousBroadphasePairs=broad,continuousUnitTestsPassed=True,degenerateUVTriangles=0,rimTriangleCharts=rimIndex,rimAspectRegularizedExplicitly=True,medianIntrinsicSurfaceAspectOnlyNotConformalProof=True,sourceImagesNotProjected=True,rigged=False,physicsVerified=False,fidelityApproved=False,productionComplete=False,notIntegrated=True,notPublished=True,elapsedSeconds=time.time()-start)
(O/'rear_bow_uv_authoring_audit_v466.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('BOW466_UV_SAVED_REQUIRE_INDEPENDENT_REOPEN',flush=True)

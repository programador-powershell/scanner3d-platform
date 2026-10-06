"""ABF unwrap of the actual front/back sheets, without geometry deformation.

Preserve the explicitly separated rim charts and original pattern coordinates.
Compare measured distortion after independent saved re-open, before rebaking.
"""
import bpy,numpy as np,json,hashlib,time,sys
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';W=4096;start=time.time();read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'rear_bow_uv_authoring_audit_v466.json');source=R/a['path'];assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==a['sha256'];assert read(O/'rear_bow_uv_saved_audit_v468.json')['allGeometryUVWeightsAndWholeSourcesVerified'];assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
col=bpy.data.collections.new('COELHO_REAR_BOW_ABF_UV_V471_LOCAL_REVIEW');bpy.context.scene.collection.children.link(col);rows=[];arrays={};allTriangles=[]
for i,row in enumerate(a['newObjects']):
 old=bpy.data.objects[row['name']];ob=old.copy();ob.data=old.data.copy();ob.name=old.name.replace('UV466','ABF471');col.objects.link(ob);m=ob.data;beforeUV=np.asarray([u.uv[:] for u in m.uv_layers[a['UVMapName']].data],float);rimStart=len(m.polygons)-row['rimTriangles'];rimLoops=np.asarray([l for p in m.polygons[rimStart:] for l in p.loop_indices]);assert len(rimLoops)==row['rimTriangles']*3
 rimEdges=set(k for p in m.polygons[rimStart:] for k in p.edge_keys)
 for edge in m.edges:edge.use_seam=edge.key in rimEdges
 for other in bpy.context.scene.objects:other.select_set(False)
 ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
 for poly in m.polygons:poly.select=poly.index<rimStart
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_mode(type='FACE');bpy.ops.uv.unwrap(method='ANGLE_BASED',margin=0.001,correct_aspect=False);bpy.ops.object.mode_set(mode='OBJECT')
 U=np.asarray([u.uv[:] for u in m.uv_layers[a['UVMapName']].data],float);U[rimLoops]=beforeUV[rimLoops];charts=[]
 for chart in row['surfaceCharts']:
  loops=np.asarray([l for p in chart['polygons'] for l in m.polygons[p].loop_indices]);Q=U[loops];Q-=Q.min(0);span=Q.max(0);rotate=span[1]>span[0]
  if rotate:Q=Q[:,::-1];span=span[::-1]
  assert (span>1e-9).all();scale=min(976/span[0],528/span[1]);size=span*scale;index=chart['index'];origin=np.array([(index%4)*1024+24,(index//4)*576+640+24])+(np.array([976,528])-size)/2;U[loops]=(origin+Q*scale)/W;charts.append(dict(chart,index=index,originPixels=origin.tolist(),sizePixels=size.tolist(),ABFAxesSwapped=bool(rotate),actualABFUniformScale=scale))
 atlas=m.uv_layers[a['UVMapName']];atlas.name='RearBow.Atlas4K.ABF.v471';atlas.data.foreach_set('uv',U.astype(np.float32).ravel());atlas.active_render=True;m.uv_layers.active=atlas;m.calc_loop_triangles();P=np.asarray([v.co[:] for v in m.vertices],np.float32);T=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32);L=np.asarray([t.loops[:] for t in m.loop_triangles],np.int32);U=np.asarray([u.uv[:] for u in atlas.data],float);assert np.array_equal(P,np.asarray([v.co[:] for v in old.data.vertices],np.float32));assert np.array_equal(U[rimLoops],beforeUV[rimLoops]);arrays[f'object{i}_positions']=P;arrays[f'object{i}_triangles']=T;arrays[f'object{i}_uv']=U;arrays[f'object{i}_loops']=L;allTriangles.extend(U[L]);rows.append(dict(row,name=ob.name,sourceObject=old.name,proceduralSource460=row['sourceObject'],surfaceCharts=charts,UVSHA256=hashlib.sha256(U.astype(np.float32).tobytes()).hexdigest(),ABFRelaxedActualSurface=True,geometryUnchanged=True));ob.hide_set(True);ob.hide_render=True;print('BOW471_ABF_OBJECT',ob.name,flush=True)
sys.path.insert(0,str(R/'Tools'));from coelho_uv_triangle_sat import overlaps,unit_tests
assert unit_tests();Q=np.asarray(allTriangles);cross=(Q[:,1,0]-Q[:,0,0])*(Q[:,2,1]-Q[:,0,1])-(Q[:,1,1]-Q[:,0,1])*(Q[:,2,0]-Q[:,0,0]);assert (abs(cross)>1e-16).all();pairs,broad=overlaps(Q);assert len(pairs)==0,('ABF actual UV overlap',len(pairs));np.savez_compressed(O/'rear_bow_uv_arrays_v471.npz',**arrays)
out=O/'Dress/alice_coelho_rear_bow_abf_uv_candidate_v471.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==a['sha256'];report=dict(a,version='v471',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),sourcePath=a['path'],sourceSHA256=a['sha256'],collection=col.name,newObjects=rows,UVMapName='RearBow.Atlas4K.ABF.v471',continuousUVOverlapPairs=len(pairs),continuousBroadphasePairs=broad,ABFUnwrapPerformedOnActualSurfaceFrontAndBack=True,thinRimChartsRetainedExactly=True,requiresIndependentReopenAndDistortionComparison=True,sourceImagesNotProjected=True,productionComplete=False,elapsedSeconds=time.time()-start);(O/'rear_bow_uv_authoring_audit_v471.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('BOW471_ABF_SAVED_REQUIRE_REOPEN_AND_DISTORTION_COMPARISON',flush=True)

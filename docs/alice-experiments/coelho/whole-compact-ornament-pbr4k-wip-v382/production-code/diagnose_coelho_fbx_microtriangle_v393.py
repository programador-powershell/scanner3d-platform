import bpy,numpy as np,json,hashlib,time
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';pkg=json.loads((O/'package_export_v382.json').read_text());file=R/pkg['files']['fbx']['path'];assert hashlib.sha256(file.read_bytes()).hexdigest()==pkg['files']['fbx']['sha256']
for ob in list(bpy.data.objects):bpy.data.objects.remove(ob,do_unlink=True)
bpy.ops.import_scene.fbx(filepath=str(file),use_custom_normals=True);rows=[]
for row in pkg['objects']:
 ob=next(x for x in bpy.context.scene.objects if x.type=='MESH' and 'Export382.'+row['role'] in x.name);m=ob.data;m.calc_loop_triangles();ex=np.load(O/f'whole_export_source_{row["role"]}_v382.npz');P=ex['positions'].astype(float);T=ex['triangles'];L=ex['triangleLoops'];UV=ex['loopUV'];Q=np.array([ob.matrix_world@v.co for v in m.vertices]);QT=np.array([t.vertices[:] for t in m.loop_triangles]);QL=np.array([t.loops[:] for t in m.loop_triangles]);QUV=np.array([u.uv[:] for u in m.uv_layers[0].data]);same=np.array_equal(T,QT);assert same,(row['role'],T.shape,QT.shape);area=lambda p,t:np.linalg.norm(np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]),axis=1)/2
 sa=area(P,T);qa=area(Q,QT);bad=np.flatnonzero((qa<1e-16)&(sa>=1e-16));positionsDelta=np.abs(P-Q);r=dict(role=row['role'],triangleOrderExactlyPreserved=same,maxPositionComponentErrorM=float(positionsDelta.max()),cornerUVError=float(np.abs(UV[L]-QUV[QL]).max()),sourceZeroAreaTriangles=int((sa<1e-16).sum()),reimportZeroAreaTriangles=int((qa<1e-16).sum()),newTinyOrCollapsedTriangles=len(bad),examples=[dict(triangle=int(i),sourceArea=float(sa[i]),reimportArea=float(qa[i]),sourceP=P[T[i]].tolist(),reimportP=Q[QT[i]].tolist()) for i in bad[:8]])
 if row['role']=='ornament_outer_left':
  i=16204;r['failedNearestCornerTriangle']=dict(triangle=i,sourceP=P[T[i]].tolist(),reimportP=Q[QT[i]].tolist(),UV=UV[L[i]].tolist(),reimportUV=QUV[QL[i]].tolist(),sourceArea=float(sa[i]),reimportArea=float(qa[i]))
 rows.append(r);print('FBX393_ORDER_PRECISION',r,flush=True)
(O/'whole_fbx_precision_diagnostic_v393.json').write_text(json.dumps(dict(version='v393',FBXSHA256=pkg['files']['fbx']['sha256'],rows=rows,newCollapsedOrTinyTriangles=sum(r['newTinyOrCollapsedTriangles'] for r in rows),productionComplete=False,diagnosticDoesNotApproveFormat=True),indent=2),encoding='utf-8')

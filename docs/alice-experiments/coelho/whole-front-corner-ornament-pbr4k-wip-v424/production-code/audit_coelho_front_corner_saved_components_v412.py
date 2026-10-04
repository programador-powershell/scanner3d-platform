"""Independent read-only saved candidate audit, including actual per-component winding."""
import bpy,numpy as np,json,hashlib,time
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';start=time.time()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
a=read(O/'apron_ornament_front_corner_authoring_audit_v411.json');p=R/a['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256'];expected=read(O/'apron_ornament_whole_integration_audit_v377.json')['wholeCopySignatures']
for name,wanted in expected.items():
 ob=bpy.data.objects[name];m=ob.data;observed=dict(positions=hashlib.sha256(np.asarray([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.asarray([x.uv[:] for x in u.data],np.float32).tobytes()).hexdigest() for u in m.uv_layers],keys={} if not m.shape_keys else {k.name:hashlib.sha256(np.asarray([v.co[:] for v in k.data],np.float32).tobytes()).hexdigest() for k in m.shape_keys.key_blocks},materials=[mat.name for mat in m.materials],matrixWorld=[list(row) for row in ob.matrix_world]);assert observed==wanted,(name,'Original whole data changed')
records=[]
for row in a['newObjects']:
 ob=bpy.data.objects[row['object']];m=ob.data;assert ob.hide_render and len(m.uv_layers)==1;P=np.array([v.co[:] for v in m.vertices]);components=[]
 for c in row['components']:
  lo=c['firstVertex'];hi=lo+c['vertices'];faces=[tuple(p.vertices) for p in m.polygons if min(p.vertices)>=lo and max(p.vertices)<hi];assert len(faces)==c['faces'];center=P[lo:hi].mean(0);edges={};volume=0.;zeroArea=0
  for face in faces:
   for x,y in zip(face,face[1:]+face[:1]):
    key=tuple(sorted((x,y)));v=edges.setdefault(key,[0,0]);v[0]+=1;v[1]+=1 if x<y else -1
   for k in range(1,len(face)-1):
    A,B,C=P[[face[0],face[k],face[k+1]]]-center;volume+=float(np.dot(A,np.cross(B,C)))/6;zeroArea+=int(np.linalg.norm(np.cross(B-A,C-A))<1e-16)
  components.append(dict(c,signedVolumeM3=volume,inwardWinding=volume<0,boundaryEdges=sum(v[0]==1 for v in edges.values()),nonManifoldEdges=sum(v[0]>2 for v in edges.values()),inconsistentWindingEdges=sum(v[0]==2 and v[1]!=0 for v in edges.values()),zeroAreaTriangles=zeroArea))
 records.append(dict(id=row['id'],object=ob.name,allVertexCoordinatesFinite=bool(np.isfinite(P).all()),components=components,inwardComponents=sum(c['inwardWinding'] for c in components),componentCount=len(components)))
report=dict(version='v412',sourceCandidateVersion='v411',sourceCandidateSHA256=a['sha256'],independentSavedReopen=True,originalTenWholeMeshSignaturesExactlyPreserved=True,records=records,totalInwardComponents=sum(r['inwardComponents'] for r in records),normalsRequireReviewBeforeIntegration=any(r['inwardComponents'] for r in records),contactLinkageAndRigNotVerified=True,readOnlyNoSaveOrExport=True,fidelityApproved=False,productionComplete=False,notPublished=True,elapsedSeconds=time.time()-start)
(O/'apron_ornament_component_audit_v412.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('FRONT412_SAVED_COMPONENTS_AUDITED',report['totalInwardComponents'],flush=True)

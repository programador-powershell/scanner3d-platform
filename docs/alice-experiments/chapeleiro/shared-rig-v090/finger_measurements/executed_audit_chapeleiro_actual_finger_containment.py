import json,numpy as np
from pathlib import Path
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v089');a=np.load(root/'native_whole_hand_measurement_data.npz');p=a['points'];faces=a['faces'];classes=a['arm_classes'];r=json.loads((root/'native_individual_finger_targets.json').read_text());rows=[]
for side,sign in [('Left',1),('Right',-1)]:
 tri=p[faces[np.all(classes[faces]==sign,axis=1)]]
 for name,b in r['boneTargets'].items():
  if not name.startswith(side):continue
  h=np.array(b['head']);t=np.array(b['tail']);values=[]
  for fraction in np.linspace(0,1,5):
   q=h+(t-h)*fraction;x,y,z=tri[:,0]-q,tri[:,1]-q,tri[:,2]-q
   norm=np.linalg.norm(x,axis=1);ny=np.linalg.norm(y,axis=1);nz=np.linalg.norm(z,axis=1)
   numerator=np.einsum('ij,ij->i',x,np.cross(y,z));denom=norm*ny*nz+np.einsum('ij,ij->i',x,y)*nz+np.einsum('ij,ij->i',y,z)*norm+np.einsum('ij,ij->i',z,x)*ny
   values.append(float(np.arctan2(numerator,denom).sum()/(2*np.pi)))
  rows.append({'bone':name,'windingSamples':values,'allSamplesInside':all(abs(v)>.5 for v in values)})
report={'modelSha256':r['modelSha256'],'method':'solid-angle winding on actual native arm triangles; five actual samples per inferred bone','rows':rows,'outsideSampleBones':[b['bone'] for b in rows if not b['allSamplesInside']],'anatomyVerified':False,'motionVerified':False}
(root/'native_individual_finger_containment_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['outsideSampleBones']))

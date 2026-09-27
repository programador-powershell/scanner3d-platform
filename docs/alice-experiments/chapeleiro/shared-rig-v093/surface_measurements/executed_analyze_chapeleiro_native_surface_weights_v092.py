import hashlib,json
from pathlib import Path
import numpy as np
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/native_surface_measurement_v092')
r=json.loads((root/'measurement.json').read_text(encoding='utf-8'));a=np.load(root/'native_surface_weights.npz')
assert hashlib.sha256((root/'native_surface_weights.npz').read_bytes()).hexdigest()==r['dataSha256']
p=a['points'];e=a['edges'];w=a['weights'];c=a['colors'];names=[b['name'] for b in r['bones']]
length=np.linalg.norm(p[e[:,0]]-p[e[:,1]],axis=1);valid=length>1e-5
masks={'all':np.ones(len(p),bool),'upper_back':(p[:,2]>.63)&(p[:,1]>.015)&(abs(p[:,0])<.110),
       'left_upper_lateral':(p[:,0]>.08)&(p[:,0]<.22)&(p[:,2]>.48)&(p[:,2]<.78),
       'right_upper_lateral':(p[:,0]<-.08)&(p[:,0]>-.22)&(p[:,2]>.48)&(p[:,2]<.78),
       'lower_cloth_leg_transition':(p[:,2]>.16)&(p[:,2]<.45)}
def pose(weights,matrices):
    out=np.zeros_like(p)
    for index in range(len(names)):
        selected=np.flatnonzero(weights[:,index]>0)
        if len(selected):out[selected]+=(p[selected]@matrices[index,:3,:3].T+matrices[index,:3,3])*weights[selected,index,None]
    return out
def weights(index):return {names[i]:float(w[index,i]) for i in np.flatnonzero(w[index]>0)}
rows=[];max_error=0
for index,info in enumerate(r['poses']):
    posed=a['actual_posed_points'][index];predicted=pose(w,a['bone_deformations'][index])
    error=float(np.max(np.abs(predicted-posed)));max_error=max(max_error,error);assert error<2e-6
    ratio=np.zeros(len(e));ratio[valid]=np.linalg.norm(posed[e[valid,0]]-posed[e[valid,1]],axis=1)/length[valid]
    regions={}
    for region,mask in masks.items():
        indices=np.flatnonzero(valid&np.any(mask[e],axis=1));worst=indices[np.argsort(ratio[indices])[-8:][::-1]]
        regions[region]=[{'originalEdge':int(i),'originalVertices':e[i].tolist(),'stretchRatio':float(ratio[i]),
            'restLength':float(length[i]),'restEndpoints':p[e[i]].tolist(),'posedEndpoints':posed[e[i]].tolist(),
            'actualNativeAtlasColors':c[e[i]].tolist(),'actualEndpointWeights':[weights(int(v)) for v in e[i]]} for i in worst]
    rows.append({'pose':info,'linearSkinningMaximumCoordinateError':error,'regions':regions})
report={'measurementDataSha256':r['dataSha256'],'parentWholeModelSha256':r['parentWholeModelSha256'],
    'actualLinearSkinningMaximumCoordinateError':max_error,'scope':'geometric candidate boxes only; these do not prove semantic hair/arm/cloth membership',
    'poses':rows,'geometryChanged':False,'anatomicalRegionsVerified':False,'motionVerified':False,'fidelityVerified':False}
(root/'surface_boundary_diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'linearSkinningMaximumError':max_error,'poses':[{'motion':row['pose']['clip'].split(' /')[0],
    'fraction':row['pose']['fraction'],'maximumStretchByCandidateRegion':{k:v[0]['stretchRatio'] for k,v in row['regions'].items()}} for row in rows]},indent=2))

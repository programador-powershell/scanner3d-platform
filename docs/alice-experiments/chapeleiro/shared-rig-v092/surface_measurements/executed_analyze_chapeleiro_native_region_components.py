import json
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/native_surface_measurement_v090')
r=json.loads((root/'measurement.json').read_text(encoding='utf-8'));a=np.load(root/'native_surface_weights.npz')
p=a['points'];e=a['edges'];c=a['colors'];w=a['weights'];names=[b['name'] for b in r['bones']]
positions,aliases=np.unique(np.round(p,7),axis=0,return_inverse=True)
graph=coo_matrix((np.ones(len(e)),(aliases[e[:,0]],aliases[e[:,1]])),shape=(len(positions),len(positions))).tocsr()
count,labels=connected_components(graph,directed=False);components=labels[aliases]
rows=[]
for index in range(count):
    indices=np.flatnonzero(components==index);total=w[indices].sum(0)
    rows.append({'component':index,'vertices':len(indices),'bounds':[p[indices].min(0).tolist(),p[indices].max(0).tolist()],
        'atlasColorQuantiles':np.quantile(c[indices],[.1,.5,.9],axis=0).tolist(),
        'meanActualBoneWeights':{names[i]:float(total[i]/len(indices)) for i in np.argsort(total)[-8:][::-1] if total[i]>0}})
diagnosis=json.loads((root/'surface_boundary_diagnosis.json').read_text(encoding='utf-8'))
targets=[]
for region in ['upper_back','right_upper_lateral','lower_cloth_leg_transition']:
    vertices=diagnosis['poses'][2]['regions'][region][0]['originalVertices']
    targets.append({'region':region,'originalVertices':vertices,'components':components[vertices].tolist()})
report={'measurementDataSha256':r['dataSha256'],'actualMeasurementComponents':count,'measurementAliasDecimalPlaces':7,
    'rows':rows,'problemSurfaceComponents':targets,'geometryChanged':False,'anatomicalRegionsVerified':False}
(root/'native_region_components.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
np.savez_compressed(root/'native_region_components.npz',positions=positions,aliases=aliases,components=components)
print(json.dumps({'problemSurfaceComponents':targets,'problemComponentBounds':[row for row in rows if row['component'] in {i for t in targets for i in t['components']}],'largestComponents':sorted(rows,key=lambda row:row['vertices'],reverse=True)[:8]},indent=2))

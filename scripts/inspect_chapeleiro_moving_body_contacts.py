"""Validate moving point/face tests and inspect actual recorded cloth sweeps."""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--probe',required=True)
p.add_argument('--bodies',required=True)
p.add_argument('--output',required=True)
p.add_argument('--frames',type=int,nargs='+',default=[15,20,29])
a=p.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'blender'))
from chapeleiro_moving_point_face_contacts import MovingBodyFaceIndex,roots_in_unit_interval
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

# Independent analytic cases: entering/exiting a face, translating obstacle,
# outside-triangle crossing, repeated cubic root, and three distinct roots.
coefficients=np.asarray([np.polynomial.polynomial.polyfromroots([.2,.5,.8]),
                         np.polynomial.polynomial.polyfromroots([.25,.25,.8])])
roots,ambiguous=roots_in_unit_interval(coefficients)
assert not ambiguous.any()
for row,expected in zip(roots,[[.2,.5,.8],[.25,.8]]):
    finite=row[np.isfinite(row)]
    assert all(np.min(np.abs(finite-value))<1e-7 for value in expected)
triangle=np.asarray([[-1,-1,0],[1,-1,0],[0,1,0]],np.float64)
faces=np.asarray([[0,1,2]])
stationary=MovingBodyFaceIndex(triangle,triangle,faces,cell=.5)
hits,_=stationary.entering_contacts(np.asarray([[0,0,1.],[0,0,-1.],[5,0,1.]]),
                                    np.asarray([[0,0,-1.],[0,0,1.],[5,0,-1.]]),np.arange(3))
assert len(hits)==1 and hits[0]['vertex']==0 and abs(hits[0]['time']-.5)<1e-7
moving=MovingBodyFaceIndex(triangle+[0,0,-.5],triangle+[0,0,1.5],faces,cell=.5)
hits,_=moving.entering_contacts(np.asarray([[0,0,0.]]),np.asarray([[0,0,0.]]),np.arange(1))
assert len(hits)==1 and abs(hits[0]['time']-.25)<1e-7
assert np.max(np.abs(hits[0]['barycentric']-np.asarray([.25,.25,.5])))<1e-7
print('MOVING_POINT_FACE_ANALYTIC_CASES_PASSED',flush=True)

r,b=read(a.probe),read(a.bodies)
assert sha(r['dataFile'])==r['dataSha256'] and sha(b['dataFile'])==b['dataSha256']
assert r['sourcePhotoSha256']==b['sourcePhotoSha256']
assert b.get('actualBodyTrianglesFrozenBeforeDeformation'), 'Freeze the body calculation faces before testing motion'
assert b['sourcePhysicalDataSha256']==r['dataSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
d,body=np.load(r['dataFile']),np.load(b['dataFile'])
movable=np.flatnonzero(d['simulation_pin_weights']<=.999)
assert len(d['actual_simulation_points'])==29
rows=[];arrays={};started=time.time()
for frame in a.frames:
    assert 2<=frame<=29
    x0,x1=d['actual_simulation_points'][frame-2:frame]
    for index in range(3):
        points0,points1=body[f'proxy_{index}_animated_world_points'][frame-2:frame]
        triangles=body[f'proxy_{index}_animated_triangles'][frame-1]
        assert np.array_equal(triangles,body[f'proxy_{index}_animated_triangles'][frame-2])
        query=MovingBodyFaceIndex(points0,points1,triangles)
        hits,stats=query.entering_contacts(x0,x1,movable)
        prefix=f'frame_{frame:02d}_proxy_{index}'
        arrays[prefix+'_vertices']=np.asarray([h['vertex'] for h in hits],np.int32)
        arrays[prefix+'_triangles']=np.asarray([h['triangle'] for h in hits],np.int32)
        arrays[prefix+'_times']=np.asarray([h['time'] for h in hits])
        arrays[prefix+'_barycentric']=np.asarray([h['barycentric'] for h in hits]).reshape(-1,3)
        arrays[prefix+'_points_at_impact']=np.asarray([h['pointAtImpact'] for h in hits]).reshape(-1,3)
        row={'frame':frame,'proxyIndex':index,'enteringPointFaceContacts':len(hits),**stats}
        rows.append(row);print('ACTUAL_MOVING_BODY_FACE_CONTACT',json.dumps(row),flush=True)
file=out/'actual_moving_body_face_contacts.npz';np.savez_compressed(file,**arrays)
report={'sourceClothReport':str(Path(a.probe).resolve()),'sourceClothDataSha256':r['dataSha256'],
        'sourceBodyReport':str(Path(a.bodies).resolve()),'sourceBodyDataSha256':b['dataSha256'],
        'sourcePhotoSha256':r['sourcePhotoSha256'],'analyticEnteringExitingTranslatingAndCubicCasesPassed':True,
        'actualFramesAndProxies':rows,'dataFile':str(file),'dataSha256':sha(file),'elapsedSeconds':time.time()-started,
        'clothAndBodyCoordinatesUnchanged':True,'scriptSha256':sha(__file__),
        'pointFaceHelperSha256':sha(Path(__file__).resolve().parents[1]/'blender/chapeleiro_moving_point_face_contacts.py'),
        'collisionResponseApplied':False,'clothCollisionVerified':False,'fidelityVerified':False,
        'limitation':'Linear interpolation of recorded frames and moving point/face candidates only. Inside/outside classification, edge/edge contacts, friction, actual solver substeps and full collision approval remain separate.'}
(out/'moving_body_face_contacts.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(__file__,out/'executed_inspection.py')
shutil.copyfile(Path(__file__).resolve().parents[1]/'blender/chapeleiro_moving_point_face_contacts.py',out/'executed_point_face_helper.py')

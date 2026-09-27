"""Query measured fine or reimported GLB surfaces against recorded bodies.

No rig or solver is rerun. For a reimported GLB, compatibility of the recorded
body motion must be proved separately; this tool does not infer it from names.
Only vertex penetration at the selected poses is measured, not full collision.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--surface-report',required=True)
p.add_argument('--body-reference',required=True)
p.add_argument('--parts-report',required=True)
p.add_argument('--output',required=True)
p.add_argument('--frames',type=int,nargs='+',default=[1,20,29])
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
surface,body,parts=read(a.surface_report),read(a.body_reference),read(a.parts_report)
assert sha(surface['dataFile'])==surface['dataSha256']
assert sha(body['dataFile'])==body['dataSha256']
assert surface['sourcePhotoSha256']==body['sourcePhotoSha256']==parts['sourcePhotoSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
d,b=np.load(surface['dataFile']),np.load(body['dataFile'])
assert d['points'].shape==(29,22080,3) and np.isfinite(d['points']).all()
sys.path.insert(0,str(Path(__file__).parent))
from chapeleiro_xpbd_surface_contacts import closed_state
rows=[];arrays={}
for frame in a.frames:
    assert 1<=frame<=len(d['points'])
    points=d['points'][frame-1]
    proxies=[]
    for index in range(3):
        xyz=b[f'proxy_{index}_animated_world_points'][frame-1]
        triangles=b[f'proxy_{index}_animated_triangles'][frame-1]
        tree=BVHTree.FromPolygons(xyz.tolist(),triangles.tolist(),all_triangles=True)
        candidates=np.flatnonzero(np.all((points>=xyz.min(0))&(points<=xyz.max(0)),axis=1))
        certain=np.zeros(len(points),bool);ambiguous=np.zeros(len(points),bool)
        distance=np.zeros(len(points),np.float32)
        for i in candidates:
            nearest,normal,triangle,gap=tree.find_nearest(Vector(points[i]))
            assert nearest is not None
            distance[i]=gap
            if gap<=1e-5:continue
            state=closed_state(tree,points[i])
            certain[i]=state is True
            ambiguous[i]=state is None
        per_piece=[]
        for part in parts['parts']:
            ids=np.arange(part['start'],part['start']+part['vertices'])
            inside=ids[certain[ids]]
            per_piece.append({'key':part['key'],'certainInsideVertices':len(inside),
                              'maximumCertainPenetrationMeters':float(distance[inside].max()) if len(inside) else 0,
                              'ambiguousQueries':int(ambiguous[ids].sum())})
        proxies.append({'proxyIndex':index,'certainInsideVertices':int(certain.sum()),
                        'maximumCertainPenetrationMeters':float(distance[certain].max()) if certain.any() else 0,
                        'ambiguousQueries':int(ambiguous.sum()),'pieces':per_piece})
        arrays[f'frame_{frame:02d}_proxy_{index}_inside_indices']=np.flatnonzero(certain)
        arrays[f'frame_{frame:02d}_proxy_{index}_ambiguous_indices']=np.flatnonzero(ambiguous)
        arrays[f'frame_{frame:02d}_proxy_{index}_inside_distances']=distance[certain]
    rows.append({'frame':frame,'proxies':proxies})
    print('ACTUAL_RECORDED_SURFACE_BODY_CONTACT',frame,json.dumps(proxies),flush=True)
file=out/'actual_recorded_surface_body_contacts.npz'
np.savez_compressed(file,**arrays)
report={'sourceSurfaceReport':str(Path(a.surface_report).resolve()),'sourceSurfaceDataSha256':surface['dataSha256'],
        'sourceBodyReference':str(Path(a.body_reference).resolve()),'sourceBodyDataSha256':body['dataSha256'],
        'sourcePhotoSha256':surface['sourcePhotoSha256'],'frames':rows,'dataFile':str(file),'dataSha256':sha(file),
        'surfaceTrajectoryAndBodiesUnchanged':True,'scriptSha256':sha(__file__),
        'limitation':'Selected recorded vertex queries only. Body-motion compatibility is a separate prerequisite; edges, faces, thickness and continuous time are not approved.',
        'clothCollisionVerified':False,'fidelityVerified':False}
(out/'recorded_surface_body_contacts.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(__file__,out/'executed_inspection.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_xpbd_surface_contacts.py'),out/'executed_surface_contact_helper.py')

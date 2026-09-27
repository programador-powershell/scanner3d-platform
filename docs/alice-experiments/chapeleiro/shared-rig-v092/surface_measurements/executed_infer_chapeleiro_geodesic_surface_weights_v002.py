"""Infer continuous ownership along the intact native surface; no mesh edits."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/native_surface_measurement_v090')
out=root/'geodesic_surface_candidate_v002';assert not out.exists();out.mkdir()
r=json.loads((root/'measurement.json').read_text(encoding='utf-8'))
a=np.load(root/'native_surface_weights.npz');assert hashlib.sha256((root/'native_surface_weights.npz').read_bytes()).hexdigest()==r['dataSha256']
p=a['points'];edges=a['edges'];colors=a['colors'];old=a['weights'];names=[b['name'] for b in r['bones']]
indexed={n:i for i,n in enumerate(names)};bones={b['name']:(np.array(b['head']),np.array(b['tail'])) for b in r['bones']}
components=np.load(root/'native_region_components.npz');aliases=components['aliases'];positions=components['positions']
labels=components['components'];n=len(positions)
counts=np.bincount(aliases,minlength=n)
alias_colors=np.stack([np.bincount(aliases,weights=colors[:,i],minlength=n)/counts for i in range(3)],axis=1)
pairs=np.sort(aliases[edges],axis=1);pairs=np.unique(pairs,axis=0);pairs=pairs[pairs[:,0]!=pairs[:,1]]
lengths=np.linalg.norm(positions[pairs[:,0]]-positions[pairs[:,1]],axis=1)
cost=lengths*(1+15*np.linalg.norm(alias_colors[pairs[:,0]]-alias_colors[pairs[:,1]],axis=1))
graph=coo_matrix((cost,(pairs[:,0],pairs[:,1])),shape=(n,n)).tocsr()

def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)
def distances(points,groups):
    values=[]
    for name in groups:
        head,tail=bones[name];direction=tail-head
        t=np.clip((points-head)@direction/max(float(direction@direction),1e-15),0,1)
        values.append(np.linalg.norm(points-head-t[:,None]*direction,axis=1))
    return np.stack(values,axis=1)
def normalize(w):
    keep=np.argpartition(w,-4,axis=1)[:,-4:]
    sparse=np.zeros_like(w);np.put_along_axis(sparse,keep,np.take_along_axis(w,keep,axis=1),axis=1)
    total=sparse.sum(1);assert np.min(total)>0
    return sparse/total[:,None]
def near(groups,minimum):
    d=distances(p,groups);order=np.argsort(d,axis=1)[:,:3]
    best=d.min(1);v=(1-smooth((d-best[:,None])/.040))/(d+minimum)**4
    selected=np.zeros_like(v);np.put_along_axis(selected,order,np.take_along_axis(v,order,axis=1),axis=1)
    selected/=selected.sum(1)[:,None];w=np.zeros_like(old)
    for index,name in enumerate(groups):w[:,indexed[name]]=selected[:,index]
    return w
def torso():
    groups=['Hips','Spine','Spine1','Spine2','Neck'];z=np.array([bones[name][0][2] for name in groups])
    w=np.zeros_like(old);w[p[:,2]<=z[0],indexed[groups[0]]]=1
    for i in range(4):
        mask=(p[:,2]>z[i])&(p[:,2]<=z[i+1]);t=smooth((p[mask,2]-z[i])/(z[i+1]-z[i]))
        w[mask,indexed[groups[i]]]=1-t;w[mask,indexed[groups[i+1]]]=t
    w[p[:,2]>z[-1],indexed[groups[-1]]]=1;return w
def cloth(torso_weights):
    schema=json.loads(Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v090/shared_rig_bind.json').read_text(encoding='utf-8'))
    rule=schema['clothFamilies']['ExteriorCloth'];levels=rule['levels'];sectors=rule['sectors']
    theta=np.arctan2(p[:,0],-p[:,1])%(2*np.pi);angle=theta/(2*np.pi)*sectors
    sector=angle.astype(int)%sectors;fraction=smooth(angle-np.floor(angle));w=np.zeros_like(old)
    rows=np.full(len(p),len(levels)-2,int)
    for i in range(len(levels)-2,-1,-1):rows[(p[:,2]<=levels[i])&(p[:,2]>=levels[i+1])]=i
    vertical=smooth((np.array(levels)[rows]-p[:,2])/(np.array(levels)[rows]-np.array(levels)[rows+1]))
    for s,sw in [(sector,1-fraction),((sector+1)%sectors,fraction)]:
        for level,vw in [(rows,1-vertical),(np.minimum(rows+1,len(levels)-2),vertical)]:
            cols=np.array([indexed[f'ExteriorCloth_{a:02d}_{b}'] for a,b in zip(s,level)])
            np.add.at(w,(np.arange(len(p)),cols),sw*vw)
    free=smooth((levels[0]-p[:,2])/.055)
    return normalize(torso_weights*(1-free[:,None])+w*free[:,None])

x,y,z=p.T;lo=colors.min(1);hi=colors.max(1);chroma=(hi-lo)/np.maximum(hi,1e-8)
red,green,blue=colors.T
skin=(red>green*1.06)&(red>blue*1.08)&(blue>green*.60)&(lo>.08)&(hi>.35)&(chroma<.55)
head=(z>.85)|((z>.630)&(abs(x)<.112)&(y>.008)&(hi<.30)&(chroma<.25))
head|=(z>.72)&(abs(x)>.045)&(abs(x)<.10)&(y<.01)&(hi<.14)&(chroma<.30)
arms={}
for side,sign in [('Left',1),('Right',-1)]:
    distance=distances(p,[side+'Arm',side+'ForeArm',side+'Hand']).min(1)
    arm=(x*sign>.090)&(x*sign<.195)&(z>.56)&(z<.745)&(y>-.08)&(y<.065)&skin&(distance<.036)
    arm|=(x*sign>.100)&(x*sign<.18)&(z>.708)&(z<.81)&(y<.058)&(distance<.055)&(green>red*1.03)
    arms[side]=arm&~head
torso_seed=((z>.635)&(z<.825)&(abs(x)<.075)&((y<-.006)|(green>red*1.06)))
torso_seed|=(z>.585)&(z<.650)&(abs(x)<.08)&(abs(y)<.07)
torso_seed&=~head&~arms['Left']&~arms['Right']
cloth_seed=(z>.20)&(z<.60)&(((abs(x)>.135)&(z<.535))|(abs(y)>.085))&(labels==0)
cloth_seed&=~head&~arms['Left']&~arms['Right']&~torso_seed
legs={}
for side,sign in [('Left',1),('Right',-1)]:
    distance=distances(p,[side+'UpLeg',side+'Leg',side+'Foot',side+'ToeBase']).min(1)
    legs[side]=(x*sign>0)&((z<.16)|((z<.44)&(distance<.022)))&~cloth_seed
seeds={'Head':head,'Torso':torso_seed,'Cloth':cloth_seed,'LeftArm':arms['Left'],'RightArm':arms['Right'],
       'LeftLeg':legs['Left'],'RightLeg':legs['Right']}
owner_names=list(seeds);ds=[];seed_counts={}
for owner,mask in seeds.items():
    indices=np.unique(aliases[mask]);assert len(indices)>0
    ds.append(dijkstra(graph,directed=False,indices=indices,min_only=True));seed_counts[owner]=len(indices)
    print('ORIGINAL_SURFACE_GEODESIC_MEASURED',owner,len(indices),flush=True)
ds=np.stack(ds,axis=1);minimum=ds.min(1);reachable=np.isfinite(minimum)
prob=np.zeros_like(ds);delta=np.full_like(ds,np.inf);delta[reachable]=ds[reachable]-minimum[reachable,None]
prob[reachable]=np.exp(-delta[reachable]/.018);prob[reachable]/=prob[reachable].sum(1)[:,None]
prob=prob[aliases];reachable=reachable[aliases]
preserve=np.zeros(len(p),bool)
# Preserve the existing separate hand/forearm surfaces and their measured bind.
for component in np.unique(labels):
    mask=labels==component
    if component==0:continue
    mean=old[mask].mean(0);arm_total=sum(mean[i] for i,name in enumerate(names) if name.startswith(('LeftArm','RightArm','LeftForeArm','RightForeArm','LeftHand','RightHand')))
    if arm_total>.95 and p[mask,2].max()<.72:preserve|=mask
new=np.zeros_like(old);torso_weights=torso()
for i,owner in enumerate(owner_names):
    if owner=='Head':target=np.zeros_like(old);target[:,indexed['Head']]=1
    elif owner=='Torso':target=torso_weights
    elif owner=='Cloth':target=cloth(torso_weights)
    elif owner.endswith('Arm'):
        side=owner[:-3];target=near([side+'Shoulder',side+'Arm',side+'ForeArm',side+'Hand'],.008)
    else:
        side=owner[:-3];target=near([side+'UpLeg',side+'Leg',side+'Foot',side+'ToeBase'],.006)
    new+=target*prob[:,i,None]
new[~reachable|preserve]=old[~reachable|preserve];new=normalize(new)
integers=np.rint(new*65536).astype(np.int32);largest=integers.argmax(1)
integers[np.arange(len(p)),largest]+=65536-integers.sum(1)
new=integers.astype(np.float32)/65536
assert np.array_equal(new[preserve],old[preserve]) and np.all(integers.sum(1)==65536)
assert np.max((new>0).sum(1))<=4
file=out/'surface_weights.npz';np.savez_compressed(file,weights=new,owner_probabilities=prob.astype(np.float32),preserved_vertices=preserve)
length=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1);valid=length>1e-5
def pose(weights,matrices):
    result=np.zeros_like(p)
    for i in range(len(names)):
        select=np.flatnonzero(weights[:,i]>0)
        if len(select):result[select]+=(p[select]@matrices[i,:3,:3].T+matrices[i,:3,3])*weights[select,i,None]
    return result
rows=[]
for i,info in enumerate(r['poses']):
    points=pose(new,a['bone_deformations'][i]);ratio=np.linalg.norm(points[edges[valid,0]]-points[edges[valid,1]],axis=1)/length[valid]
    baseline=np.linalg.norm(a['actual_posed_points'][i,edges[valid,0]]-a['actual_posed_points'][i,edges[valid,1]],axis=1)/length[valid]
    rows.append({'pose':info,'beforeMaximumStretchRatio':float(baseline.max()),'candidateMaximumStretchRatio':float(ratio.max()),
        'beforeEdgesAbove10':int((baseline>10).sum()),'candidateEdgesAbove10':int((ratio>10).sum())})
report={'parentEditableSha256':r['parentEditableSha256'],'parentWholeModelSha256':r['parentWholeModelSha256'],
    'sourcePhotoSha256':r['sourcePhotoSha256'],'rawGeometrySha256':r['rawGeometrySha256'],'measurementDataSha256':r['dataSha256'],
    'weightsFile':str(file),'weightsSha256':hashlib.sha256(file.read_bytes()).hexdigest(),'boneNames':names,
    'method':'appearance-weighted geodesic ownership on original surface edges with coincident UV aliases only in measurement graph; continuous mixed body/cloth fields, at most four quantized influences',
    'appearanceCostMultiplier':15,'geodesicSoftTransitionMeters':.018,'seedCounts':seed_counts,'ownerNames':owner_names,
    'actualVertices':len(p),'changedVertices':int(np.any(new!=old,axis=1).sum()),'preservedSeparateArmVertices':int(preserve.sum()),
    'unreachableVerticesPreserved':int((~reachable).sum()),'actualQuantization':65536,'nativePoseEstimates':rows,
    'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'geometryChanged':False,
    'anatomicalRegionsVerified':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,
    'limitation':'Region ownership is inferred and requires actual 3D/own-photo review. Native linear-skin estimates are not new exported GLBs or physics approval.'}
(out/'inference.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'changedVertices':report['changedVertices'],'preservedArmVertices':report['preservedSeparateArmVertices'],'nativePoseEstimates':rows},indent=2))

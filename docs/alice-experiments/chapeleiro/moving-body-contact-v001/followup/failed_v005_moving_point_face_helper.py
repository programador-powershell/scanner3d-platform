"""Linear moving point/triangle contact candidates for body collision studies.

Use swept boxes and roots of the coplanarity cubic, as in the point/face test
in https://graphics.stanford.edu/papers/cloth-sig02/cloth.pdf. This is not that
paper's full collision solver: edge/edge contact and friction are not included.
"""
from itertools import product
import numpy as np

def evaluate(coefficients, t):
    return ((coefficients[:,3]*t+coefficients[:,2])*t+coefficients[:,1])*t+coefficients[:,0]

def roots_in_unit_interval(coefficients):
    """Find roots in each monotonic interval, including tangent roots.

    Endpoint/critical-point roots are retained. Numerically coplanar paths are
    returned separately as ambiguous, rather than invented point contacts.
    """
    c=np.asarray(coefficients,np.float64)
    assert c.ndim==2 and c.shape[1]==4 and np.isfinite(c).all()
    scale=np.max(np.abs(c),axis=1)
    tolerance=np.maximum(scale*1e-10,1e-18)
    coplanar=scale<1e-18
    intervals=np.empty((len(c),4));intervals[:,0]=0;intervals[:,3]=1
    intervals[:,1:3]=1
    aa,bb,cc=3*c[:,3],2*c[:,2],c[:,1]
    quadratic=np.abs(aa)>tolerance
    discriminant=bb*bb-4*aa*cc
    valid=quadratic&(discriminant>=0)
    radical=np.sqrt(np.maximum(discriminant,0))
    denominator=np.where(valid,2*aa,1)
    for slot,root in [(1,(-bb-radical)/denominator),(2,(-bb+radical)/denominator)]:
        intervals[valid&(root>0)&(root<1),slot]=root[valid&(root>0)&(root<1)]
    linear=~quadratic&(np.abs(bb)>tolerance)
    root=np.divide(-cc,bb,out=np.zeros(len(c)),where=linear)
    intervals[linear&(root>0)&(root<1),1]=root[linear&(root>0)&(root<1)]
    intervals.sort(axis=1)
    roots=np.full((len(c),7),np.nan)
    for slot in range(4):
        t=intervals[:,slot]
        near=(np.abs(evaluate(c,t))<=tolerance)&~coplanar
        roots[near,slot]=t[near]
    for slot in range(3):
        low,high=intervals[:,slot].copy(),intervals[:,slot+1].copy()
        flo,fhi=evaluate(c,low),evaluate(c,high)
        crossing=(flo*fhi<0)&(high-low>1e-12)&~coplanar
        for _ in range(40):
            middle=(low+high)*.5;fm=evaluate(c,middle)
            same=flo*fm>0
            low=np.where(same,middle,low);flo=np.where(same,fm,flo)
            high=np.where(same,high,middle)
        roots[crossing,slot+4]=((low+high)*.5)[crossing]
    return roots,coplanar

def coplanarity_coefficients(point0,point1,tri0,tri1):
    p,q,r=tri0[:,1]-tri0[:,0],tri0[:,2]-tri0[:,0],point0-tri0[:,0]
    delta=tri1-tri0
    dp,dq,dr=delta[:,1]-delta[:,0],delta[:,2]-delta[:,0],point1-point0-delta[:,0]
    cross0=np.cross(p,q)
    cross1=np.cross(dp,q)+np.cross(p,dq)
    cross2=np.cross(dp,dq)
    dot=lambda x,y:np.einsum('ij,ij->i',x,y)
    return np.column_stack([dot(cross0,r),dot(cross1,r)+dot(cross0,dr),
                            dot(cross2,r)+dot(cross1,dr),dot(cross2,dr)])

class MovingBodyFaceIndex:
    def __init__(self, points0, points1, triangles, cell=.025, tolerance=1e-6):
        self.points0=np.asarray(points0,np.float64)
        self.points1=np.asarray(points1,np.float64)
        self.triangles=np.asarray(triangles,np.int32)
        assert self.points0.shape==self.points1.shape and self.triangles.shape[1]==3
        assert cell>0 and np.isfinite(self.points0).all() and np.isfinite(self.points1).all()
        self.cell,self.tolerance=cell,tolerance
        t0,t1=self.points0[self.triangles],self.points1[self.triangles]
        self.low=np.minimum(t0.min(1),t1.min(1))-tolerance
        self.high=np.maximum(t0.max(1),t1.max(1))+tolerance
        self.buckets={}
        low,high=np.floor(self.low/cell).astype(int),np.floor(self.high/cell).astype(int)
        for index,(a,b) in enumerate(zip(low,high)):
            assert np.prod(b-a+1)<20000, 'Unexpected body sweep extent'
            for key in product(*(range(a[j],b[j]+1) for j in range(3))):
                self.buckets.setdefault(key,[]).append(index)

    def entering_contacts(self, point0, point1, ids):
        point0,point1=np.asarray(point0,np.float64),np.asarray(point1,np.float64)
        ids=np.asarray(ids,np.int32)
        body_low,body_high=self.low.min(0),self.high.max(0)
        query_low=np.minimum(point0[ids],point1[ids])-self.tolerance
        query_high=np.maximum(point0[ids],point1[ids])+self.tolerance
        ids=ids[np.all((query_low<=body_high)&(query_high>=body_low),axis=1)]
        pairs=[]
        for i in ids:
            low=np.minimum(point0[i],point1[i])-self.tolerance
            high=np.maximum(point0[i],point1[i])+self.tolerance
            a,b=np.floor(low/self.cell).astype(int),np.floor(high/self.cell).astype(int)
            assert np.prod(b-a+1)<20000, 'Unexpected cloth sweep extent'
            candidates=set()
            for key in product(*(range(a[j],b[j]+1) for j in range(3))):
                candidates.update(self.buckets.get(key,[]))
            if candidates:
                face_ids=np.asarray(sorted(candidates),np.int32)
                overlap=np.all((self.low[face_ids]<=high)&(self.high[face_ids]>=low),axis=1)
                pairs.extend((int(i),int(j)) for j in face_ids[overlap])
        if not pairs:return [],{'sweptCandidatePairs':0,'coplanarAmbiguousPairs':0}
        pairs=np.asarray(pairs,np.int32)
        tri0,tri1=self.points0[self.triangles[pairs[:,1]]],self.points1[self.triangles[pairs[:,1]]]
        x0,x1=point0[pairs[:,0]],point1[pairs[:,0]]
        roots,coplanar=roots_in_unit_interval(coplanarity_coefficients(x0,x1,tri0,tri1))
        best={}
        for slot in range(roots.shape[1]):
            t=roots[:,slot]
            selected=np.flatnonzero(np.isfinite(t)&(t>1e-8)&(t<=1))
            if not len(selected):continue
            time=t[selected,None,None]
            xyz=tri0[selected]+(tri1[selected]-tri0[selected])*time
            point=x0[selected]+(x1[selected]-x0[selected])*t[selected,None]
            u,v,w=xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0],point-xyz[:,0]
            dot=lambda x,y:np.einsum('ij,ij->i',x,y)
            uu,uv,vv,wu,wv=dot(u,u),dot(u,v),dot(v,v),dot(w,u),dot(w,v)
            determinant=uu*vv-uv*uv
            valid=determinant>1e-20
            denominator=np.where(valid,determinant,1)
            beta,gamma=(vv*wu-uv*wv)/denominator,(uu*wv-uv*wu)/denominator
            weights=np.column_stack([1-beta-gamma,beta,gamma])
            normal=np.cross(u,v);length=np.linalg.norm(normal,axis=1)
            normal/=np.maximum(length,1e-20)[:,None]
            body_motion=np.sum((tri1[selected]-tri0[selected])*weights[:,:,None],axis=1)
            approach=dot(x1[selected]-x0[selected]-body_motion,normal)
            plane_error=np.abs(dot(w,normal))
            valid&=np.all(weights>=-1e-6,axis=1)&np.all(weights<=1+1e-6,axis=1)
            valid&=(approach<-1e-10)&(plane_error<self.tolerance*2)
            for local in np.flatnonzero(valid):
                pair=selected[local];i,j=map(int,pairs[pair]);fraction=float(t[pair])
                if i not in best or fraction<best[i]['time']:
                    best[i]={'vertex':i,'triangle':j,'time':fraction,'barycentric':weights[local].copy(),
                             'pointAtImpact':point[local].copy(),'normalAtImpact':normal[local].copy()}
        return [best[i] for i in sorted(best)],{'sweptCandidatePairs':len(pairs),
                                              'coplanarAmbiguousPairs':int(coplanar.sum())}

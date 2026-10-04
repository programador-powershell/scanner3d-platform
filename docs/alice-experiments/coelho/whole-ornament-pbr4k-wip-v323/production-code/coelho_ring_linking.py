"""Oriented intersections with the actual polygon's triangulated spanning disk.

No fitted-plane projection. This is a static centerline topology diagnostic,
not a proof of surface clearance or rigid-body physics.
"""
import numpy as np

def disk_crossings(A,B,tolerance=1e-10):
    A=np.asarray(A,float);B=np.asarray(B,float);center=A.mean(0)
    hits=[];ambiguous=[]
    for i in range(len(A)):
        u=A[i]-center;v=A[(i+1)%len(A)]-center;n=np.cross(u,v)
        uu=u@u;uv=u@v;vv=v@v;den=uu*vv-uv*uv
        if den<=1e-30:raise ValueError('Degenerate spanning triangle')
        for j in range(len(B)):
            p=B[j];d=B[(j+1)%len(B)]-p;nd=n@d
            if abs(nd)<=1e-14*np.linalg.norm(n)*np.linalg.norm(d):continue
            t=n@(center-p)/nd
            if t < -1e-8 or t > 1+1e-8:continue
            q=p+t*d;w=q-center;wu=w@u;wv=w@v
            beta=(vv*wu-uv*wv)/den;gamma=(uu*wv-uv*wu)/den;alpha=1-beta-gamma
            if min(alpha,beta,gamma)<-1e-7:continue
            # Only the outer boundary of the fan is a topological ambiguity.
            if abs(alpha)<=1e-7:ambiguous.append((i,j))
            hits.append((q,int(np.sign(nd)),i,j,float(t)))
    groups=[]
    for h in hits:
        for g in groups:
            if np.linalg.norm(g[0][0]-h[0])<tolerance:g.append(h);break
        else:groups.append([h])
    rows=[]
    for g in groups:
        signs={h[1] for h in g}
        # Opposite directions at the same point are a vertex tangency, not
        # a traversal through the disk. Same-sign duplicates count once.
        sign=next(iter(signs)) if len(signs)==1 else 0
        rows.append(dict(point=g[0][0].tolist(),direction=sign,duplicates=len(g),triangleSegmentPairs=[[h[2],h[3]] for h in g]))
    return dict(linkingNumber=sum(r['direction'] for r in rows),boundaryAmbiguous=bool(ambiguous),boundaryPairs=[list(x) for x in ambiguous],crossings=rows)

def self_test():
    t=np.arange(32)*2*np.pi/32
    A=np.column_stack((np.cos(t),np.zeros(32),np.sin(t)))
    B=np.column_stack((np.zeros(32),np.cos(t),.8+np.sin(t)))
    for M in [np.eye(3),np.array([[.36,-.48,.8],[.8,.6,0],[-.48,.64,.6]])]:
        a=A@M;b=B@M
        assert abs(disk_crossings(a,b)['linkingNumber'])==abs(disk_crossings(b,a)['linkingNumber'])==1
        assert disk_crossings(a,b+[0,0,5])['linkingNumber']==0
        assert disk_crossings(b+[0,0,5],a)['linkingNumber']==0
    # Subdivision and cyclic point ordering cannot change the disk result.
    mid=(B+np.roll(B,-1,axis=0))/2;sub=np.stack((B,mid),axis=1).reshape(-1,3)
    assert disk_crossings(A,np.roll(sub,7,axis=0))['linkingNumber']==disk_crossings(A,B)['linkingNumber']
    assert disk_crossings(A,B[::-1])['linkingNumber']==-disk_crossings(A,B)['linkingNumber']
    return True

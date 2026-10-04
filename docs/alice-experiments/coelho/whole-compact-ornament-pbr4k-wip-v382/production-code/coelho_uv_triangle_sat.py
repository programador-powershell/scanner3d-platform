"""Inclusive 2D broadphase and strict positive-area triangle overlap tests."""
import numpy as np,itertools
EPSILON_UV=1e-12
def sat(A,B):
    edges=np.concatenate((np.roll(A,-1,axis=1)-A,np.roll(B,-1,axis=1)-B),axis=1);axes=np.stack((-edges[:,:,1],edges[:,:,0]),axis=2);length=np.linalg.norm(axes,axis=2);assert (length>1e-15).all();axes/=length[:,:,None];pa=np.einsum('nvc,nac->nva',A,axes);pb=np.einsum('nvc,nac->nva',B,axes);return ((np.minimum(pa.max(1),pb.max(1))-np.maximum(pa.min(1),pb.min(1)))>EPSILON_UV).all(1)
def broad(T):
    minimum=T.min(1);maximum=T.max(1);lo=np.floor(minimum*128).astype(int);hi=np.floor(maximum*128).astype(int);cells={};encoded=set();N=len(T)
    for i,(lower,upper) in enumerate(zip(lo,hi)):
        for x in range(lower[0],upper[0]+1):
            for y in range(lower[1],upper[1]+1):cells.setdefault((x,y),[]).append(i)
    for indices in cells.values():encoded.update(i*N+j for i,j in itertools.combinations(indices,2))
    pairs=np.asarray([(k//N,k%N) for k in sorted(encoded)],np.int32).reshape(-1,2)
    if len(pairs):pairs=pairs[(np.minimum(maximum[pairs[:,0]],maximum[pairs[:,1]])-np.maximum(minimum[pairs[:,0]],minimum[pairs[:,1]])>=0).all(1)]
    return pairs
def overlaps(T):
    pairs=broad(T);hits=[]
    for k in range(0,len(pairs),8192):
        pair=pairs[k:k+8192];hits.extend(pair[sat(T[pair[:,0]],T[pair[:,1]])].tolist())
    return np.asarray(hits,np.int32).reshape(-1,2),len(pairs)
def unit_tests():
    T=np.array([[[0,0],[1,0],[0,1]],[[.1,.1],[.2,.1],[.1,.2]],[[2,2],[3,2],[2,3]],[[1,0],[1,1],[0,1]],[[0,0],[1,0],[0,1]]],float);hits,_=overlaps(T);assert {tuple(p) for p in hits}=={(0,1),(0,4),(1,4)}
    # Narrow overlaps below a pixel still count; translation/rotation invariant.
    A=np.array([[0,0],[1,0],[0,1]],float);B=A+np.array([.999999,0]);Q=np.array([[np.cos(.33),-np.sin(.33)],[np.sin(.33),np.cos(.33)]]);assert sat(A[None],B[None])[0] and sat((A@Q)[None],(B@Q)[None])[0]
    return True

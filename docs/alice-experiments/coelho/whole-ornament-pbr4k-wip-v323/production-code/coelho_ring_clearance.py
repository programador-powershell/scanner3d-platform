import numpy as np

def distances(pathA,pathB):
    A=pathA[:,:,None,:];B=pathB[:,None,:,:]
    u=(np.roll(pathA,-1,axis=1)-pathA)[:,:,None,:];v=(np.roll(pathB,-1,axis=1)-pathB)[:,None,:,:];w=A-B
    dot=lambda x,y:np.einsum('...c,...c->...',x,y)
    aa=dot(u,u);bb=dot(u,v);cc=dot(v,v);dd=dot(u,w);ee=dot(v,w)
    den=aa*cc-bb*bb;safe=np.where(abs(den)>1e-30,den,1)
    s=(bb*ee-cc*dd)/safe;t=(aa*ee-bb*dd)/safe
    inside=(abs(den)>1e-30)&(s>=0)&(s<=1)&(t>=0)&(t<=1)
    norm2=lambda x:dot(x,x)
    values=[np.where(inside,norm2(w+s[...,None]*u-t[...,None]*v),np.inf)]
    values.extend([norm2(w-np.clip(ee/cc,0,1)[...,None]*v),norm2(w+u-np.clip((ee+bb)/cc,0,1)[...,None]*v),norm2(w+np.clip(-dd/aa,0,1)[...,None]*u),norm2(w-v+np.clip((bb-dd)/aa,0,1)[...,None]*u)])
    return np.sqrt(np.maximum(np.minimum.reduce(values).min(axis=(1,2)),0))

"""Bake the repaired back into a separate 4K atlas, testing visibility per texel."""
import argparse,hashlib,json,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--pixels',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
g=json.loads(Path(a.generation).read_text());assert sha(g['editableBlend'])==g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);s=bpy.context.scene;s.frame_set(1)
target_names=['Chapeleiro / finished posterior bodice / checkpoint',g['posteriorBodice']['underlyingSkinObject'],'Chapeleiro / posterior closure placket']
targets=[bpy.data.objects[n] for n in target_names]
pixels=np.load(a.pixels,mmap_mode='r');resolution=4096
atlas=np.empty((resolution,resolution,4),np.uint8);atlas[:]=[24,50,40,255]
owner=np.full((resolution,resolution),-1,np.int32);projected=np.zeros((resolution,resolution),bool)
verts=[];tris=[];jobs=[];charts={};object_rows=[]
dg=bpy.context.evaluated_depsgraph_get()
for obj in s.objects:
    if obj.type!='MESH' or obj.hide_render or obj.get('alice_collision_proxy'):continue
    ev=obj.evaluated_get(dg);mesh=ev.to_mesh();mesh.calc_loop_triangles()
    points=np.array([ev.matrix_world@v.co for v in mesh.vertices],np.float32)
    offset=len(verts);triangle_offset=len(tris);verts.extend(points.tolist());tris.extend([[offset+i for i in t.vertices] for t in mesh.loop_triangles])
    if obj in targets:
        index=targets.index(obj);raw=obj.data;source_uv=np.array([x.uv[:] for x in raw.uv_layers.active.data],np.float32)
        uv=np.empty_like(source_uv)
        for loop in raw.loops:
            vi=loop.vertex_index
            if index==0:u=(vi%65)/64;v=(vi//65)/64;uv[loop.index]=(.02+.70*u,.02+.96*v)
            elif index==1:u=(vi%41)/40;v=(vi//41)/48;uv[loop.index]=(.74+.08*u,.02+.96*v)
            else:u=vi%2;v=(vi//2)/64;uv[loop.index]=(.84+.14*u,.02+.96*v)
        charts['uv_'+str(index)]=uv
        object_rows.append(dict(name=obj.name,key='uv_'+str(index),loops=len(raw.loops),materialSlots=[i for i,m in enumerate(raw.materials) if m and m.name.startswith('Chapeleiro / posterior corset')]))
        for ti,tri in enumerate(mesh.loop_triangles):
            if tri.material_index not in object_rows[-1]['materialSlots']:continue
            loops=list(tri.loops)
            jobs.append((triangle_offset+ti,points[list(tri.vertices)],uv[loops],source_uv[loops]))
    ev.to_mesh_clear()
tree=BVHTree.FromPolygons(verts,tris,all_triangles=True);del verts,tris
def sample(uv):
    xy=np.clip(uv*[1,-1]+[0,1],0,1)*[pixels.shape[1]-1,pixels.shape[0]-1]
    low=np.floor(xy).astype(int);high=np.minimum(low+1,[pixels.shape[1]-1,pixels.shape[0]-1]);w=(xy-low).astype(np.float32)
    aa=pixels[low[:,1],low[:,0]].astype(np.float32);bb=pixels[low[:,1],high[:,0]].astype(np.float32)
    cc=pixels[high[:,1],low[:,0]].astype(np.float32);dd=pixels[high[:,1],high[:,0]].astype(np.float32)
    return (aa*(1-w[:,0,None])+bb*w[:,0,None])*(1-w[:,1,None])+(cc*(1-w[:,0,None])+dd*w[:,0,None])*w[:,1,None]
tested=visible=occluded=0;start=time.time();direction=Vector((0,-1,0));offset=Vector((0,2,0))
for order,(tid,points,uv,source_uv) in enumerate(jobs):
    chart=(uv*[1,-1]+[0,1])*resolution-.5
    lo=np.maximum(np.ceil(chart.min(0)).astype(int),0);hi=np.minimum(np.floor(chart.max(0)).astype(int),resolution-1)
    if (hi<lo).any():continue
    e1,e2=chart[1]-chart[0],chart[2]-chart[0];den=e1[0]*e2[1]-e1[1]*e2[0]
    if abs(den)<1e-10:continue
    yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];xy=np.c_[xx.ravel(),yy.ravel()];delta=xy-chart[0]
    b1=(delta[:,0]*e2[1]-delta[:,1]*e2[0])/den;b2=(e1[0]*delta[:,1]-e1[1]*delta[:,0])/den
    bary=np.c_[1-b1-b2,b1,b2];keep=(bary>=-1e-7).all(1)&(owner[xy[:,1],xy[:,0]]<0);xy,bary=xy[keep],bary[keep]
    if not len(xy):continue
    loc=bary@points;colors=sample(bary@source_uv);accepted=np.zeros(len(xy),bool)
    for i,point in enumerate(loc):
        hit,normal,face,distance=tree.ray_cast(Vector(point)+offset,direction,2.1);tested+=1
        accepted[i]=hit is not None and (face==tid or (hit-Vector(point)).length<.00002)
    visible+=int(accepted.sum());occluded+=int((~accepted).sum());owner[xy[:,1],xy[:,0]]=tid
    x=xy[accepted];atlas[x[:,1],x[:,0]]=np.clip(np.rint(colors[accepted]),0,255).astype(np.uint8);atlas[x[:,1],x[:,0],3]=255;projected[x[:,1],x[:,0]]=True
    if order%128==0:print('POSTERIOR_UV4K',order,len(jobs),'rays',tested,'visible',visible,'seconds',round(time.time()-start,1),flush=True)
np.save(out/'atlas_encoded_rgba.npy',atlas);np.save(out/'projected_texels.npy',projected);np.save(out/'triangle_owner.npy',owner);np.savez_compressed(out/'uv_coordinates.npz',**charts)
report=dict(sourceGeneration=a.generation,sourceBlendSha256=g['editableBlendSha256'],painting=g['posteriorBodice']['projectionPainting'],paintingSha256=g['posteriorBodice']['projectionPaintingSha256'],pixelCache=a.pixels,pixelCacheSha256=sha(a.pixels),resolution=[4096,4096],raysTested=tested,visibleTexels=visible,occludedTexelsRetainedAsDarkUnderlayer=occluded,visibilityMethod='Per-texel orthographic rear depth ray against actual rendered meshes with hair temporarily excluded; original whole-hair mask evaluated',objects=object_rows,atlas=str(out/'atlas_encoded_rgba.npy'),uvCoordinates=str(out/'uv_coordinates.npz'),sourceUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],published=False,finalFidelityApproved=False)
(out/'bake.json').write_text(json.dumps(report,indent=2)+'\n');print('POSTERIOR_UV4K_COMPLETE',json.dumps(report),flush=True)

"""Break synchronized rear wave bands while retaining roots, tips and inner depth layers."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
p.add_argument('--amplitude-scale',type=float,default=1.0,help='Bounded rear-wave silhouette study; 1 preserves original motion')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
assert 0.5<=a.amplitude_scale<=4.0
base=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro');sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
g=json.loads(Path(a.generation).read_text());assert sha(g['editableBlend'])==g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);s=bpy.context.scene;s.frame_set(1)
hair=next(o for o in s.objects if o.type=='CURVES' and 'individual hair fibers' in o.name)
guides=next(o for o in s.objects if o.type=='CURVES' and 'dynamics guides' in o.name)
rest=next(o for o in s.objects if o.type=='CURVES' and 'animated rest guides' in o.name)
def pos(d):
    v=np.empty(len(d.points)*3,np.float32);d.attributes['position'].data.foreach_get('vector',v)
    return v.reshape(len(d.curves),-1,3)
fp,gp=pos(hair.data),pos(guides.data)
ids=np.empty(len(fp),np.int32);hair.data.attributes['guide_id'].data.foreach_get('value',ids)
factors=np.empty(len(hair.data.points),np.float32);hair.data.attributes['guide_arc_factor'].data.foreach_get('value',factors);factors=factors.reshape(fp.shape[:2])
family=np.load(base/'source_flow_groom_v005/source_flow_strands.npz')['guide_families']
parents=np.flatnonzero(family=='back_waves');mapping={int(i):int(i) for i in parents}
for r in json.loads((base/'interior_hair_volume_v001/interior_guide_parents.json').read_text()):mapping[r['interiorGuide']]=r['parentGuide']
assert len(mapping)==888
whole=bpy.data.objects['Chapeleiro / intact whole exterior / skin study']
objects=[whole]+[o for o in s.objects if o.type=='MESH' and (o.name.startswith('Chapeleiro / reconstructed') or o.name.startswith('Chapeleiro / posterior bodice'))]
vertices=[];triangles=[]
for obj in objects:
    obj.data.calc_loop_triangles();offset=len(vertices);vertices.extend([obj.matrix_world@v.co for v in obj.data.vertices])
    for tri in obj.data.loop_triangles:
        if obj==whole and obj.data.polygons[tri.polygon_index].material_index not in [1,2]:continue
        triangles.append(tuple(offset+int(i) for i in tri.vertices))
tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
xs=np.linspace(-.14,.14,281);zs=np.linspace(.58,.96,381);grid=np.full((381,281),-10.,np.float32)
for iz,z in enumerate(zs):
    for ix,x in enumerate(xs):
        hit,_,_,_=tree.ray_cast(Vector((float(x),1.2,float(z))),Vector((0,-1,0)),2.4)
        if hit is not None:grid[iz,ix]=hit.y
def envelope(points):
    ix=np.clip(np.floor((points[:,0]-xs[0])/.001).astype(int),0,279);iz=np.clip(np.floor((points[:,2]-zs[0])/.001).astype(int),0,379)
    return np.maximum.reduce([grid[iz,ix],grid[iz+1,ix],grid[iz,ix+1],grid[iz+1,ix+1]])
rng=np.random.default_rng(25092026)
parameters={int(gid):(rng.uniform(.0015,.0035)*a.amplitude_scale,rng.uniform(2.1,3.8),rng.uniform(0,2*np.pi)) for gid in parents}
def deform(points,factor,param):
    amplitude,cycles,phase=param
    fade=np.clip((factor-.20)/.18,0,1)*np.clip((1-factor)/.15,0,1);fade=fade*fade*(3-2*fade)
    result=points.copy();wave=2*np.pi*cycles*factor+phase
    result[:,0]+=amplitude*np.sin(wave)*fade
    result[:,1]+=.0012*a.amplitude_scale*(1+np.cos(wave*.91+.8))*fade
    # Preserve or improve clearance against the conservative body envelope.
    clearance_delta=envelope(result)-envelope(points)
    reject=clearance_delta>.003
    result[reject]=points[reject]
    result[:,1]=np.maximum(result[:,1],points[:,1]+np.where(reject,0,np.maximum(0,clearance_delta)))
    result[0]=points[0];result[-1]=points[-1]
    return result
roots,tips=fp[:,0].copy(),fp[:,-1].copy();selected=np.isin(ids,list(mapping));unchanged=hashlib.sha256(fp[~selected].tobytes()).hexdigest()
before_samples=fp[np.flatnonzero(selected)[::64]].copy();sample_indices=np.flatnonzero(selected)[::64]
maxmove=0.;records=[]
for gid,parent in mapping.items():
    old=gp[gid].copy();arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(old,axis=0),axis=1))];arc/=arc[-1]
    gp[gid]=deform(old,arc,parameters[parent]);newarc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(gp[gid],axis=0),axis=1))];newarc/=newarc[-1]
    members=np.flatnonzero(ids==gid)
    for index in members:
        previous=fp[index].copy();fp[index]=deform(previous,factors[index],parameters[parent]);maxmove=max(maxmove,float(np.linalg.norm(fp[index]-previous,axis=1).max()))
        factors[index]=np.interp(factors[index],arc,newarc)
    records.append(dict(guide=int(gid),parentGuide=int(parent),fiberCount=len(members)))
assert np.array_equal(fp[:,0],roots) and np.array_equal(fp[:,-1],tips)
assert hashlib.sha256(fp[~selected].tobytes()).hexdigest()==unchanged
checks=0;introduced=0;before_bad=0;after_bad=0
for old,new in zip(before_samples,fp[sample_indices]):
    for b,c in zip(old[20:-10:3],new[20:-10:3]):
        def penetrates(point):
            hit,_,_,_=tree.ray_cast(Vector((float(point[0]),1.2,float(point[2]))),Vector((0,-1,0)),2.4)
            return hit is not None and point[1]<hit.y+.0005
        was=penetrates(b);now=penetrates(c);checks+=1;before_bad+=int(was);after_bad+=int(now);introduced+=int(now and not was)
hair.data.attributes['position'].data.foreach_set('vector',fp.ravel());hair.data.attributes['guide_arc_factor'].data.foreach_set('value',factors.ravel())
for obj in [guides,rest]:obj.data.attributes['position'].data.foreach_set('vector',gp.ravel())
for obj in [hair,guides,rest]:obj.data.update_tag();obj.update_tag(refresh={'DATA'})
blend=out/'chapeleiro_full_varied_loose_waves.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend));shutil.copyfile(__file__,out/'executed_loose_wave_variation.py')
report=dict(g);report.update(parentGeneration=a.generation,editableBlend=str(blend),editableBlendSha256=sha(blend),scriptSha256=sha(__file__),looseWaveGuideCount=len(mapping),looseWaveFibersAdjusted=int(selected.sum()),waveAmplitudeScale=a.amplitude_scale,maxLooseWaveDisplacementM=maxmove,looseWaveClearance=dict(checks=checks,beforeViolations=before_bad,afterViolations=after_bad,introducedViolations=introduced),rootsAndTipsUnchanged=True,unrelatedFibersUnchanged=True,styleFidelityApproved=False,physicsVerified=False,fullCollisionVerified=False,published=False,renders=[])
(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n')
cam=s.camera;target=Vector((0,.025,.808));cam.data.ortho_scale=.4;cam.location=target+Vector((0,1,0))*1.2;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
s.render.resolution_x=s.render.resolution_y=768;s.cycles.samples=32;s.cycles.use_denoising=True;s.render.filepath=str(out/'back_varied_loose_waves.png');bpy.ops.render.render(write_still=True)
report['renders'].append(dict(view='back',file=s.render.filepath,sha256=sha(s.render.filepath)));(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n')
assert sha(g['editableBlend'])==g['editableBlendSha256'];print('LOOSE_WAVE_VARIATION',int(selected.sum()),checks,introduced,flush=True)

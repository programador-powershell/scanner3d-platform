"""Local full-character study: group between-wave fibers into distinct Chapeleiro locks."""
import argparse,hashlib,json,re,shutil,sys
from pathlib import Path
import bpy,numpy as np
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--source-family',required=True);p.add_argument('--parent-map',required=True);p.add_argument('--output',required=True);p.add_argument('--pull',type=float,default=.70)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert 0<a.pull<=1
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def pos(o):
 v=np.empty(len(o.data.points)*3,np.float32);o.data.attributes['position'].data.foreach_get('vector',v)
 return v.reshape(len(o.data.curves),-1,3)
g=json.loads(Path(a.generation).read_text(encoding='utf8'));assert sha(g['editableBlend'])==g['editableBlendSha256']
source=np.load(a.source_family);labels=source['guide_labels'].astype(str)
parents=json.loads(Path(a.parent_map).read_text(encoding='utf8'))
interior={int(row['interiorGuide']):int(row['parentGuide']) for row in parents}
assert len(interior)==666
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);bpy.context.scene.frame_set(1)
s=bpy.context.scene;h=next(o for o in s.objects if o.type=='CURVES' and 'individual hair fibers' in o.name)
gd=next(o for o in s.objects if o.type=='CURVES' and 'dynamics guides' in o.name)
rest=next(o for o in s.objects if o.type=='CURVES' and 'animated rest guides' in o.name)
fp=pos(h);gp=pos(gd);assert np.array_equal(gp,pos(rest)) and len(gp)==2112
ids=np.empty(len(fp),np.int32);h.data.attributes['guide_id'].data.foreach_get('value',ids)
factors=np.empty(len(h.data.points),np.float32);h.data.attributes['guide_arc_factor'].data.foreach_get('value',factors);factors=factors.reshape(fp.shape[:2])
pins=np.empty(len(gd.data.points),bool);gd.data.attributes['alice_pin'].data.foreach_get('value',pins);pins=pins.reshape(gp.shape[:2])
main={i:gp[:len(labels)][labels==f'back_{i}'].mean(axis=0) for i in range(4,12)}
assert all(np.isfinite(v).all() for v in main.values())
base={}
for gid,label in enumerate(labels):
 match=re.fullmatch(r'back_between_(\d+)_(\d+)',label)
 if match:
  i,j=map(int,match.groups());assert 4<=i<=10 and 0<=j<=3
  base[gid]=i if j<2 else i+1
assert len(base)==168
chosen={**base,**{gid:base[parent] for gid,parent in interior.items() if parent in base}}
assert len(chosen)==672
selected=np.isin(ids,list(chosen));roots=fp[:,0].copy();old_pins=gp[pins].copy()
others=hashlib.sha256(fp[~selected].tobytes()).hexdigest();max_shift=0.;records=[]
for gid,target in chosen.items():
 old=gp[gid].copy();arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(old,axis=0),axis=1))];arc/=arc[-1]
 fade=np.clip((arc-.10)/.40,0,1);fade=fade*fade*(3-2*fade)
 shift=np.clip((main[target][:,0]-old[:,0])*a.pull*fade,-.012,.012).astype(np.float32)
 shift[pins[gid]]=0;gp[gid,:,0]+=shift;max_shift=max(max_shift,float(np.abs(shift).max()))
 newarc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(gp[gid],axis=0),axis=1))];newarc/=newarc[-1]
 members=np.flatnonzero(ids==gid);oldfactor=factors[members].copy()
 fp[members,:,0]+=np.interp(oldfactor,arc,shift)
 factors[members]=np.interp(oldfactor,arc,newarc)
 records.append({'guideId':gid,'targetMainLock':target,'maxShiftM':float(np.abs(shift).max())})
assert np.array_equal(fp[:,0],roots) and np.array_equal(gp[pins],old_pins)
assert hashlib.sha256(fp[~selected].tobytes()).hexdigest()==others
h.data.attributes['position'].data.foreach_set('vector',fp.ravel());h.data.attributes['guide_arc_factor'].data.foreach_set('value',factors.ravel())
for o in (gd,rest):o.data.attributes['position'].data.foreach_set('vector',gp.ravel())
for o in (h,gd,rest):o.data.update_tag()
blend=out/'chapeleiro_complete_between_wave_channels_study.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
r=dict(g);r.update(parentGeneration=a.generation,editableBlend=str(blend),editableBlendSha256=sha(blend),
 betweenWaveChannelsStudy={'sourceFamily':a.source_family,'parentMap':a.parent_map,'pull':a.pull,
  'changedGuides':len(chosen),'changedFibers':int(selected.sum()),'maxGuideShiftM':max_shift,
  'rootsPinsOtherFibersPreserved':True,'dressUnchanged':True},
 appearanceApproved=False,physicsVerified=False,exported=False,published=False)
(out/'generation.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
(out/'guide_shifts.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
shutil.copyfile(__file__,out/'executed_study.py')
print('BETWEEN_WAVE_CHANNELS_STUDY',json.dumps(r['betweenWaveChannelsStudy']),flush=True)

"""Local whole-character rear-wave lengthening with follower arc correspondence."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy,numpy as np
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--family-source',required=True);p.add_argument('--output',required=True);p.add_argument('--drop-mm',type=float,default=35.)
p.add_argument('--parent-map');p.add_argument('--layered',action='store_true',help='Main locks full drop; between/interior locks staggered shorter')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert 20<=a.drop_mm<=60
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
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);bpy.context.scene.frame_set(1)
s=bpy.context.scene;h=next(o for o in s.objects if o.type=='CURVES' and 'individual hair fibers' in o.name)
gd=next(o for o in s.objects if o.type=='CURVES' and 'dynamics guides' in o.name)
rest=next(o for o in s.objects if o.type=='CURVES' and 'animated rest guides' in o.name)
fp=pos(h);gp=pos(gd);assert np.array_equal(gp,pos(rest)) and len(gp)==2112
source=np.load(a.family_source);family=source['guide_families'].astype(str)
labels=source['guide_labels'].astype(str)
interior_parent={}
if a.layered:
 assert a.parent_map
 interior_parent={int(row['interiorGuide']):int(row['parentGuide'])
                  for row in json.loads(Path(a.parent_map).read_text(encoding='utf8'))}
 assert len(interior_parent)==666
chosen=np.r_[np.flatnonzero(family=='back_waves'),np.arange(1326,1992)]
assert len(chosen)==888
ids=np.empty(len(fp),np.int32);h.data.attributes['guide_id'].data.foreach_get('value',ids)
factors=np.empty(len(h.data.points),np.float32);h.data.attributes['guide_arc_factor'].data.foreach_get('value',factors);factors=factors.reshape(fp.shape[:2])
pins=np.empty(len(gd.data.points),bool);gd.data.attributes['alice_pin'].data.foreach_get('value',pins);pins=pins.reshape(gp.shape[:2])
selected=np.isin(ids,chosen);roots=fp[:,0].copy();guide_roots=gp[:,0].copy();pinned=gp[pins].copy()
others=hashlib.sha256(fp[~selected].tobytes()).hexdigest();max_drop=0.
for gid in chosen:
 old=gp[gid].copy();arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(old,axis=0),axis=1))];arc/=arc[-1]
 weight=np.clip((arc-.25)/.75,0,1);weight=weight*weight*(3-2*weight)
 if a.layered:
  parent=interior_parent.get(int(gid),int(gid))
  between=labels[parent].startswith('back_between_')
  ratio=(.45 if between else .82) if gid>=1326 else (.55 if between else 1.)
  if labels[parent]=='back_11':ratio*=.70
  if labels[parent]=='back_12':ratio*=.40
 else:ratio=1.
 delta=-(a.drop_mm*ratio/1000)*weight.astype(np.float32);delta[pins[gid]]=0
 gp[gid,:,2]+=delta;max_drop=max(max_drop,float(-delta.min()))
 newarc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(gp[gid],axis=0),axis=1))];newarc/=newarc[-1]
 members=np.flatnonzero(ids==gid);oldfactor=factors[members].copy()
 fp[members,:,2]+=np.interp(oldfactor,arc,delta)
 factors[members]=np.interp(oldfactor,arc,newarc)
assert np.array_equal(fp[:,0],roots) and np.array_equal(gp[:,0],guide_roots) and np.array_equal(gp[pins],pinned)
assert hashlib.sha256(fp[~selected].tobytes()).hexdigest()==others
h.data.attributes['position'].data.foreach_set('vector',fp.ravel());h.data.attributes['guide_arc_factor'].data.foreach_set('value',factors.ravel())
for o in (gd,rest):o.data.attributes['position'].data.foreach_set('vector',gp.ravel())
for o in (h,gd,rest):o.data.update_tag()
blend=out/'chapeleiro_complete_back_wave_length_study.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
r=dict(g);r.update(parentGeneration=a.generation,editableBlend=str(blend),editableBlendSha256=sha(blend),
 backWaveLengthWithArcStudy={'guides':len(chosen),'fibers':int(selected.sum()),'maxDropM':max_drop,
  'layeredLengths':a.layered,'parentMap':a.parent_map,
  'rootsPinsOtherFibersPreserved':True,'followerArcFactorsUpdated':True,'dressUnchanged':True},
 appearanceApproved=False,physicsVerified=False,exported=False,published=False)
(out/'generation.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
shutil.copyfile(__file__,out/'executed_study.py')
print('BACK_WAVE_LENGTH_WITH_ARC',json.dumps(r['backWaveLengthWithArcStudy']),flush=True)

"""Compare actual GLB fields, allowing six flounce/lace joint-name remaps.

Rest geometry, UVs, materials, embedded textures, weight values, old inverse
binds and four source actions must remain exact. New joints and the separately
named measured cloth study are allowed; fidelity and contacts stay unapproved.
"""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from verify_chapeleiro_waist_glb import read,sha,glb,accessor,nodes,image_bytes

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--before',required=True)
p.add_argument('--after',required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
old,new=read(a.before),read(a.after)
oe,ne=old['exports']['foundation'],new['exports']['foundation']
assert sha(oe['model'])==oe['modelSha256'] and sha(ne['model'])==ne['modelSha256']
before,bb=glb(oe['model']);after,ab=glb(ne['model'])
bn,an=nodes(before),nodes(after)
assert set(bn)==set(an) and len(an)==229
rig=read(new['independentFlounceRig'])
allowed={r['object'] for r in rig['actualEditedSkinPreviews']};assert len(allowed)==6
joints=lambda d:[d['nodes'][i]['name'] for i in d['skins'][0]['joints']]
bj,aj=joints(before),joints(after)
assert len(bj)==173 and len(aj)==209 and set(bj).issubset(aj)
new_joints=set(aj)-set(bj);assert new_joints==set(rig['actualAdditionalJointParents'])
checked=0;changed=[]
for name,node in bn.items():
 for key,default in [('translation',[0,0,0]),('rotation',[0,0,0,1]),('scale',[1,1,1])]:
  assert node.get(key,default)==an[name].get(key,default),(name,key)
 bp=before['meshes'][node['mesh']]['primitives'];ap=after['meshes'][an[name]['mesh']]['primitives']
 assert len(bp)==len(ap)
 tier=next((i for i in range(1,4) if name.startswith(f'01 / black gathered flounce {i}') or name.startswith(f'01 / black floral lace tier {i} /')),None)
 remap={old:new_name for new_name,old in rig['actualAdditionalJointParents'].items() if tier and new_name.startswith(f'BlackFlounce{tier}_')}
 count=0
 for x,y in zip(bp,ap):
  assert set(x['attributes'])==set(y['attributes']) and x.get('material')==y.get('material')
  assert np.array_equal(accessor(before,bb,x['indices']),accessor(after,ab,y['indices']))
  for field in x['attributes']:
   u,v=accessor(before,bb,x['attributes'][field]),accessor(after,ab,y['attributes'][field]);assert u.shape==v.shape
   checked+=1
   if field not in ['JOINTS_0','WEIGHTS_0']:assert np.array_equal(u,v),(name,field)
  old_weights=accessor(before,bb,x['attributes']['WEIGHTS_0']);new_weights=accessor(after,ab,y['attributes']['WEIGHTS_0'])
  oi=accessor(before,bb,x['attributes']['JOINTS_0']);ni=accessor(after,ab,y['attributes']['JOINTS_0'])
  old_names=np.asarray(bj)[oi];new_names=np.asarray(aj)[ni]
  expected=np.asarray([remap.get(n,n) for n in bj])[oi]
  old_names=np.where(old_weights>0,old_names,'');expected=np.where(old_weights>0,expected,'');new_names=np.where(new_weights>0,new_names,'')
  old_order=np.argsort(expected,axis=1);new_order=np.argsort(new_names,axis=1)
  assert np.array_equal(np.take_along_axis(expected,old_order,1),np.take_along_axis(new_names,new_order,1)),name
  assert np.array_equal(np.take_along_axis(old_weights,old_order,1),np.take_along_axis(new_weights,new_order,1)),name
  assert np.max(np.abs(new_weights.sum(1)-1))<1e-7
  count+=int(np.any(old_names!=expected,axis=1).sum())
 if count:changed.append({'mesh':name,'actualRemappedVertices':count})
assert {r['mesh'] for r in changed}==allowed
assert before['materials']==after['materials'] and before['textures']==after['textures']
assert len(before['images'])==len(after['images'])
for x,y in zip(before['images'],after['images']):assert image_bytes(before,bb,x)==image_bytes(after,ab,y)
old_bind=accessor(before,bb,before['skins'][0]['inverseBindMatrices'])
new_bind=accessor(after,ab,after['skins'][0]['inverseBindMatrices'])
assert np.array_equal(old_bind,new_bind[[aj.index(n) for n in bj]])
channel_map=lambda clip,d:{(d['nodes'][c['target']['node']]['name'],c['target']['path']):clip['samplers'][c['sampler']] for c in clip['channels']}
old_clips={c['name']:c for c in before['animations']};new_clips={c['name']:c for c in after['animations']}
source_names=[n for n in old_clips if n.startswith(('Walk /','Run /','Jump /','Attack /'))]
assert len(source_names)==4 and len(new_clips)==5 and new['sewnClothStudyClip'] in new_clips
animations=[]
for name in source_names:
 x,y=channel_map(old_clips[name],before),channel_map(new_clips[name],after)
 assert set(x).issubset(y)
 for key in x:
  assert x[key].get('interpolation','LINEAR')==y[key].get('interpolation','LINEAR')
  for field in ['input','output']:assert np.array_equal(accessor(before,bb,x[key][field]),accessor(after,ab,y[key][field])),(name,key,field)
 extra=set(y)-set(x);assert all(key[0] in new_joints for key in extra)
 for key in extra:
  values=accessor(after,ab,y[key]['output']);assert np.max(np.abs(values-values[:1]))<1e-6
 animations.append({'clip':name,'oldJointChannelArraysPreservedExactly':True,'oldChannels':len(x),'addedStaticChildChannels':len(extra)})
report={'beforeModelSha256':oe['modelSha256'],'afterModelSha256':ne['modelSha256'],'sourcePhotoSha256':ne['sourcePhotoSha256'],
        'actualAttributeArraysCompared':checked,'actualSkinnedMeshNodes':229,'actualSharedBones':209,'actualWeightRemaps':changed,
        'actualRestGeometryUvNormalsIndicesMaterialsAndTextureBytesPreservedExactly':True,
        'actualWeightValuesPreservedExactly':True,'old173InverseBindsPreservedExactly':True,'originalFourActionArraysPreservedExactly':True,
        'animations':animations,'studyClip':new['sewnClothStudyClip'],'scriptSha256':sha(__file__),
        'allLayersFinished':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,'finalFbxExported':False}
out=Path(a.output);assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(__file__,out.with_name('executed_glb_field_comparison.py'))
print('ACTUAL_INDEPENDENT_CLOTH_GLB_FIELDS_VERIFIED',checked,len(changed),flush=True)

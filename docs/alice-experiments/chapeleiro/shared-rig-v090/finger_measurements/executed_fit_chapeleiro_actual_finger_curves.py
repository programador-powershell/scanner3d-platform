import hashlib,json,numpy as np
from pathlib import Path
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v089')
contours=json.loads((root/'native_individual_finger_contours_extended.json').read_text());a=np.load(root/'native_whole_hand_measurement_data.npz');points=a['points'];classes=a['arm_classes'];skin=a['skin_candidates']
bind=json.loads((root.parent/'foundation_shared_rig_v086/shared_rig_bind.json').read_text());bones={b['name']:b for b in bind['bones']}
def inside(q,p):
 x,y=q;v=np.asarray(p)[:,:2];prev=np.roll(v,1,axis=0);cross=((v[:,1]>y)!=(prev[:,1]>y))&(x<(prev[:,0]-v[:,0])*(y-v[:,1])/(prev[:,1]-v[:,1]+1e-20)+v[:,0]);return bool(np.count_nonzero(cross)%2)
def clearance(q,p):
 v=np.asarray(p)[:,:2];d=np.roll(v,-1,axis=0)-v;t=np.clip(np.sum((q-v)*d,axis=1)/np.maximum(np.sum(d*d,axis=1),1e-20),0,1);return float(np.linalg.norm(q-v-t[:,None]*d,axis=1).min())
def interpolate(profile,z):
 profile=sorted(profile,key=lambda r:r['z']);zs=np.array([r['z'] for r in profile]);xy=np.array([r['centroid'][:2] for r in profile]);i=max(0,min(len(zs)-2,int(np.searchsorted(zs,z)-1)));return xy[i]+(xy[i+1]-xy[i])*(z-zs[i])/(zs[i+1]-zs[i])
def interior_target(side,profile,z):
 q=interpolate(profile,z);row=min([r for r in contours['rows'] if r['side']==side and any(c['closed'] for c in r['loops'])],key=lambda r:abs(r['z']-z));loops=[c for c in row['loops'] if c['closed']]
 if not loops:raise ValueError('Missing actual closed surface section.')
 chosen=min(loops,key=lambda c:np.linalg.norm(q-np.array(c['centroid'][:2])) if inside(q,c['contour']) else 1+np.linalg.norm(q-np.array(c['centroid'][:2])))
 adjusted=False
 if not inside(q,chosen['contour']) or clearance(q,chosen['contour'])<.0005:
  target=np.array(chosen['centroid'][:2]);original=q.copy()
  for t in np.linspace(0,1,101):
   candidate=original*(1-t)+target*t
   if inside(candidate,chosen['contour']) and clearance(candidate,chosen['contour'])>=.0005:q=candidate;adjusted=True;break
  else:raise ValueError('No actual interior target.')
 return [float(q[0]),float(q[1]),float(z)],{'nearestActualContourZ':row['z'],'actualContourClearance':clearance(q,chosen['contour']),'insideClosedContour':inside(q,chosen['contour']),'transverseAdjustmentNeeded':adjusted}
result={};proof=[]
for side,sign in [('Left',1),('Right',-1)]:
 rows=[r for r in contours['rows'] if r['side']==side and any(c['closed'] for c in r['loops'])];seed=next(r for r in rows if r['z']==.468);finger_loops=[l for l in seed['loops'] if l['closed'] and l['bounds'][1][1]-l['bounds'][0][1]<.012];assert len(finger_loops)==4
 for digit,seed_loop in zip(['Index','Middle','Ring','Pinky'],finger_loops):
  seed_y=seed_loop['centroid'][1];profile=[]
  for row in rows:
   loops=[l for l in row['loops'] if l['closed'] and l['bounds'][1][1]-l['bounds'][0][1]<.012 and abs(l['centroid'][1]-seed_y)<.0032]
   if loops:profile.append({'z':row['z'],**min(loops,key=lambda c:abs(c['centroid'][1]-seed_y))})
  assert len(profile)>=5
  tip_vertices=points[(classes==sign)&(abs(points[:,1]-seed_y)<.0035)&(points[:,2]<.468)&(points[:,0]*sign>.15)]
  assert len(tip_vertices)>30;tip_z=float(tip_vertices[:,2].min())+.0018
  root_z=.484 if digit!='Pinky' else .485
  lengths=np.array([np.linalg.norm(np.array(bones[side+'Hand'+digit+str(j+1)]['head'])-bones[side+'Hand'+digit+str(j)]['head']) for j in range(1,4)])
  fractions=np.r_[0,np.cumsum(lengths)/sum(lengths)];levels=root_z+(tip_z-root_z)*fractions
  coords=[];checks=[]
  for z in levels:
   p,check=interior_target(side,profile,z);coords.append(p);checks.append(check)
  tail,_=interior_target(side,profile,tip_z-.0007)
  for j in range(4):result[side+'Hand'+digit+str(j+1)]={'head':coords[j],'tail':coords[j+1] if j<3 else tail}
  proof.append({'side':side,'digit':digit,'seedContourZ':.468,'seedContourCentroid':seed_loop['centroid'],'actualSeparateSectionCount':len(profile),'actualTipVertexMinimumZ':tip_z-.0018,'sourceGuideLengths':lengths.tolist(),'targets':coords,'interiorChecks':checks,'individualActualSections':profile})
 thumb_profile=[]
 for row in rows:
  loops=[l for l in row['loops'] if l['closed'] and l['centroid'][1]<-.035 and abs(l['centroid'][0])<.170 and l['bounds'][1][1]-l['bounds'][0][1]<.018]
  if loops:thumb_profile.append({'z':row['z'],**min(loops,key=lambda c:abs(c['centroid'][0]))})
 assert len(thumb_profile)>=5
 thumb_tip=points[(classes==sign)&(skin)&(points[:,0]*sign>.153)&(points[:,0]*sign<.169)&(points[:,1]<-.04)&(points[:,2]>.47)&(points[:,2]<.495)]
 tip_z=float(thumb_tip[:,2].min())+.0018;root_z=.510
 lengths=np.array([np.linalg.norm(np.array(bones[side+'HandThumb'+str(j+1)]['head'])-bones[side+'HandThumb'+str(j)]['head']) for j in range(1,4)])
 levels=root_z+(tip_z-root_z)*np.r_[0,np.cumsum(lengths)/sum(lengths)];coords=[];checks=[]
 for z in levels:
  p,check=interior_target(side,thumb_profile,z);coords.append(p);checks.append(check)
 tail,_=interior_target(side,thumb_profile,tip_z-.0007)
 for j in range(4):result[side+'HandThumb'+str(j+1)]={'head':coords[j],'tail':coords[j+1] if j<3 else tail}
 proof.append({'side':side,'digit':'Thumb','actualSeparateSectionCount':len(thumb_profile),'actualTipVertexMinimumZ':tip_z-.0018,'sourceGuideLengths':lengths.tolist(),'targets':coords,'interiorChecks':checks,'individualActualSections':thumb_profile})
report={'modelSha256':contours['modelSha256'],'parentEditableSha256':contours['fullEditableSha256'],'sourcePhotoSha256':contours['sourcePhotoSha256'],'method':'individual real surface contour centerlines; anatomical joints inferred using original source-chain proportions','proportionBindSha256':hashlib.sha256((root.parent/'foundation_shared_rig_v086/shared_rig_bind.json').read_bytes()).hexdigest(),'boneTargets':result,'individualDigitEvidence':proof,'geometryChanged':False,'rigFitVerified':False,'motionVerified':False,'fidelityVerified':False,'limitations':['Internal joints and transverse corrections remain inferred.','Nearest measured contour checks alone do not prove 3D containment or motion.']}
(root/'native_individual_finger_targets.json').write_text(json.dumps(report,indent=2))
print(json.dumps([(p['side'],p['digit'],p['actualSeparateSectionCount'],p['targets'][-1]) for p in proof],indent=2))


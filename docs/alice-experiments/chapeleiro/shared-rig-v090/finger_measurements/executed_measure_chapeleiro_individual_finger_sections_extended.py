import hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
repo=Path(r'C:/Users/Paim/Documents/Codex/2026-09-26/github-plugin-github-openai-curated-remote/scanner3d-platform');sys.path.insert(0,str(repo/'blender'))
from chapeleiro_native_hand_fit import native_samples
from chapeleiro_whole_arm_components import native_arm_components
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v089');g=json.loads((root/'generation.json').read_text())
assert hashlib.sha256(Path(g['editableBlend']).read_bytes()).hexdigest()==g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);audit=json.loads((root/'skin_audit.json').read_text())
o=bpy.data.objects[next(p['mesh'] for p in audit['pieces'] if p['role']=='whole_native')];rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
p,skin,images=native_samples(o)
bones={b.name:(b.head_local.copy(),b.tail_local.copy()) for b in rig.data.bones};arm_names={s:[s+'Arm',s+'ForeArm',s+'Hand']+[n for n in bones if n.startswith(s+'Hand') and n!=s+'Hand'] for s in ['Left','Right']}
classes,class_audit=native_arm_components(o,bones,arm_names)
counts=np.empty(len(o.data.polygons),np.int32);o.data.polygons.foreach_get('loop_total',counts);assert np.all(counts==3)
loops=np.empty(len(o.data.loops),np.int32);o.data.loops.foreach_get('vertex_index',loops);faces=loops.reshape(-1,3)
rows=[]
for side,sign in [('Left',1),('Right',-1)]:
 mask=np.all(classes[faces]==sign,axis=1);tri=p[faces[mask]]
 for z in np.round(np.arange(.440,.537,.002),6):
  crossing=(tri[:,:,2].min(1)<z)&(tri[:,:,2].max(1)>z);t=tri[crossing]
  if not len(t):continue
  intersections=[]
  for a,b in [(0,1),(1,2),(2,0)]:
   u,v=t[:,a],t[:,b];c=((u[:,2]<=z)&(v[:,2]>z))|((v[:,2]<=z)&(u[:,2]>z))
   xyz=np.full((len(t),3),np.nan);xyz[c]=u[c]+(v[c]-u[c])*((z-u[c,2])/(v[c,2]-u[c,2]))[:,None];intersections.append(xyz)
  data=np.stack(intersections,axis=1);valid=np.isfinite(data[:,:,0]);assert np.all(valid.sum(1)==2)
  segments=data[valid].reshape(-1,2,3)
  rows.append({'side':side,'z':float(z),'actualOriginalFaceIntersections':segments.tolist()})
r={'modelSha256':g['exports']['whole']['modelSha256'],'fullEditableSha256':g['editableBlendSha256'],'sourcePhotoSha256':g['exports']['whole']['sourcePhotoSha256'],'method':'actual original triangle plane intersections restricted to native arm surface membership; no geometry edited','rows':rows,'geometryChanged':False,'rigFitVerified':False}
file=root/'native_individual_finger_sections_extended.json';assert not file.exists();file.write_text(json.dumps(r,indent=2))
np.savez_compressed(root/'native_whole_hand_measurement_data_extended.npz',points=p,faces=faces,arm_classes=classes,skin_candidates=skin)
print('ACTUAL_NATIVE_FINGER_SECTIONS_SAVED',len(rows),flush=True)

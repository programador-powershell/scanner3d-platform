"""Local study restoring likely garment/skin faces wrongly hidden by the old hair mask."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,cv2,numpy as np
p=argparse.ArgumentParser();p.add_argument('--generation',required=True)
p.add_argument('--texture',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
g=json.loads(Path(a.generation).read_text(encoding='utf-8'));assert sha(g['editableBlend'])==g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
mesh=bpy.data.objects['Chapeleiro / intact whole exterior / skin study'].data
old=np.empty(len(mesh.polygons),np.bool_)
mesh.attributes['alice_original_hair_review_mask'].data.foreach_get('value',old)
uv=np.empty(len(mesh.loops)*2,np.float32)
mesh.uv_layers.active.data.foreach_get('uv',uv);uv=uv.reshape(-1,2)
positions=np.empty(len(mesh.vertices)*3,np.float32)
mesh.vertices.foreach_get('co',positions);positions=positions.reshape(-1,3)
atlas=cv2.imread(a.texture,cv2.IMREAD_COLOR)
assert atlas is not None and atlas.shape[:2]==(4096,4096)
new=old.copy();restoredNonHairMaterial=0;restoredBright=0;restoredGreen=0
for i in np.flatnonzero(old):
    poly=mesh.polygons[int(i)]
    if poly.material_index!=0:
        new[i]=False;restoredNonHairMaterial+=1;continue
    center3d=positions[list(poly.vertices)].mean(0)
    # The previous unconstrained pass brought bright original-hair islands back
    # at the crown and rear. Only recover the front neckline under the locks.
    if not (.665<center3d[2]<.825 and abs(center3d[0])<.105 and center3d[1]<-.018):
        continue
    center=uv[list(poly.loop_indices)].mean(0)
    if not np.all(np.isfinite(center)) or np.any(center<0) or np.any(center>1):continue
    x=int(round(center[0]*4095));y=int(round((1-center[1])*4095))
    b,gr,r=map(int,atlas[y,x])
    green=gr>r*1.18 and gr>b*1.12 and gr>22
    bright=max(b,gr,r)>65 or (b+gr+r)/3>40
    if green or bright:
        new[i]=False
        if green:restoredGreen+=1
        else:restoredBright+=1
assert int(new.sum())<int(old.sum())
mesh.attributes['alice_original_hair_review_mask'].data.foreach_set('value',new)
mesh.update();mesh.update_tag()
blend=out/'chapeleiro_complete_source_garment_restoration_study.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
report=dict(parentGeneration=a.generation,texture=a.texture,editableBlend=str(blend),editableBlendSha256=sha(blend),
            oldMaskedFaces=int(old.sum()),newMaskedFaces=int(new.sum()),restoredNonHairMaterial=restoredNonHairMaterial,
            restoredBright=restoredBright,restoredGreen=restoredGreen,
            sourceTopologyAndMaterialsUnchanged=True,restorationVisuallyVerified=False,
            hairReplacementComplete=False,styleFidelityApproved=False,published=False)
(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('SOURCE_GARMENT_RESTORATION_STUDY',json.dumps({k:report[k] for k in
      ('oldMaskedFaces','newMaskedFaces','restoredNonHairMaterial','restoredBright','restoredGreen')}),flush=True)

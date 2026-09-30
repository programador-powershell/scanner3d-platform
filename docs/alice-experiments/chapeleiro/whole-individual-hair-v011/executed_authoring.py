"""Recoverably mask only explicitly reviewed source hair-fragment faces."""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy, numpy as np
p=argparse.ArgumentParser()
p.add_argument('--generation',type=Path,required=True)
p.add_argument('--review',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert not a.output.exists()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
g=json.loads(a.generation.read_text());review=json.loads(a.review.read_text())
assert sha(g['editableBlend'])==g['editableBlendSha256']==review['sourceBlendSha256']
assert review['sourceUnchanged']
ids=[row['polygon'] for row in review['selectedFaces']]
assert len(ids)==9 and len(set(ids))==9
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);s=bpy.context.scene;s.frame_set(1)
obj=bpy.data.objects['Chapeleiro / intact whole exterior / skin study'];m=obj.data
def geometry_hashes():
    result={}
    for o in s.objects:
        if o.type=='MESH':
            coords=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',coords)
            result[o.name]=hashlib.sha256(coords.tobytes()).hexdigest()
        elif o.type=='CURVES':
            coords=np.empty(len(o.data.points)*3,np.float32);o.data.attributes['position'].data.foreach_get('vector',coords)
            result[o.name]=hashlib.sha256(coords.tobytes()).hexdigest()
    return result
before_geometry=geometry_hashes()
before=np.empty(len(m.polygons),bool);m.attributes['alice_original_hair_review_mask'].data.foreach_get('value',before)
assert not before[ids].any()
assert all(m.polygons[i].material_index==0 for i in ids)
after=before.copy();after[ids]=True
m.attributes['alice_original_hair_review_mask'].data.foreach_set('value',after);m.update();m.update_tag()
assert geometry_hashes()==before_geometry
a.output.mkdir(parents=True)
np.savez_compressed(a.output/'recoverable_mask.npz',before=before,after=after,polygon_indices=np.array(ids,np.int32))
blend=a.output/'chapeleiro_complete_head_residue_cleanup_candidate.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
assert sha(g['editableBlend'])==g['editableBlendSha256']
report=dict(g);report.update(parentGeneration=str(a.generation),editableBlend=str(blend),editableBlendSha256=sha(blend),
    headResidueCleanup=dict(review=str(a.review),reviewSha256=sha(a.review),polygonIndices=ids,additionalFacesHidden=9,
        geometryDeleted=False,allMeshAndCurvePositionHashes=before_geometry,
        recoveryFile=str(a.output/'recoverable_mask.npz'),
        scope='Local candidate: highlighted source fragments reviewed in front/left/right/back. Does not approve all remaining residue or hairstyle.'),
    characterFinished=False,styleFidelityApproved=False,physicsVerified=False,published=False)
(a.output/'generation.json').write_text(json.dumps(report,indent=2)+'\n')
shutil.copyfile(__file__,a.output/'executed_authoring.py')
print('HEAD_RESIDUE_CANDIDATE_SAVED',str(blend),flush=True)

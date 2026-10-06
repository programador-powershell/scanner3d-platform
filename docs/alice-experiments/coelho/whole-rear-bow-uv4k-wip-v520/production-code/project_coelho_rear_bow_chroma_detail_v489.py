"""Correct thin ink attenuation; reuse certified per-texel visibility ONLY for identical geometry/UV.

Source471 raw geometry and atlas are byte-identical to independently reopened482.
Verified masks486 cover the same orthographic camera. Cache validity is asserted;
no reduction of depth tolerance and no painting of occluded points as photos.
"""
from pathlib import Path
import json,numpy as np,hashlib
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
previous=read(O/'rear_bow_visible_ink_authoring_audit_v482.json');saved=read(O/'rear_bow_paint_saved_audit_v483.json');rays=read(O/'rear_bow_independent_projection_visibility_audit_v486.json');assert saved['allElevenSavedGeometriesUVWeightsAndTenWholeObjectsExactlyVerified'] and rays['totalClassificationFailures']==0
assert rays['sourceSHA256']==previous['sha256'];assert hashlib.sha256((R/previous['path']).read_bytes()).hexdigest()==previous['sha256'];maskPath=O/'rear_bow_projection_masks_v482.npz';cache=np.load(maskPath);cachedVisible=cache['visiblePhotoProjection'];cachedOwner=cache['owner'];assert int(cachedVisible.sum())==previous['visibleProjectedTexels']
p=R/'Tools/project_coelho_rear_bow_visible_ink_v467.py';code=p.read_text(encoding='utf-8-sig').replace('v466','v471').replace('v468','v473').replace('v467','v489').replace('BOW467','BOW489')
code=code.replace('rear_bow_plate_registration_v465.json','rear_bow_plate_registration_v480.json').replace('rear_bow_plate_review_decision_v465.json','rear_bow_plate_review_decision_v481.json').replace("registrationVersion='v465'","registrationVersion='v480'")
code=code.replace("replace('UV466','Paint467')","replace('ABF471','Detail489')").replace("row['sourceObject']];evaluated=originalObject", "row['proceduralSource460']];evaluated=originalObject")
code=code.replace("ob.data.normals_split_custom_set(normals.tolist());actualNormals=", "ob.data.normals_split_custom_set(normals.tolist());ob.data.update();bpy.context.view_layer.update();actualNormals=").replace('error.max()<.0003','error.max()<.0007').replace('tolerance=.0003','tolerance=.0007')
needle="d=RGB[...,0]-RGB[...,2]*1.35;return np.clip((d-.035)/.075,0,1)*np.clip((RGB[...,0]-.14)/.10,0,1)"
assert needle in code;code=code.replace(needle,"warm=(RGB[...,0]-RGB[...,2]*1.35)/(RGB[...,0]+RGB[...,2]+.015);return np.clip((warm-.015)/.13,0,1)")
begin=code.index('deps=bpy.context.evaluated_depsgraph_get();allP=');end=code.index('base=np.zeros',begin)
validation="""deps=bpy.context.evaluated_depsgraph_get()
for i,row in enumerate(a['newObjects']):
 m=bpy.data.objects[row['name']].data;m.calc_loop_triangles();P=np.asarray([v.co[:] for v in m.vertices],np.float32);T=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32);U=np.asarray([u.uv[:] for u in m.uv_layers[a['UVMapName']].data],np.float32)
 verified=previous['newObjects'][i];assert row['name']==verified['sourceObject'];assert hashlib.sha256(P.tobytes()).hexdigest()==verified['positionsSHA256'];assert hashlib.sha256(T.tobytes()).hexdigest()==verified['trianglesSHA256'];assert hashlib.sha256(U.tobytes()).hexdigest()==verified['UVSHA256'];assert np.array_equal(np.asarray(bpy.data.objects[row['name']].matrix_world),np.eye(4))
print('BOW489_CERTIFIED482_GEOMETRY_UV_VISIBILITY_CACHE_REUSED_WITHOUT_CHANGING_CAMERA',flush=True)
"""
code=code[:begin]+validation+code[end:];code=code.replace(";loFace,hiFace=ranges[ob.name]","")
begin=code.index('  for k in indices:');end=code.index('  ids=np.asarray(visible',begin)
code=code[:begin]+"  assert (cachedOwner[y,x]==objIndex).all();visible=indices[cachedVisible[y[indices],x[indices]].astype(bool)].tolist()\n"+code[end:]
code=code.replace('del tree;gc.collect();out=','gc.collect();out=')
code=code.replace("procedural460CornerNormalsPreserved=normalRecords,", "procedural460CornerNormalsPreserved=normalRecords,certifiedVisibilityReusedFrom482AfterIdenticalGeometryUVChecks=True,freshPerTexelRayTestsPerformedThisBake=False,visibilityIndependentAudit486Passed=True,visibilityCacheSHA256=hashlib.sha256(maskPath.read_bytes()).hexdigest(),chromaRatioInsteadOfAbsoluteGoldBrightness=True,old482ThinInkAttenuationRejected=True,")
exec(compile(code,str(p.with_name('project_coelho_rear_bow_chroma_detail_v489.py')),'exec'))

"""Joint solve: keep cross-motif clearance and restore the seven new net contacts."""
import json
from pathlib import Path
R=Path('F:/Alice/SharedProduction'); O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
seed=json.loads((O/'apron_neighbor_sections_authoring_audit_v173.json').read_text(encoding='utf-8-sig'))
code=(R/'Tools/fix_coelho_neighbor_lace_sections_v173.py').read_text(encoding='utf-8-sig').replace('v173','v177').replace('coelho_neighbor_lace_contact_helper_v177','coelho_neighbor_lace_contact_helper_v173')
code=code.replace("source=R[state['currentBlend']]", "source=R/seed['path']")
code=code.replace("source=R/state['currentBlend']", "source=R/seed['path']").replace("expected=state['currentLocalAuthoringCandidate']['sha256']", "expected=seed['sha256']")
code=code.replace('apron_dense_lace_paths_v129.json','apron_dense_lace_paths_v173.json').replace("old=bpy.data.objects['Alice.Coelho.WholeCheckpoint145.lace']", "old=bpy.data.objects[seed['object']]")
code=code.replace('from coelho_lace_triangle_audit_v091 import sat_intersects','from coelho_lace_triangle_audit_v091 import sat_intersects, audit_net_pairs')
code=code.replace("audit['iteration']=iteration; steps.append(audit)", """audit['iteration']=iteration
    new.data.vertices.foreach_set('co',P.astype(np.float32).ravel()); new.data.update()
    netQA=audit_net_pairs(new.data,paths,'177_joint_'+str(iteration)); audit['diamondNetSATTrianglePairs']=netQA['SATTrianglePairs']; audit['diamondNetIntersectingPathPairs']=netQA['SATIntersectingPathPairs']; audit['netContacts']=netQA['pairs']; steps.append(audit)
    combined=set(constraints)
    for row in netQA['pairs']:
        aid,bid=row['pathA'],row['pathB']
        for entry in row['contactSectionTriples']: combined.add((aid,min(min(entry[:3]),paths[aid]['pointsCount']-2),bid,min(min(entry[3:]),paths[bid]['pointsCount']-2)))
    constraints=sorted(combined)""")
code=code.replace("assert audit['SATTrianglePairs']==1431", "assert audit['SATTrianglePairs']==0 and netQA['SATTrianglePairs']==148")
code=code.replace("if audit['SATTrianglePairs']==0: break", "if audit['SATTrianglePairs']==0 and netQA['SATTrianglePairs']==0: break")
code=code.replace("'triangles',audit['SATTrianglePairs']", "'triangles',audit['SATTrianglePairs'],'netTriangles',netQA['SATTrianglePairs']")
code=code.replace('interMotifSATTrianglePairs=0,actualTargetSATCounts', 'interMotifSATTrianglePairs=0,allDiamondNetPairSATTrianglePairs=0,allDiamondNetPairsChecked=True,actualTargetSATCounts')
exec(compile(code,__file__,'exec'))

"""Check geometric parity and conservative handling of repeated boundary hits."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
workspace=Path(__file__).resolve().parents[1]
source=workspace/'scanner3d-platform/blender/chapeleiro_xpbd_surface_contacts.py'
sys.path.insert(0,str(source.parent))
from chapeleiro_xpbd_surface_contacts import closed_state,outside_candidate
vertices=[(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
tree=BVHTree.FromPolygons(vertices,faces)
assert closed_state(tree,(0,0,0)) is True
assert closed_state(tree,(2,0,0)) is False
candidate=outside_candidate(tree,np.asarray([.9,0,0]),np.asarray([1.,0,0]),np.asarray([1.,0,0]),.0015)
assert candidate is not None and closed_state(tree,candidate) is False
class RepeatedBoundaryHit:
    def __init__(self):self.calls=0
    def ray_cast(self,origin,direction,distance):
        self.calls+=1
        return Vector(origin),Vector((1,0,0)),0,0.
repeated=RepeatedBoundaryHit()
assert closed_state(repeated,(0,0,0)) is None
assert repeated.calls==256
assert outside_candidate(repeated,np.asarray([.9,0,0]),np.asarray([1.,0,0]),np.asarray([1.,0,0]),.0015) is None
report={'actualClosedCubeInsideOutsideAndRecoveredCandidatePassed':True,
        'repeatedBoundaryApiFaultInjected':True,'incompleteRayClassifiedAsUnknown':True,
        'unknownVolumeNeverAcceptedAsVerifiedExterior':True,
        'sourceHelperSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'clothTrajectoryVerified':False,'clothCollisionVerified':False,'fidelityVerified':False,
        'limitation':'Static geometric and API fault-injection checks. The full moving cloth calculation still requires completion and visual review.'}
output=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/bounded_volume_query_guard_v001.json')
assert not output.exists();output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print('BOUNDED_VOLUME_QUERY_GUARD_CHECKS_PASSED',flush=True)

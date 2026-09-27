# Chapeleiro: moving body contact study, unfinished

Compare the complete own-stage photo in `photo_comparison.jpg` with the actual
same-pose renders: previous measured cloth, published v096 GLB, and the new
strain/normal-velocity trial. Both new trial renders were visually inspected.
The leg still penetrates the ivory layer, black support remains exposed, and
the waist, gathers, cascades, lace, UV/normal polish and all other layers remain
unfinished. This trial is not approved for baking or replacing the GLB.

The complete 29-frame trial only marginally reduces the support's peak stretch
from 5.47 to 5.23. A requested 1.1 unilateral edge bound does not establish
convergence: final contact corrections reintroduce excess strain. Proper
triangle crossings remain 533 and 823 in the two reviewed moving poses.

Body calculation copies are now triangulated in bind geometry before rig
deformation. All 29 poses retain identical closed triangle topology, original
vertices, bone groups and weights; original visible meshes remain untouched.
Both compared studies use exactly equal body coordinates and frozen faces.

Moving point/face tests pass independent entering, exiting, outside-triangle,
translating-body, repeated-root and three-root cases. They record 283 entering
point/face candidates across three selected pose intervals of the old study.
The acceleration filter preserves all 45 output arrays exactly. Those tests
do not implement the full robust cloth collision algorithm: garment edge/edge
contacts, friction, substep response and final contact approval remain pending.

The source includes a provisional moving point/face response with previous
outside and endpoint exterior checks. Its new complete trajectory is still
being calculated and is not included as a completed result here. Source FBXs
provide bones/actions only. No new model is exported in this package.

The full 130,167,778-byte authoring checkpoint remains local without trimming;
the v096 GLB and protected Alice/intact dressed Chapeleiro masters are unchanged.
The final FBX, low-poly delivery, all actions, all stage photographs and the
remaining Chapeleiro layers must be completed before another Alice variant.
No additional Tripo credits or premium operations are used.

Point/face and strain reference: https://graphics.stanford.edu/papers/cloth-sig02/cloth.pdf

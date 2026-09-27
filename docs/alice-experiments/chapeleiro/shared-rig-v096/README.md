# Chapeleiro v096: independent flounce study, still in refinement

The three black flounces and their lace now have independent child joints. The
actual foundation GLB contains 229 skinned meshes, one shared 209-joint skeleton,
four unchanged source actions and the measured study clip **Corrida com tecido /
camadas em refinamento**. It is a work in progress, not a finished character.

Compare `foundation/photo_vs_actual_sewn_joint_motion.jpg` with the complete
unchanged photograph of this stage. It shows the actual previous GLB, measured
cloth and the new reimported GLB in the same poses and camera. All 101 body and
exterior joint matrices in both GLBs match exactly over all 29 recorded frames.
Six actual new export renders additionally show the initial front/back and the
running front, three-quarter, profile and back views.

The physical layer-contact study reduces proper triangle crossings at the two
inspected motion poses from 4,135 to 532 and from 3,655 to 823. It does not solve
all contact. Fine-detail queries still detect body penetration, the black
support has excessive local stretch and skin approximation error reaches 6.98
cm there. The lower flounce's maximum fitting error decreases from 8.16 cm to
2.39 cm with independent controls; its fidelity and collisions remain pending.

The new GLB was reimported and all five original garment midsurfaces measured
over 29 frames. Its actual coordinates reproduce the fitted response within
the recorded tolerance, not the physical target exactly. `foundation/review/`
contains those measured arrays and renders. `foundation/glb_field_comparison.json`
verifies exact rest geometry, UVs, normals, indices, material and texture bytes,
weight values, old inverse binds and four original action arrays. Only six
flounce/lace previews remap their bone names; added child channels in the four
original clips remain static. Source FBXs contribute only motion, not foreign
character meshes.

The complete authoring checkpoint is 130,167,778 bytes and remains local without
trimming. Its SHA-256 and the complete independent-control checkpoint are saved
under `bake/` and `rig/`. This Git package contains the actual GLB and physical,
detail, skin-seed, fitting and reimport arrays; absolute Windows paths in the raw
reports describe the execution environment. No final FBX is exported yet.

The raised leg still passes through the ivory layer. Profile/back views reveal
black support through the ivory surface, and waist gaps persist. Gathers,
diagonal cascades, scalloped lace, corset shape, UV/normal polish, all actions,
remaining layers and final low-poly/FBX review must still be completed against
their own stage photographs. Other Alice variants may not start yet. The
protected Alice and intact whole dressed Chapeleiro masters remain unchanged.
No additional Tripo credits or premium operations were used.

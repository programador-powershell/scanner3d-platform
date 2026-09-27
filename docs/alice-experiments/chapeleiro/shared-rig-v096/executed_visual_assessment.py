"""Record actual visual review and protected masters before the direct commit."""
import hashlib,json,shutil
from pathlib import Path
workspace=Path(__file__).resolve().parents[1]
out=workspace/'scanner3d-platform/docs/alice-experiments/chapeleiro/shared-rig-v096'
b=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inventory=read(out/'artifact_inventory.json')
def write(name,data):
 path=out/name;assert not path.exists()
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 inventory['artifacts'].append({'file':name,'bytes':path.stat().st_size,'sha256':sha(path)})
assessment={'sourcePhotoSha256':'f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4',
 'actualReviewedExportRenders':[r['sha256'] for r in read(out/'foundation/review/comparison.json')['renders']],
 'actualExportPhotoBoardReviewed':True,'actualContactPhotoBoardReviewed':True,
 'observedImprovements':['The front running pose retains more of the ivory skirt and its lower trim than the previous GLB.',
                         'Black flounces respond separately instead of remaining on the old shared bottom-ring controls.',
                         'Whole garment topology, UVs, materials and embedded textures remain intact.'],
 'observedRemainingDefects':['The raised leg still intersects the ivory layer in pose 29.',
                            'Black support remains visible through the ivory surface in profile and back poses.',
                            'Waist gaps and discontinuities around independently weighted decorations persist.',
                            'Reference gathers, diagonal cascades, scalloped lace, corset silhouette and finish are not yet faithful.'],
 'motionScope':'Only the separately named measured run study has the new two-anagua response. Four original actions are unchanged, and their cloth physics is not approved.',
 'allLayersFinished':False,'motionVerified':False,'clothCollisionVerified':False,'fidelityVerified':False,
 'finalFbxExported':False,'nextVariantMayStart':False,'additionalTripoCreditsConsumed':0}
write('visual_assessment.json',assessment)
protected=[
 ('scanner3d-platform/data/assets/alice-detail.glb','27200e6ea06b7940aa21ae86a18e6ad7442f1ff844add0cf0e471336cfa48c05'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-vestido-chapeleiro.glb','84e27a46ecc472db6f3d5345dbf1c6d2164c5830c6bd6104cfb919fd10bc4943'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-vestido-chapeleiro.blend','ab9af2be98449a3cc0d2d1f593bbd52243fc5be26dd28bbc0c8868bed69dc9d9'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-chapeleiro-fundacao.glb','d8ae24de525947e104218c5e518e217535b2c8bc0ce452338590ba738abea2e1'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-chapeleiro-fundacao.blend','55ae0b5e32aa7b6374d02e82752e7a21893bc95bc480397f56172ad9236e9fbd')]
rows=[]
for name,digest in protected:
 file=workspace/name;assert sha(file)==digest
 rows.append({'file':str(file),'bytes':file.stat().st_size,'sha256':digest,'unchanged':True})
parent=read(b/'foundation_shared_rig_v095/generation.json');assert sha(parent['editableBlend'])==parent['editableBlendSha256']
write('protected_assets.json',{'masters':rows,'previousCompleteAuthoringBytes':Path(parent['editableBlend']).stat().st_size,
      'previousCompleteAuthoringSha256':parent['editableBlendSha256'],'previousCompleteAuthoringUnchanged':True})
readme='''# Chapeleiro v096: independent flounce study, still in refinement

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
'''
path=out/'README.md';assert not path.exists();path.write_text(readme,encoding='utf-8',newline='\n')
inventory['artifacts'].append({'file':'README.md','bytes':path.stat().st_size,'sha256':sha(path)})
for file,name in [(workspace/'tools/package_chapeleiro_independent_cloth_study.py','executed_package.py'),(Path(__file__),'executed_visual_assessment.py')]:
 target=out/name;assert not target.exists();shutil.copyfile(file,target)
 inventory['artifacts'].append({'file':name,'bytes':target.stat().st_size,'sha256':sha(target)})
inventory['totalBytes']=sum(r['bytes'] for r in inventory['artifacts'])
for row in inventory['artifacts']:
 file=out/row['file'];assert file.stat().st_size==row['bytes'] and sha(file)==row['sha256'];assert row['bytes']<100*1024*1024
(out/'artifact_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('ACTUAL_V096_REVIEW_AND_MASTERS_VERIFIED',len(inventory['artifacts']),inventory['totalBytes'],flush=True)

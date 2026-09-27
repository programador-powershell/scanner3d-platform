"""Publish one complete-character refinement package with its own-photo evidence."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro');out=Path(a.output);assert not out.exists()
read=lambda q:json.loads(Path(q).read_text());sha=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest()
review=read(root/'dress_uv4k_integrated_v003/actual_visual_review.json');assert review['safeToPublishWholeCharacterRefinement']
generation=read(review['generation']);export=read(review['export']);roundtrip=read(review['actualGlbRoundtrip'])
assert export['wholeCharacterWithDress'] and export['meshCount']==export['skinCount']==1 and len(export['animations'])==4
assert sha(export['model'])==export['modelSha256'];assert sha(generation['editableBlend'])==generation['editableBlendSha256'];out.mkdir(parents=True)
artifacts=[]
def copy(source,relative,expected=None):
    source=Path(source);digest=sha(source)
    if expected:assert digest==expected
    # Keep the complete authoring master locally; never shrink it to fit GitHub.
    assert source.stat().st_size<100*1024*1024
    target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==digest
    item=dict(file=relative,sha256=digest,bytes=target.stat().st_size);artifacts.append(item);return item
model=copy(export['model'],'whole/alice_chapeleiro_dress_uv4k.glb',export['modelSha256'])
photo=copy(review['garmentReference'],'whole/source_photo.png',review['garmentReferenceSha256'])
paint=read(root/'dress_multiview_paint_v001/paint_sources.json');sources=[]
for row in paint['sources']:
    image=copy(row['image'],'projection_sources/'+row['view']+'.png',row['sha256']);prompt=copy(row['prompt'],'projection_sources/'+row['view']+'_prompt.txt',row['promptSha256'])
    sources.append(dict(view=row['view'],image=image['file'],sha256=image['sha256'],resolution=row['resolution'],prompt=prompt['file'],promptSha256=prompt['sha256']))
for view in ['front','left','right','back']:
    copy(root/'dress_uv4k_direct_before_after_v005'/(view+'_reference_before_after.png'),'whole/comparisons/'+view+'_photo_before_after.png')
    copy(root/'dress_texture_direct_baseline_v002'/(view+'_basecolor.png'),'whole/before/'+view+'.png')
for row in roundtrip['renders']:copy(row['file'],'whole/reimported/'+row['view']+'_'+row['kind']+'.png',row['sha256'])
write=lambda q,v:(out/q).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
write('projection_sources/paint_sources.json',dict(mode='built-in image_gen edits',sources=sources,garmentReference=photo['file'],garmentReferenceSha256=photo['sha256'],paintingsAreProjectionSourcesOnly=True))
checkpoint=dict(status='in_refinement',publicationUnit='whole Alice character with dress',model=model,sourcePhoto=photo,animations=export['animations'],skins=1,skinJoints=export['skinJoints'],nativeTriangles=roundtrip['actualImportedTriangles'],
    garmentTextureResolution=[4096,4096],garmentUvTexCoord=1,originalNormalAndOrmTexCoord=0,embeddedGarmentAlbedoPixelsExact=True,
    newlyProjectedSleeveFaces=generation['localSleevePolygonsAdded'],assignedGarmentPolygons=generation['modifiedMaterialPolygons'],visibleFaceOcclusionChecked=True,conflictingUvOverlapTexels=0,
    originalGeometryAndSkinWeightsPreserved=True,sourceProtectedPixelMaximumDifference=0,sourceCamerasIdentical=True,
    actualGlbReimport=dict(meshes=1,skeletons=1,bones=roundtrip['actualImportedBones'],maximumSurfaceErrorMeters=roundtrip['originalSurfaceNearestDistanceMaximumMeters']),
    fullLocalEditableBytes=generation['editableBytes'],fullLocalEditableSha256=generation['editableBlendSha256'],completeAuthoringLayersRetainedLocally=True,
    allLayersFinished=False,characterFidelityVerified=False,clothMotionVerified=False,finalFbxExported=False,nextVariantMayStart=False,additionalTripoCreditsConsumed=0,
    remainingWork=review['remainingWork'],artifacts=artifacts)
write('checkpoint.json',checkpoint)
(out/'README.md').write_text('''# Alice Chapeleiro — refinamento do vestido em UV 4K

Esta revisão contém a Alice inteira com vestido no GLB. A projeção usa quatro vistas 2D geradas com a habilidade imagegen, a foto própria desta variante e teste de oclusão na malha completa. A geometria original, os pesos, o rig e as quatro ações existentes foram preservados.

As comparações em `whole/comparisons/` mostram, nesta ordem: foto original sem alteração (ajustada ao quadro), render 3D anterior e render 3D após o refinamento. As câmeras são idênticas; o passe de cor não utiliza redução de ruído. O modelo realmente reimportado está em `whole/reimported/`.

Foram corrigidas manchas transferidas para pequenos trechos de pele, sobreposições do novo UV e a cobertura de 564 faces das mangas. O GLB incorpora a textura de 4096 × 4096 sem alteração dos pixels. As pinturas 2D de entrada têm 1024 × 1536.

O personagem continua em refinamento. A textura não comprova fidelidade da forma, relevo dos bordados, renda, rosto, cabelo, camadas interiores ou movimento. Caminhada, corrida, salto e ataque estão presentes como estudos; física e colisões ainda exigem correção. O projeto Blender completo de 149.334.303 bytes permanece preservado localmente. O FBX final aguarda a validação do personagem completo. Nenhum crédito adicional do Tripo foi utilizado.
''',encoding='utf-8')
print(json.dumps(dict(output=str(out.resolve()),wholeModel=model,completeLocalAuthoringPreserved=True,finalCharacterFinished=False)))

"""Archive the actual waist GLB, own-stage photo, reimport renders and cloth controls."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--assessment',required=True)
p.add_argument('--resume',action='store_true')
a=p.parse_args()
workspace=Path(__file__).resolve().parents[1]
repo=workspace/'scanner3d-platform'
base=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
root=base/'foundation_shared_rig_v095_export_v002'
out=repo/'docs/alice-experiments/chapeleiro/shared-rig-v095'
assert not out.exists() or a.resume
out.mkdir(parents=True,exist_ok=a.resume)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,r:Path(p).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
inventory=[]
def copy(file,relative,digest=None):
    file=Path(file)
    if digest: assert sha(file)==digest,str(file)
    target=out/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): assert sha(target)==sha(file),'Changed partial artifact: '+str(target)
    shutil.copyfile(file,target)
    assert sha(file)==sha(target)
    inventory.append({'file':target.relative_to(out).as_posix(),'bytes':target.stat().st_size,'sha256':sha(target)})
def generated(file):
    inventory.append({'file':file.relative_to(out).as_posix(),'bytes':file.stat().st_size,'sha256':sha(file)})

g=read(root/'generation.json')
assert sha(g['editableBlend'])==g['editableBlendSha256']
assert Path(g['editableBlend']).stat().st_size==g['editableBytes']>100*1024*1024
assert g['wholeExportInheritedUnchanged'] and g['physicalSpringStudyNotBakedIntoExport']
waist=read(g['waistSkinRefinement'])
fields=read(root/'actual_glb_waist_field_comparison.json')
assert fields['afterModelSha256']==g['exports']['foundation']['modelSha256']
assert fields['restGeometryUvNormalsIndicesMaterialsImagesBindJointsIdentical']
assert fields['allFiveAnimationChannelArraysIdentical'] and fields['noChangesAtOrBelowWaistTransition']
assert len(fields['changedWeightMeshes'])==9
copy(g['exports']['foundation']['model'],'foundation/skin_study.glb',g['exports']['foundation']['modelSha256'])
copy(g['exports']['foundation']['sourcePhoto'],'foundation/source_photo.png',g['exports']['foundation']['sourcePhotoSha256'])
copy(root/'generation.json','actual_export_generation.json')
copy(root/'executed_export.py','executed_export.py',g['scriptSha256'])
copy(root/'actual_glb_waist_field_comparison.json','actual_glb_waist_field_comparison.json')
copy(root/'executed_glb_field_comparison.py','executed_glb_field_comparison.py',fields['scriptSha256'])
copy(base/'foundation_shared_rig_v095_export_v002.log','actual_export_execution.log')
copy(g['waistSkinRefinement'],'waist_skin_refinement.json')
copy(base/'foundation_shared_rig_v095/generation.json','actual_authoring_generation.json')
copy(base/'foundation_shared_rig_v095/executed_waist_skin_refinement.py','executed_waist_skin_refinement.py',waist['scriptSha256'])
copy(base/'foundation_shared_rig_v095.log','actual_waist_skin_execution.log')
copy(base/'foundation_shared_rig_v095/export_dependencies_inspection.log','export_dependencies_inspection.log')
for name in ['chapeleiro_shared_rig_fields.py','chapeleiro_sewn_cloth_assembly.py','chapeleiro_cloth_colliders.py','chapeleiro_cloth_motion_entry.py','chapeleiro_closed_underlayer_proxies.py','chapeleiro_cloth_material_settings.py']:
    copy(repo/'blender'/name,'executed_helpers/'+name)

motion=read(root/'actual_shared_rig_review_v001/motion_comparison.json')
assert motion['actualImportedSkinnedMeshes']==229 and motion['actualImportedSkeletons']==1
assert len(motion['restRenders'])==4 and sum(len(c['poses']) for c in motion['clips'])==12
assert motion['modelSha256']==fields['afterModelSha256']
copy(root/'actual_shared_rig_review_v001/motion_comparison.json','foundation/motion_comparison.json')
copy(root/'actual_shared_rig_review_v001/executed_review.py','foundation/executed_review.py',motion['scriptSha256'])
copy(root/'actual_shared_rig_review_v001.log','foundation/actual_review_execution.log')
renders=[]
for row in motion['restRenders']:
    copy(row['file'],'foundation/rest/'+Path(row['file']).name,row['sha256'])
    renders.append(row['sha256'])
for clip in motion['clips']:
    for row in clip['poses']:
        copy(row['render'],'foundation/motion/'+Path(row['render']).name,row['renderSha256'])
        renders.append(row['renderSha256'])
ivory=read(root/'actual_ivory_export_review_v001/comparison.json')
assert ivory['modelSha256']==fields['afterModelSha256'] and len(ivory['renders'])==7
copy(root/'actual_ivory_export_review_v001/comparison.json','actual_ivory_export_review/comparison.json')
copy(root/'actual_ivory_export_review_v001/actual_pose_measurements.json','actual_ivory_export_review/actual_pose_measurements.json')
copy(root/'actual_ivory_export_review_v001/actual_exported_ivory_poses.npz','actual_ivory_export_review/actual_exported_ivory_poses.npz',ivory['actualExportDataSha256'])
copy(root/'actual_ivory_export_review_v001/executed_review.py','actual_ivory_export_review/executed_review.py',ivory['scriptSha256'])
copy(root/'actual_ivory_export_review_v001_retry.log','actual_ivory_export_review/actual_execution.log')
for row in ivory['renders']:
    copy(row['file'],'actual_ivory_export_review/renders/'+Path(row['file']).name,row['sha256'])
    renders.append(row['sha256'])

arrays,reports={},{}
for version in [7,8,9]:
    folder=base/f'retopo_ivory_black_cloth_v{version:03d}'
    r=reports[version]=read(folder/'actual_sewn_solver_motion.json')
    arrays[version]=np.load(r['dataFile'])
    assert len(r['frames'])==29
    for flag in ['allLayersFinished','fidelityVerified','motionVerified','clothCollisionVerified','finalFbxExported','modelExported','responseBakedIntoRig']:
        assert r[flag] is False
    label=f'cloth_control_{version:03d}'
    copy(folder/'actual_sewn_solver_motion.json',label+'/actual_sewn_solver_motion.json')
    copy(r['dataFile'],label+'/actual_cloth_frames.npz',r['dataSha256'])
    if version==8:
        assert not r['physicalSolverReexecutedInThisStep'] and all(x['actualBound'] for x in r['actualSurfaceDeformBindings'])
        copy(folder/'executed_surface_deform_refinement.py',label+'/executed_surface_deform_refinement.py',r['scriptSha256'])
    else:
        for filename,key in [('executed_probe.py','scriptSha256'),('executed_assembly.py','assemblyHelperSha256'),('executed_retopo_assembly.py','retopoAssemblyHelperSha256'),('executed_material_settings.py','materialSettingsHelperSha256')]:
            copy(folder/filename,label+'/'+filename,r[key])
        copy(folder/'mass_calibration.json',label+'/mass_calibration.json')
        copy(base/(folder.name+'.log'),label+'/actual_execution.log')
    review=read(folder/'actual_receiver_review/comparison.json')
    assert review['probeDataSha256']==r['dataSha256'] and len(review['renders'])==2
    assert 'Target vertices changed' not in (folder/'actual_receiver_review.log').read_text(encoding='utf-8')
    copy(folder/'actual_receiver_review/comparison.json',label+'/review/comparison.json')
    copy(folder/'actual_receiver_review/executed_render.py',label+'/review/executed_render.py',review['scriptSha256'])
    copy(folder/'actual_receiver_review.log',label+'/review/actual_execution.log')
    for row in review['renders']:
        copy(row['file'],label+'/review/'+Path(row['file']).name,row['sha256'])
        renders.append(row['sha256'])
    if version!=8:
        for name,log in [('pinned_input_clearance_inspection','pinned_input_clearance.log'),('dynamic_clearance_inspection','dynamic_clearance.log')]:
            d=read(folder/name/'dynamic_clearance_inspection.json')
            assert d['sourcePhysicalDataSha256']==r['dataSha256']
            copy(folder/name/'dynamic_clearance_inspection.json',label+'/'+name+'/dynamic_clearance_inspection.json')
            copy(d['dataFile'],label+'/'+name+'/actual_dynamic_clearance.npz',d['dataSha256'])
            copy(folder/name/'executed_inspection.py',label+'/'+name+'/executed_inspection.py',d['scriptSha256'])
            copy(folder/name/'executed_closed_proxy_helper.py',label+'/'+name+'/executed_closed_proxy_helper.py',d['closedProxyHelperSha256'])
            copy(folder/(name+'.log' if version==7 else log),label+'/'+name+'/actual_execution.log')
for key in reports[8]['exactPreservedPhysicalArrays']:
    assert np.array_equal(arrays[7][key],arrays[8][key]),key
contact=read(base/'retopo_ivory_black_cloth_v009/actual_waist_contact_comparison_v002.json')
assert contact['waistAnchorConflictEliminatedInMeasuredSequence'] and contact['freeClothPenetrationStillPresent']
copy(base/'retopo_ivory_black_cloth_v009/actual_waist_contact_comparison_v002.json','actual_waist_contact_comparison.json')
copy(base/'retopo_ivory_black_cloth_v009/executed_contact_comparison.py','executed_contact_comparison.py',contact['scriptSha256'])

for folder,label,log in [('retopo_ivory_black_cloth_v010','quality48_springs_stopped','retopo_ivory_black_cloth_v010.log'),('foundation_shared_rig_v095_export_v001','unoptimized_export_stopped','foundation_shared_rig_v095_export_v001.log')]:
    stopped=read(base/folder/'stopped_execution.json')
    assert not stopped['completed']
    for file in (base/folder).iterdir():
        if file.is_file(): copy(file,label+'/'+file.name)
    copy(base/log,label+'/actual_execution.log')

boards=read(root/'photo_review_boards_v001/boards.json')
assessment=read(a.assessment)
assert set(renders)==set(assessment['actuallyViewedRenderSha256'])
assert assessment['actuallyViewedAllRenderBoards'] and not assessment['fidelityVerified']
copy(a.assessment,'visual_assessment.json')
copy(root/'photo_review_boards_v001/boards.json','photo_review_boards.json')
for row in boards['boards']:
    copy(row['file'],'foundation/'+Path(row['file']).name,row['sha256'])
copy(workspace/'tools/build_chapeleiro_v095_photo_boards.py','executed_photo_boards.py',boards['scriptSha256'])
checkpoint={'fullLocalEditable':{'file':g['editableBlend'],'bytes':g['editableBytes'],'sha256':g['editableBlendSha256']},
            'actualFoundationGlb':{'file':'foundation/skin_study.glb','bytes':g['exports']['foundation']['bytes'],'sha256':fields['afterModelSha256']},
            'actualSkinnedMeshes':229,'actualJoints':173,'actualClips':g['exports']['foundation']['actualClips'],
            'wholeGlbInheritedUnchanged':g['exports']['whole'],'wholeModelRevision':'f02c7040e4312d3839d0900394d3a01886079961',
            'sourcePhotoSha256':g['exports']['foundation']['sourcePhotoSha256'],'actualNewWeightMeshes':9,
            'actualOriginalWeightMeshesUnchanged':220,'actualFullEditableWaistObjectsChanged':10,
            'allActualRestGeometryUvMaterialsFiveAnimationsPreserved':True,
            'physicalSpringStudiesBakedIntoGlb':False,'allLayersFinished':False,'fidelityVerified':False,
            'motionVerified':False,'clothCollisionVerified':False,'finalFbxExported':False,
            'nextVariantMayStart':False,'additionalCreditsConsumed':0}
write(out/'checkpoint.json',checkpoint);generated(out/'checkpoint.json')
(out/'.gitattributes').write_text('* -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n',encoding='utf-8',newline='\n')
generated(out/'.gitattributes')
(out/'README.md').write_text('''# Alice Chapeleiro — cintura do rig e contato em refinamento

O novo [GLB das camadas inferiores](foundation/skin_study.glb) altera apenas os pesos da cintura de nove peças dos bloomers. A comparação de 1.153 arrays reais confirmou posição, normal, UV, índices, materiais, imagens, bind e todos os canais das cinco animações idênticos ao v094. Pesos de outras 220 peças e todos os vértices abaixo da transição de 55 cm permanecem iguais. O arquivo completo editável tem 129.796.311 bytes, preservado localmente com SHA no [checkpoint](checkpoint.json); não foi truncado para caber no limite de arquivo GitHub. O exterior inteiro e Alice base estão preservados.

Os pontos totalmente presos da anágua tinham conflito com a cintura movida só pelo quadril: 34 penetravam até 5 mm no volume dos bloomers durante a corrida. Agora a faixa superior dos bloomers acompanha o mesmo campo do torso dos pontos de fixação. Nas mesmas 29 poses, nenhum desses 192 pontos totalmente presos entrou no volume ou teve consulta ambígua. Pontos parcialmente presos ainda tiveram consultas ambíguas. O restante do tecido continua reprovado: o número de vértices físicos dentro dos bloomers passou de 431 para 677 e a penetração máxima chegou a 3,72 cm. Isso resolve o conflito medido da fixação, sem aprovar a simulação completa.

O controle de costuras separa as raízes dos babados em uma malha de cálculo independente de 9.024 vértices e 8.544 quads, ligada por 288 molas de costura e sem arestas de superfície com três faces. Nenhuma geometria visual foi recortada. Um controle adicional usa cinco vínculos Surface Deform reais do Blender para transferir exatamente a mesma trajetória física aos receptores de detalhe, mantendo UV e repouso. O erro máximo em repouso ficou abaixo de 0,5 micrômetro; no movimento, a distorção diminui mas continua inadequada. Outro controle solicitando 48 passos foi interrompido após a pose 20 preservada, com arestas físicas chegando a 6,81 vezes o comprimento original. Não existe trajetória completa ou render desse controle interrompido.

A reimportação efetiva do novo GLB confirmou uma armature compartilhada, 229 superfícies com pesos normalizados e UVs, quatro vistas de repouso, doze poses das quatro ações e sete renders do estudo de anágua já existente. Veja [foto original completa](foundation/source_photo.png), [repouso](foundation/photo_vs_geometry.jpg), [doze poses](foundation/photo_vs_shared_skin_motion.jpg), [estudo da anágua](foundation/photo_vs_actual_ivory_joint_motion.jpg) e [controles do contato](foundation/photo_vs_actual_waist_cloth_contact.jpg). Todos os renders e a [avaliação visual](visual_assessment.json) são reais. As novas trajetórias com molas de costura não estão incorporadas ao GLB; ele mantém o estudo de anágua anterior. A exportação que avaliava desnecessariamente modificadores de peças não selecionadas foi substituída por uma concluída que altera só a visibilidade e avaliação em memória, sem salvar ou reduzir o checkpoint original.

Rig presente, cinco ações e ausência do conflito de fixação não aprovam a fidelidade da roupa. Corset, cascatas, franzidos, renda, contato entre camadas, transições, física de todas as ações, retopologia final e UV/bakes ainda precisam de acabamento. O FBX final e o início da próxima variante continuam pendentes. Nenhum crédito adicional ou recurso premium do Tripo foi usado. Os modelos e evidências desta revisão ficam no GitHub, sem Supabase como origem dos arquivos.
''',encoding='utf-8',newline='\n');generated(out/'README.md')
copy(__file__,'executed_package.py')
assert all(r['bytes']<100*1024*1024 for r in inventory)
write(out/'artifact_inventory.json',{'artifacts':inventory,'preservedExactlyAsExecutedBytes':True})
print('ACTUAL_V095_REVIEW_PACKAGED',len(inventory),sum(r['bytes'] for r in inventory))

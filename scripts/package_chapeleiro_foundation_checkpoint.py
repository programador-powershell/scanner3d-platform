"""Publish reviewed partial internals alongside, without replacing, the whole GLB."""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
from alice_foundation_parts import foundation_review_members

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--comparison', required=True)
parser.add_argument('--audit', required=True)
parser.add_argument('--game', required=True)
parser.add_argument('--part-comparison', action='append', default=[])
parser.add_argument('--exported-contact-audit')
args = parser.parse_args()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
generation = json.loads(Path(args.generation).read_text(encoding='utf-8'))
comparison = json.loads(Path(args.comparison).read_text(encoding='utf-8'))
audit = json.loads(Path(args.audit).read_text(encoding='utf-8'))
if (audit['editableBlendSha256'] != generation['editableBlendSha256']
        or not audit.get('savedModelUnchanged')
        or {a['mesh'] for a in audit.get('actualApertureAudit',[])}
           != {p['name'] for p in generation['pieces'] if p.get('actualGeometricApertures')
                                                     or p['role']=='internal_photographic_lace'}
        or not audit.get('allActualFollowersCovered')
        or audit.get('actualInternalObjects') != len(generation['pieces'])
        or audit.get('verifiedFollowers') != len(generation['pieces'])-len(audit.get('attachmentRoots',[]))
        or {p['follower'] for p in audit.get('carrierTranslationProbe',[])}
           != {p['name'] for p in generation['pieces']}-set(audit.get('attachmentRoots',[]))
        or any(p['p95TranslationError'] > .001 for p in audit['carrierTranslationProbe'])):
    raise ValueError('Requires the actual geometric-aperture and carrier-translation audit.')
if any(p['role']=='foundation_bloomers' for p in generation['pieces']):
    lower=audit.get('actualLowerConstructionAudit',[])
    if (sum(bool(p.get('connectedCrotchVerified')) for p in lower)!=1
            or sum(bool(p.get('closedToeVerified')) for p in lower)!=2
            or sum(bool(p.get('bindingVerified')) for p in lower)
               != len(generation.get('additionalSimulationCages',[]))+len(generation.get('additionalSkinCages',[]))):
        raise ValueError('Requires actual connected-crotch, closed-foot and lower carrier evidence.')
if any(p['role']=='foundation_gathered_blouse' for p in generation['pieces']):
    seams=audit.get('actualBlouseSeamAudit',[])
    if len(seams)!=5 or any(not s['measuredFromActualCages'] or s['maximumRootGap']>1e-6 for s in seams):
        raise ValueError('Requires measurements of both armholes, both cuffs and the neckline seam.')
    solvers=audit.get('blouseSolverPartitionAudit',[])
    if len(solvers)!=3 or any(not s['singleSolver'] or s['uvNonDegenerateTriangleFraction']<.95 for s in solvers):
        raise ValueError('Requires actual single-solver and evaluated blouse UV evidence.')
if generation.get('stockingAnatomyConstruction'):
    feet=audit.get('actualStockingAnatomyAudit',[])
    if ({p['mesh'] for p in feet}!={p['mesh'] for p in generation['stockingAnatomyConstruction']}
            or any(not p['measuredFromActualCage'] or not p['connectedFootVerified']
                   or not p['closedToeVerified'] or p['minimumTriangleArea']<=1e-12 for p in feet)):
        raise ValueError('Requires actual connected, non-collapsed refined stocking feet.')
if generation.get('garterCupConstruction'):
    details=audit.get('actualGarterDetailAudit',[])
    expected={p['name'] for p in generation['pieces'] if ' garter /' in p['name']
              and ('pointed thigh reinforcement' in p['name'] or any(
                  key in p['name'] for key in ['narrow top facing','top facing stitch','curved panel seam',
                      'curved seam sewing threads','side bow']))}
    if ({p['mesh'] for p in details}!=expected or any(
            not p['bindingVerified'] or not p['measuredFromActualMesh']
            or p['uvNonDegenerateTriangleFraction']<.95 for p in details)):
        raise ValueError('Requires actual refined cup, sewing-thread and ribbon attachment/UV evidence.')
if generation.get('garterCupDrapeConstruction'):
    drapes=audit.get('actualGarterDrapeAudit',[])
    if ({p['mesh'] for p in drapes}!={p['mesh'] for p in generation['garterCupDrapeConstruction']}
            or any(not p['measuredFromActualCage'] or not p['originalTopAndHemVerified']
                   or not p['originalTopFacingVerified'] or p['minimumTriangleArea']<=1e-12 for p in drapes)):
        raise ValueError('Requires actual sculpted cup topology, original rims and facing geometry.')
if generation.get('garterBeltGatherConstruction'):
    belts=audit.get('actualGarterBeltAudit',[])
    expected=generation['garterBeltGatherConstruction']
    if (len(belts)!=1 or belts[0]['mesh']!=expected['mesh']
            or not belts[0]['measuredFromActualMeshes'] or not belts[0]['singleThinClothSolver']
            or not belts[0]['originalStrapRootRingVerified'] or not belts[0]['actualWaistPinsVerified']
            or not belts[0].get('actualClothGroupSchemaVerified') or not belts[0].get('actualPressureFieldVerified')
            or not belts[0].get('actualLaceHeaderSeam',{}).get('measuredFromActualRawEdges')
            or belts[0]['actualLaceHeaderSeam']['maximumRawHeaderEdgeGap']>.00025
            or any(p['maximumRawSeamGap']>1e-6 for p in belts[0]['frillSeams'])
            or any(p['uvNonDegenerateTriangleFraction']<.95 for p in belts[0]['evaluatedUvQuality'])
            or {p['mesh'] for p in belts[0]['actualElasticSeamMeshes']}!=set(expected['actualElasticSeamMeshes'])
            or any(not p['actualClosedThreadLoopVerified'] for p in belts[0]['actualElasticSeamMeshes'])):
        raise ValueError('Requires actual casing, sewn frill, cloth fields, UV, thread and sampled lace-edge seam evidence.')
    if generation.get('garterLaceThreadRefinement'):
        threads=belts[0].get('actualRoundedLaceThreadAudit') or {}
        expected_threads=generation['garterLaceThreadRefinement']
        if (threads.get('mesh')!=expected_threads['mesh']
                or not threads.get('measuredFromActualRawMesh')
                or not threads.get('allEdgesManifoldVerified')
                or not threads.get('allYarnsCappedOrClosedVerified')
                or not threads.get('duplicateThicknessAbsentVerified')
                or threads.get('minimumRawTriangleArea',0)<=1e-14
                or threads.get('actualClosedYarnComponents')!=len(expected_threads['components'])
                or threads.get('sourceThreadGraphSha256')!=expected_threads['sourceThreadGraphSha256']):
            raise ValueError('Requires actual closed yarn topology, UVs and the own-photo filament graph.')
        exported=json.loads((Path(args.generation).resolve().parent/'exported_lace_threads_audit.json').read_text(encoding='utf-8'))
        if (exported['modelSha256']!=generation['modelSha256'] or not exported.get('passed')
                or not exported.get('measuredActualExportedMesh') or not exported.get('primaryUvMeasured')
                or exported['mesh']!=expected_threads['mesh']):
            raise ValueError('Requires independent measurements of actual exported round yarn geometry and UVs.')
if generation.get('garterFrontWebConstruction'):
    webs=audit.get('actualGarterWebContactAudit',[])
    if ({p['mesh'] for p in webs}!={p['mesh'] for p in generation['garterFrontWebConstruction']}
            or any(not p['measuredFromEvaluatedGeometry'] or not p['restSeparationVerified']
                   or p['minimumMeasuredFrontClearance']<.00015 for p in webs)):
        raise ValueError('Requires actual evaluated separation of both webs from their sculpted cups.')
    if not args.exported_contact_audit:
        raise ValueError('Requires an independent actual exported GLB rest-contact audit.')
    exported_contacts=json.loads(Path(args.exported_contact_audit).read_text(encoding='utf-8'))
    if (exported_contacts['modelSha256']!=generation['modelSha256']
            or not exported_contacts.get('measuredActualExportedGeometry')
            or not exported_contacts.get('sampledRestClearancePassed')
            or {p['side'] for p in exported_contacts.get('contacts',[])}!={'left','right'}
            or any(p['minimumClearance']<.00015 or p['sampledContacts']<15
                   for p in exported_contacts['contacts'])):
        raise ValueError('The actual exported web/cup rest separation failed.')
if generation.get('petticoatSimulationCages'):
    partition=audit.get('petticoatSolverPartitionAudit',[])
    expected={p['name'] for p in generation['petticoatSimulationCages']}
    if ({p['simulationCage'] for p in partition}!=expected
            or any(not p['singleThinSolver'] or not p['fixedBindingTargetDiagonals']
                   or p['uvNonDegenerateTriangleFraction']<.95 for p in partition)
            or sum(bool(p.get('actualWaistAndGatherPinsVerified')) for p in partition)!=2):
        raise ValueError('Requires actual thin petticoat solvers, UVs, waist seams and drawstring pins.')
    point_followers=[p for p in partition if p.get('followMethod')=='same_topology_point_index']
    if len(point_followers)!=2 or any(
            p.get('maximumSolvedPositionError',1)>1e-6
            or p.get('evaluatedCarrierDisplacementProbe',{}).get('maximumCarrierDisplacement',0)<.0005
            or p.get('evaluatedCarrierDisplacementProbe',{}).get('maximumFollowingError',1)>1e-6
            for p in point_followers):
        raise ValueError('Requires actual evaluated deformation of both visible side panels.')
if (generation['sourcePhotoSha256'] != comparison['sourcePhotoSha256']
        or comparison['stageId'] != 'alice_chapeleiro_stage_01'
        or comparison['status'] != 'needs_refinement'
        or not comparison.get('visibleDifferences')
        or generation.get('completeExteriorVerticesUnchanged') is not True):
    raise ValueError('Requires an actually reviewed partial foundation of the intact Chapeleiro.')
for field in ['model', 'editableBlend', 'sourcePhoto']:
    if sha(generation[field]) != generation[field+'Sha256']:
        raise ValueError('Changed construction evidence: '+field)
artifacts = [comparison['displayModel'], comparison['comparisonBoard'], *comparison['renders'].values()]
if any(sha(a['file']) != a['sha256'] for a in artifacts):
    raise ValueError('Changed visual review evidence.')
part_reviews=[]
for path in args.part_comparison:
    part=json.loads(Path(path).read_text(encoding='utf-8'))
    if (part.get('reviewScope')!='selected_internal_components'
            or part.get('status')!='needs_refinement' or not part.get('visibleDifferences')
            or part['sourcePhotoSha256']!=generation['sourcePhotoSha256']
            or part['modelSha256']!=generation['modelSha256']
            or set(part['renderedComponents'])!=foundation_review_members(
                generation['pieces'], part.get('selectedRolePrefix'), part.get('selectedComponentGroup'))
            or set(part['renders'])!={'front','side','back','threequarter'}):
        raise ValueError('Requires an own-photo four-view review of the same actual construction.')
    if any(sha(a['file'])!=a['sha256'] for a in [part['comparisonBoard'],*part['renders'].values()]):
        raise ValueError('Changed part review evidence.')
    part_reviews.append(part)
model = Path(comparison['displayModel']['file'])
binary = model.read_bytes()
if binary[:4] != b'glTF' or len(binary) > 100 * 1024 * 1024:
    raise ValueError('Expected a GitHub-compatible real GLB, not an LFS pointer.')
size = struct.unpack_from('<I',binary,12)[0]
gltf = json.loads(binary[20:20+size])
triangles = sum(gltf['accessors'][p['indices']]['count']//3
                for mesh in gltf['meshes'] for p in mesh['primitives'])
if gltf.get('skins') or gltf.get('animations'):
    raise ValueError('This unrigged construction checkpoint must not advertise motion.')
game = Path(args.game)
complete = game/'Content/Assets/3D/personagens/alice-vestido-chapeleiro.glb'
complete_hash = sha(complete)
editable_dependencies=[]
for dependency in generation.get('editableLibraryDependencies',[]):
    canonical=complete.parent/dependency['file']
    local=Path(generation['editableBlend']).parent/dependency['file']
    if sha(local)!=dependency['sha256'] or sha(canonical)!=dependency['sha256']:
        raise ValueError('The existing Git-tracked editable master must remain identical.')
    editable_dependencies.append({**dependency,'file':canonical.relative_to(game).as_posix()})
docs = game/'Docs/alice-variants/chapeleiro/foundation'
docs.mkdir(parents=True,exist_ok=True)
def copy(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination)
    if sha(source)!=sha(destination):
        raise ValueError('Copy identity mismatch.')
model_path = game/'Content/Assets/3D/personagens/alice-chapeleiro-fundacao.glb'
blend_path = game/'Content/Assets/3D/personagens/alice-chapeleiro-fundacao.blend'
copy(model,model_path)
copy(generation['editableBlend'],blend_path)
copy(generation['sourcePhoto'],docs/'source_photo.png')
copy(comparison['comparisonBoard']['file'],docs/'photo_vs_geometry.jpg')
copy(args.audit,docs/'carrier_audit.json')
if args.exported_contact_audit:
    copy(args.exported_contact_audit,docs/'exported_contact_diagnostic.json')
if generation.get('garterLaceThreadRefinement'):
    yarn_source=Path(args.generation).resolve().parent/'exported_lace_threads_audit.json'
    copy(yarn_source,docs/'exported_lace_threads_audit.json')
    thread_source=Path(generation['garterLaceThreadRefinement']['sourceThreadGraph'])
    copy(thread_source,docs/'thread_paths_local_provenance.json')
    thread_graph=json.loads(thread_source.read_text(encoding='utf-8'))
    if sha(thread_graph['interpretedMask'])!=thread_graph['interpretedMaskSha256']:
        raise ValueError('Changed own-photo ridge skeleton.')
    copy(thread_graph['interpretedMask'],docs/'photographic_filament_skeleton.png')
    thread_graph.update(sourcePhoto='source_photo.png',interpretedMask='photographic_filament_skeleton.png')
    (docs/'thread_paths.json').write_text(json.dumps(thread_graph,ensure_ascii=False,indent=2),encoding='utf-8')
for name, artifact in comparison['renders'].items():
    copy(artifact['file'],docs/(name+'.png'))
portable_parts=[]
for part in part_reviews:
    prefix=part.get('selectedComponentGroup') or part['selectedRolePrefix']
    if prefix not in ['foundation_bloomers','foundation_garter_','foundation_stocking','corset','petticoats']:
        raise ValueError('Unknown foundation part review.')
    folder=docs/'parts'/prefix.removeprefix('foundation_').rstrip('_')
    copy(part['comparisonBoard']['file'],folder/'photo_vs_geometry.jpg')
    record={k:part[k] for k in ['sourcePhotoSha256','sourceCrop','reviewScope','selectedRolePrefix',
                              'renderedComponents','modelSha256','status','visibleDifferences']}
    record['selectedComponentGroup']=part.get('selectedComponentGroup')
    record['renders']={}
    for name,artifact in part['renders'].items():
        destination=folder/(name+'.png')
        copy(artifact['file'],destination)
        record['renders'][name]={'file':destination.relative_to(game).as_posix(),'sha256':sha(destination)}
    record['comparisonBoard']={'file':(folder/'photo_vs_geometry.jpg').relative_to(game).as_posix(),
                               'sha256':sha(folder/'photo_vs_geometry.jpg')}
    (folder/'comparison.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    portable_parts.append(record)
if sha(complete)!=complete_hash:
    raise ValueError('The whole dressed gallery item must remain unchanged.')
report={'variant':'alice_chapeleiro','stage':'alice_chapeleiro_stage_01',
        'status':'needs_refinement','sourcePhoto':'Docs/alice-variants/chapeleiro/foundation/source_photo.png',
        'sourcePhotoSha256':generation['sourcePhotoSha256'],'method':generation['method'],
        'model':{'file':model_path.relative_to(game).as_posix(),'sha256':sha(model_path),
                 'bytes':model_path.stat().st_size,'triangles':triangles,'meshes':len(gltf['meshes']),
                 'joints':0,'animations':[]},
        'editable':{'file':blend_path.relative_to(game).as_posix(),'sha256':sha(blend_path),
                    'bytes':blend_path.stat().st_size,'libraries':editable_dependencies},
        'completeExteriorVerticesUnchanged':True,'completeGalleryModelSha256Unchanged':complete_hash,
        'addon':{'name':generation['addon'],'author':generation['author'],
                 'version':generation['addonVersion'],'originalAssetSha256':generation['originalAssetSha256']},
        'newInternalPieces':generation['pieces'],'visibleDifferences':comparison['visibleDifferences'],
        'stockingAnatomyConstruction':generation.get('stockingAnatomyConstruction',[]),
        'garterCupConstruction':generation.get('garterCupConstruction',[]),
        'garterCupDrapeConstruction':generation.get('garterCupDrapeConstruction',[]),
        'garterFrontWebConstruction':generation.get('garterFrontWebConstruction',[]),
        'garterBeltGatherConstruction':generation.get('garterBeltGatherConstruction'),
        'isolatedPartReviews':portable_parts,
        'attachmentAudit':{'file':'Docs/alice-variants/chapeleiro/foundation/carrier_audit.json',
                           'sha256':sha(args.audit),'frame':1,'verifiedFollowers':audit['verifiedFollowers'],
                           'actualApertureAudit':audit['actualApertureAudit'],
                           'actualBlouseSeamAudit':audit.get('actualBlouseSeamAudit',[]),
                           'blouseSolverPartitionAudit':audit.get('blouseSolverPartitionAudit',[]),
                           'petticoatSolverPartitionAudit':audit.get('petticoatSolverPartitionAudit',[]),
                           'actualLowerConstructionAudit':audit.get('actualLowerConstructionAudit',[]),
                           'actualStockingAnatomyAudit':audit.get('actualStockingAnatomyAudit',[]),
                           'actualGarterDetailAudit':audit.get('actualGarterDetailAudit',[]),
                           'actualGarterDrapeAudit':audit.get('actualGarterDrapeAudit',[]),
                           'actualGarterWebContactAudit':audit.get('actualGarterWebContactAudit',[]),
                           'actualGarterBeltAudit':audit.get('actualGarterBeltAudit',[]),
                           'dynamicSimulationVerified':False},
        'additionalCreditsConsumed':0,'fidelityVerified':False,'allLayersFinished':False,
        'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False,'nextVariantMayStart':False}
if args.exported_contact_audit:
    report['exportedRestContactAudit']={'file':'Docs/alice-variants/chapeleiro/foundation/exported_contact_diagnostic.json',
        'sha256':sha(args.exported_contact_audit),'modelSha256':generation['modelSha256'],
        'sampledRestClearancePassed':True,'motionVerified':False,'clothCollisionVerified':False}
if generation.get('garterLaceThreadRefinement'):
    report['exportedLaceThreadsAudit']={'file':(docs/'exported_lace_threads_audit.json').relative_to(game).as_posix(),
        'sha256':sha(yarn_source),'modelSha256':generation['modelSha256'],
        'measuredActualGeneratedModel':True,'passed':True,'fidelityVerified':False}
    report['photographicFilamentPaths']={'file':(docs/'thread_paths.json').relative_to(game).as_posix(),
        'sha256':sha(docs/'thread_paths.json'),'localProvenanceFile':(docs/'thread_paths_local_provenance.json').relative_to(game).as_posix(),
        'localProvenanceSha256':sha(thread_source),'sourcePhotoSha256':generation['sourcePhotoSha256'],
        'fineGroundAndUnseenRepeatsInferred':True,'fidelityVerified':False}
    canonical_audit=Path(args.generation).resolve().parent/'canonical_lace_threads_audit.json'
    if canonical_audit.exists():
        canonical_record=json.loads(canonical_audit.read_text(encoding='utf-8'))
        if not canonical_record['passed'] or canonical_record['modelSha256']!=sha(model_path):
            raise ValueError('Canonical round-yarn export evidence belongs to another actual model.')
        copy(canonical_audit,docs/'canonical_lace_threads_audit.json')
        report['canonicalLaceThreadsAudit']={'file':(docs/'canonical_lace_threads_audit.json').relative_to(game).as_posix(),
            'sha256':sha(canonical_audit),'modelSha256':sha(model_path),
            'measuredActualGalleryModel':True,'passed':True,'fidelityVerified':False}
(docs/'checkpoint.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(docs/'README.md').write_text(
    '# Chapeleiro: fundação da ficha 1 em refinamento\n\n'
    'Anáguas internas novas, renda floral com aberturas em geometria, camisa '
    'franzida com cavas reais, mangas bufantes e corsete '
    'com canais, fechos, ilhoses, cruzamentos traseiros, babados nas bordas, '
    'renda inferior vazada e fitas traseiras com largura e espessura. Bloomers com entrepernas '
    'conectado, ligas com tiras e ferragens e meias com pés fechados também '
    'fazem parte desta construção. As comparações isoladas estão em parts/. O GLB do vestido '
    'completo permanece inteiro no seu item original. As rendas acompanham '
    'os respectivos suportes no arquivo Blender por Surface Deform; isso '
    'ainda não valida rig, simulação em gameplay ou colisões.\n\n'+
    ('As cascatas laterais da anágua são superfícies novas de tecido, com '
     'canais de franzido, cordões, ilhoses e laços. Cada painel tem uma única '
     'malha fina de Cloth; sua superfície visível amostra os vértices resolvidos '
     'por índice antes da espessura e do UV do Bystedt. O vínculo à cintura e '
     'os pontos de franzido foram medidos no arquivo editável. Essa verificação '
     'é estática e ainda exige simulação com o corpo, rig e movimentos.\n\n'
     if generation.get('petticoatSimulationCages') else '')+
    ('As meias receberam uma transição contínua de calcanhar e peito do pé, '
     'pontas arredondadas e ajuste do eixo das pernas às medidas das botas do '
     'mestre inteiro. Essas medidas não extraem nem alteram sua geometria. '
     'O formato das áreas ocultas é inferido; o teste estático de topologia '
     'não valida encaixe completo nas botas, UV final, rig ou colisões.\n\n'
     if generation.get('stockingAnatomyConstruction') else '')+
    ('Os reforços das ligas receberam volume arredondado, costuras curvas com '
     'pontos em geometria, faixas superiores e laços laterais com fitas planas. '
     'Os detalhes seguem os suportes das meias no editável; as bordas originais '
     'dos reforços foram preservadas. O UV e os vínculos foram medidos, mas '
     'a tensão do tecido, as rendas e a resposta em movimento continuam '
     'pendentes de refinamento e validação.\n\n'
     if generation.get('garterCupConstruction') else '')+
    ('Os painéis frontais dos reforços foram abaulados e receberam pequenos '
     'vincos diagonais. A malha de quadriláteros ganhou amostras verticais; '
     'fios e laços foram transferidos pelas coordenadas das faces reais do '
     'tecido anterior. As duas bordas e as faixas superiores mantêm sua '
     'geometria, conferida no editável. Esses volumes ainda exigem comparação '
     'fina com a foto, ajuste ao corpo e testes de deformação e colisão.\n\n'
     if generation.get('garterCupDrapeConstruction') else '')+
    ('O cinto das ligas recebeu uma faixa central mais estreita, franzidos '
     'menores e babados ligados às suas bordas reais. '
     'Duas costuras contínuas seguem o mesmo suporte fino de Cloth. '
     'O encontro das tiras foi preservado e os vínculos foram refeitos; '
     'proporções, encaixe no corpo, rig e resposta em movimento continuam em revisão.\n\n'
     if generation.get('garterBeltGatherConstruction') else '')+
    ('A renda inferior das ligas usa fios claros do recorte original, '
     'reconstruídos com seção arredondada, pontas fechadas e UVs próprios. '
     'Uma trama fina inferida cobre as regiões sombreadas; as sombras da foto '
     'não se tornam grandes vazados recortados. A união segue o babado real. '
     'Esses fios já têm volume, portanto não recebem espessura adicional dos '
     'Geometry Nodes. Desenho, densidade, dobras, escala e partes ocultas '
     'continuam em revisão nas quatro vistas, sem aprovação de fidelidade, '
     'LOD final, rig ou colisões. O diagnóstico e os caminhos estão nesta pasta.\n\n'
     if generation.get('garterLaceThreadRefinement') else '')+
    ('A renda inferior do cinto foi subdividida ainda plana, antes de envolver '
     'o contorno franzido. Seus vazados e UVs próprios foram preservados. '
     'O auditador mede também pontos ao longo das bordas da renda para impedir '
     'que segmentos retos atravessem a curvatura entre vértices aparentemente '
     'unidos ao babado. Essa medida é de repouso, sem aprovação de movimento.\n\n'
     if generation.get('garterLaceSurfaceRefinement') else '')+
    'O add-on fornecido pelo usuário é Bystedts Cloth Builder 1.0.1, de Daniel '
    'Bystedt. O arquivo editável contém os grupos originais Post sim cloth / '
    'Solidify / UV unwrap solidified. A cópia carregada recebe a adaptação '
    'FLOAT2 de UV para Blender 5.2; o pacote original não foi alterado. '
    'A licença e o pacote original estão no scanner3d-platform em '
    'blender/addons/bystedts-cloth-builder.\n\n'
    'Quando listado no checkpoint, o exterior inteiro é vinculado ao arquivo '
    'alice-vestido-chapeleiro.blend já existente na mesma pasta do editável. '
    'Conservar os dois arquivos juntos; isso preserva geometria e texturas '
    'sem duplicar o mestre dentro da fundação.\n\n'
    'A foto original desta etapa, os quatro renders e os hashes estão juntos '
    'nesta pasta. Flores/sombras visíveis orientam o traçado, mas a repetição '
    'ao redor da peça e as superfícies não visíveis são inferidas.\n\n'
    'Pendências observadas:\n\n'+''.join('- '+v+'\n' for v in comparison['visibleDifferences'])+
    '\nNão iniciar outra versão antes de terminar todas as camadas e o rig do Chapeleiro.\n',encoding='utf-8')
print(json.dumps({'model':report['model'],'editable':report['editable'],
                  'wholeModelUnchanged':True,'fidelityVerified':False},ensure_ascii=False))

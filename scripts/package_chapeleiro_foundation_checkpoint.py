"""Publish reviewed partial internals alongside, without replacing, the whole GLB."""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--comparison', required=True)
parser.add_argument('--audit', required=True)
parser.add_argument('--game', required=True)
args = parser.parse_args()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
generation = json.loads(Path(args.generation).read_text(encoding='utf-8'))
comparison = json.loads(Path(args.comparison).read_text(encoding='utf-8'))
audit = json.loads(Path(args.audit).read_text(encoding='utf-8'))
if (audit['editableBlendSha256'] != generation['editableBlendSha256']
        or not audit.get('savedModelUnchanged')
        or len(audit.get('actualApertureAudit',[])) != 4
        or len(audit.get('carrierTranslationProbe',[])) != 80
        or any(p['p95TranslationError'] > .001 for p in audit['carrierTranslationProbe'])):
    raise ValueError('Requires the actual geometric-aperture and carrier-translation audit.')
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
model = Path(comparison['displayModel']['file'])
binary = model.read_bytes()
if binary[:4] != b'glTF' or len(binary) >= 100_000_000:
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
for name, artifact in comparison['renders'].items():
    copy(artifact['file'],docs/(name+'.png'))
if sha(complete)!=complete_hash:
    raise ValueError('The whole dressed gallery item must remain unchanged.')
report={'variant':'alice_chapeleiro','stage':'alice_chapeleiro_stage_01',
        'status':'needs_refinement','sourcePhoto':'Docs/alice-variants/chapeleiro/foundation/source_photo.png',
        'sourcePhotoSha256':generation['sourcePhotoSha256'],'method':generation['method'],
        'model':{'file':model_path.relative_to(game).as_posix(),'sha256':sha(model_path),
                 'bytes':model_path.stat().st_size,'triangles':triangles,'meshes':len(gltf['meshes']),
                 'joints':0,'animations':[]},
        'editable':{'file':blend_path.relative_to(game).as_posix(),'sha256':sha(blend_path),
                    'bytes':blend_path.stat().st_size},
        'completeExteriorVerticesUnchanged':True,'completeGalleryModelSha256Unchanged':complete_hash,
        'addon':{'name':generation['addon'],'author':generation['author'],
                 'version':generation['addonVersion'],'originalAssetSha256':generation['originalAssetSha256']},
        'newInternalPieces':generation['pieces'],'visibleDifferences':comparison['visibleDifferences'],
        'attachmentAudit':{'file':'Docs/alice-variants/chapeleiro/foundation/carrier_audit.json',
                           'sha256':sha(args.audit),'frame':1,'verifiedFollowers':80,
                           'actualApertureAudit':audit['actualApertureAudit'],
                           'dynamicSimulationVerified':False},
        'additionalCreditsConsumed':0,'fidelityVerified':False,'allLayersFinished':False,
        'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False,'nextVariantMayStart':False}
(docs/'checkpoint.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(docs/'README.md').write_text(
    '# Chapeleiro: fundação da ficha 1 em refinamento\n\n'
    'Anáguas internas novas, renda floral com aberturas em geometria e corsete '
    'com canais, fechos, ilhoses e cruzamentos traseiros. O GLB do vestido '
    'completo permanece inteiro no seu item original. As rendas acompanham '
    'os respectivos suportes no arquivo Blender por Surface Deform; isso '
    'ainda não valida rig, simulação em gameplay ou colisões.\n\n'
    'O add-on fornecido pelo usuário é Bystedts Cloth Builder 1.0.1, de Daniel '
    'Bystedt. O arquivo editável contém os grupos originais Post sim cloth / '
    'Solidify / UV unwrap solidified. A cópia carregada recebe a adaptação '
    'FLOAT2 de UV para Blender 5.2; o pacote original não foi alterado. '
    'A licença e o pacote original estão no scanner3d-platform em '
    'blender/addons/bystedts-cloth-builder.\n\n'
    'A foto original desta etapa, os quatro renders e os hashes estão juntos '
    'nesta pasta. Flores/sombras visíveis orientam o traçado, mas a repetição '
    'ao redor da peça e as superfícies não visíveis são inferidas.\n\n'
    'Pendências observadas:\n\n'+''.join('- '+v+'\n' for v in comparison['visibleDifferences'])+
    '\nNão iniciar outra versão antes de terminar todas as camadas e o rig do Chapeleiro.\n',encoding='utf-8')
print(json.dumps({'model':report['model'],'editable':report['editable'],
                  'wholeModelUnchanged':True,'fidelityVerified':False},ensure_ascii=False))

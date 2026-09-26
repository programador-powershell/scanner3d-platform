"""Publish one reviewed partial rig and its real evidence as portable Git files."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--comparison', required=True)
parser.add_argument('--motion', required=True)
parser.add_argument('--rig-audit', required=True)
parser.add_argument('--preview', required=True)
parser.add_argument('--destination', required=True)
args = parser.parse_args()
read = lambda file: json.loads(Path(file).read_text(encoding='utf-8'))
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
write = lambda file, value: Path(file).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
generation, comparison, motion, audit = (read(file) for file in
                                       [args.generation, args.comparison, args.motion, args.rig_audit])
preview_path = Path(args.preview)
preview = read(preview_path / 'stage_comparisons.json')
if len(preview['stages']) != 1:
    raise ValueError('Publish only the currently reviewed stage.')
stage = preview['stages'][0]
stage_id = stage['id']
if not re.fullmatch(r'alice_[a-z]+_stage_\d{2}', stage_id):
    raise ValueError('Unsafe stage directory.')
if (generation.get('reusedGeometry') is not False or not generation.get('rigPresent')
        or comparison['status'] != 'needs_refinement'
        or not audit['allComponentsSkinned'] or not audit['allRequiredClipsPresent']):
    raise ValueError('Requires reviewed new geometry with all actual components skinned.')
model_sha = generation['modelSha256']
if {model_sha, sha(generation['model']), comparison['modelSha256'], motion['modelSha256'],
        audit['modelSha256'], stage['comparison']['displayModel']['sha256']} != {model_sha}:
    raise ValueError('All evidence must concern the exact same exported animated GLB.')
if sha(generation['editableBlend']) != generation['editableBlendSha256'] or audit['blendSha256'] != generation['editableBlendSha256']:
    raise ValueError('The editable shared rig changed.')
photo_sha = generation['sourcePhotoSha256']
if {photo_sha, sha(generation['sourcePhoto']), comparison['sourcePhotoSha256'],
        motion['sourcePhotoSha256'], audit['sourcePhotoSha256'], stage['sourcePhotoSha256']} != {photo_sha}:
    raise ValueError('Mixed photographs from different layers are not permitted.')
destination = Path(args.destination).resolve()
manifest = destination / 'stage_comparisons.json'
plan = read(manifest)
if not any(s['id'] == stage_id for s in plan['stages']):
    raise ValueError('This stage does not exist in the repository inventory.')
target = destination / stage_id
target.mkdir(parents=True, exist_ok=True)

def copy(source, digest, name):
    if sha(source) != digest:
        raise ValueError('Changed evidence: ' + str(source))
    file = target / name
    file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, file)
    return {'file': (Path(stage_id) / name).as_posix(), 'sha256': digest}

copy(generation['sourcePhoto'], photo_sha, Path(stage['sourcePhoto']).name)
copy(generation['model'], model_sha, 'inspection.glb')
copy(comparison['comparisonBoard']['file'], comparison['comparisonBoard']['sha256'], 'photo_vs_geometry.jpg')
editable = copy(generation['editableBlend'], generation['editableBlendSha256'], 'editable.blend')
renders = {name: copy(artifact['file'], artifact['sha256'], name + '.png')
           for name, artifact in comparison['renders'].items()}
motion['sourcePhoto'] = (Path(stage_id) / Path(stage['sourcePhoto']).name).as_posix()
for clip in motion['clips']:
    for pose in clip['poses']:
        artifact = copy(pose['render'], pose['renderSha256'], 'motion_review/' + Path(pose['render']).name)
        pose['render'] = artifact['file']
motion['contactBoard'] = copy(motion['contactBoard']['file'], motion['contactBoard']['sha256'], 'photo_vs_skin_motion.jpg')
motion['status'] = 'needs_refinement'
motion['visualReviewPerformed'] = True
motion['visibleDifferences'] = comparison['visibleDifferences']
write(target / 'motion_comparison.json', motion)
write(target / 'rig_audit.json', audit)
bind_file = Path(generation['editableBlend']).parent / 'shared_rig_bind.json'
bind = copy(bind_file, sha(bind_file), 'shared_rig_bind.json')
checkpoint = {'variant': stage['variant'], 'stageId': stage_id,
              'version': Path(generation['editableBlend']).parent.name,
              'status': 'needs_refinement', 'sourcePhoto': Path(stage['sourcePhoto']).name,
              'sourcePhotoSha256': photo_sha, 'studioModelId': generation['studioModelId'],
              'geometryParentSha256': generation['geometryParentSha256'],
              'reconstructionModelSha256': model_sha, 'displayModel': stage['comparison']['displayModel'],
              'editableBlend': editable, 'sharedRigBind': bind,
              'detailScriptSha256': generation['detailScriptSha256'], 'rigScriptSha256': generation['rigScriptSha256'],
              'bodyConstruction': generation['bodyConstruction'], 'componentAudit': generation['componentAudit'],
              'skinAudit': generation['skinAudit'], 'rigSources': [dict(s, file=Path(s['file']).name) for s in generation['rigSources']],
              'exportAudit': generation['exportAudit'], 'actualFourViewReview': comparison['visibleDifferences'],
              'motionComparison': {'file': stage_id + '/motion_comparison.json', 'sha256': sha(target / 'motion_comparison.json')},
              'rigAudit': {'file': stage_id + '/rig_audit.json', 'sha256': sha(target / 'rig_audit.json')},
              'rigPresent': True, 'countsAsFinishedLayer': False, 'fidelityVerified': False,
              'motionVerified': False, 'clothCollisionVerified': False, 'nextVariantMayStart': False,
              'additionalCreditsConsumed': 0, 'originalTripoCreditsConsumed': generation['creditsConsumed'],
              'premiumFeaturesUsed': False, 'artifacts': renders, 'limitations': generation['limitations']}
write(target / 'checkpoint.json', checkpoint)
plan['stages'] = [stage if s['id'] == stage_id else s for s in plan['stages']]
write(manifest, plan)
print(json.dumps({'publishedStage': stage_id, 'components': len(audit['components']),
                  'rigPresent': True, 'motionVerified': False, 'completed': False}))

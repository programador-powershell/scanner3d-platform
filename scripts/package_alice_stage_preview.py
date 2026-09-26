"""Package selected partial stages for a portable viewer, preserving original hashes."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--plan', required=True)
parser.add_argument('--stage', action='append', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
out = Path(args.output)
if (out / 'stage_comparisons.json').exists():
    raise ValueError('Use a new preview directory; do not overwrite previous evidence.')
out.mkdir(parents=True, exist_ok=True)
stages = []
for selected in args.stage:
    stage = copy.deepcopy(next(s for s in plan['stages'] if s['id'] == selected))
    evidence = stage.get('comparison')
    if not evidence or evidence.get('reusedGeometry') is not False or evidence['sourcePhotoSha256'] != stage['sourcePhotoSha256']:
        raise ValueError('A fresh model with the same stage photograph is required.')
    def package(file, expected, name):
        source = Path(file)
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Changed evidence: {source.name}')
        target = out / selected / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return target.relative_to(out).as_posix()
    stage['sourcePhoto'] = package(stage['sourcePhoto'], stage['sourcePhotoSha256'], 'source_photo' + Path(stage['sourcePhoto']).suffix)
    for key, name in [('displayModel', 'inspection.glb'), ('board', 'photo_vs_geometry.jpg')]:
        artifact = evidence[key]
        artifact['file'] = package(artifact['file'], artifact['sha256'], name)
    stage['fidelityVerified'] = False
    stages.append(stage)
preview = {key: plan[key] for key in ['comparisonPolicy', 'freshGeometryPolicy', 'motionPolicy']}
preview.update(status='partial_preview', completed=False, fidelityVerified=False, stages=stages,
               scope='Selected partial studies only; the complete six-variant inventory remains local.')
(out / 'stage_comparisons.json').write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'packagedStages': len(stages), 'completed': False}))

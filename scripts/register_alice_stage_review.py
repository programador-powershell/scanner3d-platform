"""Publish one actually rendered stage comparison, preserving visible failures."""
import argparse
import hashlib
import json
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--plan',required=True)
parser.add_argument('--comparison',required=True)
parser.add_argument('--generation',required=True)
parser.add_argument('--difference',action='append',required=True)
parser.add_argument('--verdict',choices=['rejected_fidelity','needs_refinement'],required=True)
parser.add_argument('--part-only',action='store_true',help='Review an isolated component without replacing the complete stage.')
args=parser.parse_args()
plan_path=Path(args.plan);plan=json.loads(plan_path.read_text(encoding='utf-8'))
comparison=json.loads(Path(args.comparison).read_text(encoding='utf-8'))
generation=json.loads(Path(args.generation).read_text(encoding='utf-8'))
stage=next(s for s in plan['stages'] if s['id']==comparison['stageId'])
if (comparison.get('reviewScope')=='selected_internal_components')!=args.part_only:
    raise ValueError('Isolated component reviews must explicitly preserve the complete stage.')
sha=lambda file:hashlib.sha256(Path(file).read_bytes()).hexdigest()
if generation['reusedGeometry'] is not False or generation['status']!='generated_awaiting_visual_review':
    raise ValueError('Only actual fresh geometry can enter the stage viewer.')
if comparison['sourcePhotoSha256']!=stage['sourcePhotoSha256'] or generation['sourcePhotoSha256']!=stage['sourcePhotoSha256']:
    raise ValueError('Model, comparison and stage must share the exact original photo.')
if sha(stage['sourcePhoto'])!=stage['sourcePhotoSha256'] or comparison['modelSha256']!=generation['modelSha256']:
    raise ValueError('Source photo or inferred model identity does not match.')
for artifact in [comparison['displayModel'],comparison['comparisonBoard'],*comparison['renders'].values()]:
    if sha(artifact['file'])!=artifact['sha256']:raise ValueError('Comparison artifact changed.')
comparison['status']=args.verdict;comparison['visibleDifferences']=args.difference
Path(args.comparison).write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
if args.part_only:
    print(json.dumps({'stage':stage['id'],'part':comparison['selectedRolePrefix'],
                      'status':args.verdict,'fidelityVerified':False,'stageUnchanged':True}))
    raise SystemExit(0)
stage.update(status=args.verdict,fidelityVerified=False,
    review={'verdict':args.verdict,'visibleDifferences':args.difference},
    comparison={'reusedGeometry':False,'sourcePhotoSha256':stage['sourcePhotoSha256'],
                'displayModel':comparison['displayModel'],'board':comparison['comparisonBoard'],
                'modelSha256':comparison['modelSha256'],'method':generation['method'],'frontAxis':comparison['frontAxis']})
plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'stage':stage['id'],'status':args.verdict,'fidelityVerified':False}))

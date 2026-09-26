"""Measure the supplied motion bones for new foundation tailoring; discard meshes."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fbx',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source=Path(args.fbx)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(source))
rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
if len(rigs)!=1:
    raise ValueError('Expected one motion skeleton.')
rig=rigs[0]
discarded=[o for o in list(bpy.context.scene.objects) if o!=rig]
for obj in discarded:
    bpy.data.objects.remove(obj,do_unlink=True)
rig.data.pose_position='REST'
scale=.685
offset=Vector((0,.002,0))
bones={b.name.split(':')[-1]:{'head':list((rig.matrix_world@b.head_local)*scale+offset),
        'tail':list((rig.matrix_world@b.tail_local)*scale+offset)} for b in rig.data.bones}
required=['Hips','LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase',
          'RightUpLeg','RightLeg','RightFoot','RightToeBase']
if any(n not in bones for n in required):
    raise ValueError('Missing actual lower-body motion bones.')
report={'sourceFbx':str(source.resolve()),'sourceFbxSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'scale':scale,'offset':list(offset),'bones':bones,'discardedNonRigObjects':len(discarded),
        'foreignCharacterGeometryUsed':False,'purpose':'rest-bone measurements only; garment fit still requires visual review'}
Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ALICE_LOWER_BONE_MEASUREMENTS',json.dumps({n:bones[n] for n in required}),flush=True)

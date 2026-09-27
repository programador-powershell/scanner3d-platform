"""Export the actual waist skin, excluding unrelated authoring solver evaluation.

The 229 exported previews have only Armature modifiers. Keep the full checkpoint
on disk and mute modifiers only on excluded authoring objects in export memory.
"""
import argparse
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
path, out = Path(a.generation), Path(a.output)
g = read(path)
ref = Path(g['authoringReferenceRoot'])
waist = read(g['waistSkinRefinement'])
assert sha(g['editableBlend']) == g['editableBlendSha256'] == waist['editableBlendSha256']
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rigs = [o for o in scene.objects if o.type == 'ARMATURE']
assert len(rigs) == 1 and len(rigs[0].data.bones) == 173
rig = rigs[0]
pieces = [bpy.data.objects[p['mesh']] for p in read(ref / 'skin_audit.json')['pieces'][:-1]]
assert len(pieces) == 229
assert all(len(o.modifiers) == 1 and o.modifiers[0].type == 'ARMATURE' and o.modifiers[0].object == rig for o in pieces)
selected = {rig, *pieces}
muted = []
for collection in bpy.data.collections:
    collection.hide_viewport = False
for obj in scene.objects:
    obj.hide_viewport = obj not in selected
    if obj in selected:
        obj.hide_set(False)
    else:
        for modifier in obj.modifiers:
            if modifier.show_viewport:
                muted.append({'object': obj.name, 'modifier': modifier.name, 'type': modifier.type})
                modifier.show_viewport = False
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.animation_data.action = None
for pose in rig.pose.bones:
    pose.matrix_basis = Matrix.Identity(4)
scene.frame_set(1)
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for obj in selected:
    obj.select_set(True)
model = out / 'foundation_shared_rig_study.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                         export_yup=True, export_animations=True, export_animation_mode='NLA_TRACKS', export_frame_range=False)
raw = model.read_bytes()
length = struct.unpack_from('<I', raw, 12)[0]
doc = json.loads(raw[20:20 + length])
assert len([n for n in doc['nodes'] if 'mesh' in n and 'skin' in n]) == 229
assert len(doc['skins']) == 1 and len(doc['skins'][0]['joints']) == 173
assert [a['name'] for a in doc['animations']] == g['exports']['foundation']['actualClips']
assert sha(g['editableBlend']) == g['editableBlendSha256']
entry = {**g['exports']['foundation'], 'model': str(model), 'modelSha256': sha(model), 'bytes': model.stat().st_size}
report = {**g, 'exports': {**g['exports'], 'foundation': entry}, 'parentGeneration': str(path),
          'exportsInheritedForReferenceOnly': False, 'modelExportedInThisRefinement': True,
          'wholeExportInheritedUnchanged': True, 'scriptSha256': sha(__file__),
          'actualSelectedModifierTypes': ['ARMATURE'], 'excludedAuthoringModifiersMutedInExportMemoryOnly': muted,
          'fullEditableCheckpointNotSavedOrTrimmedByExport': True,
          'allLayersFinished': False, 'fidelityVerified': False, 'motionVerified': False,
          'clothCollisionVerified': False, 'finalFbxExported': False, 'nextVariantMayStart': False,
          'publicationStatus': 'local_export_pending_actual_reimport_and_photo_review',
          'physicalSpringStudyNotBakedIntoExport': True, 'sourcePhotoComparisonAndExportReimportPending': True,
          'limitation': 'Only bloomer waist skin weights changed. Five original study actions are preserved; new spring cloth and Surface Deform diagnostic trajectories are not baked into this GLB.'}
(out / 'generation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_export.py')
print('ACTUAL_BLOOMER_WAIST_SKIN_EXPORTED', model.stat().st_size, sha(model), flush=True)

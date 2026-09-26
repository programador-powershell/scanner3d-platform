"""Save a portable working copy without duplicating the immutable bake master."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
file = Path(args.generation)
record = json.loads(file.read_text(encoding='utf-8'))
original = Path(record['editableBlend'])
if hashlib.sha256(original.read_bytes()).hexdigest() != record['editableBlendSha256']:
    raise ValueError('Changed baked checkpoint.')
bpy.ops.wm.open_mainfile(filepath=str(original))
for obj in list(bpy.context.scene.objects):
    if obj.type == 'MESH' and obj.hide_render:
        bpy.data.objects.remove(obj, do_unlink=True)
# Release only unused in-memory data in this new copy, not any source file.
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
target = original.parent / 'chapeleiro_whole_baked_working.blend'
if target.exists():
    raise ValueError('Working copy already exists.')
bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True)
if target.stat().st_size >= 100 * 1024 * 1024:
    raise ValueError('Working copy exceeds plain GitHub per-file limit.')
record['archivedBakeScene'] = str(original)
record['archivedBakeSceneSha256'] = record['editableBlendSha256']
record['editableBlend'] = str(target)
record['editableBlendSha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
record['optimizationAudit']['limitations'] = ['Collapse reduction is a first candidate, not anatomical retopology.',
    'High-to-low 4K PBR maps baked; projection artifacts and close-ups still need review.',
    'No rig, internal layers or collision approval implied.']
file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('PORTABLE_BAKED_WORKING_COPY', target.stat().st_size)

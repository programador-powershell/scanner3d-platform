"""Import a newly downloaded full Tripo GLB, retaining its source and materials."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
generation_path = Path(args.generation)
generation = json.loads(generation_path.read_text(encoding='utf-8'))
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
if generation['status'] != 'generated_awaiting_visual_review' or generation['reusedGeometry'] is not False:
    raise ValueError('A verified newly downloaded full-model generation is required.')
if not generation.get('studioModelId') or generation['creditsConsumed'] > generation['creditsDisplayedBeforeSubmission']:
    raise ValueError('Missing new Studio task identity or unexpected credit spend.')
if sha(generation['sourcePhoto']) != generation['sourcePhotoSha256']:
    raise ValueError('Original full-outfit photo changed.')
for view in generation['sourceViews']:
    if sha(view['file']) != view['sha256']:
        raise ValueError('Generation input view changed.')
model = Path(generation['model'])
if model.suffix.lower() != '.glb' or sha(model) != generation['modelSha256']:
    raise ValueError('Downloaded GLB changed or is missing.')
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
if any(out.iterdir()):
    raise ValueError('Use a new Blender import directory; previous evidence is immutable.')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(model))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
if not meshes:
    raise ValueError('Downloaded GLB contains no actual geometry.')
points = [obj.matrix_world @ v.co for obj in meshes for v in obj.data.vertices]
minimum = Vector(tuple(min(point[i] for point in points) for i in range(3)))
maximum = Vector(tuple(max(point[i] for point in points) for i in range(3)))
if min(maximum - minimum) <= 1e-5:
    raise ValueError('Expected volumetric character geometry.')
scene = bpy.context.scene
scene['alice_variant'] = generation['variant']
scene['studio_model_id'] = generation['studioModelId']
scene['source_photo_sha256'] = generation['sourcePhotoSha256']
scene['source_glb_sha256'] = generation['modelSha256']
scene['fidelity_verified'] = False
scene['motion_verified'] = False
# Keep imported topology, materials, UVs and textures. Layer reconstruction and
# rigging are separate work; a successful import never marks them as completed.
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type == 'VIEW_3D':
        area.spaces.active.clip_start = 0.001
        area.spaces.active.clip_end = max(100, (maximum - minimum).length * 20)
        area.spaces.active.region_3d.view_location = (minimum + maximum) / 2
        area.spaces.active.region_3d.view_distance = (maximum - minimum).length * 1.4
        area.spaces.active.shading.type = 'MATERIAL'
editable = out / 'chapeleiro_full_imported.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
report = {
    'variant': generation['variant'], 'studioModelId': generation['studioModelId'],
    'sourcePhotoSha256': generation['sourcePhotoSha256'], 'modelSha256': generation['modelSha256'],
    'editableBlend': str(editable), 'editableBlendSha256': sha(editable),
    'blenderVersion': bpy.app.version_string,
    'meshCount': len(meshes),
    'vertices': sum(len(obj.data.vertices) for obj in meshes),
    'triangles': sum(sum(max(0, len(face.vertices) - 2) for face in obj.data.polygons) for obj in meshes),
    'materialCount': len({material.name for obj in meshes for material in obj.data.materials if material}),
    'armatureCount': sum(obj.type == 'ARMATURE' for obj in bpy.context.scene.objects),
    'bounds': {'min': list(minimum), 'max': list(maximum)},
    'status': 'imported_full_model_awaiting_layer_refinement_and_rig',
    'fidelityVerified': False, 'motionVerified': False, 'allLayersFinished': False,
    'components': [{'name': obj.name, 'vertices': len(obj.data.vertices),
                    'polygons': len(obj.data.polygons),
                    'hasUV': bool(obj.data.uv_layers),
                    'materials': [material.name for material in obj.data.materials if material]}
                   for obj in meshes],
}
(out / 'import.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
generation['editableBlend'] = str(editable)
generation['editableBlendSha256'] = report['editableBlendSha256']
generation['originalDownloadedModelSha256'] = generation.get('originalDownloadedModelSha256', generation['modelSha256'])
generation['localWorkStatus'] = report['status']
generation_path.write_text(json.dumps(generation, ensure_ascii=False, indent=2), encoding='utf-8')
print('NEW_TRIPO_FULL_MODEL_IMPORTED', json.dumps({key: report[key] for key in
    ['variant', 'meshCount', 'vertices', 'triangles', 'materialCount', 'armatureCount', 'status']}))

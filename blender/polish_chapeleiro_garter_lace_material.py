"""Give the actual traced garter lace cotton shading, preserving all geometry."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy
import numpy as np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
for field in ['model','editableBlend','sourcePhoto']:
    if sha(parent[field])!=parent[field+'Sha256']:raise ValueError('Changed actual parent evidence.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve each prior actual comparison.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    path=Path(parent['editableBlend']).parent/dependency['file']
    if sha(path)!=dependency['sha256']:raise ValueError('Changed intact exterior library.')
    shutil.copyfile(path,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene;scene.frame_set(1)
def geometry_hash(obj):
    points=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',points)
    return hashlib.sha256(points.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
meshes=[o for o in scene.objects if o.type=='MESH']
before={o.name:geometry_hash(o) for o in meshes}
lace=bpy.data.objects[parent['garterBeltGatherConstruction']['lowerPhotographicLace']]
previous=[m.name for m in lace.data.materials]
material=bpy.data.materials['Foundation / warm ivory cotton'].copy()
material.name='Photo 1 / garter belt needle cotton / scene lighting'
lace.data.materials.clear();lace.data.materials.append(material)
if any(geometry_hash(o)!=before[o.name] for o in meshes):raise ValueError('A raw garment or exterior mesh changed.')
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_garter_belt_cotton.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
objects=[o for o in meshes if o.get('constructedNewInternalLayer')]
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
model=out/'foundation_garter_belt_cotton.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_apply=True,
                         export_yup=True,export_animations=False)
construction=dict(parent['garterBeltGatherConstruction'])
construction['lowerLaceMaterial']='cotton weave; photograph contours and UV retained without baked photographic lighting'
report={**parent,'method':'own_photo_garter_belt_with_cotton_shading_and_preserved_photographic_apertures',
    'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
    'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),
    'garterBeltGatherConstruction':construction,
    'cumulativeGarterBeltConstruction':{'inheritedInternalPieces':parent['inheritedInternalPieces'],
        'addedInternalPieces':parent['addedInternalPieces'],'refinedInternalPieces':parent['refinedInternalPieces'],
        'changedExistingRawMeshes':parent['changedExistingRawMeshes']},
    'inheritedInternalPieces':len(objects),'addedInternalPieces':0,'refinedInternalPieces':0,
    'changedExistingRawMeshes':[],'existingCagesUnchanged':True,
    'laceCottonMaterialRefinement':{'mesh':lace.name,'previousMaterials':previous,'actualMaterial':material.name,
        'allActualRawGeometryUnchanged':True,'photographicColorAndNormalLightingRemoved':True,
        'actualPhotoLaceUvsAndAperturesRetained':True,'visualFidelityVerified':False},
    'additionalCreditsConsumed':0,'fidelityVerified':False,'rigPresent':False,'motionVerified':False,
    'clothCollisionVerified':False,'allLayersFinished':False,'nextVariantMayStart':False}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACTUAL_GARTER_LACE_COTTON_CHECKPOINT_SAVED',len(objects),flush=True)

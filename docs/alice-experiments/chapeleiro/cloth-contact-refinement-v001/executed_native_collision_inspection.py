"""Read installed collision RNA and the actual immutable garment carriers."""
import hashlib, json, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix

root = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
generation = json.loads((root/'foundation_shared_rig_v095/generation.json').read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(generation['editableBlend']) == generation['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=generation['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
for bone in rig.pose.bones: bone.matrix_basis = Matrix.Identity(4)
sys.path.insert(0, str(Path(__file__).parent.parent/'scanner3d-platform/blender'))
from chapeleiro_cloth_colliders import thin_underlayer_colliders
audit = json.loads((Path(generation['authoringReferenceRoot'])/'skin_audit.json').read_text())
names = ['01 / left stocking / fitted leg ankle and closed toe',
         '01 / right stocking / fitted leg ankle and closed toe',
         '01 / bloomers / continuous waist and sewn crotch']
objects, rows = thin_underlayer_colliders(scene, audit, names, rig)
for collection in bpy.data.collections: collection.hide_viewport = False
for obj in scene.objects:
    obj.hide_viewport = obj not in [rig, *objects]
    if obj in [rig, *objects]: obj.hide_set(False)
for obj, row in zip(objects, rows):
    obj.modifiers.new('Read native defaults', 'COLLISION')
    obj.collision.thickness_outer = obj.collision.thickness_inner = .0008
    obj.collision.cloth_friction = 5
    settings = {}
    for prop in obj.collision.bl_rna.properties:
        key = prop.identifier
        if key == 'rna_type' or prop.type not in {'BOOLEAN','INT','FLOAT','STRING','ENUM'}: continue
        value = getattr(obj.collision,key)
        settings[key] = {'value': list(value) if prop.is_array else value, 'description': prop.description}
    row['actualInstalledCollisionSettings'] = settings
    row['modifierOrder'] = [m.type for m in obj.modifiers]
scene.frame_set(1)
bpy.context.view_layer.update()
for obj,row in zip(objects,rows):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh(); mesh.calc_loop_triangles()
    xyz = np.asarray([tuple(ev.matrix_world @ v.co) for v in mesh.vertices])
    triangles = np.asarray([tuple(t.vertices) for t in mesh.loop_triangles])
    tri = xyz[triangles]
    row['boundsMeters'] = [xyz.min(0).tolist(),xyz.max(0).tolist()]
    row['signedOpenSurfaceVolumeNotClosedInsideProof'] = float(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()/6)
    row['sourceScale'] = list(obj.scale)
    ev.to_mesh_clear()
report = {'actualBlenderVersion':bpy.app.version_string,'actualBlenderBuildHash':bpy.app.build_hash.decode(),
          'fps':scene.render.fps,'fpsBase':scene.render.fps_base,'unitSystem':scene.unit_settings.system,
          'scaleLength':scene.unit_settings.scale_length,'gravity':list(scene.gravity),'colliders':rows,
          'sourceEditableSha256':generation['editableBlendSha256'],
          'sourceEditableUnchanged':sha(generation['editableBlend'])==generation['editableBlendSha256'],
          'noSimulationRun':True,'notFidelityOrCollisionApproval':True}
output=root/'native_collision_settings_v001.json'
assert not output.exists()
output.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
print(json.dumps(report,indent=2))

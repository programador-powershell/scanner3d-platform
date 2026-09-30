"""Study two individual-fiber rear braids on the complete dressed Alice."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy
import cv2
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p = argparse.ArgumentParser()
p.add_argument('--generation', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--fibers-per-tress', type=int, default=250)
p.add_argument('--braid-melanin', type=float, default=.87)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert not a.output.exists() and 24 <= a.fibers_per_tress <= 500 and .55 <= a.braid_melanin <= .95

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()

g = json.loads(a.generation.read_text(encoding='utf-8'))
assert sha(g['editableBlend']) == g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
scene.frame_set(1)
hair = next(o for o in scene.objects if o.type == 'CURVES' and 'individual hair fibers' in o.name)
original_count = len(hair.data.curves)
assert original_count == 101424
whole = bpy.data.objects['Chapeleiro / intact whole exterior / skin study']
whole.data.calc_loop_triangles()
surface = BVHTree.FromPolygons([whole.matrix_world@v.co for v in whole.data.vertices],
                               [list(tri.vertices) for tri in whole.data.loop_triangles],
                               all_triangles=True)
closed_head = bpy.data.objects['Chapeleiro / reconstructed closed head interior / review']
closed_head.data.calc_loop_triangles()
head_surface = BVHTree.FromPolygons([closed_head.matrix_world@v.co for v in closed_head.data.vertices],
                                    [list(tri.vertices) for tri in closed_head.data.loop_triangles],
                                    all_triangles=True)
hair_inv = np.asarray(hair.matrix_world.inverted(), np.float64)
evaluated = hair.evaluated_get(bpy.context.evaluated_depsgraph_get())
controls = np.empty(len(evaluated.data.points)*3, np.float32)
evaluated.data.attributes['position'].data.foreach_get('vector', controls)
controls = controls.reshape(len(evaluated.data.curves), -1, 3)[::4, ::2].reshape(-1, 3)
transform = np.asarray(evaluated.matrix_world, np.float32)
world_controls = controls @ transform[:3, :3].T + transform[:3, 3]
grid_step = .0005
grid_x0, grid_z0 = -.16, .78
grid = np.full((400, 640), -1, np.float32)
gx = np.floor((world_controls[:, 0]-grid_x0)/grid_step).astype(np.int32)
gz = np.floor((world_controls[:, 2]-grid_z0)/grid_step).astype(np.int32)
valid = (gx >= 0) & (gx < grid.shape[1]) & (gz >= 0) & (gz < grid.shape[0])
np.maximum.at(grid, (gz[valid], gx[valid]), world_controls[valid, 1])
grid = cv2.dilate(grid, np.ones((7, 7), np.uint8))

count = 2*3*a.fibers_per_tress
points_per_fiber = 96
data = bpy.data.hair_curves.new('Chapeleiro / rear braid individual fibers / study')
data.add_curves([points_per_fiber]*count)
data.set_types(type='CATMULL_ROM')
data.surface = hair.data.surface
data.surface_uv_map = hair.data.surface_uv_map
for material in hair.data.materials:
    data.materials.append(material)
braid_material = hair.data.materials[0].copy()
braid_material.name = 'Alice / Chapeleiro rear braid / local contrast study'
shader = next(n for n in braid_material.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfHairPrincipled')
shader.inputs['Melanin'].default_value = a.braid_melanin
shader.inputs['Melanin Redness'].default_value = .07
shader.inputs['Roughness'].default_value = .25
shader.inputs['Radial Roughness'].default_value = .24
shader.inputs['Random Color'].default_value = .08
data.materials.clear()
data.materials.append(braid_material)
obj = bpy.data.objects.new('Chapeleiro / rear braid individual fibers / study', data)
scene.collection.objects.link(obj)
obj.parent = hair.parent
obj.parent_type = hair.parent_type
obj.parent_bone = hair.parent_bone
obj.matrix_parent_inverse = hair.matrix_parent_inverse.copy()
obj.matrix_world = hair.matrix_world.copy()

rng = np.random.default_rng(20260930)
t = np.linspace(0, 1, points_per_fiber, dtype=np.float64)
positions = np.empty((count, points_per_fiber, 3), np.float32)
radii = np.empty((count, points_per_fiber), np.float32)
braid_side = np.empty(count, np.int32)
braid_tress = np.empty(count, np.int32)
index = 0
for side in (-1, 1):
    # Roots tuck under the existing side hair; tips stop beside the ornament.
    x = .018 + side*(.055 - .042*t)
    z = .883 - .020*t + .002*np.sin(np.pi*t)
    emerge = np.clip((t-.08)/.20, 0, 1)**2
    taper = np.clip((1-t)/.12, 0, 1)**2
    braid_window = emerge*taper
    scalp_y = np.empty_like(t)
    for point, (xp, zp) in enumerate(zip(x, z)):
        ix = int((xp-grid_x0)/grid_step)
        iz = int((zp-grid_z0)/grid_step)
        sampled = grid[iz, ix] if 0 <= iz < grid.shape[0] and 0 <= ix < grid.shape[1] else -1
        if sampled > 0:
            exterior_y = sampled
        else:
            hit, _, _, _ = surface.ray_cast(Vector((float(xp), .3, float(zp))), Vector((0, -1, 0)), .5)
            exterior_y = hit.y if hit is not None else .038
        head_hit, _, _, _ = head_surface.ray_cast(Vector((float(xp), .3, float(zp))), Vector((0, -1, 0)), .5)
        scalp_y[point] = max(exterior_y, head_hit.y + .006 if head_hit is not None else exterior_y)
    # World-space shell offset is small at roots and clears the existing hair
    # as the plait emerges; transform it into the shared Head-local coordinates.
    y = scalp_y + .001 + .003*emerge
    for strand in range(3):
        phase = strand*2*np.pi/3 + (0 if side < 0 else np.pi/3)
        helix = 5*np.pi*t + phase
        cord_center_y = y + .0033*braid_window*np.cos(helix)
        cord_center_z = z + .0040*braid_window*np.sin(helix)
        for lane in range(a.fibers_per_tress):
            theta = 2*np.pi*lane/a.fibers_per_tress + rng.normal(0, .028)
            radial = .0018*np.sqrt((lane+.5)/a.fibers_per_tress)
            micro = rng.normal(0, .00011)
            positions[index, :, 0] = x + radial*np.cos(theta)*braid_window + micro*np.sin(8*np.pi*t+theta)*braid_window
            positions[index, :, 1] = cord_center_y + radial*np.sin(theta)*braid_window
            positions[index, :, 2] = cord_center_z + micro*np.cos(6*np.pi*t+theta)*braid_window
            radii[index] = np.maximum(.00000004, .000030*(1-t)**.7)
            braid_side[index] = side
            braid_tress[index] = strand
            index += 1
assert index == count
positions = (positions.astype(np.float64) @ hair_inv[:3, :3].T + hair_inv[:3, 3]).astype(np.float32)
data.attributes['position'].data.foreach_set('vector', positions.ravel())
radius_attr = data.attributes.new('radius', 'FLOAT', 'POINT')
radius_attr.data.foreach_set('value', radii.ravel())
side_attr = data.attributes.new('alice_braid_side', 'INT', 'CURVE')
side_attr.data.foreach_set('value', braid_side)
tress_attr = data.attributes.new('alice_braid_tress', 'INT', 'CURVE')
tress_attr.data.foreach_set('value', braid_tress)
data.update_tag()

a.output.mkdir(parents=True)
blend = a.output/'chapeleiro_complete_rear_braid_strands_study.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
report = dict(g)
report.update(parentGeneration=str(a.generation), editableBlend=str(blend), editableBlendSha256=sha(blend),
              rearBraidStrandStudy=dict(newFiberCount=count, existingFiberCount=original_count,
                                        sides=2, tressesPerSide=3, fibersPerTress=a.fibers_per_tress,
                                        rootsBuriedUnderOriginalSideHair=True, originalHairUnchanged=True,
                                        dressUnchanged=True, headBoneParented=True,
                                        scalpSurfaceRaycast=True, worldToHeadLocalTransform=True,
                                        evaluatedHairSurfaceDepthMap=True,
                                        closedHeadClearanceGate=True,
                                        separateBraidMaterialStudy=True,
                                        braidMelanin=a.braid_melanin,
                                        independentDynamicsVerified=False, exportIntegrationVerified=False),
              styleFidelityApproved=False, physicsVerified=False, exported=False, published=False)
(a.output/'generation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
shutil.copyfile(__file__, a.output/'executed_study.py')
assert sha(g['editableBlend']) == g['editableBlendSha256']
print('REAR_BRAID_STRANDS_STUDY', count, flush=True)

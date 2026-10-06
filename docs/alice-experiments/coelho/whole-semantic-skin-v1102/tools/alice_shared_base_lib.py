"""Shared Alice library primitives, executed inside Blender 5.2.

Never append/make-local the shared head, body, skeleton or action datablocks.
Development libraries can be incomplete; production/export gates are separate.
"""
import bpy
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
COLLECTION = 'ALICE_SHARED_BASE'
RIG = 'Alice.Shared.Rig'
HEAD = 'Alice.Shared.Head'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def array_hash(seq, prop, width, dtype=np.float32):
    values = np.empty(len(seq) * width, dtype)
    seq.foreach_get(prop, values)
    return hashlib.sha256(values.tobytes()).hexdigest()


def head_hash(obj):
    mesh = obj.data
    return dict(
        positions=array_hash(mesh.vertices, 'co', 3),
        indices=array_hash(mesh.loops, 'vertex_index', 1, np.int32),
        uv={u.name: array_hash(u.data, 'uv', 2) for u in mesh.uv_layers},
        weights=hashlib.sha256(np.array(
            [(v.index, g.group, g.weight) for v in mesh.vertices for g in v.groups],
            np.float64).tobytes()).hexdigest())


def rig_hash(obj):
    rows = [(b.name, b.parent.name if b.parent else None,
             [float(x) for x in np.asarray(b.matrix_local).ravel()], b.use_deform)
            for b in obj.data.bones]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def action_hash(action):
    channels = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                for curve in bag.fcurves:
                    channels.append((curve.data_path, curve.array_index, [
                        (list(p.co), list(p.handle_left), list(p.handle_right), p.interpolation)
                        for p in curve.keyframe_points]))
    return hashlib.sha256(json.dumps(channels).encode()).hexdigest()


def find_core(scene=None):
    scene = scene or bpy.context.scene
    rigs = [o for o in scene.objects if o.get('aliceRole') == 'shared_rig']
    heads = [o for o in scene.objects if o.get('aliceRole') == 'shared_head']
    assert len(rigs) == len(heads) == 1, (len(rigs), len(heads))
    return rigs[0], heads[0]


def bind_core(library_path, asset_id):
    """Link a collection with a pose-only hierarchy override; mesh stays linked."""
    library_path = Path(library_path).resolve()
    assert library_path.exists()
    assert not any(o.get('aliceRole') == 'shared_rig' for o in bpy.context.scene.objects)
    with bpy.data.libraries.load(str(library_path), link=True, relative=True) as (src, dst):
        assert COLLECTION in src.collections
        dst.collections = [COLLECTION]
    linked = dst.collections[0]
    bpy.context.scene.collection.children.link(linked)
    bpy.context.view_layer.update()
    overridden = linked.override_hierarchy_create(
        bpy.context.scene, bpy.context.view_layer, do_fully_editable=False)
    assert overridden is not None
    if linked.name in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.unlink(linked)
    if overridden.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(overridden)
    bpy.context.view_layer.update()
    rig, head = find_core()
    mesh_source = head.data.override_library.reference if head.data.override_library else head.data
    assert rig.override_library and mesh_source.library
    assert rig.data.library, 'Skeleton must remain a linked datablock'
    rig.override_library.is_system_override = False
    assert head.parent == rig
    assert any(m.type == 'ARMATURE' and m.object == rig for m in head.modifiers)
    local = bpy.data.collections.new('ALICE_VARIANT_LOCAL_' + asset_id)
    bpy.context.scene.collection.children.link(local)
    for name in ['Dress', 'Hair', 'Accessories', 'SecondaryMotion']:
        child = bpy.data.collections.new(asset_id + '.' + name)
        local.children.link(child)
    bpy.context.scene['alice_asset_id'] = asset_id
    bpy.context.scene['alice_library_path'] = str(library_path)
    bpy.context.scene['alice_template_only'] = True
    bpy.context.scene['alice_body_missing'] = not bool(overridden.get('alice_base_complete'))
    return overridden, rig, head, local


def audit_link(expected_library=None):
    rig, head = find_core()
    mesh_source = head.data.override_library.reference if head.data.override_library else head.data
    assert mesh_source.library and rig.data.library
    library = Path(bpy.path.abspath(mesh_source.library.filepath)).resolve()
    if expected_library:
        assert library == Path(expected_library).resolve(), (library, expected_library)
    assert Path(bpy.path.abspath(rig.data.library.filepath)).resolve() == library
    assert head.parent == rig
    assert all(m.object == rig for m in head.modifiers if m.type == 'ARMATURE')
    actions = {s.action.name: action_hash(s.action)
               for track in rig.animation_data.nla_tracks for s in track.strips if s.action}
    assert all(s.action.library for t in rig.animation_data.nla_tracks for s in t.strips if s.action)
    shared_meshes={}
    for o in bpy.context.scene.objects:
        if o.type!='MESH' or not str(o.get('aliceRole','')).startswith('shared_'):continue
        data_source=o.data.override_library.reference if o.data.override_library else o.data
        shared_meshes[o.get('aliceRole')]=dict(name=o.name,meshHash=head_hash(o),linked=bool(data_source.library),vertices=len(o.data.vertices),faces=len(o.data.polygons),armatureTargets=[m.object.name for m in o.modifiers if m.type=='ARMATURE' and m.object],objectMatrix=[list(row) for row in o.matrix_local])
        assert data_source.library and Path(bpy.path.abspath(data_source.library.filepath)).resolve()==library
        assert all(m.object==rig for m in o.modifiers if m.type=='ARMATURE')
    body_missing='shared_body' not in shared_meshes
    return dict(library=str(library), librarySHA256=sha(library),
                rigObject=rig.name, headObject=head.name,
                linkedHeadMesh=True, linkedSkeleton=True,
                headMeshBinding='library_override' if head.data.override_library else 'direct_link',
                headMeshOverrideProperties=[p.rna_path for p in head.data.override_library.properties] if head.data.override_library else [],
                editablePoseOverride=bool(rig.override_library and not rig.override_library.is_system_override),
                headDataPreserved=head_hash(head), rigRestHash=rig_hash(rig),
                boneCount=len(rig.data.bones), actions=actions,
                bodyMissing=body_missing,sharedMeshes=shared_meshes,
                shapeKeys=[k.name for k in head.data.shape_keys.key_blocks] if head.data.shape_keys else [])

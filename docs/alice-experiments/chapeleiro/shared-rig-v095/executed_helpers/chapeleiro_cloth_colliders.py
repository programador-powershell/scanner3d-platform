"""Use existing thin garment carriers as local collision proxies.

No foreign body mesh, cropped exterior or replacement garment is created.
Only the already authored own-photo carrier objects are copied in memory.
"""
import bpy


def thin_underlayer_colliders(scene, audit, names, rig):
    entries = {a['receiver']: a for a in audit['authoringCages']}
    result, rows = [], []
    for name in names:
        source = bpy.data.objects[entries[name]['mesh']]
        assert len([m for m in source.modifiers if m.type == 'ARMATURE' and m.object == rig]) == 1
        proxy = source.copy()
        proxy.name = 'Local collision only / existing thin carrier / ' + name
        scene.collection.objects.link(proxy)
        for modifier in list(proxy.modifiers):
            if modifier.type not in {'ARMATURE', 'TRIANGULATE'}:
                proxy.modifiers.remove(modifier)
        for modifier in proxy.modifiers:
            modifier.show_viewport = True
            modifier.show_render = True
        proxy.hide_viewport = False
        proxy.hide_render = True
        proxy.hide_set(False)
        assert proxy.data is source.data
        result.append(proxy)
        rows.append({'proxy': proxy.name, 'actualSourceCarrier': source.name,
                     'visibleGarment': name, 'sourceVertices': len(source.data.vertices),
                     'sourceFaces': len(source.data.polygons), 'sharedActualMeshData': True,
                     'sameActualSkinGroups': [(g.name, g.index) for g in proxy.vertex_groups] ==
                                             [(g.name, g.index) for g in source.vertex_groups],
                     'sourceGeometryChanged': False, 'foreignBodyMesh': False,
                     'sourceClothAndThicknessExcludedFromLocalCollider': True})
    return result, rows

# This program is free software: you can redistribute it and/or modify
# it under the terms of the Creative Commons Attribution-ShareAlike 4.0 International License (CC-BY-SA 4.0).
# 
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# For more information, visit the official license page: https://creativecommons.org/licenses/by-sa/4.0/

bl_info = {
    "name": "Z-KeyColors",
    "author": "Marcin Zieliński, Z-Anatomy",
    "description": "Tools to toggle the material'aspect.",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Interface"
}

import bpy

class OBJECT_OT_key_color(bpy.types.Operator):
    bl_idname = "object.key_color"
    bl_label = "Key Colors"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        context.scene.zanatomy_keycolors.key_color = not context.scene.zanatomy_keycolors.key_color
        return {"FINISHED"}

class ZAnatomyKeyColorsProps(bpy.types.PropertyGroup):
    def key_color_func(self, context):
        var = self.key_color
        for ob in [c for col in bpy.data.collections for c in col.all_objects if c.type == 'MESH' and 'key_color' in c]:
            ob['key_color'] = var
            ob.update_tag(refresh={'OBJECT'})
        context.area.tag_redraw()

    key_color: bpy.props.BoolProperty(default=False, name="Key Color", update=key_color_func)

class ZANATOMY_PT_key_colors_panel(bpy.types.Panel):
    bl_label = "Key Colors"
    bl_idname = "VIEW3D_PT_z_key_colors"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Z-Anatomy'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.zanatomy_keycolors, "key_color")

def register():
    bpy.utils.register_class(OBJECT_OT_key_color)
    bpy.utils.register_class(ZAnatomyKeyColorsProps)
    bpy.utils.register_class(ZANATOMY_PT_key_colors_panel)
    bpy.types.Scene.zanatomy_keycolors = bpy.props.PointerProperty(type=ZAnatomyKeyColorsProps)

    # Force UI update after registration
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_key_color)
    bpy.utils.unregister_class(ZAnatomyKeyColorsProps)
    bpy.utils.unregister_class(ZANATOMY_PT_key_colors_panel)
    del bpy.types.Scene.zanatomy_keycolors

if __name__ == "__main__":
    register()

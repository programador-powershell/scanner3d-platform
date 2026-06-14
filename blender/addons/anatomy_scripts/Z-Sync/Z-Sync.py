# This program is free software: you can redistribute it and/or modify
# it under the terms of the Creative Commons Attribution-ShareAlike 4.0 International License (CC-BY-SA 4.0).
# 
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# For more information, visit the official license page: https://creativecommons.org/licenses/by-sa/4.0/

bl_info = {
    "name": "Z-Sync",
    "author": "Marcin Zieliński, Z-Anatomy",
    "description": "Render only what you see",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Interface"
}

import bpy

class OBJECT_OT_sync_visibility(bpy.types.Operator):
    bl_idname = "object.sync_visibility"
    bl_label = "Render what is visible"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        for o in context.scene.objects:
            if o.hide_render == o.visible_get():
                o.hide_render = not o.visible_get()
        return {"FINISHED"}

class ZANATOMY_PT_sync_panel(bpy.types.Panel):
    bl_label = "Synchronize Render"
    bl_idname = "VIEW3D_PT_z_sync_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Z-Anatomy'

    def draw(self, context):
        layout = self.layout
        layout.operator("object.sync_visibility")

def register():
    bpy.utils.register_class(OBJECT_OT_sync_visibility)
    bpy.utils.register_class(ZANATOMY_PT_sync_panel)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_sync_visibility)
    bpy.utils.unregister_class(ZANATOMY_PT_sync_panel)

if __name__ == "__main__":
    register()

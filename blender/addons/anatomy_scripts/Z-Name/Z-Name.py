# This program is free software: you can redistribute it and/or modify
# it under the terms of the Creative Commons Attribution-ShareAlike 4.0 International License (CC-BY-SA 4.0).
# 
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# For more information, visit the official license page: https://creativecommons.org/licenses/by-sa/4.0/

bl_info = {
    "name": "Z-Name",
    "author": "Marcin Zieliński, Z-Anatomy",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > N Panel > Z-Anatomy",
    "description": "Displays the active object's name as an overlay.",
    "category": "Object",
}

import bpy
import blf

font_info = {
    "handler": None,
}

def clean_name(name):
    # Implement your cleaning logic here if needed
    return name,

def draw_callback_px(self, context):
    if not context.object:
        return

    font_size = 24
    blf.color(0, 1, 1, 1, 1)  # Set font color to white
    blf.size(0, font_size)
    blf.position(0, 55, context.area.height - 70 - font_size, 0)
    blf.draw(0, f'{clean_name(context.object.name)[0]}')

def update_overlay(self, context):
    if context is None:
        return

    if context.scene.zanatomy_name.show_name_overlay:
        if font_info["handler"] is None:
            font_info["handler"] = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_px, (None, context), 'WINDOW', 'POST_PIXEL')
    else:
        if font_info["handler"] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(font_info["handler"], 'WINDOW')
            font_info["handler"] = None

    # Force UI update
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

class ZAnatomyNameProps(bpy.types.PropertyGroup):
    show_name_overlay: bpy.props.BoolProperty(
        name="Show Object Name",
        description="Toggle the display of the active object's name",
        default=True,
        update=update_overlay
    )

class VIEW3D_PT_z_anatomy_overlay(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Show Object Name"
    bl_idname = "VIEW3D_PT_z_anatomy_overlay"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Z-Anatomy'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        zanatomy = context.scene.zanatomy_name
        layout.prop(zanatomy, "show_name_overlay")

def load_post_handler(dummy):
    # Initialize the overlay based on the default property value after loading
    update_overlay(None, bpy.context)

def register():
    bpy.utils.register_class(ZAnatomyNameProps)
    bpy.utils.register_class(VIEW3D_PT_z_anatomy_overlay)
    bpy.types.Scene.zanatomy_name = bpy.props.PointerProperty(type=ZAnatomyNameProps)

    # Use a load_post handler to initialize the overlay
    bpy.app.handlers.load_post.append(load_post_handler)

def unregister():
    bpy.utils.unregister_class(ZAnatomyNameProps)
    bpy.utils.unregister_class(VIEW3D_PT_z_anatomy_overlay)
    del bpy.types.Scene.zanatomy_name

    if font_info["handler"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(font_info["handler"], 'WINDOW')
        font_info["handler"] = None

    bpy.app.handlers.load_post.remove(load_post_handler)

if __name__ == "__main__":
    register()

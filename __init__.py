import bpy
import os
import mathutils
import math
import steps


class COLLECTION_OT_MergeExportBake(bpy.types.Operator):
    bl_idname = "collection.merge_export_bake"
    bl_label = "Merge Export Bake"
    prefix: bpy.props.StringProperty(default="bake")
    size: bpy.props.IntProperty(default=2048)

    def execute(self, context):
        prefix = self.prefix
        texture_toggles = bpy.context.scene.my_render_settings.texture_toggles

        if texture_toggles.albedo_toggle:
            self.swap_to(context, self.get(prefix + ".albedo"))
            bpy.ops.object.bake(type="DIFFUSE")

        if texture_toggles.normal_toggle:
            self.swap_to(context, self.get(prefix + ".normal"))
            bpy.ops.object.bake(type="NORMAL")

        if texture_toggles.rough_toggle:
            self.swap_to(context, self.get(prefix + ".rough"))
            bpy.ops.object.bake(type="ROUGHNESS")

        #bake_mask(obj, self.get(prefix + ".mask"))

        if texture_toggles.emission_toggle:
            self.swap_to(context, self.get(prefix + ".emission"))
            bpy.ops.object.bake(type="EMIT")

        if texture_toggles.ao_toggle:
            self.swap_to(context, self.get(prefix + ".ao"))
            bpy.ops.object.bake(type="AO")

        return {'FINISHED'}


    def swap_to(self, context, image):
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue

            if not obj.material_slots:
                continue

            for slot in obj.material_slots:
                material = slot.material

                if not material.use_nodes:
                    continue

                nodes = material.node_tree.nodes
                tex_nodes = [node for node in nodes if node.type == 'TEX_IMAGE']

                if len(tex_nodes) == 0:
                    continue

                tex_nodes[0].image = image


    def bake_mask(self, obj, mask):
        saved_materials = list(obj.data.materials)

        for i in range(0, len(obj.data.materials)):
            obj.data.materials[i] = masker

        swap_to(obj, mask)
        bpy.ops.object.bake(type="DIFFUSE")

        for i in range(0, len(obj.data.materials)):
            obj.data.materials[i] = saved_materials[i]


    def get(self, name):
        images = bpy.data.images
        check = images.get(name)

        if check != None and not check.has_data:
            bpy.data.images.remove(check)
            check = None

        if check != None and check.size[0] != self.size:
            check.scale(self.size, self.size)

        if not any(image.name == name for image in images):
            bpy.ops.image.new(name=name, width=self.size, height=self.size)
            image = images.get(name)

            if "normal" in name or "rough" in name:
                image.colorspace_settings.name = 'Non-Color'

            image.use_fake_user = True
            image.alpha_mode = "NONE"

        return images.get(name)


class FILE_OT_MergeExport(bpy.types.Operator):
    bl_idname = "file.merge_export"
    bl_label = "Merge Export"

    def execute(self, context):
        with steps.PreserveSelectionsStep(context):
            for collection in context.scene.collection.children:
                steps.execute(context, collection)

        return {'FINISHED'}


class MergeExporter_Exportable(bpy.types.PropertyGroup):
    collection: bpy.props.PointerProperty(type=bpy.types.Collection)
    parent: bpy.props.PointerProperty(type=bpy.types.Collection)


class MergeExporter_CollectionProps(bpy.types.PropertyGroup):
    active: bpy.props.BoolProperty(name="Active", default=False)
    bake: bpy.props.BoolProperty(name="Bake", default=True)
    materialize: bpy.props.BoolProperty(name="Materialize", default=True)
    path: bpy.props.StringProperty(name="Export Path", subtype='DIR_PATH')
    origin: bpy.props.PointerProperty(name="Origin", type=bpy.types.Object)
    use_origin_scale: bpy.props.BoolProperty(name="Use Origin Scale", default=False)
    export_origin: bpy.props.BoolProperty(name="Export Origin", default=True)
    texture_size: bpy.props.IntProperty(name="Texture Size", default=2048)


class TextureToggles(bpy.types.PropertyGroup):
    albedo_toggle: bpy.props.BoolProperty(
        name="Albedo",
        default=True,
    )
    normal_toggle: bpy.props.BoolProperty(
        name="Normal",
        default=True,
    )
    rough_toggle: bpy.props.BoolProperty(
        name="Roughness",
        default=True,
    )
    mask_toggle: bpy.props.BoolProperty(
        name="Mask",
        default=True,
    )
    emission_toggle: bpy.props.BoolProperty(
        name="Emission",
        default=True,
    )
    ao_toggle: bpy.props.BoolProperty(
        name="Ambient Occlusion",
        default=False,
    )


class EntityList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        collection = item.collection

        row = layout.row()
        row.prop(collection.merge_exporter_props, "active", text="")
        row.label(text=collection.name, icon="OUTLINER_COLLECTION")


class MyRenderSettings(bpy.types.PropertyGroup):
    collections: bpy.props.CollectionProperty(type=MergeExporter_Exportable, name="collections")
    entities: bpy.props.BoolProperty(name="entities", default=False)
    entity_details: bpy.props.BoolProperty(name="entity_details", default=False)
    textures: bpy.props.BoolProperty(name="textures", default=False)
    export_index: bpy.props.IntProperty(name="export_index")
    textures: bpy.props.BoolProperty(name="textures", default=False)
    material_count: bpy.props.IntProperty(name="Material Count", default=4)
    texture_toggles: bpy.props.PointerProperty(type=TextureToggles)
    export_format: bpy.props.EnumProperty(
        name="Export Format",
        items=[
            ('gltf', "glTF 2.0", ""),
            ('fbx', "FBX", ""),
        ],
        default='gltf',
    )
    save_textures: bpy.props.BoolProperty(name="Save Textures", default=False)
    export_texture_format: bpy.props.EnumProperty(
        name="Texture Format",
        items=[
            ('png', "PNG", ""),
            ('jpg', "JPG", ""),
            ('tga', "TGA", ""),
        ],
        default='png',
    )


class RENDER_PT_MergeExporterPanel(bpy.types.Panel):
    bl_label = "Merge Exporter"
    bl_idname = "RENDER_PT_mergeExporter_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def draw(self, context):
        layout = self.layout
        my_settings = context.scene.my_render_settings

        sub_panel = layout.panel_prop(my_settings, "entities")
        sub_panel[0].label(text="Entities")
        if sub_panel[1]:
            sub_layout = sub_panel[1]
            row = sub_layout.row()
            row.template_list("EntityList", "", my_settings, "collections", my_settings, "export_index")

        sub_panel = layout.panel_prop(my_settings, "entity_details")
        sub_panel[0].label(text="Entity Details")
        if sub_panel[1]:
            exportables = my_settings.collections

            if my_settings.export_index < len(exportables):
                collection = exportables[my_settings.export_index].collection

                if collection != None:
                    sub_layout = sub_panel[1]

                    row = sub_layout.row()
                    row.prop(collection.merge_exporter_props, "bake")
                    row.prop(collection.merge_exporter_props, "materialize")

                    row = sub_layout.row()
                    row.prop(collection.merge_exporter_props, "texture_size")

                    row = sub_layout.row()
                    row.prop(collection.merge_exporter_props, "path")
                    if exportables[my_settings.export_index].parent:
                        row.active = False

                    row = sub_layout.row()
                    column = row.column()
                    column.prop(collection.merge_exporter_props, "export_origin")
                    column.prop(collection.merge_exporter_props, "use_origin_scale")
                    column = row.column()
                    column.prop(collection.merge_exporter_props, "origin")

        sub_panel = layout.panel_prop(my_settings, "textures")
        sub_panel[0].label(text="Bake")
        if sub_panel[1]:
            sub_layout = sub_panel[1]
            sub_layout.prop(my_settings, "material_count")

            row = sub_layout.row()
            row.prop(my_settings.texture_toggles, "albedo_toggle")
            row.prop(my_settings.texture_toggles, "normal_toggle")

            row = sub_layout.row()
            row.prop(my_settings.texture_toggles, "rough_toggle")
            row.prop(my_settings.texture_toggles, "mask_toggle")

            row = sub_layout.row()
            row.prop(my_settings.texture_toggles, "emission_toggle")
            row.prop(my_settings.texture_toggles, "ao_toggle")

        row = layout.row().split(factor=0.33)
        row.label(text="Export Format")

        sub_row = row.row()
        sub_row.prop(my_settings, "export_format", expand=True)

        row = layout.row()
        row.prop(my_settings, "save_textures", expand=True)
        row.prop(my_settings, "export_texture_format", expand=True)

        layout.operator("file.merge_export", text="Export")


classes = [
    MergeExporter_Exportable,
    MergeExporter_CollectionProps,
    COLLECTION_OT_MergeExportBake,
    FILE_OT_MergeExport,
    EntityList,
    TextureToggles,
    MyRenderSettings,
    RENDER_PT_MergeExporterPanel
]

def menu_func_export(self, context):
    self.layout.operator(FILE_OT_MergeExport.bl_idname, text="Merge Export (.glb, .fbx)")


def gather(collection, parent):
    entry = bpy.context.scene.my_render_settings.collections.add()
    entry.collection = collection
    entry.parent = parent

    for child in collection.children:
        gather(child, collection)


@bpy.app.handlers.persistent
def depsgraph_update_post(dummy1, dummy2):
    bpy.context.scene.my_render_settings.collections.clear()

    for collection in bpy.context.scene.collection.children:
        gather(collection, None)


bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)



def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Collection.merge_exporter_props = bpy.props.PointerProperty(type=MergeExporter_CollectionProps)
    bpy.types.Scene.my_render_settings = bpy.props.PointerProperty(type=MyRenderSettings)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    del bpy.types.Scene.my_render_settings
    del bpy.types.Collection.merge_exporter_props


if __name__ == "__main__":
    register()
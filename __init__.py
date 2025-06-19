import bpy
import importlib

from . import steps


class COLLECTION_OT_MergeExportBake(bpy.types.Operator):
    bl_idname = "collection.merge_export_bake"
    bl_label = "Merge Export Bake"
    prefix: bpy.props.StringProperty(default="bake")
    size: bpy.props.IntProperty(default=2048)

    def execute(self, context):
        prefix = self.prefix
        texture_toggles = bpy.context.scene.merge_exporter_settings.texture_toggles

        if texture_toggles.albedo_toggle:
            self.swap_to(context, self.get(prefix + ".albedo"))
            bpy.ops.object.bake(type="DIFFUSE")

        if texture_toggles.normal_toggle:
            self.swap_to(context, self.get(prefix + ".normal"))
            bpy.ops.object.bake(type="NORMAL")

        if texture_toggles.rough_toggle:
            self.swap_to(context, self.get(prefix + ".rough"))
            bpy.ops.object.bake(type="ROUGHNESS")

        if texture_toggles.rough_toggle:
            self.bake_mask(context, self.get(prefix + ".mask"))

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

                for node in nodes:
                    node.select = False

                tex_nodes = [
                    node for node in nodes if node.type == 'TEX_IMAGE']

                if len(tex_nodes) == 0:
                    continue

                for node in tex_nodes:
                    if node.outputs[0].is_linked or node.outputs[1].is_linked:
                        continue

                    node.image = image
                    node.select = True
                    material.node_tree.nodes.active = node

                    break

    def prepare_masker(self, context):
        if not "masker" in bpy.data.materials:
            masker = bpy.data.materials.new(name="masker")
            masker.use_nodes = True

        masker = bpy.data.materials["masker"]
        node_tree = masker.node_tree
        divisor = context.scene.merge_exporter_settings.material_count - 1

        for node in node_tree.nodes:
            node_tree.nodes.remove(node)

        node_attribute = node_tree.nodes.new(type='ShaderNodeAttribute')
        node_attribute.attribute_name = "material_index"

        node_divide = node_tree.nodes.new(type='ShaderNodeMath')
        node_divide.location = (160, 0)
        node_divide.operation = 'DIVIDE'
        node_divide.inputs[1].default_value = divisor

        node_add = node_tree.nodes.new(type='ShaderNodeMath')
        node_add.location = (320, 0)
        node_add.operation = 'ADD'
        node_add.inputs[1].default_value = 0.00  # (1.00 / divisor) / 3

        node_clamp = node_tree.nodes.new(type='ShaderNodeClamp')
        node_clamp.location = (480, 0)
        node_clamp.inputs[1].default_value = 0.00
        node_clamp.inputs[2].default_value = 1.00

        node_combine = node_tree.nodes.new(type='ShaderNodeCombineColor')
        node_combine.location = (640, 0)

        node_diffuse = node_tree.nodes.new(type='ShaderNodeBsdfDiffuse')
        node_diffuse.location = (800, 0)
        node_diffuse.inputs[1].default_value = 1

        node_output = node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location = (960, 0)

        node_image = node_tree.nodes.new(type='ShaderNodeTexImage')
        node_image.location = (160, 270)

        node_tree.links.new(node_attribute.outputs[2], node_divide.inputs[0])
        node_tree.links.new(node_divide.outputs[0], node_add.inputs[0])
        node_tree.links.new(node_add.outputs[0], node_clamp.inputs[0])
        node_tree.links.new(node_clamp.outputs[0], node_combine.inputs[0])
        node_tree.links.new(node_combine.outputs[0], node_diffuse.inputs[0])
        node_tree.links.new(node_diffuse.outputs[0], node_output.inputs[0])

        return masker

    def bake_mask(self, context, mask):
        saved_materials = {}
        masker = self.prepare_masker(context)

        for obj in context.selected_objects:
            saved_materials[obj.name] = list(obj.data.materials)

        for obj in context.selected_objects:
            for i in range(0, len(obj.data.materials)):
                obj.data.materials[i] = masker

            self.swap_to(context, mask)

        bpy.ops.object.bake(type="DIFFUSE")

        for obj in context.selected_objects:
            mats = saved_materials[obj.name]

            for i in range(0, len(obj.data.materials)):
                obj.data.materials[i] = mats[i]

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

            if "normal" in name or "rough" in name or "mask" in name:
                image.colorspace_settings.name = 'Non-Color'

            image.use_fake_user = True
            # image.alpha_mode = "NONE"

        return images.get(name)


class FILE_OT_MergeExport(bpy.types.Operator):
    bl_idname = "file.merge_export"
    bl_label = "Merge Export"

    def execute(self, context):
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
    outline_correction: bpy.props.BoolProperty(
        name="Outline Correction", default=False)
    path: bpy.props.StringProperty(name="Export Path", subtype='DIR_PATH')
    origin: bpy.props.PointerProperty(name="Origin", type=bpy.types.Object)
    use_origin_scale: bpy.props.BoolProperty(
        name="Use Origin Scale", default=False)
    export_origin: bpy.props.BoolProperty(name="Export Origin", default=True)
    texture_size: bpy.props.IntProperty(name="Texture Size", default=2048)
    override_name: bpy.props.BoolProperty(name="Override Name", default=False)
    name: bpy.props.StringProperty(name="Name", default="merged")


class MergeExporter_TextureToggles(bpy.types.PropertyGroup):
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


class COLLECTION_UL_MergeExporter_EntityList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        collection = item.collection

        row = layout.row()
        row.prop(collection.merge_exporter_props, "active", text="")
        row.label(text=collection.name, icon="OUTLINER_COLLECTION")
        row.prop(collection.merge_exporter_props, "bake")


class OBJECT_UL_MergeExporter_ObjectList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.label(text=item.name, icon="OBJECT_DATA")


class MergeExporter_SettingsSettings(bpy.types.PropertyGroup):
    collections: bpy.props.CollectionProperty(
        type=MergeExporter_Exportable, name="collections")
    entities: bpy.props.BoolProperty(name="entities", default=False)
    entity_details: bpy.props.BoolProperty(
        name="entity_details", default=False)
    export_index: bpy.props.IntProperty(name="export_index")
    textures: bpy.props.BoolProperty(name="textures", default=False)
    textures: bpy.props.BoolProperty(name="textures", default=False)
    material_count: bpy.props.IntProperty(name="Material Count", default=5)
    texture_toggles: bpy.props.PointerProperty(
        type=MergeExporter_TextureToggles)
    object_details: bpy.props.BoolProperty(
        name="object_details", default=False)
    object_index: bpy.props.IntProperty(name="object_index")
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
        my_settings = context.scene.merge_exporter_settings

        sub_panel = layout.panel_prop(my_settings, "entities")
        sub_panel[0].label(text="Entities")
        if sub_panel[1]:
            sub_layout = sub_panel[1]
            row = sub_layout.row()
            row.template_list("COLLECTION_UL_MergeExporter_EntityList",
                              "", my_settings, "collections", my_settings, "export_index")

        sub_panel = layout.panel_prop(my_settings, "entity_details")
        sub_panel[0].label(text="Entity Details")
        if sub_panel[1]:
            exportables = my_settings.collections

            if my_settings.export_index < len(exportables):
                collection = exportables[my_settings.export_index].collection

                if collection != None:
                    sub_layout = sub_panel[1]

                    row = sub_layout.row()
                    row.active = False
                    column = row.column()
                    column.prop(collection.merge_exporter_props,
                                "override_name")
                    column = row.column()
                    column.prop(collection.merge_exporter_props, "name")
                    column.active = collection.merge_exporter_props.override_name

                    row = sub_layout.row()
                    row.prop(collection.merge_exporter_props, "bake")
                    row.prop(collection.merge_exporter_props, "materialize")

                    row = sub_layout.row()
                    row.prop(collection.merge_exporter_props,
                             "outline_correction")

                    row = sub_layout.row()
                    row.prop(collection.merge_exporter_props, "texture_size")

                    row = sub_layout.row()
                    row.prop(collection.merge_exporter_props, "path")
                    if exportables[my_settings.export_index].parent:
                        row.active = False

                    row = sub_layout.row()
                    column = row.column()
                    column.prop(collection.merge_exporter_props,
                                "export_origin")
                    column.prop(collection.merge_exporter_props,
                                "use_origin_scale")
                    column = row.column()
                    column.prop(collection.merge_exporter_props, "origin")

                    sub_panel = layout.panel_prop(
                        my_settings, "object_details")
                    sub_panel[0].label(text="Object Details")
                    if sub_panel[1]:
                        sub_layout = sub_panel[1]
                        row = sub_layout.row()
                        row.template_list("OBJECT_UL_MergeExporter_ObjectList",
                                          "", collection, "objects", my_settings, "object_index")

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
    COLLECTION_UL_MergeExporter_EntityList,
    OBJECT_UL_MergeExporter_ObjectList,
    MergeExporter_TextureToggles,
    MergeExporter_SettingsSettings,
    RENDER_PT_MergeExporterPanel
]


def menu_func_export(self, context):
    self.layout.operator(FILE_OT_MergeExport.bl_idname,
                         text="Merge Export (.glb, .fbx)")


def gather(collection, parent):
    entry = bpy.context.scene.merge_exporter_settings.collections.add()
    entry.collection = collection
    entry.parent = parent

    for child in collection.children:
        gather(child, collection)


@bpy.app.handlers.persistent
def depsgraph_update_post(dummy1, dummy2):
    bpy.context.scene.merge_exporter_settings.collections.clear()

    for collection in bpy.context.scene.collection.children:
        gather(collection, None)


bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)


def register():
    importlib.reload(steps)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Collection.merge_exporter_props = bpy.props.PointerProperty(
        type=MergeExporter_CollectionProps)
    bpy.types.Scene.merge_exporter_settings = bpy.props.PointerProperty(
        type=MergeExporter_SettingsSettings)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    del bpy.types.Scene.merge_exporter_settings
    del bpy.types.Collection.merge_exporter_props


if __name__ == "__main__":
    register()

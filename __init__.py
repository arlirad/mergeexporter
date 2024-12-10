import bpy
import os
import mathutils
import math
import numpy

class OBJECT_OT_MergeExportBake(bpy.types.Operator):
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

        return {'FINISHED'}


    def swap_to(self, context, image):
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue

            if not obj.material_slots:
                continue

            for slot in obj.material_slots:
                material = slot.material

                print(material.name)

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

            if not "albedo" in name:
                image.colorspace_settings.name = 'Non-Color'

            image.use_fake_user = True
            image.alpha_mode = "NONE"

        return images.get(name)


class OBJECT_OT_MergeExport(bpy.types.Operator):
    bl_idname = "collection.merge_export"
    bl_label = "Merge Export"

    def execute(self, context):
        for collection in context.scene.collection.children:
            if not collection.merge_exporter_props.active:
                continue

            self.merge(context, collection, None)

        return {'FINISHED'}


    def merge(self, context, collection, parent):
        format = context.scene.my_render_settings.export_format
        save_textures = context.scene.my_render_settings.save_textures

        props = collection.merge_exporter_props
        prefix = os.path.abspath(bpy.path.abspath(props.path)) + "/"
        path = prefix + collection.name + "." + format

        objects = list(collection.objects)
        objects = [obj for obj in objects if obj.type != "ARMATURE" and obj.type != "EMPTY"]
        objects = [obj for obj in objects if obj.type != "ARMATURE" and obj.type != "EMPTY"]
        bpy.context.view_layer.objects.active = objects[0]

        bpy.ops.object.select_all(action="DESELECT")

        origin = mathutils.Matrix.Identity(4)

        for object in collection.objects:
            if object.name == ".origin":
                origin = object.matrix_world

        override = {}
        override["active_object"] = objects[0]
        override["selected_objects"] = objects

        with context.temp_override(**override):
            bpy.ops.object.duplicate()

        for object in context.selected_objects:
            if object.type == "MESH":
                continue

            with bpy.context.temp_override(active_object=context.selected_objects[0], selected_objects={context.selected_objects[0]}):
                bpy.ops.object.convert()

        bpy.ops.collection.merge_export_bake(prefix=collection.name, size=props.texture_size)

        self.apply_modifiers(context)

        with bpy.context.temp_override(active_object=context.selected_objects[0], selected_objects={context.selected_objects[0]}):
            bpy.ops.object.join()

        merged = context.selected_objects[0]

        merged.name = collection.name
        self.materialize(merged)

        if save_textures:
            self.save_textures(merged, prefix)

        hidden = {}

        bpy.ops.object.select_all(action="DESELECT")

        self.select_unmerges(collection)
        precopy_prefix = ".precopy.:."

        for object in context.selected_objects:
            object.name = precopy_prefix + object.name

        renamed = list(context.selected_objects)

        bpy.ops.object.duplicate()
        self.apply_modifiers(context)

        for object in context.selected_objects:
            object.name = object.name[len(precopy_prefix):-4]

        unmerged = list(context.selected_objects)

        merged.select_set(True)

        for object in collection.objects:
            if object.type == "ARMATURE" or object.type == "EMPTY":
                hidden[object.name] = object.hide_get()

                object.hide_set(False)
                object.select_set(True)

        for object in context.selected_objects:
            object.matrix_world = origin.inverted() @ object.matrix_world

        if format == "gltf":
            bpy.ops.export_scene.gltf(
                filepath = path,
                use_selection=True
            )
        else:
            bpy.ops.export_scene.fbx(
                filepath = path,
                use_selection=True
            )

        for object in context.selected_objects:
            object.matrix_world = origin @ object.matrix_world

        bpy.ops.object.select_all(action="DESELECT")

        for name in hidden:
            collection.objects[name].hide_set(hidden[name])

        merged.select_set(True)

        for object in unmerged:
            object.select_set(True)

        bpy.ops.object.delete()

        for object in renamed:
            object.name = object.name[len(precopy_prefix):]


    def apply_modifiers(self, context):
        for object in context.selected_objects:
            object.data = object.data.copy()

            with bpy.context.temp_override(active_object=object, selected_objects={object}):
                for i, mod in enumerate(object.modifiers):
                    if type(mod) is bpy.types.ArmatureModifier:
                        continue

                    bpy.ops.object.modifier_apply(modifier=mod.name)


    def select_unmerges(self, collection):
        for child in collection.children:
            self.select_unmerges(child)

            if child.name[0] != '.':
                continue

            for object in child.objects:
                object.select_set(True)


    def materialize(self, object):
        material_name = object.name + ".merged"
        texture_toggles = bpy.context.scene.my_render_settings.texture_toggles

        if not material_name in bpy.data.materials:
            mat = bpy.data.materials.new(name=material_name)
            mat.use_nodes = True

        mat = bpy.data.materials[material_name]
        node_tree = mat.node_tree

        for node in node_tree.nodes:
            node_tree.nodes.remove(node)

        node_bsdf = node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        node_bsdf.location = (480, 0)

        node_output = node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location = (640, 0)

        if texture_toggles.albedo_toggle:
            node_albedo_image = node_tree.nodes.new(type='ShaderNodeTexImage')
            node_albedo_image.location = (160, 270)
            node_albedo_image.image = bpy.data.images.get(object.name + ".albedo")
            node_tree.links.new(node_albedo_image.outputs[0], node_bsdf.inputs[0])

        if texture_toggles.normal_toggle:
            node_normalmap = node_tree.nodes.new(type='ShaderNodeNormalMap')
            node_normalmap.location = (160, -270)

            node_normal_image = node_tree.nodes.new(type='ShaderNodeTexImage')
            node_normal_image.location = (-160, -270)
            node_normal_image.image = bpy.data.images.get(object.name + ".normal")

            node_tree.links.new(node_normal_image.outputs[0], node_normalmap.inputs[1])
            node_tree.links.new(node_normalmap.outputs[0], node_bsdf.inputs[5])

        if texture_toggles.rough_toggle:
            node_rough_image = node_tree.nodes.new(type='ShaderNodeTexImage')
            node_rough_image.location = (160, -810)
            node_rough_image.image = bpy.data.images.get(object.name + ".rough")
            node_tree.links.new(node_rough_image.outputs[0], node_bsdf.inputs[2])

        node_tree.links.new(node_bsdf.outputs[0], node_output.inputs[0])

        object.data.materials.clear()
        object.data.materials.append(mat)


    def save_textures(self, object, prefix):
        format = "." + bpy.context.scene.my_render_settings.export_texture_format
        texture_toggles = bpy.context.scene.my_render_settings.texture_toggles

        if texture_toggles.albedo_toggle:
            self.save_image(object.name + ".albedo", prefix + object.name + ".albedo" + format)

        if texture_toggles.normal_toggle:
            self.save_image(object.name + ".normal", prefix + object.name + ".normal" + format)

        if texture_toggles.rough_toggle:
            self.save_image(object.name + ".rough", prefix + object.name + ".rough" + format)


    def save_image(self, name, destination):
        original = bpy.data.images.get(name)
        copy = original.copy()

        tmp_buf = numpy.empty(original.size[0] * original.size[1] * 4, numpy.float32)
        original.pixels.foreach_get(tmp_buf)
        copy.pixels.foreach_set(tmp_buf)

        copy.save(filepath=destination)
        bpy.data.images.remove(copy)


class MergeExporter_Exportable(bpy.types.PropertyGroup):
    collection: bpy.props.PointerProperty(type=bpy.types.Collection)


class MergeExporter_CollectionProps(bpy.types.PropertyGroup):
    active: bpy.props.BoolProperty(
        name="Active",
        default=False,
    )
    bake: bpy.props.BoolProperty(
        name="Bake",
        default=True,
    )
    path: bpy.props.StringProperty(
        name="Export Path",
        subtype='DIR_PATH',
    )
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


class EntityList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        column = layout.column()

        row = column.row()
        row.label(text=item.name, icon="OUTLINER_COLLECTION")
        row.prop(item.merge_exporter_props, "active")
        row.prop(item.merge_exporter_props, "bake")

        if not item.merge_exporter_props.active:
            return

        row = column.row()
        row.prop(item.merge_exporter_props, "path")

        row = column.row()
        row.prop(item.merge_exporter_props, "texture_size")


class MyRenderSettings(bpy.types.PropertyGroup):
    entities: bpy.props.BoolProperty(name="entities", default=False)
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
            row.template_list("EntityList", "", bpy.context.scene.collection, "children", my_settings, "export_index")

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

        row = layout.row().split(factor=0.33)
        row.label(text="Export Format")

        sub_row = row.row()
        sub_row.prop(my_settings, "export_format", expand=True)

        row = layout.row()
        row.prop(my_settings, "save_textures", expand=True)
        row.prop(my_settings, "export_texture_format", expand=True)

        layout.operator("collection.merge_export", text="Export")


classes = [
    MergeExporter_Exportable,
    MergeExporter_CollectionProps,
    OBJECT_OT_MergeExportBake,
    OBJECT_OT_MergeExport,
    EntityList,
    TextureToggles,
    MyRenderSettings,
    RENDER_PT_MergeExporterPanel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Collection.merge_exporter_props = bpy.props.PointerProperty(type=MergeExporter_CollectionProps)
    bpy.types.Scene.my_render_settings = bpy.props.PointerProperty(type=MyRenderSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.my_render_settings
    del bpy.types.Collection.merge_exporter_props


if __name__ == "__main__":
    register()
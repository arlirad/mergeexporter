import bpy
import mathutils
import numpy
import os


class Step:
    objects = []
    objects_forward = []
    original_names = []
    context = None
    collection = None

    def __init__(self, previous):
        if type(previous) == bpy.types.Context:
            self.context = previous
            return

        if type(previous) == list:
            self.objects_forward = previous
            return
        
        self.objects = previous.objects_forward.copy()
        self.objects_forward = self.objects
        self.original_names = previous.original_names
        self.context = previous.context
        self.collection = previous.collection


    def select(self, condition=None, list=None):
        if list == None:
            list = self.objects

        if condition == None:
            condition = lambda obj : True

        bpy.ops.object.select_all(action="DESELECT")

        for object in list:
            object.select_set(condition(object))

        if len(self.context.selected_objects) > 0:
            self.context.view_layer.objects.active = self.context.selected_objects[0]


    def select_add(self, condition=None, list=None):
        if list == None:
            list = self.objects

        if condition == None:
            condition = lambda obj : True

        for object in list:
            if condition(object):
                object.select_set(True)

        if len(self.context.selected_objects) > 0:
            self.context.view_layer.objects.active = self.context.selected_objects[0]


    def gather(self):
        return list(self.context.selected_objects)


class InitialStep(Step):
    def __init__(self, context, collection, objects):
        self.context = context
        self.collection = collection
        self.objects = objects
        self.objects_forward = self.objects
    

    def __enter__(self):
        return self


    def __exit__(self, *args):
        pass


class PreserveSelectionsStep(Step):
    selections = []

    def __enter__(self):
        self.selections = self.gather()
        return self


    def __exit__(self, *args):
        self.select(None, self.selections)


class RenameStep(Step):
    prefix = ".copy.:."
    postfix = ".#."

    def __enter__(self):
        for object in self.objects:
            self.original_names.append((object, object.name))
            object.name = self.prefix + object.name + self.postfix

        return self


    def __exit__(self, *args):
        for entry in self.original_names:
            entry[0].name = entry[1]


class UnrenameStep(Step):
    previous_names = []

    def __enter__(self):
        for entry in self.original_names:
            self.previous_names.append((entry[0], entry[0].name))
            entry[0].name = entry[1]

        return self


    def __exit__(self, *args):
        for entry in self.previous_names:
            entry[0].name = entry[1]


class BakeStep(Step):
    def __enter__(self):
        props = self.collection.merge_exporter_props
        if not props.bake:
            return self
        
        self.select(lambda object : object.type == "MESH")
        bpy.ops.collection.merge_export_bake(prefix=self.collection.name, size=props.texture_size)

        return self


    def __exit__(self, *args):
        pass


class ReoriginStep(Step):
    origin = mathutils.Matrix.Identity(4)
    origin_pure = None

    def __enter__(self):
        props = self.collection.merge_exporter_props

        if not props.origin:
            return self
        
        self.origin = mathutils.Matrix(props.origin.matrix_world)
        self.origin_pure = mathutils.Matrix(props.origin.matrix_world)

        if not props.use_origin_scale:
            decomposed = self.origin.decompose()
            self.origin_pure = mathutils.Matrix.LocRotScale(decomposed[0], decomposed[1], mathutils.Vector((1.00, 1.00, 1.00)))

        for object in self.objects:
            object.matrix_world = self.origin.inverted() @ object.matrix_world

        return self


    def __exit__(self, *args):
        props = self.collection.merge_exporter_props

        for object in self.objects:
            object.matrix_world = self.origin @ object.matrix_world

        if props.origin:
            props.origin.matrix_world = self.origin_pure


class SaveTexturesStep(Step):
    def __enter__(self):
        if not self.context.scene.my_render_settings.save_textures:
            return self

        props = self.collection.merge_exporter_props
        prefix = os.path.abspath(bpy.path.abspath(props.path)) + "/"

        for object in self.objects:
            if object.type != "MESH":
                continue

            self.save_textures(object, prefix)

        return self


    def __exit__(self, *args):
        pass


    def save_textures(self, object, path_prefix):
        format = "." + bpy.context.scene.my_render_settings.export_texture_format
        texture_toggles = bpy.context.scene.my_render_settings.texture_toggles

        if texture_toggles.albedo_toggle:
            self.save_image(object.name + ".albedo", path_prefix + object.name + ".albedo" + format)

        if texture_toggles.normal_toggle:
            self.save_image(object.name + ".normal", path_prefix + object.name + ".normal" + format)

        if texture_toggles.rough_toggle:
            self.save_image(object.name + ".rough", path_prefix + object.name + ".rough" + format)

        if texture_toggles.emission_toggle:
            self.save_image(object.name + ".emission", path_prefix + object.name + ".emission" + format)

        if texture_toggles.ao_toggle:
            self.save_image(object.name + ".ao", path_prefix + object.name + ".ao" + format)


    def save_image(self, name, destination):
        original = bpy.data.images.get(name)
        copy = original.copy()
        copy.scale(original.size[0], original.size[1])

        tmp_buf = numpy.empty(original.size[0] * original.size[1] * 4, numpy.float32)
        original.pixels.foreach_get(tmp_buf)
        copy.pixels.foreach_set(tmp_buf)

        copy.save(filepath=destination)
        bpy.data.images.remove(copy)


class ApplyModifiersStep(Step):
    def __enter__(self):
        for object in self.objects:
            if object.type != "MESH":
                continue

            object.data = object.data.copy()

            with bpy.context.temp_override(active_object=object, selected_objects={object}):
                for i, mod in enumerate(object.modifiers):
                    if type(mod) is bpy.types.ArmatureModifier:
                        continue

                    bpy.ops.object.modifier_apply(modifier=mod.name)

        return self


    def __exit__(self, *args):
        pass


class MergeMeshesStep(Step):
    to_delete = []

    def __enter__(self):
        self.select(lambda object : object.type == "MESH")
        bpy.ops.object.duplicate()
        bpy.ops.object.join()
        self.to_delete = self.gather()

        self.select_add(lambda object : object.type != "MESH")
        self.objects_forward = self.gather()

        for object in self.objects_forward:
            if object.type != "MESH":
                continue

            object.name = self.collection.name

        return self


    def __exit__(self, *args):
        self.select(None, self.to_delete)
        bpy.ops.object.delete()
        pass


class MaterializeStep(Step):
    def __enter__(self):
        format = self.context.scene.my_render_settings.export_format
        props = self.collection.merge_exporter_props
        
        if not props.materialize:
            return self
        
        for object in self.objects:
            if object.type != "MESH":
                continue

            self.process(object)

        return self


    def __exit__(self, *args):
        pass


    def process(self, object):
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


class ExportStep(Step):
    def __enter__(self):
        format = self.context.scene.my_render_settings.export_format
        props = self.collection.merge_exporter_props
        prefix = os.path.abspath(bpy.path.abspath(props.path)) + "/"
        path = prefix + self.collection.name + "." + format

        self.select()

        if props.origin and not props.export_origin:
            props.origin.select_set(False)

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

        return self


    def __exit__(self, *args):
        pass


def gather(collection, stack, parent_shared):
    if not collection.merge_exporter_props.active:
        return

    shared = {
        "parent": collection,
        "parent_object": None,
    }

    stack.append((collection, shared, parent_shared))

    for child in collection.children:
        gather(child, stack, shared)


def execute(context, collection):
    stack = []
    gather(collection, stack, None)

    if len(stack) == 0:
        return False

    return execute_inner(context, [], stack, collection)


def execute_inner(context, objects, stack, root):
    entry = stack.pop(0)
    collection = entry[0]
    shared = entry[1]
    parent_shared = entry[2]

    with (
        InitialStep(context, collection, list(collection.objects)) as s,
        RenameStep(s) as s,
        BakeStep(s) as s,
        ApplyModifiersStep(s) as s,
        MergeMeshesStep(s) as s,
        MaterializeStep(s) as s,
        SaveTexturesStep(s) as s,
        UnrenameStep(s) as s,
    ):
        objects.extend(s.objects_forward)

        for object in s.objects_forward:
            if object.type == "MESH":
                shared["parent_object"] = object
                break

        if parent_shared:
            parent_object = parent_shared["parent_object"]

            for object in s.objects_forward:
                object.parent = parent_object
                object.matrix_parent_inverse = parent_object.matrix_world.inverted()

        if len(stack) > 0:
            return execute_inner(context, objects, stack, root)
        
        with (
            InitialStep(context, root, list(objects)) as s,
            ReoriginStep(s) as s,
            ExportStep(s),
        ):
            return True
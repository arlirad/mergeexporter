import bpy
import mathutils
import numpy
import os


class StepShared:
    def __init__(self):
        self.encountered_data = {}
        self.encountered_materials = {}


class Step:
    def __init__(self, previous):
        self.objects = []
        self.objects_forward = []
        self.original_names = []
        self.duplicated_sources = []
        self.context = None
        self.collection = None
        self.root = None
        self.shared = None

        if type(previous) == bpy.types.Context:
            self.context = previous
            return

        if type(previous) == list:
            self.objects_forward = previous
            return
        
        self.objects = previous.objects_forward.copy()
        self.objects_forward = self.objects
        self.original_names = previous.original_names
        self.duplicated_sources = previous.duplicated_sources
        self.context = previous.context
        self.collection = previous.collection
        self.root = previous.root
        self.shared = previous.shared


    def select(self, condition=None, list=None):
        if list == None:
            list = self.objects

        if condition == None:
            condition = lambda obj : True

        bpy.ops.object.select_all(action="DESELECT")

        for object in list:
            try:
                object.select_set(condition(object))
            except ReferenceError:
                pass
            except:
                raise

        if len(self.context.selected_objects) > 0:
            self.context.view_layer.objects.active = self.context.selected_objects[0]


    def select_add(self, condition=None, list=None):
        if list == None:
            list = self.objects

        if condition == None:
            condition = lambda obj : True

        for object in list:
            try:
                if condition(object):
                    object.select_set(True)
            except ReferenceError:
                pass
            except:
                raise

        if len(self.context.selected_objects) > 0:
            self.context.view_layer.objects.active = self.context.selected_objects[0]


    def gather(self):
        return list(self.context.selected_objects)


class InitialStep(Step):
    def __init__(self, context, collection, root, shared, objects):
        super().__init__([])

        self.context = context
        self.collection = collection
        self.objects = objects
        self.objects_forward = self.objects
        self.root = root
        self.shared = shared
    

    def __enter__(self):
        return self


    def __exit__(self, *args):
        pass


class PreserveSelectionsStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.selections = []
        

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
            try:
                entry[0].name = entry[1]
            except ReferenceError:
                pass
            except:
                raise


class UnrenameStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.previous_names = []

    
    def __enter__(self):
        for entry in self.original_names:
            try:
                self.previous_names.append((entry[0], entry[0].name))
                entry[0].name = entry[1]
            except ReferenceError:
                pass
            except:
                raise

        return self


    def __exit__(self, *args):
        for entry in self.previous_names:
            try:
                entry[0].name = entry[1]
            except ReferenceError:
                pass
            except:
                raise


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


class DuplicateStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.to_delete = []


    def __enter__(self):
        props = self.collection.merge_exporter_props

        if not props.export_origin:
            self.select(lambda object : object.type == "MESH" and object != props.origin)
        else:
            self.select(lambda object : object.type == "MESH")

        objects = self.gather()
        duplicated = []

        for object in objects:
            self.select(None, [object])
            bpy.ops.object.duplicate(linked=True)

            object_dup = self.gather()[0]
            duplicated.append(object_dup)
            self.duplicated_sources.append((object_dup, object))

        self.select(None, duplicated)
        self.to_delete = self.gather()

        self.select_add(lambda object : object.type != "MESH")
        self.objects_forward = self.gather()

        return self


    def __exit__(self, *args):
        self.select(None, self.to_delete)
        bpy.ops.object.delete()


class CopyShapeKeysStep(Step):
    def __enter__(self):
        for pair in self.duplicated_sources:
            destination = pair[0]
            source = pair[1]

            if len(source.data.shape_keys.key_blocks) == 0:
                continue

            if destination.data.shape_keys == None:
                src_name = source.data.shape_keys.key_blocks[0].name
                destination.shape_key_add(name=src_name)

            map = self.map_indices(source, destination)
            self.copy_shapekeys(source, destination, map)

        return self
    

    def __exit__(self, *args):
        pass


    def get_distance_squared(self, a, b):
        return (a - b).length_squared


    def find_nearest_point_index(self, point, point_list):
        co = point.co
        nearest_dist = self.get_distance_squared(co, point_list[0].co)
        nearest_index = 0
        index = 0

        for list_point in point_list:
            dist = self.get_distance_squared(co, list_point.co)

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_index = index

            index = index + 1

        return nearest_index


    def map_indices(self, source, destination):
        src_basis = source.data.shape_keys.key_blocks[0]
        dst_basis = destination.data.shape_keys.key_blocks[0]
        indices = []

        for dst_point in dst_basis.data:
            index = self.find_nearest_point_index(dst_point, src_basis.data)
            indices.append(index)

        return indices


    def copy_shapekey_block(self, src_block, dst_block, map):
        for i in range(0, len(dst_block.data)):
            dst_block.data[i].co = src_block.data[map[i]].co


    def copy_shapekeys(self, source, destination, map):
        src_blocks = source.data.shape_keys.key_blocks
        dst_blocks = destination.data.shape_keys.key_blocks

        for src_block in src_blocks:
            if src_block.name in dst_blocks:
                continue

            dst_block = destination.shape_key_add(name=src_block.name)
            self.copy_shapekey_block(src_block, dst_block, map)


class DeleteShapeKeysStep(Step):
    def __enter__(self):
        for object in self.objects:
            if object.type != "MESH":
                continue

            if len(object.data.shape_keys.key_blocks) == 0:
                continue

            self.copy_data(object)
            self.remove_shapekeys(object)
        
        return self


    def __exit__(self, *args):
        pass


    def copy_data(self, object):
        object.data = object.data.copy()


    def remove_shapekeys(self, object):
        blocks = object.data.shape_keys.key_blocks

        for block in blocks:
            object.shape_key_remove(block)


class ReoriginStep(Step):
    def __init__(self, previous):
        super().__init__(previous)

        self.origin = mathutils.Matrix.Identity(4)
        self.origin_pure = None

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
            try:
                object.matrix_world = self.origin @ object.matrix_world
            except ReferenceError:
                pass
            except:
                raise

        if props.origin:
            props.origin.matrix_world = self.origin_pure


class SaveTexturesStep(Step):
    def __enter__(self):
        if not self.context.scene.merge_exporter_settings.save_textures:
            return self
        
        if not self.collection.merge_exporter_props.bake:
            return self

        props = self.root.merge_exporter_props
        prefix = os.path.abspath(bpy.path.abspath(props.path)) + "/"

        for object in self.objects:
            if object.type != "MESH":
                continue
            
            self.save_textures(self.collection.name, prefix)

        return self


    def __exit__(self, *args):
        pass


    def save_textures(self, name, path_prefix):
        format = "." + bpy.context.scene.merge_exporter_settings.export_texture_format
        texture_toggles = bpy.context.scene.merge_exporter_settings.texture_toggles

        if texture_toggles.albedo_toggle:
            self.save_image(name + ".albedo", path_prefix + name + ".albedo" + format)

        if texture_toggles.normal_toggle:
            self.save_image(name + ".normal", path_prefix + name + ".normal" + format)

        if texture_toggles.rough_toggle:
            self.save_image(name + ".rough", path_prefix + name + ".rough" + format)

        if texture_toggles.mask_toggle:
            self.save_image(name + ".mask", path_prefix + name + ".mask" + format)

        if texture_toggles.emission_toggle:
            self.save_image(name + ".emission", path_prefix + name + ".emission" + format)

        if texture_toggles.ao_toggle:
            self.save_image(name + ".ao", path_prefix + name + ".ao" + format)


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

            has_mirror = False

            try:
                for i, mod in enumerate(object.modifiers):
                    if type(mod) is bpy.types.MirrorModifier:
                        has_mirror = True
                        break

                if object.data.name in self.shared.encountered_data and not has_mirror:
                    object.data = self.shared.encountered_data[object.data.name]
                    continue
                else:
                    name = object.data.name
                    object.data = object.data.copy()
                    self.shared.encountered_data[name] = object.data

                self.select(None, [object])

                for i, mod in enumerate(object.modifiers):
                    if type(mod) is bpy.types.ArmatureModifier:
                        continue

                    bpy.ops.object.modifier_apply(modifier=mod.name)
            except ReferenceError:
                pass
            except:
                raise

        return self


    def __exit__(self, *args):
        pass


class MergeMeshesStep(Step):
    def __enter__(self):
        self.select(lambda object : object.type == "MESH")

        if len(self.context.selected_objects) > 1:
            bpy.ops.object.join()

        self.select_add(lambda object : object.type != "MESH")
        self.objects_forward = self.gather()

        name = self.collection.name

        #if self.collection.merge_exporter_props.override_name:
        #    name = self.collection.merge_exporter_props.name

        for object in self.objects_forward:
            if object.type != "MESH":
                continue

            object.name = name

        return self


    def __exit__(self, *args):
        pass


class MaterializeStep(Step):
    def __enter__(self):
        format = self.context.scene.merge_exporter_settings.export_format
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
        name = self.collection.name

        material_name = name + ".merged"
        texture_toggles = bpy.context.scene.merge_exporter_settings.texture_toggles

        if object.data.name in self.shared.encountered_materials:
            object.data.materials.clear()
            object.data.materials.append(self.shared.encountered_materials[object.data.name])

            return
        
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
            #node_albedo_image.image = bpy.data.images.get(name + ".albedo")
            node_tree.links.new(node_albedo_image.outputs[0], node_bsdf.inputs[0])

        if texture_toggles.normal_toggle:
            node_normalmap = node_tree.nodes.new(type='ShaderNodeNormalMap')
            node_normalmap.location = (160, -270)

            node_normal_image = node_tree.nodes.new(type='ShaderNodeTexImage')
            node_normal_image.location = (-160, -270)
            #node_normal_image.image = bpy.data.images.get(name + ".normal")

            node_tree.links.new(node_normal_image.outputs[0], node_normalmap.inputs[1])
            node_tree.links.new(node_normalmap.outputs[0], node_bsdf.inputs[5])

        if texture_toggles.rough_toggle:
            node_rough_image = node_tree.nodes.new(type='ShaderNodeTexImage')
            node_rough_image.location = (160, -810)
            #node_rough_image.image = bpy.data.images.get(name + ".rough")
            node_tree.links.new(node_rough_image.outputs[0], node_bsdf.inputs[2])

        node_tree.links.new(node_bsdf.outputs[0], node_output.inputs[0])

        self.shared.encountered_materials[object.data.name] = mat

        object.data.materials.clear()
        object.data.materials.append(mat)


class ExportStep(Step):
    def __enter__(self):
        format = self.context.scene.merge_exporter_settings.export_format
        props = self.collection.merge_exporter_props
        prefix = os.path.abspath(bpy.path.abspath(props.path)) + "/"
        path = prefix + self.collection.name + "." + format

        self.select()

        if format == "gltf":
            bpy.ops.export_scene.gltf(
                filepath = path,
                use_selection=True
            )
        else:
            bpy.ops.export_scene.fbx(
                filepath = path,
                use_selection=True,
                apply_scale_options="FBX_SCALE_ALL",
            )

        return self


    def __exit__(self, *args):
        pass


class ReparentStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.original_parents = []


    def __enter__(self):
        self.select(lambda obj : obj.type == "MESH")
        objs = self.gather()

        if len(objs) == 0:
            return self

        root = objs[0]

        for object in self.objects:
            if object.parent:
                continue

            if object.type != "MESH" and object.type != "EMPTY":
                continue

            if object == root:
                continue

            self.original_parents.append((object, object.parent))
            object.parent = root
            object.matrix_parent_inverse = root.matrix_world.inverted()

        return self


    def __exit__(self, *args):
        for entry in self.original_parents:
            try:
                entry[0].parent = entry[1]

                if entry[1]:
                    entry[0].matrix_parent_inverse = entry[1].matrix_world.inverted()
            except ReferenceError:
                pass
            except:
                raise


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

    step_shared = StepShared()
    step_shared.encountered_data = {}
    step_shared.encountered_materials = {}

    with PreserveSelectionsStep(context):
        return execute_inner(context, [], stack, collection, step_shared)


def execute_inner(context, objects, stack, root, step_shared):
    entry = stack.pop(0)
    collection = entry[0]
    shared = entry[1]
    parent_shared = entry[2]

    with (
        InitialStep(context, collection, root, step_shared, list(collection.objects)) as s,
        RenameStep(s) as s,
        BakeStep(s) as s,
        DuplicateStep(s) as s,
        DeleteShapeKeysStep(s) as s,
        ApplyModifiersStep(s) as s,
        CopyShapeKeysStep(s) as s,
        MergeMeshesStep(s) as s,
        MaterializeStep(s) as s,
        SaveTexturesStep(s) as s,
        UnrenameStep(s) as s,
        ReoriginStep(s) as s,
        ReparentStep(s) as s,
    ):
        objects.extend(s.objects_forward)

        for object in s.objects_forward:
            if object.type == "MESH":
                shared["parent_object"] = object
                break

        if parent_shared:
            parent_object = parent_shared["parent_object"]

            if parent_object:
                for object in s.objects_forward:
                    if object.parent != "MESH":
                        continue

                    object.parent = parent_object
                    object.matrix_parent_inverse = parent_object.matrix_world.inverted()

        if len(stack) > 0:
            return execute_inner(context, objects, stack, root, step_shared)
        
        with (
            InitialStep(context, root, root, step_shared, list(objects)) as s,
            ExportStep(s),
        ):
            return True
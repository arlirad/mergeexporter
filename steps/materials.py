import os

import bpy
import numpy

from .step import Step


class BakeStep(Step):
    def __enter__(self):
        props = self.collection.merge_exporter_props
        if not props.bake:
            return self

        self.select(lambda object: object.type == "MESH")
        bpy.ops.collection.merge_export_bake(
            prefix=self.collection.name, size=props.texture_size)

        return self

    def __exit__(self, *args):
        pass


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
            self.save_image(name + ".albedo", path_prefix +
                            name + ".albedo" + format)

        if texture_toggles.normal_toggle:
            self.save_image(name + ".normal", path_prefix +
                            name + ".normal" + format)

        if texture_toggles.rough_toggle:
            self.save_image(name + ".rough", path_prefix +
                            name + ".rough" + format)

        if texture_toggles.mask_toggle:
            self.save_image(name + ".mask", path_prefix +
                            name + ".mask" + format)

        if texture_toggles.emission_toggle:
            self.save_image(name + ".emission", path_prefix +
                            name + ".emission" + format)

        if texture_toggles.ao_toggle:
            self.save_image(name + ".ao", path_prefix + name + ".ao" + format)

    def save_image(self, name, destination):
        original = bpy.data.images.get(name)
        copy = original.copy()
        copy.scale(original.size[0], original.size[1])

        tmp_buf = numpy.empty(
            original.size[0] * original.size[1] * 4, numpy.float32)
        original.pixels.foreach_get(tmp_buf)
        copy.pixels.foreach_set(tmp_buf)

        copy.save(filepath=destination)
        bpy.data.images.remove(copy)


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
            object.data.materials.append(
                self.shared.encountered_materials[object.data.name])

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
            # node_albedo_image.image = bpy.data.images.get(name + ".albedo")
            node_tree.links.new(
                node_albedo_image.outputs[0], node_bsdf.inputs[0])

        if texture_toggles.normal_toggle:
            node_normalmap = node_tree.nodes.new(type='ShaderNodeNormalMap')
            node_normalmap.location = (160, -270)

            node_normal_image = node_tree.nodes.new(type='ShaderNodeTexImage')
            node_normal_image.location = (-160, -270)
            # node_normal_image.image = bpy.data.images.get(name + ".normal")

            node_tree.links.new(
                node_normal_image.outputs[0], node_normalmap.inputs[1])
            node_tree.links.new(node_normalmap.outputs[0], node_bsdf.inputs[5])

        if texture_toggles.rough_toggle:
            node_rough_image = node_tree.nodes.new(type='ShaderNodeTexImage')
            node_rough_image.location = (160, -810)
            # node_rough_image.image = bpy.data.images.get(name + ".rough")
            node_tree.links.new(
                node_rough_image.outputs[0], node_bsdf.inputs[2])

        node_tree.links.new(node_bsdf.outputs[0], node_output.inputs[0])

        self.shared.encountered_materials[object.data.name] = mat

        object.data.materials.clear()
        object.data.materials.append(mat)

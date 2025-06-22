# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright(c) 2025 Arlirad
# Licensed under the GNU General Public License v3.0 or later
# See the LICENSE file in the top-level directory for details.

import os

import bpy

from mathutils import Matrix, Vector

from .step import Step


class ReoriginStep(Step):
    def __init__(self, previous):
        super().__init__(previous)

        self.matrices = []

    def __enter__(self):
        props = self.collection.merge_exporter_props

        if not props.origin:
            return self

        for object in self.objects:
            self.matrices.append((object, Matrix(object.matrix_world)))

        origin = Matrix(props.origin.matrix_world)

        if props.use_origin_scale:
            decomposed = origin.decompose()
            origin = Matrix.LocRotScale(
                decomposed[0], decomposed[1], Vector((1.00, 1.00, 1.00)))

        for object in self.objects:
            object.matrix_world = origin.inverted() @ object.matrix_world

        return self

    def __exit__(self, *args):
        props = self.collection.merge_exporter_props

        if not props.origin:
            return

        for matrix in self.matrices:
            matrix[0].matrix_world = matrix[1]


class ReparentStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.original_parents = []

    def __enter__(self):
        self.select(lambda obj: obj.type == "MESH")
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
            entry[0].parent = entry[1]

            if entry[1]:
                entry[0].matrix_parent_inverse = entry[1].matrix_world.inverted()


class MergeMeshesStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.to_delete = []
        self.renamed_object = None
        self.renamed_original_name = None

    def __enter__(self):
        self.select(lambda object: object.type == "MESH")

        if len(self.context.selected_objects) > 1:
            bpy.ops.object.join()

        self.to_delete = self.gather()

        self.select_add(lambda object: object.type != "MESH")
        self.objects_forward = self.gather()

        name = self.collection.name

        if self.collection.merge_exporter_props.override_name:
            name = self.collection.merge_exporter_props.name

        if name in bpy.context.scene.objects:
            to_rename = bpy.context.scene.objects[name]

            self.renamed_object = to_rename
            self.renamed_original_name = to_rename.name

            to_rename.name = "...:..." + to_rename.name

        for object in self.objects_forward:
            if object.type != "MESH":
                continue

            object.name = name

        return self

    def __exit__(self, *args):
        self.select(None, self.to_delete)
        bpy.ops.object.delete()

        if self.renamed_object != None:
            self.renamed_object.name = self.renamed_original_name


class ExportStep(Step):
    def __enter__(self):
        format = self.context.scene.merge_exporter_settings.export_format
        props = self.collection.merge_exporter_props
        prefix = os.path.abspath(bpy.path.abspath(props.path)) + "/"
        name = self.collection.name

        if self.collection.merge_exporter_props.override_name:
            name = self.collection.merge_exporter_props.name

        path = prefix + name + "." + format

        self.select()

        if format == "gltf":
            bpy.ops.export_scene.gltf(
                filepath=path,
                use_selection=True
            )
        else:
            bpy.ops.export_scene.fbx(
                filepath=path,
                use_selection=True,
                apply_scale_options="FBX_SCALE_ALL",
            )

        return self

    def __exit__(self, *args):
        pass

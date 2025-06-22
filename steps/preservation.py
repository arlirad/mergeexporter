# Copyright(c) 2025 Arlirad
# Licensed under the GNU General Public License v3.0
# See the LICENSE file in the top-level directory for details.

import bpy

from .step import Step


class PreserveSelectionsStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.selections = []
        self.object = None

    def __enter__(self):
        self.object = bpy.context.view_layer.objects.active
        self.selections = self.context.selected_objects.copy()

        return self

    def __exit__(self, *args):
        self.select(None, self.selections)

        if self.object != None:
            bpy.context.view_layer.objects.active = self.object


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
            self.previous_names.append((entry[0], entry[0].name))
            entry[0].name = entry[1]

        return self

    def __exit__(self, *args):
        for entry in self.previous_names:
            entry[0].name = entry[1]


class DuplicateStep(Step):
    def __enter__(self):
        props = self.collection.merge_exporter_props

        if not props.export_origin:
            self.select(lambda object: object.type ==
                        "MESH" and object != props.origin)
        else:
            self.select(lambda object: object.type == "MESH")

        objects = self.gather()
        duplicated = []

        for object in objects:
            self.select(None, [object])
            bpy.ops.object.duplicate()

            object_dup = self.gather()[0]
            duplicated.append(object_dup)
            self.duplicated_sources.append((object_dup, object))

        self.select(None, duplicated)
        self.select_add(lambda object: object.type != "MESH")

        self.objects_forward = self.gather()

        return self

    def __exit__(self, *args):
        pass

# Copyright(c) 2025 Arlirad
# Licensed under the GNU General Public License v3.0
# See the LICENSE file in the top-level directory for details.

import bpy

from .step import Step


class ObjectModeStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.mode = None
        self.object = None

    def __enter__(self):
        self.object = bpy.context.view_layer.objects.active

        if self.object:
            self.mode = self.object.mode
            bpy.ops.object.mode_set(mode='OBJECT')

        return self

    def __exit__(self, *args):
        if self.mode != None:
            bpy.ops.object.mode_set(mode=self.mode)


class UnhideStep(Step):
    def __init__(self, previous):
        super().__init__(previous)
        self.visibilities = []
        self.collection_was_visible = False

    def __enter__(self):
        layer_collection = self.context.view_layer.layer_collection
        layer_collection_collection = self.find_layer_collection(
            layer_collection, self.collection.name
        )

        self.collection_was_visible = layer_collection_collection.hide_viewport
        layer_collection_collection.hide_viewport = False

        for object in self.objects:
            self.visibilities.append(
                (object, object.hide_get(), object.hide_viewport, object.hide_render)
            )

            object.hide_set(False)
            object.hide_viewport = False
            object.hide_render = False

        return self

    def __exit__(self, *args):
        layer_collection = self.context.view_layer.layer_collection
        self.find_layer_collection(
            layer_collection, self.collection.name
        ).hide_viewport = self.collection_was_visible

        for visibility in self.visibilities:
            visibility[0].hide_set(visibility[1])
            visibility[0].hide_viewport = visibility[2]
            visibility[0].hide_render = visibility[3]

    def find_layer_collection(self, layer_collection, name):
        if layer_collection.name == name:
            return layer_collection

        for child in layer_collection.children:
            found = self.find_layer_collection(child, name)
            if found:
                return found

        return None

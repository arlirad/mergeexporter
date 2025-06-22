# Copyright(c) 2025 Arlirad
# Licensed under the GNU General Public License v3.0
# See the LICENSE file in the top-level directory for details.

import bpy

from .step import Step


class CopyShapeKeysStep(Step):
    def __enter__(self):
        for pair in self.duplicated_sources:
            destination = pair[0]
            source = pair[1]

            if source.data.shape_keys == None:
                continue

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

            if object.data.shape_keys == None:
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

        for block in reversed(blocks):
            object.shape_key_remove(block)


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

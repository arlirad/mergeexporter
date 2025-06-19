import os

import bpy
import importlib
import numpy

from .final import ReoriginStep, ReparentStep, MergeMeshesStep, ExportStep
from .materials import BakeStep, MaterializeStep, SaveTexturesStep
from .modifiers import DeleteShapeKeysStep, CopyShapeKeysStep, ApplyModifiersStep
from .outlines import OutlineCorrectionStep
from .preparations import ObjectModeStep, UnhideStep
from .preservation import PreserveSelectionsStep, RenameStep, UnrenameStep, DuplicateStep
from .step import StepShared, InitialStep


def reload():
    importlib.reload(final)
    importlib.reload(materials)
    importlib.reload(modifiers)
    importlib.reload(outlines)
    importlib.reload(preparations)
    importlib.reload(preservation)
    importlib.reload(step)


reload()


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

    with (
        ObjectModeStep(context) as s,
        PreserveSelectionsStep(context) as s,
    ):
        return execute_inner(context, [], stack, collection, step_shared)


def execute_inner(context, objects, stack, root, step_shared):
    entry = stack.pop(0)
    collection = entry[0]
    shared = entry[1]
    parent_shared = entry[2]

    with (
        InitialStep(context, collection, root, step_shared, list(collection.objects)) as s,
        UnhideStep(s) as s,
        RenameStep(s) as s,
        BakeStep(s) as s,
        DuplicateStep(s) as s,
        DeleteShapeKeysStep(s) as s,
        OutlineCorrectionStep(s) as s,
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
            UnhideStep(s),
            ExportStep(s),
        ):
            return True

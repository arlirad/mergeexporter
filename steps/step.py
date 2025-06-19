import bpy


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
            def condition(obj): return True

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
            def condition(obj): return True

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

import bmesh
from mathutils import Matrix, Vector

from .step import Step

uv_name = "Outline"


def outline_normals(obj):
    meshd = obj.data.copy()
    meshs = obj.data.copy()

    if uv_name not in obj.data.uv_layers:
        obj.data.uv_layers.new(name=uv_name)

    bm = bmesh.new()
    bm.from_mesh(meshd)
    bm.to_mesh(meshd)
    bm.free()

    bm = bmesh.new()
    bm.from_mesh(meshs)

    for f in bm.edges:
        f.smooth = True

    for f in bm.faces:
        f.smooth = True

    bm.to_mesh(meshs)
    bm.free()

    active_name = meshd.uv_layers.active.name

    meshd.calc_tangents(uvmap=active_name)
    meshs.calc_tangents(uvmap=active_name)

    uv_layer = obj.data.uv_layers[uv_name].data

    for i in range(0, len(meshd.loops)):
        loopd = meshd.loops[i]
        loops = meshs.loops[i]

        nd = loopd.normal
        td = loopd.tangent
        bd = loopd.bitangent
        ns = loops.normal

        tbnd = Matrix((td, bd, nd)).transposed().inverted()
        corrected_normal = tbnd @ ns

        uv_layer[loopd.index].uv = Vector(
            (corrected_normal.x, -corrected_normal.y * loopd.bitangent_sign))


class OutlineCorrectionStep(Step):
    def __init__(self, previous):
        super().__init__(previous)

    def __enter__(self):
        props = self.collection.merge_exporter_props
        if not props.outline_correction:
            return self

        for object in self.objects:
            if object.type != "MESH":
                continue

            bm = bmesh.new()
            bm.from_mesh(object.data)
            bmesh.ops.triangulate(
                bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY"
            )
            bm.to_mesh(object.data)
            bm.free()

            outline_normals(object)

        return self

    def __exit__(self, *args):
        pass

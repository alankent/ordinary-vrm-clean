from pxr import Usd, Sdf, Gf, UsdGeom, UsdShade


# This class creates a new Mesh by adding faces one at a time.
# When don, you ask it to create a new Mesh prim.
class MeshMaker:

    def __init__(self, stage: Usd.Stage, material):
        self.stage = stage
        self.material = material
        #self.extent = [] # Two float3 values, representing the min/max coords of the 3D space occupied.
        self.faceVertexCounts = []
        self.faceVertexIndices = []
        self.normals = []
        self.st = []
        self.points = []

    # Create a Mesh prim at the given prim path.
    def create_at_path(self, prim_path) -> UsdGeom.Mesh:
        # https://stackoverflow.com/questions/74462822/python-for-usd-map-a-texture-on-a-cube-so-every-face-have-the-same-image
        mesh: UsdGeom.Mesh = UsdGeom.Mesh.Define(self.stage, prim_path)
        mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
        mesh.CreatePointsAttr(self.points)
        mesh.CreateExtentAttr(UsdGeom.PointBased(mesh).ComputeExtent(mesh.GetPointsAttr().Get()))
        mesh.CreateNormalsAttr(self.normals)
        mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
        mesh.CreateFaceVertexCountsAttr(self.faceVertexCounts)
        mesh.CreateFaceVertexIndicesAttr(self.faceVertexIndices)
        mesh.CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying).Set(self.st)
        mesh.CreatePrimvar('skel:geomBindTransform', Sdf.ValueTypeNames.Matrix4d).Set(Gf.Matrix4d(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1))
        UsdShade.MaterialBindingAPI(mesh).GetDirectBindingRel().SetTargets(self.material)

        #mesh.GetStAttr().SetInterpolation("faceVarying")
        #UsdGeom.Primvar(mesh).SetInterpolation("faceVarying")
        #UsdGeom.Primvar(mesh).SetElementSize(4)

        return mesh
    
    # Add a new face (3 points with normals and mappings to part of the texture)
    def add_face(self, point1, point2, point3, normal1, normal2, normal3, st1, st2, st3):
        self.faceVertexCounts.append(3)
        self.faceVertexIndices.append(self.index_of_point(point1))
        self.faceVertexIndices.append(self.index_of_point(point2))
        self.faceVertexIndices.append(self.index_of_point(point3))
        self.normals.append(normal1)
        self.normals.append(normal2)
        self.normals.append(normal3)
        self.st.append(st1)
        self.st.append(st2)
        self.st.append(st3)

    # Given a point, find an existing points array entry and return its index, otherwise add another point
    # and return the index of the new point.
    def index_of_point(self, point: Gf.Vec3f):
        for i in range(0, len(self.points)):
            if self.points[i] == point:
                return i
        self.points.append(point)
        return len(self.points) - 1
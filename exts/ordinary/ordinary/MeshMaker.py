from pxr import Usd, Sdf, Gf, UsdGeom, UsdShade, UsdSkel


# This class creates a new Mesh by adding faces one at a time.
# When don, you ask it to create a new Mesh prim.
class MeshMaker:

    def __init__(self, stage: Usd.Stage, material, skeleton, skelJoints):
        self.stage = stage
        self.material = material
        self.faceVertexCounts = []
        self.faceVertexIndices = []
        self.normals = []
        self.st = []
        self.points = []
        self.skeleton = skeleton
        self.skelJoints = skelJoints
        self.skelJointIndices = []
        self.skelJointWeights = []

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
        ba: UsdSkel.BindingAPI = UsdSkel.BindingAPI(mesh)
        ba.Apply(mesh.GetPrim())
        ba.CreateGeomBindTransformAttr(Gf.Matrix4d(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1))
        ba.CreateSkeletonRel().SetTargets(self.skeleton)
        ba.CreateJointsAttr(self.skelJoints)
        ba.CreateJointIndicesPrimvar(False, elementSize=4).Set(self.skelJointIndices)
        ba.CreateJointWeightsPrimvar(False, elementSize=4).Set(self.skelJointWeights)
        UsdShade.MaterialBindingAPI(mesh).GetDirectBindingRel().SetTargets(self.material)
        return mesh
    
    # Add a new face (3 points with normals and mappings to part of the texture)
    def add_face(self, points, jointIndices, jointWeights, pi1, pi2, pi3, normal1, normal2, normal3, st1, st2, st3):
        self.faceVertexCounts.append(3)
        self.faceVertexIndices.append(self.new_index_of_point(points, jointIndices, jointWeights, pi1))
        self.faceVertexIndices.append(self.new_index_of_point(points, jointIndices, jointWeights, pi2))
        self.faceVertexIndices.append(self.new_index_of_point(points, jointIndices, jointWeights, pi3))
        self.normals.append(normal1)
        self.normals.append(normal2)
        self.normals.append(normal3)
        self.st.append(st1)
        self.st.append(st2)
        self.st.append(st3)

    # Given a point, find an existing points array entry and return its index, otherwise add another point
    # and return the index of the new point.
    # If adding a new point, also copy across the skeleton joint index and joint weight from the old point.
    # TODO: This could be optimized with a lookup table of point->index.
    def new_index_of_point(self, points, jointIndices, jointWeights, point_index):

        point = points[point_index]
        for i in range(0, len(self.points)):
            if self.points[i] == point:
                return i

        self.points.append(point)

        # Copy across the old joint information. This assumes element_size = 4.
        self.skelJointIndices.append(jointIndices[point_index * 4])
        self.skelJointIndices.append(jointIndices[point_index * 4 + 1])
        self.skelJointIndices.append(jointIndices[point_index * 4 + 2])
        self.skelJointIndices.append(jointIndices[point_index * 4 + 3])
        self.skelJointWeights.append(jointWeights[point_index * 4])
        self.skelJointWeights.append(jointWeights[point_index * 4 + 1])
        self.skelJointWeights.append(jointWeights[point_index * 4 + 2])
        self.skelJointWeights.append(jointWeights[point_index * 4 + 3])
        
        return len(self.points) - 1
    
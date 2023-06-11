import typing
import omni.ext
import omni.ui as ui
import omni.kit.commands
from pxr import Usd, Sdf, Gf, UsdGeom, UsdShade
from .MeshMaker import MeshMaker
import math

# Good resource https://github.com/NVIDIA-Omniverse/USD-Tutorials-And-Examples/blob/main/ColaboratoryNotebooks/usd_introduction.ipynb
# Also https://docs.omniverse.nvidia.com/prod_kit/prod_kit/programmer_ref/usd/transforms/get-world-transforms.html


def get_world_translate(prim: Usd.Prim) -> Gf.Vec3d:
    """
    Get the local transformation of a prim using Xformable.
    See https://graphics.pixar.com/usd/release/api/class_usd_geom_xformable.html
    Args:
        prim: The prim to calculate the world transformation.
    Returns:
        - Translation vector.
    """
    xform = UsdGeom.Xformable(prim)
    time = Usd.TimeCode.Default() # The time at which we compute the bounding box
    world_transform: Gf.Matrix4d = xform.ComputeLocalToWorldTransform(time)
    translation: Gf.Vec3d = world_transform.ExtractTranslation()
    return translation


class ExtractFaceMeshes:
    
    def __init__(self, stage: Usd.Stage):
        self.stage = stage
        self.segment_map = None
    
    def mesh_is_face_mesh(mesh: UsdGeom.Mesh):
        """
        Return true if this Mesh is the Face mesh we want to convert.
        Names are like "Face_baked" and "Face__merged__Clone_".
        """
        name: str = mesh.GetName()
        if name.startswith("Face_"):
            return True
        else:
            return False
    
    def extract_face_meshes(self, mesh: UsdGeom.Mesh):
        
        # Run through the children sub-meshes
        # "F00_000_00_FaceMouth_00_FACE" -- Needs splitting into upper teeth, lower teeth, mouth cavity, toungue
        # "F00_000_00_EyeWhite_00_EYE"
        # "F00_000_00_FaceEyeline_00_FACE"
        # "F00_000_00_FaceEyelash_00_FACE"
        # "F00_000_00_FaceBrow_00_FACE"
        # "F00_000_00_EyeIris_00_EYE"
        # "F00_000_00_EyeHighlight_00_EYE" -- Drop? Gone in new version.
        # "F00_000_00_Face_00_SKIN" or "N00_000_00_Face_00_SKIN__Instance_"
        # "F00_000_00_Face_00_SKIN_1"
        # "F00_000_00_EyeExtra_01_EYE" -- Drop? Gone in new version.
        for child in mesh.GetChildren():
            if child.IsA(UsdGeom.Subset):
                name: str = child.GetName()
                if "_Face_" in name and "SKIN" in name:
                    self.extract_face_skin(mesh, child)
                elif "_FaceMouth_" in name:
                    self.extract_mouth(mesh, child)
                elif "_FaceEyeline_" in name:
                    self.extract_eyeline(mesh, child)
                elif "_FaceEyelash_" in name:
                    self.extract_eyelash(mesh, child)
                elif "_FaceBrow_" in name:
                    self.extract_eyebrow(mesh, child)
                elif "_EyeWhite_" in name:
                    self.extract_eyewhites(mesh, child)
                elif "_EyeIris" in name:
                    self.extract_irises(mesh, child)

    # Copy the whole mesh across for the face.
    # The original mesh in VRoid seems to have points that are not used.
    def extract_face_skin(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        """
        Create a new Mesh for the face based on the old mesh subset.
        """
        material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
        new_mesh = MeshMaker(self.stage, material)
        self.copy_subset(new_mesh, old_mesh, old_subset)
        new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('face_skin'))

    def extract_mouth(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        """
        Extract multiple meshes from the mouth: upper teeth (needs joining), lower teeth (needs joining),
        tounge, and mouth cavity.
        """
        num_segments = self.segment_mesh(old_mesh, old_subset)
        if num_segments == 7:
            material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()

            # 0 = inner upper teeth, 1 = outer upper teeth
            new_mesh = MeshMaker(self.stage, material)
            self.copy_subset(new_mesh, old_mesh, old_subset, 0, 1)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('upper_teeth'))

            # 2 = inner lower teeth, 3 = outer lower teeth
            new_mesh = MeshMaker(self.stage, material)
            self.copy_subset(new_mesh, old_mesh, old_subset, 2, 3)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('lower_teeth'))
            
            # 4 = mouth cavity
            new_mesh = MeshMaker(self.stage, material)
            self.copy_subset(new_mesh, old_mesh, old_subset, 4, 4)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('mouth_cavity'))
            
            # 5 = upper tongue, 6 = lower tongue
            new_mesh = MeshMaker(self.stage, material)
            self.copy_subset(new_mesh, old_mesh, old_subset, 5, 6)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('tongue'))
            
        self.clear_segment_map()

    def extract_eyeline(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
        new_mesh = MeshMaker(self.stage, material)
        self.copy_subset(new_mesh, old_mesh, old_subset)
        new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('eyeline'))

    def extract_eyelash(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
        new_mesh = MeshMaker(self.stage, material)
        self.copy_subset(new_mesh, old_mesh, old_subset)
        new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('eyelash'))

    def extract_eyebrow(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
        new_mesh = MeshMaker(self.stage, material)
        self.copy_subset(new_mesh, old_mesh, old_subset)
        new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('eyebrow'))

    def extract_eyewhites(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        """
        May need two - one for left eye and one for right eye.
        """
        material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
        new_mesh = MeshMaker(self.stage, material)
        self.copy_subset(new_mesh, old_mesh, old_subset)
        new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('eyewhites'))

    def extract_irises(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        """
        Extract two eye meshes separately, then add them under an Xform prim so they can pivot.
        """
        self.segment_mesh(old_mesh, old_subset)
        eyes = ["left_eye", "right_eye"]
        for i in range(len(eyes)):
            material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
            new_mesh = MeshMaker(self.stage, material)
            self.copy_subset(new_mesh, old_mesh, old_subset, i, i)
            pivot_prim_path = old_mesh.GetPath().GetParentPath().AppendChild(eyes[i] + "_pivot")
            xformPrim = UsdGeom.Xform.Define(self.stage, pivot_prim_path)
            eye_mesh: UsdGeom.Mesh = new_mesh.create_at_path(pivot_prim_path.AppendChild(eyes[i]))
            extent = eye_mesh.GetExtentAttr().Get()
            (x1,y1,z1) = extent[0]
            (x2,y2,z2) = extent[1]
            (dx,dy,dz) = ((x1+x2)/4.0, (y1+y2)/2.0, z2 - (y2-y1) * 2.0)
            UsdGeom.XformCommonAPI(xformPrim).SetTranslate((dx, dy, dz))
            UsdGeom.XformCommonAPI(eye_mesh).SetTranslate((-dx, -dy, -dz))
        self.clear_segment_map()

    def copy_subset(self, new_mesh: MeshMaker, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset, segment1=None, segment2=None):
        faceVertexIndices = old_mesh.GetAttribute('faceVertexIndices').Get()
        points = old_mesh.GetAttribute('points').Get()     # GetPointsAttr().Get()
        normals = old_mesh.GetAttribute('normals').Get()   # GetNormalsAttr().Get()
        st = old_mesh.GetAttribute('primvars:st').Get()
        for face_index in old_subset.GetAttribute('indices').Get():  # GetIndicesAttr().Get():
            if self.segment_map is None or self.segment_map[face_index] == segment1 or self.segment_map[face_index] == segment2:
                p1 = points[faceVertexIndices[face_index * 3]]
                p2 = points[faceVertexIndices[face_index * 3 + 1]]
                p3 = points[faceVertexIndices[face_index * 3 + 2]]
                n1 = normals[face_index * 3]
                n2 = normals[face_index * 3 + 1]
                n3 = normals[face_index * 3 + 2]
                st1 = st[face_index * 3]
                st2 = st[face_index * 3 + 1]
                st3 = st[face_index * 3 + 2]
                new_mesh.add_face(p1, p2, p3, n1, n2, n3, st1, st2, st3)

    def clear_segment_map(self):
        self.segment_map = None

    def segment_mesh(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        faceVertexIndices = old_mesh.GetAttribute('faceVertexIndices').Get()
        subset_indices = old_subset.GetAttribute('indices').Get()
        num_faces = math.ceil(len(faceVertexIndices) / 3)
        self.segment_map = [None] * num_faces
        segment = 0

        while True:

            # Find first unused face
            i = 0
            while i < len(subset_indices) and self.segment_map[subset_indices[i]] is not None:
                i += 1
            if i == len(subset_indices):
                break  # Nothing found, so all done!
            first_face = i

            # Make a pass through the array looking for faces that share a point we have seen before.
            seen = set()
            seen.add(faceVertexIndices[subset_indices[i] * 3])
            seen.add(faceVertexIndices[subset_indices[i] * 3 + 1])
            seen.add(faceVertexIndices[subset_indices[i] * 3 + 2])
            self.segment_map[i] = segment
            
            found_one = True
            # print("segment " + str(segment))
            while found_one:
                found_one = False
                i = first_face
                while i < len(subset_indices):
                    face = subset_indices[i]
                    if self.segment_map[face] is None:
                        if faceVertexIndices[face * 3] in seen or faceVertexIndices[face * 3 + 1] in seen or faceVertexIndices[face * 3 + 2] in seen:
                            seen.add(faceVertexIndices[face * 3])
                            seen.add(faceVertexIndices[face * 3 + 1])
                            seen.add(faceVertexIndices[face * 3 + 2])
                            self.segment_map[face] = segment
                            found_one = True
                    i += 1
                #print(self.segment_map)
            
            segment += 1

        # print("Found " + str(segment) + " segments in " + old_subset.GetName())
        # print(self.segment_map)

        return segment

import typing
import omni.ext
import omni.ui as ui
import omni.kit.commands
from pxr import Usd, Sdf, Gf, UsdGeom, UsdShade, UsdSkel
from .MeshMaker import MeshMaker
import math

# Good resource https://github.com/NVIDIA-Omniverse/USD-Tutorials-And-Examples/blob/main/ColaboratoryNotebooks/usd_introduction.ipynb
# Also https://docs.omniverse.nvidia.com/prod_kit/prod_kit/programmer_ref/usd/transforms/get-world-transforms.html


#def get_world_translate(prim: Usd.Prim) -> Gf.Vec3d:
#    """
#    Get the local transformation of a prim using Xformable.
#    See https://graphics.pixar.com/usd/release/api/class_usd_geom_xformable.html
#    Args:
#        prim: The prim to calculate the world transformation.
#    Returns:
#        - Translation vector.
#    """
#    xform = UsdGeom.Xformable(prim)
#    time = Usd.TimeCode.Default() # The time at which we compute the bounding box
#    world_transform: Gf.Matrix4d = xform.ComputeLocalToWorldTransform(time)
#    translation: Gf.Vec3d = world_transform.ExtractTranslation()
#    return translation


class ExtractMeshes:
    
    def __init__(self, stage: Usd.Stage):
        self.stage = stage
        self.segment_map = None
    
    # Return true if this Mesh is the Face mesh we want to convert.
    # Names are like "Face_baked" and "Face__merged__Clone_".
    #def mesh_is_face_mesh(mesh: UsdGeom.Mesh):
    #    name: str = mesh.GetName()
    #    if name.startswith("Face_"):
    #        return True
    #    else:
    #        return False
    
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

    def extract_hair_meshes(self, old_mesh: UsdGeom.Mesh):
        # Run through the children sub-meshes and copy them to their own Mesh
        n = 0
        for child in old_mesh.GetChildren():
            if child.IsA(UsdGeom.Subset):
                material = UsdShade.MaterialBindingAPI(child).GetDirectBindingRel().GetTargets()
                skeleton = UsdSkel.BindingAPI(old_mesh).GetSkeletonRel().GetTargets()
                skelJoints = UsdSkel.BindingAPI(old_mesh).GetJointsAttr().Get()
                new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
                self.copy_subset(new_mesh, old_mesh, child)
                new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('hair_' + str(n)))
                n += 1

    def extract_body_meshes(self, old_mesh: UsdGeom.Mesh):
        # Run through the children sub-meshes and copy them to their own Mesh
        n = 0
        for child in old_mesh.GetChildren():
            if child.IsA(UsdGeom.Subset):
                material = UsdShade.MaterialBindingAPI(child).GetDirectBindingRel().GetTargets()
                skeleton = UsdSkel.BindingAPI(old_mesh).GetSkeletonRel().GetTargets()
                skelJoints = UsdSkel.BindingAPI(old_mesh).GetJointsAttr().Get()
                new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
                self.copy_subset(new_mesh, old_mesh, child)
                name: str = child.GetName()
                if "_Body_" in name:
                    new_name = 'bodyskin'
                elif "_Tops_" in name:
                    new_name = 'clothes_upper'
                elif "_Bottoms_" in name:
                    new_name = 'clothes_lower'
                elif "_Shoes_" in name:
                    new_name = 'shoes'
                else:
                    new_name = 'body_' + str(n)
                    n += 1
                new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild(new_name))

    # Copy the whole mesh across for the face.
    # The original mesh in VRoid points that are not used in any face.
    def extract_face_skin(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        self.make_mesh_from_subset(old_mesh, old_subset, 'face_skin')

    # Extract multiple meshes from the mouth: upper teeth (needs joining), lower teeth (needs joining),
    # tounge, and mouth cavity.
    def extract_mouth(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):

        # This one is the most tricky case. There is one "subset" for the mouth, which includes upper
        # and lower teeth, as well as the mouth cavity. We need upper and lower teeth in their own
        # meshes for Audio2Face to work.
        # So, we segment the mesh, ignoring points that are not actually used by faces (there are lot!).
        # The first two connected meshes are for the inside and outside of the teeth.
        # The next two are the lower teeth.
        # Then there is a single connected mesh for the mouth cavity.
        # Finally there are another two meshes for the top and bottom of the tongue.

        num_segments = self.segment_mesh(old_mesh, old_subset)
        if num_segments == 7:
            material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
            skeleton = UsdSkel.BindingAPI(old_mesh).GetSkeletonRel().GetTargets()
            skelJoints = UsdSkel.BindingAPI(old_mesh).GetJointsAttr().Get()

            # 0 = inner upper teeth, 1 = outer upper teeth
            new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
            self.copy_subset(new_mesh, old_mesh, old_subset, 0, 1)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('upper_teeth'))

            # 2 = inner lower teeth, 3 = outer lower teeth
            new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
            self.copy_subset(new_mesh, old_mesh, old_subset, 2, 3)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('lower_teeth'))
            
            # 4 = mouth cavity
            new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
            self.copy_subset(new_mesh, old_mesh, old_subset, 4, 4)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('mouth_cavity'))
            
            # 5 = upper tongue, 6 = lower tongue
            new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
            self.copy_subset(new_mesh, old_mesh, old_subset, 5, 6)
            new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild('tongue'))
            
        self.clear_segment_map()

    # Eyeline we could split into left and right eyes, but we don't need to.
    # It uses a separate mesh with its own material.
    def extract_eyeline(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        self.make_mesh_from_subset(old_mesh, old_subset, 'eyeline')

    # Eyelash we could split into left and right eyes, but we don't need to.
    # It uses a separate mesh with its own material.
    def extract_eyelash(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        self.make_mesh_from_subset(old_mesh, old_subset, 'eyelash')

    # Eyebrows we could split into left and right eyes, but we don't need to.
    # It uses a separate mesh with its own material.
    def extract_eyebrow(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        self.make_mesh_from_subset(old_mesh, old_subset, 'eyebrow')

    # Eyewhites are interesting. Rather than be a sphere or similar, there is actually a gap
    # behind the irises, which causes shadows. Might want to adjust these one day, but they
    # stop from being able to look inside the head when the eyes move (the whites do not move).
    def extract_eyewhites(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        self.make_mesh_from_subset(old_mesh, old_subset, 'eyewhites')

    # We need to extract the left and right eye irises. There is lots of other points and things
    # that are not actually used, so we want to toss them.
    def extract_irises(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):
        self.segment_mesh(old_mesh, old_subset)
        eyes = ["left_eye", "right_eye"]
        for i in range(len(eyes)):

            material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
            skeleton = UsdSkel.BindingAPI(old_mesh).GetSkeletonRel().GetTargets()
            skelJoints = UsdSkel.BindingAPI(old_mesh).GetJointsAttr().Get()
            new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
            self.copy_subset(new_mesh, old_mesh, old_subset, i, i)

            # We do a bit more work because eyes need to rotate. So we insert an Xform about the
            # Mesh for the two eyes. Its a bit behind the eyes, moved a bit towards the center of the head
            # as the front of the characters is more rounded than a real head.
            # We use the size of the iris to estimate how far behind the iris the pivot point needs to go.
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

    # Create a new mesh from the given submesh (copy it all to a new Mesh)
    def make_mesh_from_subset(self, old_mesh, old_subset, prim_name):
        material = UsdShade.MaterialBindingAPI(old_subset).GetDirectBindingRel().GetTargets()
        skeleton = UsdSkel.BindingAPI(old_mesh).GetSkeletonRel().GetTargets()
        skelJoints = UsdSkel.BindingAPI(old_mesh).GetJointsAttr().Get()
        new_mesh = MeshMaker(self.stage, material, skeleton, skelJoints)
        self.copy_subset(new_mesh, old_mesh, old_subset)
        new_mesh.create_at_path(old_mesh.GetPath().GetParentPath().AppendChild(prim_name))

    # A GeomSubset holds an array of indicies of which faces are used by this subset.
    # But we need it in a separate Mesh for Audio2Face to be happy.
    # So we run down the list of referenced faces, and add them to a completely new Mesh.
    # This drops lots of unused points and cleans up the model.
    def copy_subset(self, new_mesh: MeshMaker, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset, segment1=None, segment2=None):
        faceVertexIndices = old_mesh.GetAttribute('faceVertexIndices').Get()
        points = old_mesh.GetAttribute('points').Get()     # GetPointsAttr().Get()
        normals = old_mesh.GetAttribute('normals').Get()   # GetNormalsAttr().Get()
        st = old_mesh.GetAttribute('primvars:st').Get()
        jointIndices = old_mesh.GetAttribute('primvars:skel:jointIndices').Get()
        jointWeights = old_mesh.GetAttribute('primvars:skel:jointWeights').Get()
        for face_index in old_subset.GetAttribute('indices').Get():  # GetIndicesAttr().Get():
            if self.segment_map is None or self.segment_map[face_index] == segment1 or self.segment_map[face_index] == segment2:

                # This is hard coded for VRoid Studio in that it assumes each face is a triangle with 3 points.
                # Pull the details of each triangle on the surface and add it to a new mesh, building it up from scratch.
                pi1 = faceVertexIndices[face_index * 3]
                pi2 = faceVertexIndices[face_index * 3 + 1]
                pi3 = faceVertexIndices[face_index * 3 + 2]
                n1 = normals[face_index * 3]
                n2 = normals[face_index * 3 + 1]
                n3 = normals[face_index * 3 + 2]
                st1 = st[face_index * 3]
                st2 = st[face_index * 3 + 1]
                st3 = st[face_index * 3 + 2]
                new_mesh.add_face(points, jointIndices, jointWeights, pi1, pi2, pi3, n1, n2, n3, st1, st2, st3)

    # Clear the segment map.
    def clear_segment_map(self):
        self.segment_map = None

    # Create a segment map by running through all the faces (and their verticies), then any other face
    # that shares a point with the same mesh is also considered to be part of the same segment.
    def segment_mesh(self, old_mesh: UsdGeom.Mesh, old_subset: UsdGeom.Subset):

        # Work out some commonly used attributes.
        faceVertexIndices = old_mesh.GetAttribute('faceVertexIndices').Get()
        subset_indices = old_subset.GetAttribute('indices').Get()
        num_faces = math.ceil(len(faceVertexIndices) / 3)
        self.segment_map = [None] * num_faces
        segment = 0

        # Loop until we fail to find a face that has not been marked with a segment number.
        while True:
            i = 0
            while i < len(subset_indices) and self.segment_map[subset_indices[i]] is not None:
                i += 1
            if i == len(subset_indices):
                # Nothing found, so we are all done!
                break
            first_face = i

            # Rather than adding the 3D coordinates, we add the index to the array of "points".
            # If anything reuses the same index, then its in the same continuous mesh.
            seen = set()
            seen.add(faceVertexIndices[subset_indices[i] * 3])
            seen.add(faceVertexIndices[subset_indices[i] * 3 + 1])
            seen.add(faceVertexIndices[subset_indices[i] * 3 + 2])
            self.segment_map[i] = segment

            # We have no guarantee on the order of faces, so we do a pass from front to end.
            # If a face was added to the current segment, we retry until we fail to find anything.            
            found_one = True
            while found_one:
                found_one = False
                i = first_face
                while i < len(subset_indices):
                    face = subset_indices[i]
                    if self.segment_map[face] is None:
                        if faceVertexIndices[face * 3] in seen or faceVertexIndices[face * 3 + 1] in seen or faceVertexIndices[face * 3 + 2] in seen:
                            # One of the 3 points of the current Face shares a vertex with the current mesh,
                            # so add all 3 points as belonging to the mesh and mark that we did find at least one more.
                            seen.add(faceVertexIndices[face * 3])
                            seen.add(faceVertexIndices[face * 3 + 1])
                            seen.add(faceVertexIndices[face * 3 + 2])
                            self.segment_map[face] = segment
                            found_one = True
                    i += 1
            
            segment += 1

        return segment

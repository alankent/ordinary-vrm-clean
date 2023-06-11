# Made using: https://youtu.be/eGxV_PGNpOg
# Lessons learned
# - work out your package name first (it affects directory structure)
# - DeletePrims references Sdf which is not imported for you
import omni.ext
import omni.ui as ui
import omni.kit.commands
from pxr import Usd, Sdf, Gf, UsdGeom, UsdShade
from .ExtractFaceMeshes import ExtractFaceMeshes


# Functions and vars are available to other extension as usual in python: `example.python_ext.some_public_function(x)`
def some_public_function(x: int):
    print("[ordinary] some_public_function was called with x: ", x)
    return x ** x


# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class OrdinaryExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def on_startup(self, ext_id):
        self._window = ui.Window("VRM Import Cleanup v1", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")

                def on_click():
                    self.clean_up_prim()
                    label.text = "clicked"

                def on_dump():
                    label.text = "empty"
                    # TODO: Debugging: Print hierarchy of all prims in stage, all attributes of prims that are arrays
                    self.dump_stage()

                label.text = "dump"

                with ui.HStack():
                    ui.Button("Clean", clicked_fn=on_click)
                    ui.Button("Dump", clicked_fn=on_dump)

    def on_shutdown(self):
        print("[ordinary] ordinary shutdown")

    def clean_up_prim(self):

        # TODO: Could wrap in a big 'undo' wrapper so there are all undone together

        # Convert to SkelRoot type.
        # TODO: This is not a command, so Undo won't work on this one
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()

        # TODO: I just removed this because I think its wrong
        # root_prim = stage.GetPrimAtPath('/World/Root')
        # root_prim.SetTypeName('SkelRoot')

        # Move Skeleton directly under Root layer
        # self.move_if_necessary(stage, '/World/Root/J_Bip_C_Hips0/Skeleton', '/World/Root/Skeleton')

        # Move meshes directly under Root layer, next to Skeleton
        # self.move_if_necessary(stage, '/World/Root/J_Bip_C_Hips0/Face_baked', '/World/Root/Face_baked')
        # self.move_if_necessary(stage, '/World/Root/J_Bip_C_Hips0/Body_baked', '/World/Root/Body_baked')
        # self.move_if_necessary(stage, '/World/Root/J_Bip_C_Hips0/Hair001_baked', '/World/Root/Hair001_baked')

        # Patch the skeleton structure, if not done already. Add "Root" to the joint list.
        skeleton_prim = stage.GetPrimAtPath('/World/Root/J_Bip_C_Hips0/Skeleton')
        if skeleton_prim:
            self.add_parent_to_skeleton_joint_list(skeleton_prim, 'Root')

        # TODO: Delete - turns out not necessary - something recomputes it automatically.
        for child in stage.GetPrimAtPath('/World/Root/J_Bip_C_Hips0').GetChildren():
            if child.IsA(UsdGeom.Mesh):
                self.add_parent_to_mesh_joint_list(child, 'Root')
                # self.split_disconnected_meshes(stage, child)
                if child.GetName().startswith("Face_"):
                    e = ExtractFaceMeshes(stage)
                    e.extract_face_meshes(child)

        #self.add_parent_to_mesh_joint_list(stage, '/World/Root/J_Bip_C_Hips0/Face_baked', 'Root')
        #self.add_parent_to_mesh_joint_list(stage, '/World/Root/J_Bip_C_Hips0/Body_baked', 'Root')
        #self.add_parent_to_mesh_joint_list(stage, '/World/Root/J_Bip_C_Hips0/Hair001_baked', 'Root')
        #self.add_parent_to_mesh_joint_list(stage, '/World/Root/J_Bip_C_Hips0/Face__merged__Clone_', 'Root')
        #self.add_parent_to_mesh_joint_list(stage, '/World/Root/J_Bip_C_Hips0/Body__merged_', 'Root')
        #self.add_parent_to_mesh_joint_list(stage, '/World/Root/J_Bip_C_Hips0/Hair001__merged_', 'Root')

        # Delete the dangling node (was old SkelRoot)
        # self.delete_if_no_children(stage, '/World/Root/J_Bip_C_Hips0')

        # Delete old skeleton if present
        if stage.GetPrimAtPath('/World/Root/J_Bip_C_Hips0/Skeleton/J_Bip_C_Hips'):
            omni.kit.commands.execute('DeletePrims', paths=[Sdf.Path('/World/Root/J_Bip_C_Hips0/Skeleton/J_Bip_C_Hips')])

    def move_if_necessary(self, stage, source_path, target_path):
        """
        If a prim exists at the source path, move it to the target path.
        Returns true if moved, false otherwise.
        """
        if stage.GetPrimAtPath(source_path):
            omni.kit.commands.execute(
                'MovePrim',
                path_from=source_path,
                path_to=target_path,
                keep_world_transform=False,
                destructive=False)
            return True
        return False

    def delete_if_no_children(self, stage, path):
        """
        Delete the prim at the specified path if it exists and has no children.
        Returns true if deleted, false otherwise.
        """
        print(path)
        prim = stage.GetPrimAtPath(path)
        if prim:
            print("found")
            if not prim.GetChildren():
                omni.kit.commands.execute(
                    'DeletePrims',
                    paths=[Sdf.Path(path)],
                    destructive=False)
                return True
        return False

    def add_parent_to_skeleton_joint_list(self, skeleton_prim: Usd.Prim, parent_name):
        """
        A skeleton has 3 attributes:
        - uniform matrix4d[] bindTransforms = [( (1, 0, -0, 0), ...]
        - uniform token[] joints = ["J_Bip_C_Hips", ...]
        - uniform matrix4d[] restTransforms = [( (1, 0, -0, 0), ...]

        In Omniverse Code etc, you can hover over the names in the "Raw USD Property" panel to get
        more documentation on the above properties.

        We need to insert the new parent at the front of the three lists, and prepend the name to the join paths.
        """

        # Get the attributes
        joints: Usd.Attribute = skeleton_prim.GetAttribute('joints')
        bindTransforms: Usd.Attribute = skeleton_prim.GetAttribute('bindTransforms')
        restTransforms: Usd.Attribute = skeleton_prim.GetAttribute('restTransforms')

        # If first join is the parent name already, nothing to do.
        if joints.Get()[0] == parent_name:
            return False

        # TODO: I use raw USD functions here, but there is also omni.kit.commands.execute("ChangeProperty",...)
        # if want undo...
        # https://docs.omniverse.nvidia.com/prod_kit/prod_kit/programmer_ref/usd/properties/set-attribute.html#omniverse-kit-commands
        joints.Set([parent_name] + [parent_name + '/' + jp for jp in joints.Get()])

        # New unity matrices for the root node we added.
        # ((1, 0, -0, 0), (0, 1, 0, -0), (0, -0, 1, 0), (0, 0, 0, 1))
        unity_matrix = Gf.Matrix4d(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        if bindTransforms.IsValid():
            bindTransforms.Set([unity_matrix] + [x for x in bindTransforms.Get()])
        if restTransforms.IsValid():
            restTransforms.Set([unity_matrix] + [x for x in restTransforms.Get()])

    def add_parent_to_mesh_joint_list(self, mesh_prim, parent_name):
        """
        The meshes have paths to bones as well - add "Root" to their paths as well.
        """
        #mesh_prim = stage.GetPrimAtPath(path)
        if mesh_prim:
            joints: Usd.Attribute = mesh_prim.GetAttribute('skel:joints')

            # Don't touch empty string. Don't add if already added. First value might be empty string.
            if not joints.Get()[1].startswith(parent_name):
                joints.Set([jp if jp == "" else parent_name + '/' + jp for jp in joints.Get()])
                return True
        return False

    #def split_disconnected_meshes(self, stage: Usd.Stage, mesh_prim: UsdGeom.Mesh):
    #    """
    #    Look for child GeomSubset prims and see if they have discontiguous meshes.
    #    Audio2Face cannot work with such meshes, so we need to split them into separate
    #    GeomSubset prims.
    #    """
    #    mesh_indices = mesh_prim.GetAttribute('faceVertexIndices')
    #    for child in mesh_prim.GetChildren():
    #        if child.IsA(UsdGeom.Subset):
    #            subset_prim: UsdGeom.Subset = child
    #            subset_indices = child.GetAttribute('indices').Get()
    #            split = self.split_subset(mesh_indices, subset_indices)
    #            if len(split) > 1:
    #                print("Create new meshes for " + subset_prim)
    #                i = 0
    #                for split_subset in split:
    #                    subset_path = subset_prim.GetPath() + "_" + i
    #                    new_prim: UsdGeom.Subset = stage.DefinePrim(subset_path, usdType=UsdGeom.Subset)
    #                    new_prim.CreateElementTypeAttr().Set(subset_prim.GetElementTypeAttr().Get())
    #                    new_prim.CreateFamilyNameAttr().Set(subset_prim.GetFamilyNameAttr().Get())
    #                    new_prim.CreateIndicesAttr().Set(split_subset)
    #                    material_binding: UsdShade.MaterialBindingAPI = UsdShade.MaterialBindingAPI(new_prim)
    #                    binding_targets = material_binding.GetMaterialBindSubsets()
    #                    material_binding.CreateMaterialBindSubset().Set(UsdShade.MaterialBindingAPI(subset_prim).GetMaterialBindingTargets())
    #                    i += 1
    #                    


    #def split_subset(self, mesh_indices, subset_indices):
    #    """
    #    Given an array of mesh face vertex indicies (multiply them by 3 to get the points index)
    #    and an array of subset indices into the mesh indicies array, return an array of
    #    disconnected submeshes.
    #    """
    def dump_stage(self):
        """
        Traverse the tree of prims, printing out selected attribute information.
        Useful for debugging.
        """
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        for prim in stage.Traverse():
            for attr in prim.GetAttributes():
                try:
                    if len(attr.Get()) >= 50:
                        print(attr.GetPath(), len(attr.Get()))
                except Exception:
                    pass

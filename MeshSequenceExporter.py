# Blender Add-on metadata
bl_info = {
    "name": "FBX Sequence Exporter",
    "author": "GouGouTang https://github.com/LifeSugar/Blender-Per-frame-FBX-Exporter",
    "version": (1, 4),
    "blender": (2, 83, 0),
    "location": "3D Viewport > Sidebar (N) > FBX Exporter",
    "description": "Export per-frame FBX sequence with Transform options and a visual progress bar.",
    "warning": "推荐使用Blender 4.0+，有问题可以提issue，但我应该懒得改，嘻嘻",
    "doc_url": "",
    "category": "Import-Export",
}

import bpy
import os

SEQ_PAD = 4
USE_SYSTEM_PROGRESS_HUD = False


# --------------------- Properties ---------------------
class FBXExporterProperties(bpy.types.PropertyGroup):
    export_path: bpy.props.StringProperty(
        name="Export Folder", description="Destination directory for the FBX sequence",
        subtype='DIR_PATH', default="//FBX_Sequence/"
    )
    start_frame: bpy.props.IntProperty(name="Start Frame", default=1)
    end_frame: bpy.props.IntProperty(name="End Frame", default=100)

    # 1 = every frame; 2 = skip 1; 3 = skip 2
    frame_interval: bpy.props.EnumProperty(
        name="Frame Interval",
        description="Export every Nth frame (1=every frame, 2=skip 1, 3=skip 2)",
        items=[
            ('1', "No Interval", "Export every frame"),
            ('2', "One Frame Interval)", "Export every 2nd frame"),
            ('3', "Two Frame Interval", "Export every 3rd frame"),
        ],
        default='1'
    )

    global_scale: bpy.props.FloatProperty(
        name="Scale", description="Global scale applied at export",
        default=1.00, min=0.001, soft_max=100.0
    )
    apply_scalings: bpy.props.EnumProperty(
        name="Apply Scalings",
        description="How scaling is applied to the generated FBX",
        items=[
            ('ALL_LOCAL', "All Local", "Apply scaling to object transforms (FBX scale stays 1.0)"),
            ('FBX_ALL',   "FBX All",   "Apply custom + units scaling to FBX scale"),
            ('FBX_UNITS', "FBX Units", "Apply units scaling to FBX scale"),
        ],
        default='ALL_LOCAL'
    )
    axis_forward: bpy.props.EnumProperty(
        name="Forward", description="Forward axis",
        items=[('X', "X Forward", ""), ('Y', "Y Forward", ""), ('Z', "Z Forward", ""),
               ('-X', "-X Forward", ""), ('-Y', "-Y Forward", ""), ('-Z', "-Z Forward", "")],
        default='-Z'
    )
    axis_up: bpy.props.EnumProperty(
        name="Up", description="Up axis",
        items=[('X', "X Up", ""), ('Y', "Y Up", ""), ('Z', "Z Up", ""),
               ('-X', "-X Up", ""), ('-Y', "-Y Up", ""), ('-Z', "-Z Up", "")],
        default='Y'
    )
    bake_space_transform: bpy.props.BoolProperty(
        name="Apply Transform", description="Bake object/world space transforms into FBX",
        default=True
    )
    use_mesh_modifiers: bpy.props.BoolProperty(
        name="Apply Modifiers", description="Apply visible modifiers", default=True
    )
    bake_anim: bpy.props.BoolProperty(
        name="Bake Animation", description="Bake current frame pose when exporting frames", default=True
    )


# --------------------- Progress (WM state + drawing) ---------------------
def _ensure_wm_props():
    WM = bpy.types.WindowManager
    if not hasattr(WM, "fbxseq_running"):
        WM.fbxseq_running = bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    if not hasattr(WM, "fbxseq_progress"):
        WM.fbxseq_progress = bpy.props.FloatProperty(
            name="FBX Export Progress", min=0.0, max=1.0, subtype='FACTOR', default=0.0, options={'HIDDEN'}
        )
    if not hasattr(WM, "fbxseq_status"):
        WM.fbxseq_status = bpy.props.StringProperty(default="", options={'HIDDEN'})
    if not hasattr(WM, "fbxseq_cancel"):
        WM.fbxseq_cancel = bpy.props.BoolProperty(default=False, options={'HIDDEN'})


def _has_ui_progress() -> bool:
    return hasattr(bpy.types.UILayout, "progress")


def _draw_progress(layout, factor: float, text: str):
    if _has_ui_progress():
        layout.progress(factor=factor, type="BAR", text=text)
    else:
        layout.prop(bpy.context.window_manager, "fbxseq_progress", text=text, slider=True)


def _tag_redraw(area_types=("STATUSBAR", "VIEW_3D")):
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in area_types:
                area.tag_redraw()


def _draw_statusbar(self, context):
    wm = context.window_manager
    if not wm.fbxseq_running:
        return
    row = self.layout.row(align=True)
    _draw_progress(row, wm.fbxseq_progress, wm.fbxseq_status)
    row.operator("wm.fbx_sequence_cancel", text="", icon='CANCEL')


class WM_OT_FbxSequenceCancel(bpy.types.Operator):
    bl_idname = "wm.fbx_sequence_cancel"
    bl_label = "Cancel FBX Sequence Export"
    bl_description = "Cancel the running FBX sequence export"

    def execute(self, context):
        context.window_manager.fbxseq_cancel = True
        return {'FINISHED'}


# --------------------- Export (Modal) ---------------------
def _map_apply_scalings(internal_value: str) -> str:
    v = bpy.app.version
    if internal_value == 'ALL_LOCAL':
        return 'FBX_SCALE_NONE'
    if internal_value == 'FBX_ALL':
        return 'FBX_SCALE_ALL'
    if internal_value == 'FBX_UNITS':
        return 'FBX_SCALE_UNITS' if v >= (2, 90, 0) else 'FBX_SCALE_UNIT'
    return 'FBX_SCALE_NONE'


class WM_OT_ExportFbxSequence(bpy.types.Operator):
    """Export per-frame FBX sequence with a visual progress (Status Bar + Panel)"""
    bl_idname = "wm.fbx_sequence_exporter_modal"
    bl_label = "Export FBX Sequence"

    _timer = None
    _props = None
    _objects = []
    _export_folder = ""
    _original_active = None
    _current_frame = 0
    _object_index = 0
    _total_files = 0
    _exported_count = 0
    _step = 1
    _end_frame = 0

    def invoke(self, context, event):
        self._props = context.scene.fbx_exporter_props
        self._export_folder = bpy.path.abspath(self._props.export_path)

        if not self._export_folder or self._export_folder == "//":
            self.report({'ERROR'}, "Please set a valid export folder.")
            return {'CANCELLED'}

        os.makedirs(self._export_folder, exist_ok=True)

        self._objects = context.selected_objects[:]
        if not self._objects:
            self.report({'ERROR'}, "Select at least one object.")
            return {'CANCELLED'}

        if self._props.start_frame > self._props.end_frame:
            self.report({'ERROR'}, "Start frame must be <= End frame.")
            return {'CANCELLED'}

        self._original_active = context.view_layer.objects.active
        self._current_frame = self._props.start_frame
        self._end_frame = self._props.end_frame
        self._object_index = 0
        self._exported_count = 0
        self._step = int(self._props.frame_interval)

        frames_count = len(range(self._props.start_frame, self._props.end_frame + 1, self._step))
        self._total_files = len(self._objects) * frames_count

        wm = context.window_manager
        wm.fbxseq_running = True
        wm.fbxseq_cancel = False
        wm.fbxseq_progress = 0.0
        wm.fbxseq_status = f"Exporting… 0/{self._total_files}"

        if USE_SYSTEM_PROGRESS_HUD:
            context.window_manager.progress_begin(0, self._total_files)

        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        _tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        wm = context.window_manager

        if event.type == 'ESC' or wm.fbxseq_cancel or not self._objects:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self._current_frame > self._end_frame:
                self.finish(context)
                return {'FINISHED'}

            obj = self._objects[self._object_index]
            context.scene.frame_set(self._current_frame)

            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            seq_str = f"{(self._exported_count + 1):0{SEQ_PAD}d}"
            if self._step > 1:
                name_prefix = f"{obj.name}_frame{self._step - 1}_"
            else:
                name_prefix = f"{obj.name}_frame_"
            filepath = os.path.join(self._export_folder, f"{name_prefix}{seq_str}.fbx")

            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                global_scale=self._props.global_scale,
                apply_scale_options=_map_apply_scalings(self._props.apply_scalings),
                axis_forward=self._props.axis_forward,
                axis_up=self._props.axis_up,
                bake_space_transform=self._props.bake_space_transform,
                use_mesh_modifiers=self._props.use_mesh_modifiers,
                bake_anim=self._props.bake_anim,
                bake_anim_use_nla_strips=False,
                bake_anim_use_all_actions=False,
                object_types={'MESH', 'ARMATURE', 'EMPTY'},
            )

            self._exported_count += 1
            if USE_SYSTEM_PROGRESS_HUD:
                context.window_manager.progress_update(self._exported_count)

            wm.fbxseq_progress = self._exported_count / self._total_files
            wm.fbxseq_status = f"Exporting… {self._exported_count}/{self._total_files} (Frame {self._current_frame})"

            self._object_index += 1
            if self._object_index >= len(self._objects):
                self._object_index = 0
                self._current_frame += self._step

            _tag_redraw()

        return {'RUNNING_MODAL'}

    def finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        if USE_SYSTEM_PROGRESS_HUD:
            context.window_manager.progress_end()

        bpy.ops.object.select_all(action='DESELECT')
        for o in self._objects:
            o.select_set(True)
        context.view_layer.objects.active = self._original_active

        wm = context.window_manager
        wm.fbxseq_running = False
        wm.fbxseq_progress = 1.0
        wm.fbxseq_status = "Export finished"
        _tag_redraw()

        self.report({'INFO'}, f"Exported {self._exported_count} files.")

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        if USE_SYSTEM_PROGRESS_HUD:
            context.window_manager.progress_end()

        bpy.ops.object.select_all(action='DESELECT')
        for o in self._objects:
            o.select_set(True)
        context.view_layer.objects.active = self._original_active

        wm = context.window_manager
        wm.fbxseq_running = False
        wm.fbxseq_status = "Export cancelled"
        _tag_redraw()

        self.report({'WARNING'}, "Export cancelled.")


# --------------------- Helper ---------------------
class WM_OT_SetSceneFrameRange(bpy.types.Operator):
    bl_idname = "wm.fbx_set_scene_frame_range"
    bl_label = "Match Scene Frame Range"

    def execute(self, context):
        p = context.scene.fbx_exporter_props
        p.start_frame = context.scene.frame_start
        p.end_frame = context.scene.frame_end
        return {'FINISHED'}


# --------------------- Panel ---------------------
class VIEW3D_PT_FBXExporterPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'FBX Exporter'
    bl_label = "FBX Sequence Exporter"

    def draw(self, context):
        layout = self.layout
        props = context.scene.fbx_exporter_props
        wm = context.window_manager

        box = layout.box()
        box.label(text="Main")
        box.prop(props, "export_path", text="")
        row = box.row()
        row.operator(WM_OT_SetSceneFrameRange.bl_idname, text="Match Scene Frame Range")
        split = box.split(factor=0.5)
        split.prop(props, "start_frame", text="Start")
        split.prop(props, "end_frame", text="End")
        box.prop(props, "frame_interval", text="Frame Interval")

        row = layout.row()
        row.scale_y = 1.3
        row.operator(WM_OT_ExportFbxSequence.bl_idname, text="Export FBX Sequence")
        layout.separator()

        box = layout.box()
        box.label(text="Transform")
        box.prop(props, "global_scale")
        box.prop(props, "apply_scalings", text="")
        split = box.split(factor=0.5, align=True)
        split.prop(props, "axis_forward", text="Forward")
        split.prop(props, "axis_up", text="Up")
        box.prop(props, "bake_space_transform")

        box = layout.box()
        box.label(text="Other Options")
        box.prop(props, "use_mesh_modifiers")
        box.prop(props, "bake_anim")

        if wm.fbxseq_running:
            box = layout.box()
            box.label(text="Progress")
            _draw_progress(box.row(align=True), wm.fbxseq_progress, wm.fbxseq_status)
            box.operator("wm.fbx_sequence_cancel", text="Cancel", icon='CANCEL')


# --------------------- Register / Unregister ---------------------
classes = (
    FBXExporterProperties,
    WM_OT_FbxSequenceCancel,
    WM_OT_ExportFbxSequence,
    WM_OT_SetSceneFrameRange,
    VIEW3D_PT_FBXExporterPanel,
)

def register():
    _ensure_wm_props()
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.fbx_exporter_props = bpy.props.PointerProperty(type=FBXExporterProperties)
    bpy.types.STATUSBAR_HT_header.append(_draw_statusbar)
    print("[FBX Sequence Exporter] Registered v1.4")

def unregister():
    try:
        bpy.types.STATUSBAR_HT_header.remove(_draw_statusbar)
    except Exception:
        pass
    del bpy.types.Scene.fbx_exporter_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()

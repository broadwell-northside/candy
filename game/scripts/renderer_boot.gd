extends Node

# Headless tests stay on the project renderer, GL Compatibility.
# A desktop run can switch to Forward+ from Settings, from
# STILLWATER_RENDERER, or from --rendering-method forward_plus.


func _ready() -> void:
    if restart_requested():
        _restart()


func current_method() -> String:
    # Godot 4.3 has no RenderingServer.get_current_rendering_method().
    # The feature tag follows the renderer that actually started.
    if OS.has_feature("forward_plus"):
        return "forward_plus"
    if OS.has_feature("mobile"):
        return "mobile"
    if OS.has_feature("gl_compatibility"):
        return "gl_compatibility"
    return str(ProjectSettings.get_setting("rendering/renderer/rendering_method", "gl_compatibility"))


func restart_requested() -> bool:
    if _headless():
        return false
    if OS.get_cmdline_args().has("--stillwater-renderer-restart"):
        return false
    var desired := desired_method()
    if desired == "":
        return false
    return desired != current_method()


func desired_method() -> String:
    var env := OS.get_environment("STILLWATER_RENDERER").strip_edges()
    if env == "forward_plus" or env == "gl_compatibility" or env == "mobile":
        return env
    var chosen := ""
    if is_instance_valid(Settings):
        chosen = str(Settings.get("rendering_method"))
    if chosen == "forward_plus" or chosen == "gl_compatibility":
        return chosen
    if bool(ProjectSettings.get_setting("stillwater/use_desktop_renderer", false)):
        return str(ProjectSettings.get_setting("stillwater/desktop_rendering_method", ""))
    return ""


func apply_desktop_choice() -> void:
    if restart_requested():
        _restart()


func _restart() -> void:
    OS.set_restart_on_exit(true, PackedStringArray([
        "--rendering-method", desired_method(),
        "--stillwater-renderer-restart",
    ]))
    get_tree().quit(0)


func _headless() -> bool:
    if OS.has_feature("headless"):
        return true
    return DisplayServer.get_name() == "headless"

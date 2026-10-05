"""Render repeatable close-ups of the saved Y-bracket without modifying it."""
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blend', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    import bpy
    from mathutils import Vector
    if not bpy.app.background:
        raise RuntimeError('Preview requires isolated background Blender')
    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    scene = bpy.context.scene
    for obj in scene.objects:
        obj.hide_render = not (obj.name in {'DRB01_Ybracket','B03','C20_F','C20_B'} or
                               'DRB01_Ybracket' in obj.name)
    for material in bpy.data.materials:
        color = material.diffuse_color[:]
        material.use_nodes = True
        shader = material.node_tree.nodes.get('Principled BSDF')
        if shader:
            shader.inputs['Base Color'].default_value = color
            shader.inputs['Roughness'].default_value = .8
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.render.resolution_x = scene.render.resolution_y = 700
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Bracket_review_world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.25,.25,.25,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .7
    target = Vector((-3.02, 0, 1.86))
    light_data = bpy.data.lights.new('Review_light', 'AREA')
    light_data.energy, light_data.shape, light_data.size = 350, 'DISK', 3
    light = bpy.data.objects.new('Review_light',light_data)
    scene.collection.objects.link(light)
    light.location = (-4, -3, 5)
    light.rotation_euler = (target-light.location).to_track_quat('-Z','Y').to_euler()
    data = bpy.data.cameras.new('Bracket_review_camera')
    data.type, data.ortho_scale = 'ORTHO', .64
    camera = bpy.data.objects.new('Bracket_review_camera', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name, location in [('closed_end',(-4,-2,2.9)),('beam_entry',(-2,-2,2.9)),
                           ('end_on',(-4,0,1.86)),('top',(-3.02,0,4))]:
        camera.location = location
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath = str((args.output_dir / (name+'.png')).resolve())
        bpy.ops.render.render(write_still=True)

if __name__ == '__main__':
    main()

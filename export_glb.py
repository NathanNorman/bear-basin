import bpy, os
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "bear_basin.blend"))
for o in list(bpy.data.objects):
    if o.name == "Ground": bpy.data.objects.remove(o)
for m in bpy.data.materials:   # glTF reads Principled BSDF, not the viewport colour
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b: b.inputs["Base Color"].default_value = m.diffuse_color; b.inputs["Roughness"].default_value = 0.8
for o in bpy.data.objects:     # tag each object with its collection so the viewer can toggle groups
    o["group"] = o.users_collection[0].name if o.users_collection else ""
bpy.ops.export_scene.gltf(filepath=os.path.join(HERE, "viewer", "bear_basin.glb"), export_format='GLB',
                          export_extras=True, export_apply=True, export_yup=True)

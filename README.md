# Bear Basin model

A 3D model of the Little Tikes Real Wood Adventures Bear Basin playset (item 651281), built in Blender from the manufacturer's 193-step assembly manual. It is meant for physics simulation (swing dynamics, tip-over and anchoring), so it models every structural part, brace, bolt, screw, nut and washer at the joint the manual puts it in.

## Build

Requires Blender 5 on the PATH.

```sh
./build.sh
```

This runs `build.py`, which builds the model and writes `bear_basin.blend` and `bear_basin.json`, then runs `export_glb.py`, which writes `viewer/bear_basin.glb` for the viewer. All three are generated and gitignored.

`build.py` also checks the model on every run and prints the results:

- every joint's two parts touch
- every fastener's head is in the part it holds and its tip is in the part behind it
- every joint references parts that exist
- nut and washer counts against the manual's hardware page
- total mass against the retailer's listed 574 lb

## View

```sh
/Users/nathan.norman/.pyenv/versions/3.12.11/bin/python3 viewer/serve.py 8472
```

Then open http://localhost:8472. Drag to rotate, right-drag to pan, scroll to zoom. Click a part to see its manual code, add a note about it, and copy all notes. The checkboxes hide groups such as the roof or the fasteners.

## Coordinates

Metres. x points away from the swings (the swings are at -x), y+ is the back of the tower (the climbing net and the upper opening), z is up, and the origin is on the ground at the tower's centre. Tower legs use the manual's codes: C02, C04A and C01A on the back; C01B, C04B and C03 on the front; C05 on the west face; C06 on the east face.

## Sources and estimates

- **From the manual:** the layout, part codes, joint and fastener assignments per step, overall heights (from the p.4 vertical-height diagram) and hardware types.
- **From the retailer listing:** total mass (574 lb), footprint (155 in deep) and the beam's top-to-ground height.
- **Estimates:** lumber cross-sections, wall thicknesses of the steel brackets, the Y-bracket's setback and socket drop, and fastener shear capacities (±50%). These are marked `E` in `build.py`. The model weighs about 296 kg against the listed 260 kg, so the section estimates run about 14% heavy.

The manual PDF is not in this repo (it's copyrighted). Get it from https://www.littletikes.com/pages/instruction-manuals.

## Files

- `build.py`: the model, joints, fastener placement and checks
- `export_glb.py`: Blender to glTF for the viewer
- `build.sh`: runs both
- `viewer/`: the web viewer and its no-cache server
- `docs/manual-notes.md`: notes taken while reading the manual
- `MEMORY.md`: decision log (local only; the global gitignore excludes it)
- `ERRORS.md`: approaches that failed and what worked instead (local only)

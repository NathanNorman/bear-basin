# Bear Basin model

A Blender assembly visualization of the Little Tikes Real Wood Adventures Bear Basin playset (651281), based on its assembly manual. Dimensions that are not supplied by the manual remain estimates. The Blender source is an assembly model; the browser viewer includes a visual physics simulation.

The October 5, 2026 review and completed rebuild are recorded in [docs/review.md](docs/review.md). The published model passes 849 fastener checks, 122 nut/washer checks, and an independent reopen/export comparison of all 1,275 components. See `validation.json` and `artifact-verification.json` for the generated receipts and limitations.

## Build

Requires Blender 5 with its bundled Python and NumPy. Run from a terminal with normal graphics access. On this Mac, launching Blender inside the restricted agent sandbox crashed in Metal initialization before Python ran. Background builds outside that sandbox completed successfully without changing the open Blender GUI.

```sh
./build.sh
# Optional executable override:
BLENDER=/path/to/blender ./build.sh
```

The pipeline runs three isolated background Blender processes with factory startup: generate/validate, export, then independently reopen and compare saved artifacts. It stages all outputs and publishes them only after every phase succeeds. A failed build preserves the previous model and viewer export. Full diagnostics are shown; failure reports are retained as `validation.failed.json` and `artifact-verification.failed.json` when available.

Generated, gitignored outputs:

- `bear_basin.blend`: modeled assembly, without a physics setup.
- `bear_basin.json`: schema v2 manifest with members, component transforms/masses, joints and hardware.
- `validation.json`: record checks, actual-mesh fastener/contact checks and inventory discrepancies.
- `viewer/bear_basin.glb`: browser export including converted ropes and other curves.
- `artifact-verification.json`: saved scene/export integrity checks and SHA-256 hashes. Input paths identify the temporary staging directory used for verification; hashes identify the published files.

`build.sh` enables strict mesh validation. Mesh failures stop publication. For investigation, `build.py` also accepts `--output-dir PATH` without `--strict-mesh`; that diagnostic mode can save a model marked `needs_review`. A successful geometry check does not verify estimated dimensions, material properties, loading, or structural safety.

## View

```sh
python3 viewer/serve.py 8472
```

Open [the local viewer](http://127.0.0.1:8472). Drag to rotate, right-drag or Shift-drag to pan, and scroll to zoom. Click a part for its manual code. **Y-bracket close-up** frames the corrected sleeve-to-cup connections. Notes persist in the same browser and origin; use **Copy all notes** to export them. Group checkboxes hide components. The viewer loads pinned Three.js modules from unpkg and needs internet access for those modules.

## Tests without Blender

These commands never launch the installed Blender executable:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test viewer/tests/*.test.mjs
```

The Python tests cover manual-derived joint schedules, hardware stacks, notches, record validation and failure-preserving build/export behavior using a fake Blender executable. Browser behavior and generated geometry require separate verification.

## Layout

- `build.py`: CLI, scene lifecycle, validation and output orchestration.
- `bear_basin/geometry.py`: scene geometry, scoped to one build.
- `bear_basin/joints.py`: manual assembly schedule.
- `bear_basin/hardware.py`: hardware catalog, nut assignments and estimated masses.
- `bear_basin/placement.py`: explicit attachment locations and shared contact solver.
- `bear_basin/mesh_placement.py`: bounded surface refinement of failed contact proposals.
- `bear_basin/assembly.py`: hardware meshes, stable identities and placement records.
- `bear_basin/shapes.py`: pure polygon calculations.
- `bear_basin/validation.py`: independent record and actual-mesh checks.
- `bear_basin/report.py`: versioned manifest and scene mass accounting.
- `export_glb.py`: background-only glTF export with staged replacement.
- `tests/verify_artifacts.py`: fresh-process saved scene, metadata and exported world-bounds checks.
- `viewer/`: browser presentation, selection, notes, and local server.
- `docs/manual-notes.md`: earlier manual-reading notes; corrections are in the review.

Coordinates are metres: x points away from the swings, y+ is the tower back (climbing net/opening), z is up, and the origin is on the ground at the tower centre. The glTF export converts to y-up; the viewer's `viewerState.look(camera, target)` accepts Blender coordinates.

The supplied PDF is intentionally not included in Git. The manufacturer provides manuals through its [instruction-manual page](https://www.littletikes.com/pages/instruction-manuals).

The bottom **FIELD / ASSEMBLY** slider scrubs a reversible exploded animation. Hardware releases first, then roof and structure separate; **Disassemble** and **Reassemble** play the transition. Cyan points accent suspended hardware. **Show inspector** restores selection, visibility and note controls. This is a visual exploration, not a prescribed construction sequence or a collision simulation; the source model and GLB remain unchanged.

At full separation, a short suspended pause is followed automatically by a gravity release. The locally vendored Apache-2.0-licensed Rapier 0.21.0 WebAssembly engine simulates gravity at 9.81 m/s², rigid contact, friction, low restitution and native sleeping bodies. Timber and the slide use hulls derived from their visible mesh instead of oversized box envelopes. The ground is a deep solid slab. CCD and a fixed 120 Hz timestep resolve fast impacts; bodies are never teleported back onto the floor.

Ropes and the tarp use Rapier's native soft bodies. Rope edges resist tension; the cloth has damped tension constraints and deforming surface contacts. Soft bodies have lower contact dominance: they collide with and drape over timber, but do not hold heavy planks up or push them around. This is an explicit visual approximation. Other limitations include estimated masses, simplified steel/plastic colliders, omitted fastener-to-fastener and rope-to-rope contacts, and uncalibrated fabric stiffness and no bending resistance. The fall is a visual effect, not an engineering prediction.

Normal playback uses a compressed trajectory baked from the verified Rapier simulation, interpolated at render speed. The cache matches the model geometry, release transforms and physics source hashes; a mismatch uses the live worker solver. Position samples have 0.1 mm resolution. Reassembling or moving the slider terminates that worker and restores the original meshes. The recorded trajectory ends only after the physics engine puts every body to sleep; there is no arbitrary timed freeze. Regenerate it after model or physics changes with `node --experimental-loader ./scripts/three-loader.mjs ./scripts/bake-fall.mjs`. Verify playback with the matching `scripts/verify-playback.mjs` command. Hardware remains instanced to reduce draw calls.

Verification: run `node --test viewer/tests/*.test.mjs`, then `node --experimental-loader ./scripts/three-loader.mjs ./scripts/verify-fall.mjs`. The second command loads the actual GLB, runs twenty simulated seconds, checks native sleep, escaped parts, finite poses, late motion and mesh restoration. Research and receipts are in [docs/physics-research.md](docs/physics-research.md).

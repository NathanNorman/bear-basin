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

Generated outputs (the accepted GLB is committed; other build outputs remain local):

- `bear_basin.blend`: modeled assembly, without a physics setup.
- `bear_basin.json`: schema v2 manifest with members, component transforms/masses, joints and hardware.
- `validation.json`: record checks, actual-mesh fastener/contact checks and inventory discrepancies.
- `viewer/bear_basin.glb`: browser export including converted ropes and other curves.
- `artifact-verification.json`: saved scene/export integrity checks and SHA-256 hashes. Input paths identify the temporary staging directory used for verification; hashes identify the published files.

`build.sh` enables strict mesh validation. Mesh failures stop publication. For investigation, `build.py` also accepts `--output-dir PATH` without `--strict-mesh`; that diagnostic mode can save a model marked `needs_review`. A successful geometry check does not verify estimated dimensions, material properties, loading, or structural safety.

## View

Public viewer: [nathannorman.github.io/bear-basin](https://nathannorman.github.io/bear-basin/).

GitHub Pages deploys the committed GLB and viewer on every push to `main` or `codex/pages` through `.github/workflows/pages.yml`. No Blender build runs during deployment. A scoped service worker supplies cross-origin isolation for threaded Jolt; the first visit may reload once. It does not cache the site for offline use. Browsers without isolation retain the single-threaded fallback. Notes stay in the visitor’s browser.

```sh
python3 viewer/serve.py 8473
```

Open [the local viewer](http://127.0.0.1:8473). Drag to rotate, right-drag or Shift-drag to pan, and scroll to zoom. Click a part for its manual code. **Y-bracket close-up** frames the corrected sleeve-to-cup connections. Notes persist in the same browser and origin; use **Copy all notes** to export them. Group checkboxes hide components. Three.js and Jolt modules are vendored locally; the viewer works offline.

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

The bottom **FIELD / ASSEMBLY** slider scrubs a reversible exploded animation. Hardware releases first, then roof and structure separate; **Disassemble** and **Reassemble** play the transition. **Release gravity** stops the transition and drops all parts from their current positions at any slider value, including the assembled model. Cyan points accent suspended hardware. **Show inspector** restores selection, visibility and note controls. The exploded sequence is a visual exploration, not a prescribed construction sequence. The subsequent fall uses physical collision solving; the source model and GLB remain unchanged.

At full separation, a short suspended pause is followed automatically by a fresh randomized gravity release. Three.js renders the scene; locally vendored Jolt Physics JS 1.1.0 WebAssembly solves rigid contacts in a worker. Gravity is 9.81 m/s², with friction, low restitution, continuous collision detection and native sleeping bodies. Exact rotated cuboids replace 174 rectangular timber hulls without changing their geometry; other timber and the slide retain mesh-derived hulls. Rigid simulation uses two 120 Hz steps per outer update. Small hardware receives additional native contact iterations. The threaded WebAssembly build uses SIMD and three native job workers; the local server supplies its required COOP/COEP headers. Browsers without isolation use the single-threaded build. Bodies are never teleported onto the floor.

Ropes and the tarp use an XPBD particle solver: gravity, compliant tension constraints, swept sphere contacts, contact projection and friction. They collide with timber but do not push it back. Canopy contacts cover entire fabric triangles using thin prism queries, barycentric response and swept mean translation; a broad-phase bounds check skips empty queries. This prevents timber slipping between the sparse fabric vertices. Face contacts also wake sleeping cloth when nearby timber moves. Cloth has 57 simulation nodes; ropes use 4–8 nodes. Deformables sleep only after supported motion remains below 0.025 m/s for 0.75 s and rigid parts have stopped. Nearby moving rigid contacts can wake them. Rigid bodies use Jolt's native sleep. There is no timed animation cutoff or prescribed resting pose.

The worker owns its clock. Rendering interpolates snapshots, and hardware remains instanced. Every release gets a cryptographically generated seed for small initial linear/angular velocities; `?seed=42` fixes those initial conditions for debugging. The default viewer does not load the baked trajectory. Reassembly or slider interaction terminates the worker and restores original meshes. The previous smooth baked version remains recoverable from the [checkpoint](docs/checkpoint.md).

This is a visual physics effect, not an engineering prediction. Masses and drag are estimates; steel/plastic use simplified colliders; slide concavities are hull-filled; tiny fastener mutual contacts, textile self-contact, textile-to-hardware contacts, bending resistance and textile force feedback are omitted.

Verification: `node --test viewer/tests/*.test.mjs`, then `node --experimental-loader ./scripts/three-loader.mjs ./scripts/verify-fall.mjs 42`. The latter loads the actual GLB, allows twenty simulated seconds for settling, then checks another five seconds for exact unchanged rest, visible geometry below the floor, finite poses, upright narrow components and mesh restoration. Profiling: `JOLT_THREADS=3 node --experimental-loader ./scripts/three-loader.mjs ./scripts/profile-fall.mjs baseline 42`. Research and current receipts are in [docs/physics-research.md](docs/physics-research.md).

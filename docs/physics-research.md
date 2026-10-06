# Falling assembly: research and verification

## Findings

The viewer used a real physics engine, but its collision model and custom corrections were unreliable. Several diagonal timbers occupied only a small portion of their local bounding box. A box collider therefore created invisible supports. The old per-step ground projection teleported bodies after the solver had resolved contacts, injecting discontinuities. Unilateral rope joints and an undamped cloth edge network could keep contact islands awake.

Rapier's official documentation warns against repositioning dynamic bodies after contact resolution and explains that collider shape also determines inertia and center of mass:

- https://rapier.rs/docs/user_guides/javascript/rigid_bodies/
- https://rapier.rs/docs/user_guides/javascript/colliders/

The current official 0.21.0 package provides native soft bodies with tension-only rope edges, damped stretch constraints, cloth bending constraints and native sleep. Its troubleshooting table specifically recommends deformation and material damping for continued wobbling:

- https://rapier.rs/docs/user_guides/javascript/soft_body_cohesion/
- https://rapier.rs/docs/user_guides/javascript/soft_bodies/

## Historical checkpoint implementation

- Vendored the official `@dimforge/rapier3d-compat` 0.21.0 package and its Apache license.
- Mesh-derived convex hulls for timber and the slide.
- Removed post-solver position corrections; deep ground collider, CCD and 120 Hz physics.
- Replaced rigid particle rope joints with native soft-body wire contacts and tension-only edges.
- Cloth surface contacts and damped, tension-only edges. Bending constraints are omitted: preserving the original folded roof angles created artificial support.
- Lower soft-body contact dominance. Cloth and ropes receive rigid contact forces without acting as supports for heavy timber. This approximation avoids unstable mass-ratio feedback; it is not a calibrated material simulation.
- Worker execution and interpolated rendering, with one update in flight and termination on reassembly.
- Native sleep determines the end, rather than an elapsed-time freeze.

## Historical checkpoint verification

Run `node --test viewer/tests/*.test.mjs` for gravity, contact stacks, fasteners under a heavy block, rope collapse, unsupported plank tipping, stable native sleep, worker lifecycle and existing viewer behavior.

Run `node --experimental-loader ./scripts/three-loader.mjs ./scripts/verify-fall.mjs` to load all 1,275 meshes from the generated GLB, release the assembly and check finite poses, escaped bodies, native sleep, late displacement and geometry restoration. The verifier uses the same vendored Three.js 0.160.0 GLTFLoader as the browser, rather than reconstructing its meshes by hand. Browser playback is checked separately, because loader transforms and floating-point differences can change a chaotic pile.

See `physics-verification.json` for the final receipt. Remaining limits: estimated masses, box envelopes for most steel/plastic, hull-filled concavities in the slide, omitted tiny fastener mutual contacts and uncalibrated textile stiffness, approximate drag and omitted bending resistance.

Final checks: 21 viewer tests passed. All 1,275 GLB meshes and 41 flexible parts reached native sleep by five simulated seconds and showed zero late displacement through twenty seconds. The live viewer reported SETTLED at 4.66 simulated seconds, zero awake parts and about 120 FPS rendering, with no console errors. Reassembly restored the original model. See [the screenshot](physics-settled.jpg).

## Historical baked playback performance

Rendering at 120 FPS did not mean the live solver delivered motion at that rate. The worker could accumulate delay, slowing the falling animation. Normal playback at the checkpoint used the verified physics trajectory sampled at 60 Hz, with interpolation at render speed. Its 279 frames cover 4.633 seconds and end at native sleep. Delta-coded samples at 0.1 mm position resolution compress the recording to about 883 KB. Model/release geometry and physics source hashes guard against replaying stale data; unmatched models use the live worker.

`node --experimental-loader ./scripts/three-loader.mjs ./scripts/bake-fall.mjs` generates the recording and refuses to save a pile that has not reached native sleep. `scripts/verify-playback.mjs` checks cache matching, stable rest and restoration, and measures the actual pose/deformation update cost. The final benchmark averaged 0.528 ms per update, with a 0.701 ms 95th percentile. All 22 viewer tests pass. Browser verification confirms cached playback at approximately 120 FPS, rather than merely a responsive rendering loop around a slower solver.

## Randomized live simulation (current)

The baked playback above is preserved at tag `codex/checkpoint-2026-10-05-smooth-physics`. The current viewer computes a fresh fall for each release. Three.js renders; Jolt Physics JS 1.1.0 solves rigid contacts in a browser worker. Godot also offers Jolt as a physics backend. A browser renderer plus a native physics library compiled to WebAssembly is an appropriate equivalent for this small interactive scene; adopting a complete game engine is not required to get real physical collision solving.

### Why change the backend?

Profiling and multiple seeded piles exposed persistent contact jitter and sleep failures with the attempted Rapier configurations. Some configurations passed one seed but failed another, or let tiny fasteners sink through the floor. Parameter experiments and custom island sleep policies were discarded. Jolt is being verified against the same geometry and stricter visible-mesh ground checks. Rigid bodies use native contact resolution and native sleep, rather than a custom support-footprint freeze.

`collision-shapes.mjs` recognizes true rectangular eight-corner meshes in any local orientation and fits exact rotated cuboids. It rejects tapered/missing-corner shapes. This converts 174 timber colliders without enlarging them or creating invisible supports. Nonrectangular timbers and the slide retain convex hulls. Hardware uses simplified box envelopes; tiny hardware mutual contacts are omitted, but it exchanges forces with timber and the ground.

The worker advances autonomously instead of waiting for render requests. Snapshots interpolate at display speed. Every release gets fresh initial velocities from a random seed, and a fixed `?seed=42` supports debugging. Rendering frame rate and physical-update timing are separate measurements: responsive camera rendering alone does not prove real-time falling motion.

### Textiles

Textiles use a small XPBD tension network with gravity and contact friction. Projection belongs to the deformable constraint solver before reconstructed velocities; no post-render correction moves rigid timber. Swept sphere queries use Jolt's collision shapes and broad phase. Sweep normals are retained so nodes resting on timber recognize support and can sleep. Rope contact radii come from visible rope widths, and their cross-section rotates with the deformed centreline. Cloth uses 57 nodes; ropes use 4–8 nodes. There are 309 particles across 41 flexible parts.

Deformables sleep after contact-supported speeds below 0.025 m/s persist for 0.75 s and rigid bodies stop. Renewed nearby rigid motion can wake them. Neither solver stops because an arbitrary animation duration has elapsed. Textiles do not push rigid bodies back, and omit bending resistance, self-contact and hardware contact. These are explicit visual approximations, not fitted material measurements.

### Validation

Unit fixtures exercise equal gravitational acceleration, stacking, tiny hardware under a 15 kg block, a vertical rod, vertical rope collapse, tarp folding, an unsupported plank tipping, native resting sleep, elevated rope support, seed reproducibility and worker lifecycle. The fastener impact fixture allows at most 5 mm transient contact penetration and 2.1 mm at rest; the full-model verifier separately checks actual rendered geometry stays within 3 mm of the ground. It records the first sleep state, then requires exact unchanged positions for five further simulated seconds and restoration of original geometry on reset.

Current seed receipts, isolated CPU profiles and browser measurements are recorded in `physics-live-verification.json`. Historical `physics-performance.json` measures the checkpoint's baked playback, not the current live solver. Library capacity is sized to the scene and each world is explicitly disposed. Worker termination on reassembly also releases its WebAssembly memory.

Primary references:

- [Jolt Physics](https://github.com/jrouwe/JoltPhysics)
- [Jolt JavaScript/WebAssembly bindings and examples](https://github.com/jrouwe/JoltPhysics.js)
- [Jolt ownership and cleanup example](https://github.com/jrouwe/JoltPhysics.js/blob/main/Examples/proper_cleanup.html)
- [Godot Jolt physics documentation](https://docs.godotengine.org/en/4.6/tutorials/physics/using_jolt_physics.html)
- [XPBD original paper](https://matthias-research.github.io/pages/publications/XPBD.pdf)

Vendored package: `jolt-physics@1.1.0`, official npm distribution, MIT license in `viewer/vendor/jolt.LICENSE`. The downloaded tarball SHA-512 was checked against npm's integrity metadata before use. The previous Rapier dependency and trajectory are preserved with the checkpoint; default playback uses Jolt.

The multithreaded distribution enables SIMD and up to three native job workers in addition to the controlling physics worker. The local server sends COOP/COEP headers required for shared WebAssembly memory. Browsers without isolation use the single-threaded fallback. One upstream Node-only worker-bootstrap expression is parenthesized in the vendored multithread module so headless tests can run the same backend; browser code is unchanged. See `viewer/vendor/README.md` for exact provenance.

Final checks: 49 Python tests and 26 viewer tests passed; the viewer suite also passed with the threaded backend. Four full-model seeds (42, 4131, 1, 299) settled in 8.3–14.1 seconds and remained exactly motionless for five subsequent seconds. Three fresh browser releases produced distinct seeds and piles, zero awake parts, no console errors and approximately 120 FPS rendering. The final worker clock run averaged 8.86 ms/update (15.81 ms P95), completing 7.10 simulated seconds in 7.11 wall seconds. Reassembly and reverse scrubbing restored the assembly. All five generated model/validation artifacts and the checkpoint archive retained their hashes. No Blender process was launched.

Optional trajectory tooling remains for diagnostics, separately from default live playback. The preserved checkpoint trajectory has the old particle layout. To verify a new recording without replacing it, use `JOLT_THREADS=3 node --experimental-loader ./scripts/three-loader.mjs scripts/bake-fall.mjs /tmp/bear-debug.gz`, then `node --experimental-loader ./scripts/three-loader.mjs scripts/verify-playback.mjs /tmp/bear-debug.gz`. Verification reads the recording duration instead of assuming a five-second fall.

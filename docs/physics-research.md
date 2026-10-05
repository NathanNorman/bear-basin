# Falling assembly: research and verification

## Findings

The viewer used a real physics engine, but its collision model and custom corrections were unreliable. Several diagonal timbers occupied only a small portion of their local bounding box. A box collider therefore created invisible supports. The old per-step ground projection teleported bodies after the solver had resolved contacts, injecting discontinuities. Unilateral rope joints and an undamped cloth edge network could keep contact islands awake.

Rapier's official documentation warns against repositioning dynamic bodies after contact resolution and explains that collider shape also determines inertia and center of mass:

- https://rapier.rs/docs/user_guides/javascript/rigid_bodies/
- https://rapier.rs/docs/user_guides/javascript/colliders/

The current official 0.21.0 package provides native soft bodies with tension-only rope edges, damped stretch constraints, cloth bending constraints and native sleep. Its troubleshooting table specifically recommends deformation and material damping for continued wobbling:

- https://rapier.rs/docs/user_guides/javascript/soft_body_cohesion/
- https://rapier.rs/docs/user_guides/javascript/soft_bodies/

## Implemented

- Vendored the official `@dimforge/rapier3d-compat` 0.21.0 package and its Apache license.
- Mesh-derived convex hulls for timber and the slide.
- Removed post-solver position corrections; deep ground collider, CCD and 120 Hz physics.
- Replaced rigid particle rope joints with native soft-body wire contacts and tension-only edges.
- Cloth surface contacts and damped, tension-only edges. Bending constraints are omitted: preserving the original folded roof angles created artificial support.
- Lower soft-body contact dominance. Cloth and ropes receive rigid contact forces without acting as supports for heavy timber. This approximation avoids unstable mass-ratio feedback; it is not a calibrated material simulation.
- Worker execution and interpolated rendering, with one update in flight and termination on reassembly.
- Native sleep determines the end, rather than an elapsed-time freeze.

## Verification

Run `node --test viewer/tests/*.test.mjs` for gravity, contact stacks, fasteners under a heavy block, rope collapse, unsupported plank tipping, stable native sleep, worker lifecycle and existing viewer behavior.

Run `node --experimental-loader ./scripts/three-loader.mjs ./scripts/verify-fall.mjs` to load all 1,275 meshes from the generated GLB, release the assembly and check finite poses, escaped bodies, native sleep, late displacement and geometry restoration. The verifier uses the same vendored Three.js 0.160.0 GLTFLoader as the browser, rather than reconstructing its meshes by hand. Browser playback is checked separately, because loader transforms and floating-point differences can change a chaotic pile.

See `physics-verification.json` for the final receipt. Remaining limits: estimated masses, box envelopes for most steel/plastic, hull-filled concavities in the slide, omitted tiny fastener mutual contacts and uncalibrated textile stiffness, approximate drag and omitted bending resistance.

Final checks: 21 viewer tests passed. All 1,275 GLB meshes and 41 flexible parts reached native sleep by five simulated seconds and showed zero late displacement through twenty seconds. The live viewer reported SETTLED at 4.66 simulated seconds, zero awake parts and about 120 FPS rendering, with no console errors. Reassembly restored the original model. See [the screenshot](physics-settled.jpg).

## Playback performance follow-up

Rendering at 120 FPS did not mean the live solver delivered motion at that rate. The worker could accumulate delay, slowing the falling animation. Normal playback now uses the verified physics trajectory sampled at 60 Hz, with interpolation at render speed. Its 279 frames cover 4.633 seconds and end at native sleep. Delta-coded samples at 0.1 mm position resolution compress the recording to about 883 KB. Model/release geometry and physics source hashes guard against replaying stale data; unmatched models use the live worker.

`node --experimental-loader ./scripts/three-loader.mjs ./scripts/bake-fall.mjs` generates the recording and refuses to save a pile that has not reached native sleep. `scripts/verify-playback.mjs` checks cache matching, stable rest and restoration, and measures the actual pose/deformation update cost. The final benchmark averaged 0.528 ms per update, with a 0.701 ms 95th percentile. All 22 viewer tests pass. Browser verification confirms cached playback at approximately 120 FPS, rather than merely a responsive rendering loop around a slower solver.

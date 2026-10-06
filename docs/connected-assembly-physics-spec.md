# Connected assembly physics specification

Status: proposed implementation; no simulation changes made by this specification.
Inspected against the local model and viewer on 2026-10-05.

For the longer-term goal of an 80 lb child swinging for 1,000 hours, see [the realistic physics and wear plan](realistic-physics-and-wear-plan.md). This specification remains the connected interactive foundation; its ideal rigid connections alone cannot calculate internal joint movement or long-term wear.

## Intended result

Gravity should act on an assembled object, with its connections intact. At 0% disassembly, timber, brackets, and installed hardware stay attached; swing seats hang from their supports. At partial disassembly, released parts fall while remaining connected sections move together. At 100%, all deliberately released pieces can fall independently. Contacts, friction, inertia, and support determine the resting pile.

This means a physically connected interactive assembly. The initial version will idealize bolted timber connections as rigid and unbreakable. It will not predict whether real timber splits, screws pull out, soil anchors fail, or the playground is safe. Those require material and connection measurements that we do not have. Existing unverified fastener capacity fields must not drive failure behavior.

## What exists and what is missing

The existing browser stack is sufficient: Three.js draws the model; Jolt WebAssembly simulates rigid bodies in a worker with three native job threads. Changing to a full game engine would not supply the missing assembly semantics.

The current manifest contains:

| Data | Count | Relevance |
| --- | ---: | --- |
| Render components | 1,275 | Accepted visual geometry |
| Assembly connection records | 462 | Named endpoints, fastener type/count, manual step references |
| Fasteners | 849 | Individual IDs, connection IDs, placement and axes |
| Nuts and washers | 122 | Fastener references, but no explicit component IDs in these records |
| Rope components | 40 | Visual strands; no complete load-bearing network |

All 462 connection records reference existing components. However, 55 wood/plastic/rope/fabric components are absent from their endpoints: all 40 ropes and 15 plastic parts, including swing seats, seat brackets, and handle assemblies. Other omissions include articulated hanger/hook/ring connections. A successful mesh/placement validation does not validate this physical topology.

Today, gravity releases 1,234 independent rigid bodies and 41 flexible parts. Installed hardware does not hold members together. Flexible parts receive solid collision corrections without transmitting the corresponding loads back to solids. The disassembly paths independently offset parts according to broad categories; they do not preserve connected sections.

Relevant existing sources: `bear_basin/joints.py`, `bear_basin/assembly.py`, `bear_basin/geometry.py`, `bear_basin/report.py`, `viewer/model-state.mjs`, `viewer/disassembly.mjs`, and `viewer/physics-worker.mjs`.

## 1. Compile a physical assembly description

Add a versioned assembly sidecar, initially generated from the existing manifest without rebuilding the accepted geometry. Keep render geometry, connection metadata, and simulation state separate.

Each physical part needs:

- A canonical part ID and explicit mapping to its render nodes. Read exported `part_id`, including fastener IDs, rather than assuming mesh names are IDs. Multiple render primitives must not duplicate a part's mass or bodies.
- Its assembled transform, collision shape, mass, and provenance. Audit missing/zero masses and distinguish a truly massless visual child from a dynamic part.
- Explicit ownership for decorative children, hardware, and subassemblies.

Each connection needs:

- Stable identity, both endpoint IDs, connection kind, and attachment frames expressed in the parts' assembled local coordinates.
- Its associated fastener IDs and explicit nut/washer IDs, plus the condition that releases it.
- Manual references, source geometry, and confidence. Manual step numbers are provenance, not automatically a teardown timeline.
- A classification: rigid attachment, articulation, tension-only rope attachment, textile pin, or world anchor.

Use the existing 462 records as input, then audit the manual and modeled geometry to fill missing relationships. Do not infer a load-bearing connection merely because surfaces touch or two rope curves cross. Audit rope knots/intersections, endpoints, seat attachments, and hanger articulation explicitly.

Preserve a mapping from current `joint_####` IDs, whose numbering depends on list order, to durable semantic IDs. Add explicit hardware component references at the source/export boundary so future ordering changes do not silently rewire the model.

Validation must reject unknown endpoints, duplicate physical ownership, invalid local frames, missing load paths, and unintended unconnected components. Every intentionally loose or decorative component must be declared as such.

## 2. Represent connected sections efficiently

Use rigid compound bodies for sections joined by idealized rigid connections. Preserve each constituent's collision shape and local transform; do not replace a whole frame with one bounding box or a convex hull that fills its openings. Installed hardware belongs to its section until extracted, with its mass counted once.

Use separate bodies and physical constraints for moving connections: hanger pivots, appropriate hook/ring freedom, and suspended loads. A connected graph is not necessarily a rigid cluster: rope and articulated edges must not weld an entire swing into the tower.

Build a small fixed-constraint reference fixture first to check attachment frames and expected behavior. Then use it to validate the compound representation. Avoid one solver constraint per visible screw; multiple screws can support one modeled rigid connection.

Jolt already provides fixed constraints and compound shapes. Its automatic fixed-constraint frame detection preserves the bodies' *current* relative pose. Therefore, creating constraints after individual parts have been exploded would lock in gaps. Frames and grouping must come from the canonical assembly description, not whichever poses happen to be visible when gravity is clicked.

## 3. Make disassembly topology-aware

Replace independent category-based separation with a connection release schedule. Each event extracts specified hardware and disables specified connections. With multiple fasteners, define which removal completes release; removing one of two screws must not accidentally release the connection twice or leave it permanently attached.

Parts that remain rigidly joined must share a section transform. Only after an event splits that section may its pieces acquire independent paths. Remaining alternate load paths matter: removing one connection from a braced loop does not necessarily disconnect the frame.

The slider remains a reversible visual preview. Every slider value resolves to both transforms and connection state. Preview uses controlled motion; it is not presented as a physical unscrewing simulation.

Clicking gravity must atomically snapshot that preview state, stop controlled animation, and start physics with exactly the remaining connections. It must not silently disable everything, attach displaced pieces across gaps, or add random impulses to intact sections.

Dragging the slider after a drop restores the canonical preview and its connection state. Reassembly may remain cinematic; do not weld fallen pieces across space and call the resulting correction physical motion. Preserve the user's camera during these transitions.

## 4. Split sections without injecting energy

On a connection release, recompute rigid connected components. A newly separated section inherits its parent's angular velocity and its linear velocity at the new center of mass:

`v_child = v_parent + omega_parent × (COM_child - COM_parent)`

Recompute mass, center of mass, and inertia using constituent shapes and masses. Preserve every visible world transform while changing body ownership. Rebind remaining articulated/textile anchors to the correct new body. Wake affected bodies and their connected island; do not reset unrelated sections.

Queue mutations at simulation-step boundaries. Maintain canonical-part-to-body mappings independently of render-node mappings. Filter collisions within a rigid compound and handle initially overlapping connected neighbors deliberately; do not globally disable collisions between every part in a connected graph.

A fresh random seed may perturb detached pieces or an explicitly requested disturbance. Gravity alone at 0% should not require randomness. Identical stable initial conditions can correctly produce identical behavior.

## 5. Give flexible parts actual load paths

Swing ropes must support seat weight and transfer tension back to the hangers. They need attachment frames, rest lengths, mass, slack, and tension-only behavior. Releasing one support should leave the other support active.

Hammock and climbing nets need shared physical nodes at actual tied intersections, attachment to eyelets, and two-way forces between strands and rigid supports. A collection of independently animated crossing curves is insufficient.

Evaluate Jolt's exposed soft-body facilities against a small anchored-rope/net fixture. If the current custom XPBD solver is retained, add two-way impulse coupling and verify convergence with the rigid solver. Choose based on fixture correctness and measured cost, not appearance alone. Keep chain/hook render detail separate from the smallest useful physical representation.

The tarp needs explicit pins and release events. Simplified textile collision, bending, and self-contact are acceptable only when documented and when they do not invalidate the demonstrated support behavior.

## 6. Define ground anchoring honestly

Attaching a stake to a leg does not attach the stake to the world. Default ground support should be contact and friction. An intact unanchored assembly may slide or tip if its loading and support genuinely warrant it.

An optional anchored mode may use explicit world constraints, clearly labeled as an idealized installation. Do not invent soil stiffness or pull-out strength from the manual illustration. Structural failure and calibrated soil response are separate future work.

## 7. Preserve responsiveness and reproducibility

Keep physics off the rendering thread, fixed simulation steps, threaded Jolt, and interpolated rendering. Compound sections reduce the initial active-body count and contact workload substantially; detached pieces progressively become independent bodies. Installed fasteners should not be hundreds of colliding loose bodies at 0%.

Audit shapes for both cost and support accuracy. Retain actual timber extents and enough bracket/slide shape detail to avoid impossible resting poses. Decorative small hardware may use documented simplified collision rules; do not describe the result as unrestricted hardware-to-hardware simulation.

Profile assembled, partially released, and fully loose states. Existing measurements show why: fully separated physics averaged about 8.86 ms per outer update, whereas releases at 35% and 0% averaged about 23.46 ms and 40.98 ms respectively. These are previous local receipts, not promises for the new implementation. Dense initial contacts must be tested explicitly.

Record seed, assembly schema/hash, release events, physics settings, and initial state for replay. Random live drops remain available; repeatability is a debugging feature rather than a prerecorded substitute for physics.

Acceptance target on the current machine: sustained 60 FPS rendering, worker update P95 at or below 16.7 ms after initialization, and simulation lag below 100 ms in representative releases. Measure wall time versus simulated time so smooth rendering cannot disguise slow physics. Higher refresh rendering is an additional target. If these budgets fail, profile body/contact counts, island work, flexible coupling, allocations, and snapshot transfer before lowering fidelity.

## Implementation sequence and exit criteria

| Stage | Deliverable | Exit criterion |
| --- | --- | --- |
| A: topology | Versioned compiler, canonical IDs, ownership, connections and release schedule | Every physical part has an audited role; all missing load paths resolved or explicitly excluded |
| B: rigid proof | One frame section with installed hardware, then whole rigid assembly | Gravity preserves connections; removing the final supporting connection splits the correct section without a pose jump |
| C: articulation and textiles | Hangers, seats, ropes, nets, tarp pins | Suspended loads transfer forces to supports; releasing one anchor produces the correct remaining load path |
| D: interaction | Slider preview and gravity share one connection state | Releases at arbitrary progress use the displayed poses and active connections; reset/reassembly restores both |
| E: performance and verification | Measured runs, replay fixtures, browser checks and receipts | Correctness and frame/time budgets pass across assembled, partial and fully released states |

The main uncertainties are completing the assembly graph, preserving body state during splits, and stable two-way textile coupling. Prove these on small representative fixtures before applying them to all 1,275 components. This is several implementation milestones, not a gravity-toggle patch.

## Required verification

- At 0%, stable frame fixtures remain assembled for 30 seconds under gravity. Ideal rigid connections preserve relative transforms; no hardware falls out or unexplained separation occurs. An explicit unanchored tipping fixture must still be allowed to tip.
- Push an assembled section: its members move together. Push a suspended seat: it swings and loads its supports instead of remaining frozen or falling independently.
- Remove one of several fasteners, then the final one; verify release conditions and alternate graph paths. Include a cyclic brace fixture.
- At 25%, 50%, 75%, and 100%, and immediately around every release boundary, check active connections, connected sections, transforms, and correct loose-body membership.
- Release gravity during animation and from a stationary slider. Check atomic handoff, no position jump, inherited velocities, no unexplained energy gain, and unchanged camera.
- Remove one rope support and both supports. Check tension, slack, attachment reaction, remaining suspension, and eventual ground contact.
- Check actual visible ground clearance, bracket support, and unsupported long planks, rather than only proxy-body heights. Keep the existing 3 mm floor tolerance where appropriate; investigate any unsupported hovering or persistent jitter.
- Confirm bodies settle through native contact/sleep behavior. No timed pose freeze, post-render floor correction, or hidden stabilizing support.
- Run multiple seeds at 0%, partial, and full release, including the densest contact state. Record render timing, worker P95, real/simulated time, awake bodies, and contact counts.
- Repeat at least 20 release/reset cycles; check worker/thread count, native object cleanup, memory trend, render geometry, and restored topology. Save replay receipts and representative browser captures.

## Primary references

- [Jolt fixed constraint settings](https://jrouwe.github.io/JoltPhysics/class_fixed_constraint_settings.html): attachment frames and automatic preservation of current relative pose.
- [Jolt constraint API](https://jrouwe.github.io/JoltPhysics/class_constraint.html): constraint activation and solver iteration behavior.
- [Jolt Physics JavaScript bindings](https://github.com/jrouwe/JoltPhysics.js): browser WebAssembly integration. Compound, constraint and soft-body interfaces are present in the inspected IDL; exact capabilities must be checked against our pinned runtime before implementation.
- [XPBD paper](https://matthias-research.github.io/pages/publications/XPBD.pdf): compliant position-based constraints; it does not by itself supply the missing assembly graph or two-way rigid-body coupling.

# Review and verified rebuild — October 5, 2026

## Verification boundary

The revised model was rebuilt and exported with Blender 5.0.1 on October 5, 2026. The full pipeline completed successfully and published fresh `.blend`, manifest, validation, GLB and artifact-verification outputs.

Two earlier sandboxed background Blender starts crashed in Metal GPU initialization (`supports_barycentric_whitelist` / `MTLBackend::metal_is_supported`), before Python ran. After the user explicitly requested rebuilding, all subsequent Blender work ran outside that sandbox in isolated background processes. These rebuilds completed without crashing; the user's open GUI was left untouched.

`validation.json` records 849 fasteners checked, zero unchecked, zero failures, and 122 nut/washer records checked. `artifact-verification.json` records 1,275 matching saved/exported components, including all 48 curves. A fresh process reopened the saved file, compared identities, transforms, masses and metadata, and checked every exported component's world bounds against the saved geometry. The maximum coordinate discrepancy was 0.0000002384 m against a 0.001 m tolerance. Published file hashes match the verified staging inputs.

This establishes modeled contact and artifact integrity. It does not establish structural safety, physical simulation, measured dimensions, full fastener-volume clearance, or tool access for every connection.

## Checks completed without Blender

- 49 Python tests passed: manual-derived assembly/shape cases, record validation, mesh interval math, placement, flush bracket joining profiles and mocked build/export/verification failures.
- 9 Node tests passed: note persistence, corrupt storage, export formatting, metadata inheritance, visibility, material restoration and camera argument checks.
- Python compilation, focused Ruff undefined-name/import checks, shell syntax and `git diff --check` passed.
- The rebuilt assembly contains 252 members and 462 joints, with no unknown references, 24 tarp screws and 401 SW35.

## Browser verification

The final rebuilt GLB loaded as 1,275 meshes in the browser. Front and rear views showed the slide, ladder, swing assembly, roof and nets. Clicking the rebuilt slide returned its part code and coordinates; hiding its group cleared selection, and restoring visibility restored the model. The browser warning/error log was empty. Earlier viewer checks covered note persistence, clipboard export and floorboard selection using the previous GLB; the QA note was removed and the session clipboard cleared afterward.

A low-level inspection call stalled in the browser tool and was interrupted. The tool's read-only evaluation scope did not expose application globals; that is not evidence that the viewer's public state API is broken. Mobile sizing and injected load-failure behavior were not browser-tested. The new Remove/Undo controls also permit cleanup of ordinary review notes.

## Corrections backed by the supplied manual

Printed page numbers differ from PDF sheet numbers because the PDF contains paired pages.

| Finding | Source | Source correction |
|---|---|---|
| Missing hammock-eye nuts | Steps 175–178, pp.98–99 | Eight BM818 nut assignments added. |
| Wrong climbing-net nuts | Steps 182–183, pp.101–102 | Four NM815 assignments replaced with BM818. |
| Only one washer per hanger | Step 159, p.90 | Head-side washer added alongside base-side washer/locknut. |
| Missing tarp fasteners | Steps 131–133, pp.76–77 | Six SW16 per F16 rail; grouped step provenance, estimated spacing. |
| Missing W01 attachments | Steps 65/70 | One screw at each CA10 and one at KA11_C. |
| W02 misses its joist | Steps 66/71 | Extend estimated end to ±0.27 m; attach once to the outer rail, K05 and KA11. |
| W10 shortened past its rail supports | Step 67, p.44 | Full-length plank with local C04 corner notches; six screws per plank. |
| Small-deck edge boards short one screw | Steps 93/97 | W12A and W12 each use six SW35. |
| Gaps between tabletop boards | Step 145, p.83 | Board pitch equals width (135 mm). |
| Seat thickness lowered clearance twice | Step 192 and p.4 | Finished seat underside targets 360 mm; thickness added before solidify. |
| Mitred board mass counted a full rectangle | Modeled geometry | Mass subtracts the two/one triangular cuts. |

All listed corrections were rebuilt and passed the mesh checks. The manual does not provide enough dimensions to prove real-world fit from source alone.

The first strict rebuild exposed 92 placements that the old box checks missed. Additional checks exposed nut engagement and stale manifest transforms. Corrections include F05 rail overlap with posts; the tarp skirt following the roof-rail slope; upward slide normals and holes in its flat mounting bed; ladder screws entering through uprights into rung ends; actual base-mesh exits for nuts; correct flange/barrel orientation; and a dependency-graph update before serializing transforms. Handle mounting feet are separate from their standoffs, with all six screw heads clearing those standoffs and the foot edges by 0.9 mm in the modeled geometry.

Several unknown dimensions were revised as explicitly labeled fit estimates: FA17 fixing depth 30 mm, roof board layers 25 mm, net fixing plate/eye body depths 5/15 mm, and Y-bracket clearances 1 mm per face. These are model assumptions constrained by the listed hardware, not measurements from the manual.

### Y-bracket attachment correction

The user's end-on inspection exposed an error missed by fastener contact checks: each inclined sleeve's inner wall met the vertical cup wall only at its top edge, leaving an opening below. An initial widened-cheek correction filled the opening but distorted the sleeves into wedges; that iteration was rejected and is retained under `docs/bracket-review/after/` only as review history.

The replacement retains a constant 78 mm square sleeve section and cuts each upper end on the vertical cup-wall plane. The leg angle is solved with the lower miter corner at the cup bottom and the existing foot positions. The upper tip is trimmed horizontally to maintain the 25 mm top offset. The vertical mating edges therefore stop at the cup bottom instead of protruding below it. Wood seating and hardware follow the new sleeve frame. Cup position and foot spacing remain fixed; leg axes and upper wood endpoints change.

The full rebuild passed all contact/export checks. A fresh process independently found both flush end faces, checked the sleeves for constant section (`constant_section_sleeves: 2`), measured 123 mm of contact with each cup wall, and checked that each mating face ends at the cup bottom. Four fixed CPU-rendered close-ups of this replacement are saved under `docs/bracket-review/iteration2/`; all four views were inspected. The viewer's **Y-bracket close-up** button provides the end-on inspection angle. These checks establish modeled fit, not measured manufacturer dimensions or structural capacity.

## Validation and maintainability

The former 1,098-line script built on import and shared mutable names across unrelated sections. It mixed shape creation, manual schedule, placement heuristics, reporting and file writes. Those responsibilities now have separate modules; geometry state is scoped to a build, and the assembly step is passed explicitly rather than through `CUR_STEP`.

The original shell pipeline suppressed Blender failure and could export stale outputs. The revised pipeline propagates failures, uses factory-startup background processes, stages outputs, and retains failure diagnostics. Mock-process tests inject build/export/verification failures and missing outputs and verify that previous files survive. Publication is sequential across five files; it is not a filesystem-wide atomic transaction. During the real rebuild, independent verification rejected stale hardware matrices in the manifest and correctly preserved the previous outputs until the update-order fix passed.

The former validation assigned zero contact gaps to explicit placements and skipped slide, knee and bracket fasteners. New checks inspect actual mesh intersections and head surfaces for every modeled fastener, including continuous material engagement and nut reach. Disconnected closed shells are traced separately and unioned to avoid phantom voids inside joined brackets. Record validation checks references, identities, counts, assignments, finite coordinates, normalized axes and nut stacks. Bounded surface refinement corrects failed box proposals and rejects grazing paths; unresolved refinements fail verification. Generic projected positions remain labeled estimates. Strict pipeline mode rejects failures; the diagnostic CLI mode can report `needs_review`.

The new manifest includes orientations and every rendered component's estimated mass, including ropes, hanger parts and nuts/washers. It labels unsupported fastener capacities as unverified and removes the unsupported ±50% confidence claim. It does not create inertia, constraints or an anchoring model.

## Source inconsistencies and remaining model limitations

Do not add arbitrary hardware to force these counts to agree:

| Item | Assembly evidence | Inventory page |
|---|---|---|
| SW60 | Explicit step quantities total 128 | 124 |
| SW50 | 54 before step 191; stake wording can imply 2 total or 2 per stake | 54 |
| BM818 | Corrected net assignments produce 24; steps 49–50 also use the conflicting label NM818 | 21 |
| NM815 | Correcting net nuts leaves 72 modeled assignments | 80 |
| SW35 | Rebuilt schedule produces 401 | 405 |

Still unresolved:

- Lumber cross sections, many layout dimensions, bracket thickness/setback/socket dimensions, material densities and rope radius remain estimates. The 574 lb listing is inherited and unverified; it is a comparison, not a calibration target.
- The two sun shades in steps 187–189 are absent. Their chosen placement and dimensions have not been established.
- The visible net has no load-bearing topology connecting each rope to the eight eyes. No rigid bodies, constraints, inertia, wood flexure, anchoring or soil behavior are configured.
- Several repeated legacy assemblies use representative step numbers. `source_steps` identifies grouped references where known; this is not a verified bill of materials for all 193 steps.
- Automatic placement starts from local boxes and refines invalid proposals against actual surfaces. This does not verify joint strength or clearance from every unrelated third part.
- The viewer still depends on the pinned CDN modules. Failures are now visible and retryable.

## Files changed

| File | Change |
|---|---|
| `.gitignore` | Ignore staging and validation outputs. |
| `README.md` | Current commands, architecture and honest validation boundary. |
| `build.py` | Import-safe entry point and explicit build lifecycle. |
| `build.sh` | Failures propagate; staged output publication; strict checks. |
| `export_glb.py` | Background-only export, curve conversion and safe replacement. |
| `bear_basin/__init__.py` | Side-effect-free package entry. |
| `bear_basin/geometry.py` | Extracted geometry and manual-backed corrections. |
| `bear_basin/joints.py` | Explicit assembly schedule and corrected hardware counts. |
| `bear_basin/hardware.py` | Catalog, nut stacks, inventory and estimated mass. |
| `bear_basin/placement.py` | Shared contact solver and explicit-context positions. |
| `bear_basin/mesh_placement.py` | Actual-surface refinement with bounded searches and explicit unresolved outcomes. |
| `bear_basin/assembly.py` | Hardware creation, stable IDs and stack records. |
| `bear_basin/shapes.py` | Pure notched-board geometry. |
| `bear_basin/validation.py` | Record consistency and actual mesh checks. |
| `bear_basin/report.py` | Versioned manifest and complete scene mass accounting. |
| `tests/test_model.py` | Manual-derived schedule and validation regressions. |
| `tests/test_pipeline.py` | Mock build/export failure and scene-safety tests. |
| `tests/verify_artifacts.py` | Independent saved scene and GLB integrity and world-bounds verification. |
| `viewer/index.html` | Semantic UI and module entry. |
| `viewer/viewer.css` | Extracted layout/styles. |
| `viewer/app.js` | Notes, persistence, remove/undo, clipboard fallback and startup errors. |
| `viewer/viewer.js` | Model loading, selection, group toggles and demand rendering. |
| `viewer/notes.mjs` | Compatible note serialization. |
| `viewer/model-state.mjs` | Metadata inheritance, visibility and reversible highlighting. |
| `viewer/serve.py` | Portable CLI, validation and clean shutdown. |
| `viewer/tests/state.test.mjs` | Viewer data/state regressions. |
| `docs/review.md` | Findings, evidence, verification and remaining work. |

Intentionally unchanged: the supplied PDF, original local `MEMORY.md`/`ERRORS.md`, earlier `docs/manual-notes.md`, `.claude/launch.json`, and Blender's user preferences/add-ons. Generated outputs now contain the rebuilt, verified refactor. Original baseline copies remain in `/private/tmp/bear-basin-baseline/`.

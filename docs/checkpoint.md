# Smooth physics checkpoint — 2026-10-05

This checkpoint preserves the accepted playground geometry and the smooth, deterministic playback of a verified Rapier simulation before work on fresh randomized live physics.

The source, vendored dependencies, compressed physics trajectory, tests and verification receipts are committed together. Verification before the checkpoint: 22 viewer tests passed; cached model updates averaged approximately 0.53 ms; the browser rendered approximately 120 FPS and completed fall and reassembly.

Git tag: `codex/checkpoint-2026-10-05-smooth-physics`.

Generated Blender, manifest, GLB and validation artifacts are backed up separately in `.checkpoints/2026-10-05-smooth-physics/generated-artifacts.tar.gz`. The adjacent `manifest.json` records SHA-256 hashes and the source commit. The local archive is intentionally ignored by Git and remains in this checkout.

To recover without overwriting ongoing work, create a separate checkout from the tag and extract the generated archive into that checkout. Restore both the source checkpoint and the generated artifacts to recover the exact visible model.

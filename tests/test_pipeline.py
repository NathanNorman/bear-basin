"""Pipeline failure and export safety checks that never launch real Blender."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (
    "bear_basin.blend",
    "bear_basin.json",
    "validation.json",
    "viewer/bear_basin.glb",
    "artifact-verification.json",
)
MOCK_BLENDER = r"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
assert "--background" in args and "--factory-startup" in args
assert args[args.index("--python-exit-code") + 1] == "1"
script = Path(args[args.index("--python") + 1]).name
options = args[args.index("--") + 1:]
phase = {"build.py": "build", "export_glb.py": "export", "verify_artifacts.py": "verify"}[script]
with open(os.environ["MOCK_BLENDER_LOG"], "a") as log:
    log.write(json.dumps({"phase": phase, "options": options}) + "\n")
if phase == "build":
    stage = Path(options[options.index("--output-dir") + 1])
    for name in ("bear_basin.blend", "bear_basin.json", "validation.json"):
        if os.environ.get("MOCK_BLENDER_OMIT") != name:
            (stage / name).write_text("new " + name)
elif phase == "export":
    source = Path(options[options.index("--input") + 1])
    target = Path(options[options.index("--output") + 1])
    assert source.parent == target.parent
    assert source.read_text() == "new bear_basin.blend"
    if os.environ.get("MOCK_BLENDER_OMIT") != "bear_basin.glb":
        target.write_text("new viewer/bear_basin.glb")
else:
    source = Path(options[options.index("--blend") + 1])
    manifest = Path(options[options.index("--manifest") + 1])
    glb = Path(options[options.index("--glb") + 1])
    receipt = Path(options[options.index("--receipt") + 1])
    assert source.parent == manifest.parent == glb.parent == receipt.parent
    assert source.read_text() == "new bear_basin.blend"
    assert manifest.read_text() == "new bear_basin.json"
    assert glb.read_text() == "new viewer/bear_basin.glb"
    if os.environ.get("MOCK_BLENDER_OMIT") != "artifact-verification.json":
        receipt.write_text("new artifact-verification.json")
if os.environ.get("MOCK_BLENDER_FAIL_PHASE") == phase:
    print("Injected " + phase + " failure", file=sys.stderr)
    sys.exit(23)
"""


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bear basin tests ")
        self.root = Path(self.temp.name)
        shutil.copy2(ROOT / "build.sh", self.root / "build.sh")
        # Blender is always an isolated test double, never the installed binary.
        self.blender = self.root / "mock blender"
        self.blender.write_text(MOCK_BLENDER)
        self.blender.chmod(0o755)
        self.log = self.root / "calls.jsonl"
        for output in OUTPUTS:
            path = self.root / output
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("old " + output)

    def tearDown(self):
        self.temp.cleanup()

    def run_build(self, **overrides):
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("MOCK_BLENDER_")
        }
        env.update(BLENDER=str(self.blender), MOCK_BLENDER_LOG=str(self.log))
        env.update(overrides)
        result = subprocess.run(
            ["sh", str(self.root / "build.sh")],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(
            list(self.root.glob(".bear-basin-build.*")),
            [],
            "staging directory was not cleaned up",
        )
        return result

    def assert_old_outputs(self):
        for output in OUTPUTS:
            self.assertEqual((self.root / output).read_text(), "old " + output)

    def phases(self):
        return [json.loads(line)["phase"] for line in self.log.read_text().splitlines()]

    def test_success_publishes_all_staged_outputs(self):
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["build", "export", "verify"])
        for output in OUTPUTS:
            self.assertEqual((self.root / output).read_text(), "new " + output)
        self.assertIn("Built bear_basin.blend", result.stdout)

    def test_strict_mesh_checks_and_failure_diagnostics(self):
        result = self.run_build(MOCK_BLENDER_FAIL_PHASE="build")
        self.assertEqual(result.returncode, 23)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertIn("--strict-mesh", calls[0]["options"])
        self.assertEqual(
            (self.root / "validation.failed.json").read_text(), "new validation.json"
        )
        self.assert_old_outputs()

    def test_build_failure_preserves_outputs_and_skips_export(self):
        result = self.run_build(MOCK_BLENDER_FAIL_PHASE="build")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(self.phases(), ["build"])
        self.assertIn("Injected build failure", result.stderr)
        self.assertNotIn("Built bear_basin.blend", result.stdout)
        self.assert_old_outputs()

    def test_export_failure_preserves_outputs(self):
        result = self.run_build(MOCK_BLENDER_FAIL_PHASE="export")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(self.phases(), ["build", "export"])
        self.assertIn("Injected export failure", result.stderr)
        self.assertNotIn("Built bear_basin.blend", result.stdout)
        self.assert_old_outputs()

    def test_missing_build_output_cannot_reuse_old_artifact(self):
        for output in OUTPUTS[:3]:
            with self.subTest(output=output):
                self.log.unlink(missing_ok=True)
                result = self.run_build(MOCK_BLENDER_OMIT=output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.phases(), ["build"])
                self.assertIn("nonempty " + output, result.stderr)
                self.assert_old_outputs()

    def test_verification_failure_preserves_outputs_and_receipt(self):
        result = self.run_build(MOCK_BLENDER_FAIL_PHASE="verify")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(self.phases(), ["build", "export", "verify"])
        self.assertIn("Injected verify failure", result.stderr)
        self.assertNotIn("Built bear_basin.blend", result.stdout)
        self.assertEqual(
            (self.root / "artifact-verification.failed.json").read_text(),
            "new artifact-verification.json",
        )
        self.assertEqual(
            (self.root / "validation.failed.json").read_text(), "new validation.json"
        )
        self.assert_old_outputs()

    def test_missing_verification_receipt_cannot_reuse_old_receipt(self):
        result = self.run_build(MOCK_BLENDER_OMIT="artifact-verification.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases(), ["build", "export", "verify"])
        self.assertIn("nonempty receipt", result.stderr)
        self.assertNotIn("Built bear_basin.blend", result.stdout)
        self.assert_old_outputs()

    def test_missing_export_output_cannot_reuse_old_artifact(self):
        result = self.run_build(MOCK_BLENDER_OMIT="bear_basin.glb")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases(), ["build", "export"])
        self.assertIn("nonempty GLB", result.stderr)
        self.assert_old_outputs()

    def test_missing_blender_is_clear_failure(self):
        result = self.run_build(BLENDER=str(self.root / "no such Blender"))
        self.assertEqual(result.returncode, 127)
        self.assertIn("Blender executable not found", result.stderr)
        self.assert_old_outputs()


class ExportTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "export_glb_under_test", ROOT / "export_glb.py"
        )
        self.exporter = importlib.util.module_from_spec(spec)
        # Import cannot require bpy or execute its APIs, even with an invalid bpy
        # module already present (as in an interactive Python environment).
        with patch.dict(sys.modules, {"bpy": None}):
            spec.loader.exec_module(self.exporter)

    def test_cli_parses_explicit_paths_without_scene_effects(self):
        args = self.exporter.parse_args(
            ["--input", "new model.blend", "--output", "new model.glb"]
        )
        self.assertEqual(args.input, Path("new model.blend"))
        self.assertEqual(args.output, Path("new model.glb"))

    def test_cli_ignores_blender_flags(self):
        with patch.object(
            sys,
            "argv",
            [
                "blender",
                "--background",
                "--python",
                "export_glb.py",
                "--",
                "--input",
                "stage.blend",
            ],
        ):
            self.assertEqual(self.exporter.parse_args().input, Path("stage.blend"))

    def test_help_runs_without_blender(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "export_glb.py"), "--help"],
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--input", result.stdout)
        self.assertIn("--output", result.stdout)

    def test_interactive_export_refuses_before_loading_a_scene(self):
        bpy = types.SimpleNamespace(app=types.SimpleNamespace(background=False))
        with patch.dict(sys.modules, {"bpy": bpy}):
            with self.assertRaisesRegex(RuntimeError, "--background"):
                self.exporter.export_model("anything.blend", "anything.glb")

    def test_glb_header_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.glb"
            for blob in (
                b"",
                b"partial",
                struct.pack("<4sII", b"glTF", 1, 16) + b"data",
                struct.pack("<4sII", b"glTF", 2, 20) + b"data",
            ):
                with self.subTest(blob=blob):
                    path.write_bytes(blob)
                    with self.assertRaises(RuntimeError):
                        self.exporter.validate_glb(path)
            path.write_bytes(struct.pack("<4sII", b"glTF", 2, 16) + b"data")
            self.exporter.validate_glb(path)

    def test_failed_standalone_export_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "model.blend"
            output = Path(temp) / "model.glb"
            source.write_bytes(b"source model")
            output.write_bytes(b"previous GLB")
            for outcome in ("exception", "cancelled", "invalid"):
                with self.subTest(outcome=outcome):

                    def export(**options):
                        Path(options["filepath"]).write_bytes(b"incomplete")
                        if outcome == "exception":
                            raise RuntimeError("injected exporter error")
                        return {"CANCELLED"} if outcome == "cancelled" else {"FINISHED"}

                    bpy = types.SimpleNamespace(
                        app=types.SimpleNamespace(background=True),
                        ops=types.SimpleNamespace(
                            wm=types.SimpleNamespace(open_mainfile=Mock()),
                            export_scene=types.SimpleNamespace(gltf=export),
                        ),
                    )
                    with (
                        patch.dict(sys.modules, {"bpy": bpy}),
                        patch.object(self.exporter, "prepare_scene"),
                    ):
                        with self.assertRaises(RuntimeError):
                            self.exporter.export_model(source, output)
                    self.assertEqual(source.read_bytes(), b"source model")
                    self.assertEqual(output.read_bytes(), b"previous GLB")
                    self.assertEqual(list(Path(temp).glob(".model-*.glb")), [])

    def test_curve_conversion_keeps_parts_and_metadata(self):
        class SceneObject(dict):
            def __init__(self, name, object_type, **properties):
                super().__init__(properties)
                self.name = name
                self.type = object_type
                self.users_collection = [types.SimpleNamespace(name="Swings")]
                self.selected = False

            def hide_set(self, value):
                self.hidden = value

            def select_set(self, value):
                self.selected = value

        class Objects(list):
            def get(self, name):
                return next((obj for obj in self if obj.name == name), None)

        rope = SceneObject("rope", "CURVE", code="Rope", kind="rope", mass_kg=0.2)
        hook = SceneObject(
            "hook", "CURVE", code="Hook", kind="steel", mass_kg=0.1, group="Hardware"
        )
        board = SceneObject("board", "MESH", code="W01", kind="wood", mass_kg=1.2)
        ground = SceneObject("Ground", "MESH")
        objects = Objects([rope, hook, board, ground])

        def deselect_all(**options):
            for obj in objects:
                obj.select_set(False)

        def convert(**options):
            self.assertEqual(options, {"target": "MESH"})
            self.assertTrue(rope.selected and hook.selected)
            self.assertFalse(board.selected)
            for obj in objects:
                if obj.selected:
                    obj.type = "MESH"
            return {"FINISHED"}

        bpy = types.SimpleNamespace(
            context=types.SimpleNamespace(
                scene=types.SimpleNamespace(objects=objects),
                view_layer=types.SimpleNamespace(
                    objects=types.SimpleNamespace(active=None)
                ),
            ),
            data=types.SimpleNamespace(
                materials=[],
                objects=types.SimpleNamespace(
                    remove=lambda obj, **kwargs: objects.remove(obj)
                ),
            ),
            ops=types.SimpleNamespace(
                object=types.SimpleNamespace(select_all=deselect_all, convert=convert)
            ),
        )
        self.exporter.prepare_scene(bpy)
        self.assertEqual([obj.name for obj in objects], ["rope", "hook", "board"])
        self.assertTrue(all(obj.type == "MESH" for obj in objects))
        self.assertEqual(
            dict(rope),
            {"code": "Rope", "kind": "rope", "mass_kg": 0.2, "group": "Swings"},
        )
        self.assertEqual(
            dict(hook),
            {"code": "Hook", "kind": "steel", "mass_kg": 0.1, "group": "Hardware"},
        )


if __name__ == "__main__":
    unittest.main()

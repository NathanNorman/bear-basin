#!/bin/sh
# Generate, export and independently verify before publishing any output.
set -eu
cd "$(dirname "$0")"
ROOT=$(pwd -P)
BLENDER=${BLENDER:-blender}

if ! command -v "$BLENDER" >/dev/null 2>&1; then
    echo "Blender executable not found: $BLENDER" >&2
    exit 127
fi

stage_dir=$(mktemp -d "$ROOT/.bear-basin-build.XXXXXX")
cleanup() {
    result=$?
    if [ "$result" -ne 0 ]; then
        for diagnostic in validation artifact-verification; do
            if [ -f "$stage_dir/$diagnostic.json" ]; then
                cp "$stage_dir/$diagnostic.json" "$ROOT/$diagnostic.failed.json"
                echo "Failure diagnostics: $ROOT/$diagnostic.failed.json" >&2
            fi
        done
    fi
    rm -rf "$stage_dir"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM

# --python-exit-code makes a Python exception fail the process. Keep complete
# diagnostics visible instead of piping them through a filter that masks failure.
"$BLENDER" --background --factory-startup --python-exit-code 1 \
    --python "$ROOT/build.py" -- --output-dir "$stage_dir" --strict-mesh

for name in bear_basin.blend bear_basin.json validation.json; do
    if [ ! -s "$stage_dir/$name" ]; then
        echo "Build did not produce a nonempty $name; existing outputs preserved." >&2
        exit 1
    fi
done

"$BLENDER" --background --factory-startup --python-exit-code 1 \
    --python "$ROOT/export_glb.py" -- \
    --input "$stage_dir/bear_basin.blend" --output "$stage_dir/bear_basin.glb"

if [ ! -s "$stage_dir/bear_basin.glb" ]; then
    echo "Export did not produce a nonempty GLB; existing outputs preserved." >&2
    exit 1
fi

"$BLENDER" --background --factory-startup --python-exit-code 1 \
    --python "$ROOT/tests/verify_artifacts.py" -- \
    --blend "$stage_dir/bear_basin.blend" \
    --manifest "$stage_dir/bear_basin.json" \
    --glb "$stage_dir/bear_basin.glb" \
    --receipt "$stage_dir/artifact-verification.json"

if [ ! -s "$stage_dir/artifact-verification.json" ]; then
    echo "Verification did not produce a nonempty receipt; existing outputs preserved." >&2
    exit 1
fi

mkdir -p "$ROOT/viewer"
for name in bear_basin.blend bear_basin.json validation.json artifact-verification.json; do
    mv -f "$stage_dir/$name" "$ROOT/$name"
done
mv -f "$stage_dir/bear_basin.glb" "$ROOT/viewer/bear_basin.glb"
echo "Built bear_basin.blend, bear_basin.json, validation.json and viewer/bear_basin.glb; verified in artifact-verification.json"

#!/bin/sh
# Rebuild the model, run its contact and fastener checks, and export the viewer file.
set -e
cd "$(dirname "$0")"
blender -b --python build.py 2>&1 | grep -E "members=|joints whose|fasteners whose|nuts/washers|mass:|^    \(|Error|Traceback" || true
blender -b --python export_glb.py > /dev/null 2>&1
echo "exported viewer/bear_basin.glb"

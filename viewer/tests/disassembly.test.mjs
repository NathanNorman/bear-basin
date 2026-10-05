import test from 'node:test';
import assert from 'node:assert/strict';
import { partPath, samplePath } from '../disassembly.mjs';
test('reassembly returns exactly to the original transform after arbitrary scrubbing', () => {
  const path = partPath([-3, 1.8, .4], 'Fasteners', 'SW35_42');
  for (const t of [1, .6, .9, .2, 0]) {
    const pose = samplePath(path, t);
    assert.ok([...pose.offset, ...pose.turn].every(Number.isFinite));
  }
  assert.ok(samplePath(path, 0).offset.every((n) => n === 0));
  assert.ok(samplePath(path, 0).turn.every((n) => n === 0));
  assert.deepEqual(samplePath(path, 1).offset, path.offset);
});
test('paths are deterministic, lift parts, and release hardware before structure', () => {
  const fastener = partPath([0, 2, 0], 'Fasteners', 'bolt');
  assert.deepEqual(fastener, partPath([0, 2, 0], 'Fasteners', 'bolt'));
  const wood = partPath([0, 2, 0], 'Tower frame', 'post');
  assert.ok(samplePath(fastener, .2).offset[1] > 0);
  assert.ok(samplePath(wood, .2).offset.every((n) => n === 0));
  for (let t = 0; t <= 1; t += .01) assert.ok(samplePath(wood, t).offset[1] >= 0);
});

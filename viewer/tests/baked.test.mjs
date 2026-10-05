import test from 'node:test';
import assert from 'node:assert/strict';
import {BakedSimulation,trajectoryKey} from '../baked-simulation.mjs';

test('cached physics follows elapsed time, interpolates orientation, and holds the simulated rest pose', () => {
  const descriptors=[{part:'plank',mass:1,center:[0,2,0],quaternion:[0,0,0,1],halfExtents:[1,.1,.1]}];
  const cache={header:{frames:2,fps:1,stride:7},values:Float32Array.from([0,2,0,0,0,0,1, 2,0,0,0,1,0,0])};
  const sim=new BakedSimulation(descriptors,cache);
  const [pose]=sim.step(.5);
  assert.deepEqual(pose.position,[1,1,0]);
  assert.ok(Math.abs(Math.hypot(...pose.quaternion)-1)<1e-12);
  assert.equal(sim.active,true);
  sim.step(.5);
  assert.equal(sim.active,false);
  assert.deepEqual(pose.position,[2,0,0]);
  const resting=JSON.stringify(pose);
  sim.step(10);
  assert.equal(JSON.stringify(pose),resting);
  assert.deepEqual(descriptors[0].center,[0,2,0]);
  assert.notEqual(trajectoryKey(descriptors),trajectoryKey([{...descriptors[0],center:[1,2,0]}]));
});

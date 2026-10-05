import test from 'node:test';
import assert from 'node:assert/strict';
import { FallSimulation } from '../fall-physics.mjs';
const box = (y, mass = 1) => ({ center: [0, y, 0], quaternion: [0, 0, 0, 1], halfExtents: [.2, .2, .2], mass });
test('a zero-time first render does not stop the simulation before gravity starts', () => {
  const sim = new FallSimulation([box(3)]);
  sim.step(0);
  assert.equal(sim.active, true);
  for (let i = 0; i < 30; i++) sim.step(1 / 120);
  assert.ok(sim.records[0].body.position.y < 3);
});
test('gravity accelerates bodies equally regardless of mass; floor prevents penetration and bodies settle', () => {
  const sim = new FallSimulation([box(3), { ...box(3, 8), center: [2, 3, 0] }]);
  let poses;
  for (let i = 0; i < 30; i++) poses = sim.step(1 / 120);
  assert.ok(poses[0].position[1] < 2.8);
  assert.ok(Math.abs(poses[0].position[1] - poses[1].position[1]) < 1e-6);
  for (let i = 0; i < 1200; i++) poses = sim.step(1 / 120);
  assert.ok(poses.every((p) => Math.abs(p.position[1] - .2) < .015));
  assert.equal(sim.active, false);
});
test('solid bodies collide and stack instead of passing through each other', () => {
  const sim = new FallSimulation([box(.2), box(2)]);
  let poses;
  for (let i = 0; i < 1200; i++) poses = sim.step(1 / 120);
  assert.ok(poses[1].position[1] > .55);
});
test('tiny fasteners cannot escape through the floor under heavy parts', () => {
  const sim = new FallSimulation([{...box(.1, .002), halfExtents:[.003,.003,.025], hardware:true}, box(1, 15)]);
  for (let i = 0; i < 400; i++) {
    sim.step(1 / 120);
    for (const record of sim.records) {
      record.body.updateAABB();
      assert.ok(record.body.aabb.lowerBound.y >= -.0021);
    }
  }
});
test('flexible rope nodes fall and cannot stretch beyond their constrained lengths', () => {
  const sim = new FallSimulation([{mass:.2, points:[[0,2,0],[.3,2,0],[.6,2,0]]}]);
  let pose;
  for (let i = 0; i < 800; i++) [pose] = sim.step(1 / 120);
  assert.ok(pose.points.every((p) => p[1] >= -.01 && p[1] < .05));
  for (let i = 1; i < pose.points.length; i++) {
    assert.ok(Math.hypot(...pose.points[i].map((v,j) => v-pose.points[i-1][j])) <= .31);
  }
});
test('an initially straight vertical swing rope collapses rather than balancing upright', () => {
  const sim = new FallSimulation([{mass:.2, points:Array.from({length:12}, (_,i) => [0, .2+i*.16, 0])}]);
  let pose;
  for (let i = 0; i < 600; i++) [pose] = sim.step(1 / 60);
  assert.ok(Math.max(...pose.points.map((p) => p[1])) < .1);
});
test('a long rod released vertically tumbles onto its side instead of balancing on its end', () => {
  const sim = new FallSimulation([{...box(2),halfExtents:[.01,.6,.01]}]);
  let pose;
  for(let i=0;i<600;i++) [pose]=sim.step(1/60);
  assert.ok(pose.position[1] < .1);
});
test('an unsupported overhanging plank tips and then remains motionless in native sleep', () => {
  const sim = new FallSimulation([
    {...box(.12),halfExtents:[.12,.12,.12],mass:10},
    {...box(.35),center:[.65,.35,0],halfExtents:[.8,.025,.07],mass:2}
  ]);
  for(let i=0;i<1800;i++) sim.step(1/120);
  assert.equal(sim.active,false);
  const pose=sim.records[1].body.position.toArray();
  sim.records[1].body.updateAABB();
  assert.ok(Math.abs(sim.records[1].body.quaternion.z)>.08,'the overhang must tip');
  assert.ok(sim.records[1].body.aabb.lowerBound.y<.003,'the unsupported end must reach the ground');
  for(let i=0;i<600;i++) sim.step(1/120);
  assert.deepEqual(sim.records[1].body.position.toArray(),pose);
  sim.dispose();
});
test('a roof-shaped tarp folds onto the ground instead of keeping a rigid tent shape', () => {
  const points=[[-.4,2,-.4],[.4,2,-.4],[.4,2,.4],[-.4,2,.4],[0,2.4,0]];
  const surface=[0,1,4,1,2,4,2,3,4,3,0,4];
  const sim=new FallSimulation([{mass:1,points,surface,edges:[[0,1],[1,2],[2,3],[3,0],[0,4],[1,4],[2,4],[3,4]]}]);
  let poses;
  for(let i=0;i<1800;i++)poses=sim.step(1/120);
  assert.ok(poses[0].points.every(p=>p[1]<.05),'all unsupported cloth vertices should descend');
  assert.equal(sim.active,false);
  sim.dispose();
});

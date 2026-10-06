import test from 'node:test';
import assert from 'node:assert/strict';
import { FallSimulation } from '../fall-physics.mjs';
const box = (y, mass = 1) => ({ center: [0, y, 0], quaternion: [0, 0, 0, 1], halfExtents: [.2, .2, .2], mass });
test('a zero-time first render does not stop the simulation before gravity starts', (t) => {
  const sim = new FallSimulation([box(3)]);
  t.after(()=>sim.dispose());
  sim.step(0);
  assert.equal(sim.active, true);
  for (let i = 0; i < 30; i++) sim.step(1 / 120);
  assert.ok(sim.records[0].body.position.y < 3);
});
test('gravity accelerates bodies equally regardless of mass; floor prevents penetration and bodies settle', (t) => {
  const sim = new FallSimulation([box(3), { ...box(3, 8), center: [2, 3, 0] }]);
  t.after(()=>sim.dispose());
  let poses;
  for (let i = 0; i < 30; i++) poses = sim.step(1 / 120);
  assert.ok(poses[0].position[1] < 2.8);
  assert.ok(Math.abs(poses[0].position[1] - poses[1].position[1]) < 1e-6);
  for (let i = 0; i < 1200; i++) poses = sim.step(1 / 120);
  assert.ok(poses.every((p) => Math.abs(p.position[1] - .2) < .015));
  assert.equal(sim.active, false);
});
test('solid bodies collide and stack instead of passing through each other', (t) => {
  const sim = new FallSimulation([box(.2), box(2)]);
  t.after(()=>sim.dispose());
  let poses;
  for (let i = 0; i < 1200; i++) poses = sim.step(1 / 120);
  assert.ok(poses[1].position[1] > .55);
});
test('tiny fasteners cannot escape through the floor under heavy parts', (t) => {
  const sim = new FallSimulation([{...box(.1, .002), halfExtents:[.003,.003,.025], hardware:true}, box(1, 15)]);
  t.after(()=>sim.dispose());
  for (let i = 0; i < 1200; i++) {
    sim.step(1 / 120);
    for (const record of sim.records) {
      record.body.updateAABB();
      assert.ok(record.body.position.y >= 0,'no body may escape through the floor');
      assert.ok(record.body.aabb.lowerBound.y >= -.005,'impact penetration stays within 5 mm');
    }
  }
  assert.equal(sim.active,false);
  for(const record of sim.records){record.body.updateAABB();assert.ok(record.body.aabb.lowerBound.y>=-.0021,'resting geometry is supported above the floor');}
});
test('flexible rope nodes fall and cannot stretch beyond their constrained lengths', (t) => {
  const sim = new FallSimulation([{mass:.2, points:[[0,2,0],[.3,2,0],[.6,2,0]]}]);
  t.after(()=>sim.dispose());
  let pose;
  for (let i = 0; i < 800; i++) [pose] = sim.step(1 / 120);
  assert.ok(pose.points.every((p) => p[1] >= -.01 && p[1] < .05));
  for (let i = 1; i < pose.points.length; i++) {
    assert.ok(Math.hypot(...pose.points[i].map((v,j) => v-pose.points[i-1][j])) <= .31);
  }
});
test('an initially straight vertical swing rope collapses rather than balancing upright', (t) => {
  const sim = new FallSimulation([{mass:.2, points:Array.from({length:12}, (_,i) => [0, .2+i*.16, 0])}]);
  t.after(()=>sim.dispose());
  let pose;
  for (let i = 0; i < 600; i++) [pose] = sim.step(1 / 60);
  assert.ok(Math.max(...pose.points.map((p) => p[1])) < .1);
});
test('a long rod released vertically tumbles onto its side instead of balancing on its end', (t) => {
  const sim = new FallSimulation([{...box(2),halfExtents:[.01,.6,.01]}]);
  t.after(()=>sim.dispose());
  let pose;
  for(let i=0;i<600;i++) [pose]=sim.step(1/60);
  assert.ok(pose.position[1] < .1);
});
test('an unsupported overhanging plank tips and then remains motionless in native sleep', (t) => {
  const sim = new FallSimulation([
    {...box(.12),halfExtents:[.12,.12,.12],mass:10},
    {...box(.35),center:[.65,.35,0],halfExtents:[.8,.025,.07],mass:2}
  ]);
  t.after(()=>sim.dispose());
  for(let i=0;i<1800;i++) sim.step(1/120);
  assert.equal(sim.active,false);
  const pose=sim.records[1].body.position.toArray();
  sim.records[1].body.updateAABB();
  assert.ok(Math.abs(sim.records[1].body.quaternion.z)>.08,'the overhang must tip');
  assert.ok(sim.records[1].body.aabb.lowerBound.y<.003,'the unsupported end must reach the ground');
  for(let i=0;i<600;i++) sim.step(1/120);
  assert.deepEqual(sim.records[1].body.position.toArray(),pose);
});
test('a roof-shaped tarp folds onto the ground instead of keeping a rigid tent shape', (t) => {
  const points=[[-.4,2,-.4],[.4,2,-.4],[.4,2,.4],[-.4,2,.4],[0,2.4,0]];
  const surface=[0,1,4,1,2,4,2,3,4,3,0,4];
  const sim=new FallSimulation([{mass:1,points,surface,edges:[[0,1],[1,2],[2,3],[3,0],[0,4],[1,4],[2,4],[3,4]]}]);
  t.after(()=>sim.dispose());
  let poses;
  for(let i=0;i<1800;i++)poses=sim.step(1/120);
  assert.ok(poses[0].points.every(p=>p[1]<.05),'all unsupported cloth vertices should descend');
  assert.equal(sim.active,false);
});

test('fresh seeds produce different falls and a stored seed reproduces the same physics', (t) => {
  const run=seed=> {
    const sim=new FallSimulation([box(3), {...box(4),center:[.1,4,0]}],{seed});
    let poses;
    for(let i=0;i<120;i++)poses=sim.step(1/60);
    sim.dispose();return poses;
  };
  assert.deepEqual(run(123),run(123));
  assert.notDeepEqual(run(123),run(456));
});
test('a rope supported above the floor by a plank recognizes CCD contact and sleeps',(t)=> {
  const sim=new FallSimulation([
    {...box(.3),halfExtents:[.5,.3,.5],mass:10},
    {mass:.2,points:[[0,2,0],[.1,2,0],[.2,2,0]]}
  ]);
  t.after(()=>sim.dispose());
  for(let i=0;i<1200;i++)sim.step(1/60);
  assert.equal(sim.active,false);
  assert.ok(sim.records[1].nodes.every(n=>n.position.y>.59));
  const poses=sim.step(0);
  for(let i=0;i<60;i++)sim.step(1/60);
  assert.deepEqual(sim.step(0),poses);
});

test('cloth faces land on a narrow beam even when their vertices miss it', (t) => {
  const points=[[-.8,1.5,-.6],[.8,1.5,-.6],[.8,1.5,.6],[-.8,1.5,.6]];
  const sim=new FallSimulation([
    {...box(.2,1000),halfExtents:[.06,.2,1]},
    {mass:1,points,surface:[0,1,2,0,2,3],edges:[[0,1],[1,2],[2,3],[3,0],[0,2]]}
  ]);
  t.after(()=>sim.dispose());
  let poses;
  for(let i=0;i<1200;i++)poses=sim.step(1/120);
  const [a,,c]=poses[1].points;
  const centerY=(a[1]+c[1])/2;
  assert.ok(centerY>.39,`fabric spanning the beam must stay above it, got ${centerY}`);
});

test('a fast cloth face cannot tunnel through a thin beam between steps', (t) => {
  const points=[[-.8,1,-.6],[.8,1,-.6],[.8,1,.6],[-.8,1,.6]];
  const sim=new FallSimulation([
    {...box(.5,1000),halfExtents:[.06,.025,1]},
    {mass:1,points,surface:[0,1,2,0,2,3],edges:[[0,1],[1,2],[2,3],[3,0],[0,2]]}
  ]);
  t.after(()=>sim.dispose());
  for(let i=1;i<sim.records[1].soft.velocities.length;i+=3)sim.records[1].soft.velocities[i]=-60;
  const poses=sim.step(1/60),[a,,c]=poses[1].points;
  const centerY=(a[1]+c[1])/2;
  assert.ok(centerY>.52,`swept fabric must stay on the incoming side, got ${centerY}`);
});

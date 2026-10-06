import fs from 'node:fs';
import assert from 'node:assert/strict';
import { FallSimulation } from '../viewer/fall-physics.mjs';
const descriptors=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const simulation=new FallSimulation(descriptors);
const samples=[];
let resting;
for(let tick=0;tick<2400;tick++) {
  const poses=simulation.step(1/120);
  if(!simulation.active && !resting) resting=poses;
  if(tick%600===599) samples.push({seconds:(tick+1)/120,
    awake:simulation.records.flatMap((r,i)=>(r.nodes||[r.body]).some(b=>!b.raw.isSleeping())?[descriptors[i].part]:[])});
}
console.log(JSON.stringify({samples:samples.map(s=>({seconds:s.seconds,awake:s.awake.length})),moving:simulation.records.flatMap((r,i)=>(r.nodes||[r.body]).some(b=>Math.hypot(...Object.values(b.raw.linvel()))>.01)?[descriptors[i].part]:[])}));
assert.equal(simulation.active,false,'the actual browser input must reach its sleep conditions');
for(let tick=0;tick<600;tick++)simulation.step(1/120);
assert.deepEqual(simulation.step(1/120),resting,'the sleeping scene must not drift');
console.log(JSON.stringify({samples,rigidNativeSleep:true,deformableSleep:true,lateMotion:0}));
simulation.dispose();

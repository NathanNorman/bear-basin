import * as THREE from '../viewer/vendor/three.mjs';
import {loadReleasedModel} from './fall-fixture.mjs';
import {poseSignature} from '../viewer/random.mjs';
import {exactBox} from '../viewer/collision-shapes.mjs';
import assert from 'node:assert/strict';
import {PhysicsView} from '../viewer/physics-view.mjs';

const {pieces}=await loadReleasedModel();
const seed=process.argv[2]===undefined?null:Number(process.argv[2]);
const fall=new PhysicsView(pieces,{seed});
const bodies=fall.simulation.records.flatMap(record=>record.nodes||[record.body]);
const samples=[];
let resting;
let settledAt;
for(let tick=0;tick<2400;tick++) {
  fall.step(1/120);
  if(!fall.simulation.active && !resting){
    resting=bodies.map(body=>body.position.toArray());
    settledAt=(tick+1)/120;
  }
  if(tick%600===599)samples.push({seconds:(tick+1)/120,
    awake:bodies.filter(body=>!body.raw.isSleeping()).length});
}
if(fall.simulation.active) { console.error('Flexible residuals', fall.simulation.records.flatMap((r,i)=>r.soft&&!r.soft.isSleeping()?[{part:fall.entries[i].descriptor.part,maxSpeed:Math.max(...r.nodes.map(b=>{const v=b.raw.linvel();return Math.hypot(v.x,v.y,v.z);})),minY:Math.min(...r.nodes.map(b=>b.position.y))}]:[])); console.error('Awake count', fall.simulation.records.filter(r=>(r.nodes||[r.body]).some(b=>!b.raw.isSleeping())).length); console.error('Awake:',fall.simulation.records.flatMap((r,i)=>(r.nodes||[r.body]).some(b=>!b.raw.isSleeping())?[fall.entries[i].descriptor.part]:[]));}
assert.equal(fall.simulation.active,false,'rigid and deformable parts must reach their sleep conditions');
for(let tick=0;tick<600;tick++)fall.step(1/120);
assert.ok(bodies.every((body,i)=>body.position.toArray().every((v,j)=>v===resting[i][j])),
  'the resting pile must not drift');
const positions=bodies.map(body=>body.position.toArray());
assert.ok(positions.flat().every(Number.isFinite));
const minCenterHeight=Math.min(...positions.map(p=>p[1]));
const visualBounds=fall.entries.map(entry=>({part:entry.descriptor.part,box:new THREE.Box3().setFromObject(entry.object,true)}));
const minVisualHeight=Math.min(...visualBounds.map(e=>e.box.min.y));
if(minVisualHeight<=-.003)console.error('Ground residuals',visualBounds.filter(e=>e.box.min.y<=-.003).map(e=>({part:e.part,minY:e.box.min.y})));
assert.ok(minVisualHeight>-.003,`visible geometry escaped the ground: ${minVisualHeight}`);
const tallVisual=fall.entries.map(entry=> {
  const size=new THREE.Box3().setFromObject(entry.object,true).getSize(new THREE.Vector3());
  return {part:entry.object.userData.part,height:size.y,width:Math.max(size.x,size.z)};
}).filter(part=>part.height>.3 && part.height>part.width*3);
if(tallVisual.length)console.error('Standing parts',tallVisual);
assert.equal(tallVisual.length,0,'narrow parts must not stand unsupported');
const signature=poseSignature(fall.simulation.step(0));
const exactPrimitiveBoxes=fall.entries.filter(e=>exactBox(e.descriptor.vertices)).length;
const flexibleParts=fall.entries.filter(entry=>entry.original).length;
fall.reset();
for(const piece of pieces)assert.equal(piece.object.geometry,piece.geometry);
console.log(JSON.stringify({meshes:pieces.length,flexibleParts,samples,seed,signature,settledAt,exactPrimitiveBoxes,rigidBodiesSleeping:true,rigidSleepPolicy:"native",deformableSleep:true,
  lateDisplacement:0,minVisualHeight,minCenterHeight,tallNarrowComponents:0,finite:true,geometryRestored:true}));

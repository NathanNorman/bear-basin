import * as THREE from '../viewer/vendor/three.mjs';
import {GLTFLoader} from '../viewer/vendor/addons/loaders/GLTFLoader.js';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {PhysicsView} from '../viewer/physics-view.mjs';
import {partPath,samplePath} from '../viewer/disassembly.mjs';
import {readPartMetadata} from '../viewer/model-state.mjs';

const data=fs.readFileSync(new URL('../viewer/bear_basin.glb',import.meta.url));
const root=(await new GLTFLoader().parseAsync(data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength),'')).scene;
root.updateWorldMatrix(true,true);
const pieces=[];
root.traverse(object=> {
  if(!object.isMesh)return;
  Object.assign(object.userData,readPartMetadata(object));
  const center=new THREE.Box3().setFromObject(object).getCenter(new THREE.Vector3());
  const pose=samplePath(partPath(center.toArray(),object.userData.grp,object.userData.part),1);
  const position=object.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(...pose.offset));
  pieces.push({object,geometry:object.geometry});
  object.position.copy(object.parent.worldToLocal(position));
  object.quaternion.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(...pose.turn)));
});
root.updateWorldMatrix(true,true);
const fall=new PhysicsView(pieces);
const bodies=fall.simulation.records.flatMap(record=>record.nodes||[record.body]);
const samples=[];
let resting;
for(let tick=0;tick<2400;tick++) {
  fall.step(1/120);
  if(tick===1799)resting=bodies.map(body=>body.position.toArray());
  if(tick%600===599)samples.push({seconds:(tick+1)/120,
    awake:bodies.filter(body=>!body.raw.isSleeping()).length});
}
assert.equal(fall.simulation.active,false,'all bodies must reach native sleep');
assert.ok(bodies.every((body,i)=>body.position.toArray().every((v,j)=>v===resting[i][j])),
  'the resting pile must not drift');
const positions=bodies.map(body=>body.position.toArray());
assert.ok(positions.flat().every(Number.isFinite));
const minCenterHeight=Math.min(...positions.map(p=>p[1]));
assert.ok(minCenterHeight>-.003,`body escaped the ground: ${minCenterHeight}`);
const tallVisual=fall.entries.map(entry=> {
  const size=new THREE.Box3().setFromObject(entry.object,true).getSize(new THREE.Vector3());
  return {part:entry.object.userData.part,height:size.y,width:Math.max(size.x,size.z)};
}).filter(part=>part.height>.3 && part.height>part.width*3);
assert.equal(tallVisual.length,0,'narrow parts must not stand unsupported');
const flexibleParts=fall.entries.filter(entry=>entry.original).length;
fall.reset();
for(const piece of pieces)assert.equal(piece.object.geometry,piece.geometry);
console.log(JSON.stringify({meshes:pieces.length,flexibleParts,samples,nativeSleep:true,
  lateDisplacement:0,minCenterHeight,tallNarrowComponents:0,finite:true,geometryRestored:true}));

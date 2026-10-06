import * as THREE from '../viewer/vendor/three.mjs';
import {GLTFLoader} from '../viewer/vendor/addons/loaders/GLTFLoader.js';
import fs from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {decodeTrajectory} from '../viewer/baked-simulation.mjs';
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
const raw=gunzipSync(fs.readFileSync(process.argv[2]||new URL('../viewer/fall-trajectory.bin.gz',import.meta.url)));
const cache=decodeTrajectory(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength));
const fall=new PhysicsView(pieces,{trajectory:cache});
assert.equal(fall.cached,true,'the real model must match the cached trajectory');
const timings=[];
const playbackTicks=Math.ceil(((cache.header.frames-1)/cache.header.fps+1)*120);
for(let tick=0;tick<playbackTicks;tick++) {
  const start=performance.now();fall.step(1/120);timings.push(performance.now()-start);
}
assert.equal(fall.simulation.active,false);
const resting=JSON.stringify(fall.simulation.poses);
for(let tick=0;tick<120;tick++)fall.step(1/120);
assert.equal(JSON.stringify(fall.simulation.poses),resting);
fall.reset();
for(const piece of pieces)assert.equal(piece.object.geometry,piece.geometry);
const sorted=[...timings].sort((a,b)=>a-b);
console.log(JSON.stringify({cached:true,frames:cache.header.frames,duration:(cache.header.frames-1)/cache.header.fps,
  cpuMsMean:timings.reduce((a,b)=>a+b)/timings.length,cpuMsP95:sorted[Math.floor(sorted.length*.95)],
  nativeSleep:cache.header.nativeSleep,restingUnchanged:true,geometryRestored:true}));

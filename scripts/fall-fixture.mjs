import * as THREE from '../viewer/vendor/three.mjs';
import {GLTFLoader} from '../viewer/vendor/addons/loaders/GLTFLoader.js';
import fs from 'node:fs';
import {partPath,samplePath} from '../viewer/disassembly.mjs';
import {readPartMetadata} from '../viewer/model-state.mjs';
export async function loadReleasedModel() {
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
  return {root,pieces};
}

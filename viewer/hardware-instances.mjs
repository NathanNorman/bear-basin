import * as THREE from 'three';
import { isVisible } from './model-state.mjs';

// Keep original part meshes for picking/notes; batch their visual hardware draws.
export class HardwareInstances {
  constructor(objects, scene) {
    const groups = new Map();
    for (const object of objects.filter((o) => o.userData.grp === 'Fasteners')) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      const key = `${object.geometry.uuid}:${materials.map((m) => m.uuid).join(',')}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(object);
      object.layers.set(1);
    }
    this.batches = [...groups.values()].map((objects) => {
      const mesh = new THREE.InstancedMesh(objects[0].geometry, objects[0].material, objects.length);
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.frustumCulled = false;
      scene.add(mesh);
      return { mesh, objects };
    });
    this.matrix = new THREE.Matrix4();
  }
  update(selected) {
    for (const { mesh, objects } of this.batches) {
      objects.forEach((object, index) => {
        object.layers.set(object === selected ? 0 : 1);
        object.updateMatrix();
        this.matrix.multiplyMatrices(object.parent.matrixWorld, object.matrix);
        if (!isVisible(object) || object === selected) this.matrix.makeScale(0,0,0);
        mesh.setMatrixAt(index, this.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
    }
  }
}

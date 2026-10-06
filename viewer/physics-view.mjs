import * as THREE from 'three';
import { FallSimulation } from './fall-physics.mjs';
import {BakedSimulation,trajectoryKey} from './baked-simulation.mjs';
import { WorkerSimulation } from './worker-simulation.mjs';
import { ConvexHull } from './vendor/ConvexHull.mjs';
import { mergeVertices } from './vendor/addons/utils/BufferGeometryUtils.js';

function metadata(object, key) {
  for (let current = object; current; current = current.parent) {
    if (current.userData[key] !== undefined) return current.userData[key];
  }
}

export class PhysicsView {
  constructor(pieces, {useWorker=false,trajectory=null,seed=null} = {}) {
    this.entries = pieces.map(({ object }) => {
      object.updateWorldMatrix(true, false);
      object.geometry.computeBoundingBox();
      const box = object.geometry.boundingBox;
      const centerLocal = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const scale = object.getWorldScale(new THREE.Vector3());
      const quaternion = object.getWorldQuaternion(new THREE.Quaternion());
      const center = object.localToWorld(centerLocal.clone());
      const entry = { object, centerLocal, scale,
        parentInverse: object.parent.matrixWorld.clone().invert(),
        parentRotation: object.parent.getWorldQuaternion(new THREE.Quaternion()).invert(),
        inverseWorld: object.matrixWorld.clone().invert(),
        scaledCenter: centerLocal.clone().multiply(scale) };
      const descriptor = { part:object.userData.part, center: center.toArray(), quaternion: quaternion.toArray(),
        halfExtents: size.multiply(scale).multiplyScalar(.5).toArray(),
        mass: Number(metadata(object, 'mass_kg')) || .1,
        hardware: object.userData.grp === 'Fasteners' };
      if (object.userData.part === 'Slide' || metadata(object, 'kind') === 'wood') {
        const attr = object.geometry.attributes.position;
        const points = Array.from({length:attr.count}, (_, i) =>
          new THREE.Vector3().fromBufferAttribute(attr, i).sub(centerLocal).multiply(scale));
        const hull = new ConvexHull().setFromPoints(points);
        const vertices = [], seen = new Set();
        for (const face of hull.faces) {
          let edge = face.edge;
          do {
            const point = edge.head().point;
            if (!seen.has(point)) { seen.add(point); vertices.push(point.toArray()); }
            edge = edge.next;
          } while (edge !== face.edge);
        }
        descriptor.vertices = vertices;
      }
      if (metadata(object, 'kind') === 'fabric') {
        entry.original = object.geometry;
        let geometry = object.geometry.index ? object.geometry.toNonIndexed() : object.geometry.clone();
        // Subdivide the existing fabric surface so it can bend between particles.
        for (let level = 0; level < 1; level++) {
          const attr = geometry.attributes.position, vertices = [];
          for (let i = 0; i < attr.count; i += 3) {
            const a = new THREE.Vector3().fromBufferAttribute(attr, i);
            const b = new THREE.Vector3().fromBufferAttribute(attr, i + 1);
            const c = new THREE.Vector3().fromBufferAttribute(attr, i + 2);
            const ab = a.clone().lerp(b, .5), bc = b.clone().lerp(c, .5), ca = c.clone().lerp(a, .5);
            for (const p of [a,ab,ca,ab,b,bc,ca,bc,c,ab,bc,ca]) vertices.push(...p.toArray());
          }
          geometry.dispose();
          geometry = new THREE.BufferGeometry();
          geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        }
        // Shared vertices allow normals to blend across cloth triangles. The
        // physical nodes and face contacts remain exactly the same.
        const indexed = mergeVertices(geometry, 1e-5);
        geometry.dispose();
        geometry = indexed;
        geometry.computeVertexNormals();
        object.geometry = geometry;
        const nodes = [], lookup = new Map(), edges = new Map();
        entry.nodeIndices = [];
        const attr = geometry.attributes.position;
        for (let i = 0; i < attr.count; i++) {
          const p = object.localToWorld(new THREE.Vector3().fromBufferAttribute(attr, i));
          const key = p.toArray().map((v) => v.toFixed(5)).join(',');
          if (!lookup.has(key)) { lookup.set(key, nodes.length); nodes.push(p.toArray()); }
          entry.nodeIndices.push(lookup.get(key));
        }
        const surface = Array.from(geometry.index.array, vertex => entry.nodeIndices[vertex]);
        for (let i = 0; i < surface.length; i += 3) {
          const [a,b,c] = surface.slice(i, i + 3);
          for (const [u,v] of [[a,b],[b,c],[c,a]]) {
            if (u !== v) edges.set([u,v].sort((x,y) => x-y).join(','), [u,v]);
          }
        }
        descriptor.points = nodes;
        descriptor.edges = [...edges.values()];
        descriptor.surface = surface;
      } else if (metadata(object, 'kind') === 'rope') {
        // Tubular ropes are monotone along their longest local axis. Bin their
        // existing vertices to obtain a flexible chain without adding rigid boxes.
        const lengths = box.getSize(new THREE.Vector3()).toArray();
        const axis = lengths.indexOf(Math.max(...lengths));
        descriptor.radius=Math.max(.002,Math.min(...descriptor.halfExtents.filter((_,i)=>i!==axis)));
        const min = box.min.toArray()[axis], span = Math.max(.001, lengths[axis]);
        const count = Math.max(4, Math.min(8, Math.ceil(span / .3)));
        const attr = object.geometry.attributes.position;
        const sums = Array.from({length:count}, () => new THREE.Vector3());
        const counts = Array(count).fill(0);
        const vertices = [], weights = [];
        for (let i = 0; i < attr.count; i++) {
          const local = new THREE.Vector3().fromBufferAttribute(attr, i);
          const weight = Math.max(0, Math.min(count - 1, (local.toArray()[axis] - min) / span * (count - 1)));
          const world = object.localToWorld(local);
          vertices.push(world); weights.push(weight);
          const bin = Math.round(weight);
          sums[bin].add(world); counts[bin]++;
        }
        for (let i = 0; i < count; i++) if (counts[i]) sums[i].divideScalar(counts[i]);
        for (let i = 0; i < count; i++) {
          if (counts[i]) continue;
          let lo = i - 1, hi = i + 1;
          while (lo >= 0 && !counts[lo]) lo--;
          while (hi < count && !counts[hi]) hi++;
          if (lo < 0) sums[i].copy(sums[hi]);
          else if (hi === count) sums[i].copy(sums[lo]);
          else sums[i].copy(sums[lo]).lerp(sums[hi], (i - lo) / (hi - lo));
        }
        entry.weights = weights;
        entry.tangents = [];
        entry.offsets = vertices.map((p,i)=> {
          const lo=Math.floor(weights[i]),hi=Math.min(count-1,lo+1);
          const tangent=sums[hi===lo?Math.max(0,lo-1):lo].clone().sub(sums[hi]).normalize().negate();
          entry.tangents.push(tangent);
          const offset=p.sub(sums[lo].clone().lerp(sums[hi],weights[i]-lo));
          offset.addScaledVector(tangent,-offset.dot(tangent));
          if(offset.length()>descriptor.radius)offset.setLength(descriptor.radius);
          return offset;
        });
        entry.original = object.geometry;
        object.geometry = object.geometry.clone();
        descriptor.points = sums.map((v) => v.toArray());
      }
      entry.descriptor = descriptor;
      if (entry.original) {
        object.geometry.boundingBox = null;
        object.geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 30);
      }
      return entry;
    });
    const descriptors=this.entries.map(entry=>entry.descriptor);
    const cached=trajectory && trajectory.header.key===trajectoryKey(descriptors);
    const Simulation = useWorker && typeof Worker !== 'undefined' ? WorkerSimulation : FallSimulation;
    this.simulation = cached ? new BakedSimulation(descriptors,trajectory) : new Simulation(descriptors,{seed});
    this.cached=!!cached;
    this.frame = 0;
    this.point = new THREE.Vector3();
    this.rotation = new THREE.Quaternion();
    this.tangent = new THREE.Vector3();
    this.ropeRotation = new THREE.Quaternion();
    this.ropeOffset = new THREE.Vector3();
  }
  step(dt) {
    const poses = this.simulation.step(dt);
    this.frame++;
    this.entries.forEach((entry, index) => {
      const { object } = entry;
      const pose = poses[index];
      if (pose.points) {
        const points = pose.points.map((p) => new THREE.Vector3(...p));
        const attr = object.geometry.attributes.position;
        if (entry.nodeIndices) entry.nodeIndices.forEach((node, i) => {
          const p = this.point.copy(points[node]).applyMatrix4(entry.inverseWorld);
          attr.setXYZ(i, p.x, p.y, p.z);
        });
        else entry.weights.forEach((weight, i) => {
          const lo = Math.floor(weight), hi = Math.min(points.length - 1, lo + 1);
          const a=hi===lo?Math.max(0,lo-1):lo;
          this.tangent.copy(points[hi]).sub(points[a]).normalize();
          this.ropeRotation.setFromUnitVectors(entry.tangents[i],this.tangent);
          this.ropeOffset.copy(entry.offsets[i]).applyQuaternion(this.ropeRotation);
          const p = this.point.copy(points[lo]).lerp(points[hi], weight - lo).add(this.ropeOffset);
          p.applyMatrix4(entry.inverseWorld);
          attr.setXYZ(i, p.x, p.y, p.z);
        });
        attr.needsUpdate = true;
        if (entry.nodeIndices && this.frame % 3 === 0) object.geometry.computeVertexNormals();
      } else {
        const rotation = this.rotation.fromArray(pose.quaternion);
        const centerOffset = this.point.copy(entry.scaledCenter).applyQuaternion(rotation);
        object.position.fromArray(pose.position).sub(centerOffset).applyMatrix4(entry.parentInverse);
        object.quaternion.copy(entry.parentRotation).multiply(rotation);
      }
    });
    return this.simulation.active;
  }
  reset() {
    for (const entry of this.entries) {
      if (entry.original) {
        entry.object.geometry.dispose();
        entry.object.geometry = entry.original;
      }
    }
    this.simulation.dispose();
  }
}

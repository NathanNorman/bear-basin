import {JoltWorld} from './jolt-world.mjs';
import {randomFromSeed} from './random.mjs';
import {Deformable} from './deformable.mjs';
const array=v=>[v.x,v.y,v.z];

// SI units; estimated masses and simplified envelopes are visual approximations.
export class FallSimulation {
  constructor(descriptors,{seed=null,timestep=1/60}={}) {
    this.timestep=timestep;this.seed=seed;this.engine='Jolt JS 1.1.0';
    const random=seed===null?null:randomFromSeed(seed);
    const nudge=()=>random?(random()-.5)*2:0;
    this.world=new JoltWorld(descriptors.filter(d=>!d.points).length);
    this.workerThreads=this.world.workerThreads;
    try {
      this.records=descriptors.map(d=> {
        if(d.points){
          const soft=new Deformable(d,random);
          const nodes=d.points.map((_,index)=> {
            const raw={translation:()=>soft.particlePosition(index),rotation:()=>({x:0,y:0,z:0,w:1}),
              linvel:()=>soft.particleVelocity(index),isSleeping:()=>soft.isSleeping()};
            return {raw,get position(){const v=raw.translation();return {...v,toArray:()=>array(v)};}};
          });
          return {nodes,soft};
        }
        const body=this.world.createBody(d);
        const half=d.halfExtents.map(n=>Math.max(.003,n));
        const slender=Math.max(...half)/Math.min(...half)>6;
        if(slender||random)body.raw.setAngvel({x:(slender?.65:0)+nudge()*.6,y:(slender?.08:0)+nudge()*.3,z:(slender?.5:0)+nudge()*.6});
        if(random)body.raw.setLinvel({x:nudge()*.2,y:0,z:nudge()*.2});
        return {body};
      });
    }catch(error){this.world.free();throw error;}
    this.elapsed=0;this.accumulator=0;
  }
  step(seconds){
    const dt=Math.min(.05,Math.max(0,seconds));this.accumulator+=dt;
    while(this.accumulator>=this.timestep-1e-9){
      for(let substep=0;substep<2;substep++)this.world.step(this.timestep/2);
      const rigidActive=this.records.some(r=>r.body&&!r.body.raw.isSleeping());
      for(const record of this.records)record.soft?.step(this.timestep,this.world,rigidActive);
      this.accumulator-=this.timestep;
    }
    this.elapsed+=dt;
    return this.records.map(r=>r.nodes?{points:r.nodes.map(b=>array(b.raw.translation()))}
      :{position:array(r.body.raw.translation()),quaternion:r.body.quaternion.toArray()});
  }
  get active(){return this.elapsed<.1||this.records.some(r=>(r.nodes||[r.body]).some(b=>!b.raw.isSleeping()));}
  dispose(){this.world.free();}
}

import RAPIER from './vendor/rapier.mjs';
await RAPIER.init();
const array = (v) => [v.x, v.y, v.z];
const groups = (member, mask) => ((member << 16) | mask) >>> 0;

// SI units; estimated masses and simplified envelopes remain visual approximations.
export class FallSimulation {
  constructor(descriptors) {
    this.world = new RAPIER.World({x:0,y:-9.81,z:0});
    this.world.integrationParameters.numSolverIterations = 8;
    this.world.integrationParameters.numInternalPgsIterations = 1;
    this.world.integrationParameters.contact_natural_frequency = 30;
    this.world.integrationParameters.softBodiesContactStiffening = 1;
    this.world.integrationParameters.softBodiesMaxExtraSubsteps = 0;
    this.world.integrationParameters.maxCcdSubsteps = 4;
    this.world.integrationParameters.normalizedAllowedLinearError = .0001;
    this.world.createCollider(RAPIER.ColliderDesc.cuboid(100,50,100)
      .setTranslation(0,-50,0).setFriction(.55).setRestitution(.02)
      .setCollisionGroups(groups(1,15)));
    this.records = descriptors.map((d) => {
      if (d.points) {
        const edges = d.edges || d.points.slice(1).map((_,i)=>[i,i+1]);
        const material = RAPIER.SoftBodyMaterial.uniform(60, 2);
        material.deformationDamping = 20;
        const desc = new RAPIER.SoftBodyDesc(d.points.flat()).setEdges(edges.flat())
          .setMaterial(material).setMass(d.mass).setParticleRadius(.012)
          // Decoration receives contact forces without acting as a rigid support for timber.
          .setDominanceGroup(-1).setLinearDamping(d.surface ? 3 : .8).setCanSleep(true).setShapeMatching(false).setTensionOnly()
          .setSurfaceCollider(RAPIER.ColliderDesc.ball(.012).setFriction(.8)
            .setRestitution(0).setCollisionGroups(groups(4,3)));
        if (d.surface) desc.setSurface(d.surface);
        else desc.setWire(edges.flat()).setTensionOnly();
        const soft = this.world.createSoftBody(desc);
        const nodes = d.points.map((p,index) => {
          soft.setParticleVelocity(index,{x:Math.sin(index*1.7+p[0])*.025,y:0,z:Math.cos(index*1.3+p[2])*.025});
          const raw = {translation:()=>soft.particlePosition(index),rotation:()=>({x:0,y:0,z:0,w:1}),
            linvel:()=>soft.particleVelocity(index),isSleeping:()=>soft.isSleeping()};
          return {raw,get position(){const v=raw.translation();return {...v,toArray:()=>array(v)};},
            get quaternion(){return {toArray:()=>[0,0,0,1]};}};
        });
        return {nodes,soft};
      }
      const halfExtents = d.halfExtents.map((n)=>Math.max(.003,n));
      const shape = d.vertices ? RAPIER.ColliderDesc.convexHull(new Float32Array(d.vertices.flat()))
        : RAPIER.ColliderDesc.cuboid(...halfExtents);
      const body = this.createBody(d.center,d.quaternion,shape,d.mass,d.hardware?8:2,d.hardware?3:15,
        {halfExtents,vertices:d.vertices});
      // The suspension animation releases rigid pieces with no angular motion.
      // A slight initial tumble prevents perfectly aligned narrow rods from
      // landing on their flat ends and remaining artificially balanced.
      const slender = Math.max(...halfExtents) / Math.min(...halfExtents) > 6;
      if (slender) body.raw.setAngvel({x:.65,y:.08,z:.5},true);
      return {body};
    });
    this.elapsed = 0;
    this.accumulator = 0;
  }
  createBody(p,q,shape,mass,member,mask,envelope) {
    const desc = RAPIER.RigidBodyDesc.dynamic().setTranslation(...p)
      .setLinearDamping(member === 4 ? 3 : .5).setAngularDamping(member === 4 ? 3 : 1).setCcdEnabled(true)
      .setSoftCcdPrediction(.02).setCanSleep(true).setAdditionalSolverIterations(mass > .5 ? 4 : 0);
    if(q) desc.setRotation({x:q[0],y:q[1],z:q[2],w:q[3]});
    const raw = this.world.createRigidBody(desc);
    this.world.createCollider(shape.setMass(Math.max(.002,mass||.1)).setFriction(.55)
      .setRestitution(.02).setContactSkin(member === 8 ? .003 : .001).setCollisionGroups(groups(member,mask)),raw);
    const body = {raw,envelope,aabb:{lowerBound:{y:0}},
      get position(){const v=raw.translation();return {...v,toArray:()=>array(v)};},
      get quaternion(){const v=raw.rotation();return {...v,toArray:()=>[v.x,v.y,v.z,v.w]};},
      updateAABB(){
        const p=raw.translation(),q=raw.rotation();
        const row=[2*(q.x*q.y+q.z*q.w),1-2*(q.x*q.x+q.z*q.z),2*(q.y*q.z-q.x*q.w)];
        const lower=envelope.radius?-envelope.radius:envelope.vertices
          ?Math.min(...envelope.vertices.map(v=>v.reduce((s,n,i)=>s+n*row[i],0)))
          :-envelope.halfExtents.reduce((s,n,i)=>s+n*Math.abs(row[i]),0);
        body.aabb.lowerBound.y=p.y+lower;
      }};
    return body;
  }
  step(seconds) {
    const dt=Math.min(.05,Math.max(0,seconds));
    this.accumulator+=dt;
    while(this.accumulator>=1/120-1e-9){
      this.world.timestep=1/120;
      this.world.step();
      this.accumulator-=1/120;
    }
    this.elapsed+=dt;
    return this.records.map(r=>r.nodes?{points:r.nodes.map(b=>array(b.raw.translation()))}
      :{position:array(r.body.raw.translation()),quaternion:r.body.quaternion.toArray()});
  }
  get active(){return this.elapsed<.1||this.records.some(r=>(r.nodes||[r.body]).some(b=>!b.raw.isSleeping()));}
  dispose(){this.world.free();}
}

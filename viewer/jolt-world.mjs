const threaded=!!(globalThis.crossOriginIsolated&&globalThis.WorkerGlobalScope)||!!globalThis.process?.env?.JOLT_THREADS;
const {default:initialize}=await import(threaded?'./vendor/jolt-physics.multithread.wasm-compat.js':'./vendor/jolt.mjs');
import {exactBox} from './collision-shapes.mjs';

const initializationHold=threaded&&globalThis.process?.versions?.node?setInterval(()=>{},1000):null;
let J;
try{J=await initialize();}finally{if(initializationHold)clearInterval(initializationHold);}
const vector=v=>({x:v.GetX(),y:v.GetY(),z:v.GetZ()});
const quaternion=q=>({...vector(q),w:q.GetW()});

// One native world: timber, plastic and hardware exchange contact forces.
// Textiles query timber through the same broad phase, without force feedback.
export class JoltWorld {
  constructor(bodyCount=2048) {
    const settings=new J.JoltSettings();
    settings.mMaxWorkerThreads=threaded?3:0;
    settings.mMaxBodies=Math.max(64,2**Math.ceil(Math.log2(bodyCount+1)));
    settings.mMaxBodyPairs=Math.max(1024,settings.mMaxBodies*32);
    settings.mMaxContactConstraints=Math.max(1024,settings.mMaxBodies*4);
    const pairs=new J.ObjectLayerPairFilterTable(4);
    for(const [a,b] of [[0,1],[0,2],[1,1],[1,2],[1,3]])pairs.EnableCollision(a,b);
    const broad=new J.BroadPhaseLayerInterfaceTable(4,2);
    const fixed=new J.BroadPhaseLayer(0),moving=new J.BroadPhaseLayer(1);
    for(let i=0;i<4;i++)broad.MapObjectToBroadPhaseLayer(i,i===0?fixed:moving);
    J.destroy(fixed);J.destroy(moving);
    settings.mObjectLayerPairFilter=pairs;settings.mBroadPhaseLayerInterface=broad;
    settings.mObjectVsBroadPhaseLayerFilter=new J.ObjectVsBroadPhaseLayerFilterTable(broad,2,pairs,4);
    this.workerThreads=threaded?3:0;
    this.interface=new J.JoltInterface(settings);
    J.destroy(settings);
    this.system=this.interface.GetPhysicsSystem();
    this.bodies=this.system.GetBodyInterface();
    const gravity=new J.Vec3(0,-9.81,0);this.system.SetGravity(gravity);J.destroy(gravity);
    const physics=new J.PhysicsSettings();
    physics.mNumVelocitySteps=8;physics.mNumPositionSteps=4;
    physics.mPenetrationSlop=.0002;physics.mBaumgarte=.4;
    physics.mLinearCastMaxPenetration=.01;physics.mLinearCastThreshold=.05;
    physics.mPointVelocitySleepThreshold=.025;physics.mTimeBeforeSleep=.75;
    physics.mBodyPairCacheMaxDeltaPositionSq=.000001;
    physics.mDeterministicSimulation=true;
    this.system.SetPhysicsSettings(physics);J.destroy(physics);
    this.owned=[];this.records=[];this.byId=new Map();this.spheres=new Map();
    const own=o=>{this.owned.push(o);return o;};
    this.position=own(new J.RVec3(0,0,0));
    this.direction=own(new J.Vec3(0,0,0));
    this.one=own(new J.Vec3(1,1,1));this.zero=own(new J.RVec3(0,0,0));
    this.transform=own(new J.RMat44());
    for(const [name,values] of [['SetAxisX',[1,0,0]],['SetAxisY',[0,1,0]],['SetAxisZ',[0,0,1]]]){
      const axis=new J.Vec3(...values);this.transform[name](axis);J.destroy(axis);
    }
    this.transform.SetTranslation(this.zero);
    this.broadFilter=own(new J.DefaultBroadPhaseLayerFilter(this.interface.GetObjectVsBroadPhaseLayerFilter(),3));
    this.objectFilter=own(new J.DefaultObjectLayerFilter(this.interface.GetObjectLayerPairFilter(),3));
    this.bodyFilter=own(new J.BodyFilter());this.shapeFilter=own(new J.ShapeFilter());
    this.castSettings=own(new J.ShapeCastSettings());this.castSettings.mReturnDeepestPoint=true;
    this.contactSettings=own(new J.CollideShapeSettings());
    this.castCollector=own(new J.CastShapeClosestHitCollisionCollector());
    this.contactCollector=own(new J.CollideShapeAllHitCollisionCollector());
    this.createBody({center:[0,-50,0],quaternion:[0,0,0,1],halfExtents:[100,50,100]},true);
  }
  createBody(d,fixed=false) {
    const box=exactBox(d.vertices),half=box?.half||d.halfExtents.map(n=>Math.max(.003,n));
    let shapeSettings;
    if(box||!d.vertices){
      const size=new J.Vec3(...half);
      shapeSettings=new J.BoxShapeSettings(size,Math.min(.002,Math.min(...half)*.2));
      J.destroy(size);
      if(box){
        const p=new J.Vec3(0,0,0),q=new J.Quat(box.quaternion.x,box.quaternion.y,box.quaternion.z,box.quaternion.w);
        shapeSettings=new J.RotatedTranslatedShapeSettings(p,q,shapeSettings);
        J.destroy(p);J.destroy(q);
      }
    }else{
      shapeSettings=new J.ConvexHullShapeSettings();
      shapeSettings.mMaxConvexRadius=.001;shapeSettings.mHullTolerance=.00001;
      for(const point of d.vertices){const p=new J.Vec3(...point);shapeSettings.mPoints.push_back(p);J.destroy(p);}
    }
    const result=shapeSettings.Create();
    if(result.HasError()){const message=result.GetError().c_str();J.destroy(shapeSettings);throw new Error(`Collider ${d.part}: ${message}`);}
    const shape=result.Get();shape.AddRef();result.Clear();J.destroy(shapeSettings);
    const position=new J.RVec3(...d.center),rotation=new J.Quat(...d.quaternion);
    const creation=new J.BodyCreationSettings(shape,position,rotation,fixed?J.EMotionType_Static:J.EMotionType_Dynamic,fixed?0:d.hardware?2:1);
    shape.Release();J.destroy(position);J.destroy(rotation);
    creation.mFriction=.55;creation.mRestitution=.02;
    if(!fixed){
      creation.mMotionQuality=J.EMotionQuality_LinearCast;
      if(d.hardware){creation.mNumVelocityStepsOverride=16;creation.mNumPositionStepsOverride=8;}
      creation.mLinearDamping=.5;creation.mAngularDamping=1;
      creation.mOverrideMassProperties=J.EOverrideMassProperties_CalculateInertia;
      creation.mMassPropertiesOverride.mMass=Math.max(.002,d.mass||.1);
    }
    const native=this.bodies.CreateBody(creation);J.destroy(creation);
    if(!native)throw new Error('Jolt body capacity exceeded');
    const id=native.GetID();this.bodies.AddBody(id,fixed?J.EActivation_DontActivate:J.EActivation_Activate);
    this.records.push(native);this.byId.set(id.GetIndexAndSequenceNumber(),native);
    const raw={translation:()=>vector(native.GetPosition()),rotation:()=>quaternion(native.GetRotation()),
      linvel:()=>vector(native.GetLinearVelocity()),isSleeping:()=>!native.IsActive(),
      setAngvel:v=>{this.direction.Set(v.x,v.y,v.z);native.SetAngularVelocity(this.direction);},
      setLinvel:v=>{this.direction.Set(v.x,v.y,v.z);native.SetLinearVelocity(this.direction);}};
    const array=v=>[v.x,v.y,v.z];
    const body={raw,aabb:{lowerBound:{y:0}},
      get position(){const p=raw.translation();return {...p,toArray:()=>array(p)};},
      get quaternion(){const q=raw.rotation();return {...q,toArray:()=>[q.x,q.y,q.z,q.w]};},
      updateAABB(){const p=raw.translation(),q=raw.rotation();
        const row=[2*(q.x*q.y+q.z*q.w),1-2*(q.x*q.x+q.z*q.z),2*(q.y*q.z-q.x*q.w)];
        const lower=d.vertices?Math.min(...d.vertices.map(v=>v.reduce((s,n,i)=>s+n*row[i],0)))
          :-half.reduce((s,n,i)=>s+n*Math.abs(row[i]),0);
        body.aabb.lowerBound.y=p.y+lower;
      }};
    return body;
  }
  step(dt){this.interface.Step(dt,1);}
  sphere(radius){if(!this.spheres.has(radius)){const shape=new J.SphereShape(radius);shape.AddRef();this.spheres.set(radius,shape);}return this.spheres.get(radius);}
  at(point){this.position.Set(point.x,point.y,point.z);this.transform.SetTranslation(this.position);}
  normal(hit){const n=vector(hit.mPenetrationAxis),length=Math.hypot(n.x,n.y,n.z)||1;return {x:-n.x/length,y:-n.y/length,z:-n.z/length};}
  sweepSphere(point,delta,radius){
    this.at(point);this.direction.Set(delta.x,delta.y,delta.z);
    const cast=new J.RShapeCast(this.sphere(radius),this.one,this.transform,this.direction);
    const collector=this.castCollector;collector.Reset();
    this.system.GetNarrowPhaseQuery().CastShape(cast,this.castSettings,this.zero,collector,this.broadFilter,this.objectFilter,this.bodyFilter,this.shapeFilter);
    J.destroy(cast);
    if(!collector.HadHit())return null;
    const hit=collector.mHit;return {time_of_impact:hit.mFraction,normal1:this.normal(hit)};
  }
  sphereContacts(point,radius){
    this.at(point);const collector=this.contactCollector;collector.Reset();
    this.system.GetNarrowPhaseQuery().CollideShape(this.sphere(radius),this.one,this.transform,this.contactSettings,this.zero,collector,this.broadFilter,this.objectFilter,this.bodyFilter,this.shapeFilter);
    const contacts=[];
    for(let i=0;i<collector.mHits.size();i++){
      const hit=collector.mHits.at(i),body=this.byId.get(hit.mBodyID2.GetIndexAndSequenceNumber());
      contacts.push({normal:this.normal(hit),depth:hit.mPenetrationDepth,moving:body?.IsActive()||false});
    }
    return contacts;
  }
  free(){
    if(this.disposed)return;this.disposed=true;
    for(const native of this.records){const id=native.GetID();this.bodies.RemoveBody(id);this.bodies.DestroyBody(id);}
    for(const object of this.owned.reverse())J.destroy(object);
    for(const shape of this.spheres.values())shape.Release();
    J.destroy(this.interface);
  }
}

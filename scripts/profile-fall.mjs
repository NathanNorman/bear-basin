import {loadReleasedModel} from './fall-fixture.mjs';
import {PhysicsView} from '../viewer/physics-view.mjs';
import {FallSimulation} from '../viewer/fall-physics.mjs';

const mode=process.argv[2]||'baseline';
const seed=Number(process.argv[3]||42);
if(!['baseline','rigid-only','structure-only'].includes(mode))throw new Error(`Unknown mode: ${mode}`);
const {pieces}=await loadReleasedModel();
const view=new PhysicsView(pieces);
let descriptors=view.entries.map(e=>e.descriptor);
view.reset();
if(mode==='rigid-only')descriptors=descriptors.filter(d=>!d.points);
if(mode==='structure-only')descriptors=descriptors.filter(d=>!d.hardware&&!d.points);
const start=performance.now();
const sim=new FallSimulation(descriptors,{seed});
const initMs=performance.now()-start;
const phases=[];
try {
  for(let second=0;second<12;second++){
    const times=[];
    for(let tick=0;tick<60;tick++){
      const t=performance.now();sim.step(1/60);times.push(performance.now()-t);
    }
    times.sort((a,b)=>a-b);
    phases.push({second:second+1,meanMs:times.reduce((a,b)=>a+b)/60,p95Ms:times[57],maxMs:times[59]});
  }
  console.log(JSON.stringify({engine:sim.engine,workerThreads:sim.workerThreads,mode,seed,initMs,
    rigidBodies:descriptors.filter(d=>!d.points).length,
    flexibleParts:descriptors.filter(d=>d.points).length,
    particles:descriptors.reduce((sum,d)=>sum+(d.points?.length||0),0),phases,active:sim.active,
    awake:sim.records.flatMap((r,i)=>(r.nodes||[r.body]).some(b=>!b.raw.isSleeping())?[descriptors[i].part]:[])}));
}finally{sim.dispose();}

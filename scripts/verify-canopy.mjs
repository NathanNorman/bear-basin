import assert from 'node:assert/strict';
import {loadReleasedModel} from './fall-fixture.mjs';
import {PhysicsView} from '../viewer/physics-view.mjs';
const seed=Number(process.argv[2]||42);
const {pieces}=await loadReleasedModel();
const view=new PhysicsView(pieces,{seed});
try {
  for(let i=0;i<2400;i++)view.step(1/120);
  assert.equal(view.simulation.active,false,'the full pile must settle');
  const index=view.entries.findIndex(entry=>entry.descriptor.part==='Tarp');
  assert.ok(index>=0,'the actual canopy must exist');
  const soft=view.simulation.records[index].soft;
  let maxPenetration=0,contacts=0;
  for(const face of soft.faces){
    for(const contact of view.simulation.world.triangleContacts(...face.map(i=>soft.particlePosition(i)),soft.radius)){
      maxPenetration=Math.max(maxPenetration,contact.depth);contacts++;
    }
  }
  assert.ok(maxPenetration<.003,`canopy face penetrates timber by ${maxPenetration} m`);
  const rest=soft.particlePositions().slice();
  for(let i=0;i<600;i++)view.step(1/120);
  assert.deepEqual(soft.particlePositions(),rest,'supported canopy must remain still');
  console.log(JSON.stringify({seed,faces:soft.faces.length,contacts,maxPenetration,settled:true,lateDisplacement:0}));
}finally{view.reset();}

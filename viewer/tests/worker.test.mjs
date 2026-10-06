import test from 'node:test';
import assert from 'node:assert/strict';
import { WorkerSimulation } from '../worker-simulation.mjs';

test('worker starts its autonomous clock once and finishes interpolation without restarting a sleeping world', () => {
  const original=globalThis.Worker;
  class FakeWorker {
    messages=[];
    postMessage(data){this.messages.push(data);}
    terminate(){this.terminated=true;}
    receive(data){this.onmessage({data});}
  }
  globalThis.Worker=FakeWorker;
  try {
    const sim=new WorkerSimulation([{center:[0,2,0],quaternion:[0,0,0,1]}]);
    sim.step(1/60);
    assert.equal(sim.worker.messages.length,1,'wait for initialized worker');
    sim.worker.receive({type:'ready'});
    sim.step(1/60);
    sim.step(1/60);
    assert.equal(sim.worker.messages.length,2,'only one start is sent; the worker owns simulation timing');
    sim.worker.receive({type:'poses',poses:[{position:[0,.2,0],quaternion:[0,0,0,-1]}],elapsed:10,wallSeconds:10,workerMs:2,active:false});
    assert.equal(sim.lagMs,0);
    assert.equal(sim.workerMs,2);
    assert.equal(sim.updates,1);
    assert.equal(sim.worker.messages[1].type,'start');
    for(let i=0;i<30;i++)sim.step(1/60);
    assert.equal(sim.worker.messages.length,2,'do not restart a settled simulation while blending');
    assert.equal(sim.active,false);
    assert.ok(Math.abs(sim.poses[0].position[1]-.2)<1e-12);
    assert.ok(Math.abs(sim.poses[0].quaternion[3])===1);
    sim.dispose();
    assert.equal(sim.worker.terminated,true);
  } finally {globalThis.Worker=original;}
});

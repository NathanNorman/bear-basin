let simulation,descriptors,running=false,timer,startTime,lastTime,pendingTime=0;
const sendError=error=>{running=false;clearTimeout(timer);self.postMessage({type:'error',message:error.message});};
function tick() {
  if(!running)return;
  try {
    const now=performance.now();
    // Preserve short scheduling stalls and catch up in bounded fixed-step batches.
    pendingTime=Math.min(.25,pendingTime+(now-lastTime)/1000);
    const seconds=Math.min(.05,pendingTime);pendingTime-=seconds;
    lastTime=now;
    const begin=performance.now();
    const poses=simulation.step(seconds);
    const workerMs=performance.now()-begin;
    const active=simulation.active;
    const wallSeconds=(performance.now()-startTime)/1000;
    self.postMessage({type:'poses',poses,elapsed:simulation.elapsed,active,workerMs,wallSeconds,
      awake:simulation.records.flatMap((r,i)=>r.soft ? (!r.soft.isSleeping()?[descriptors[i].part]:[]) :
        (!r.body.raw.isSleeping()?[descriptors[i].part]:[]))});
    if(!active){running=false;return;}
    // Schedule against the deadline, rather than waiting a full tick after solving.
    timer=setTimeout(tick,Math.max(0,1000/60-(performance.now()-now)));
  } catch(error){sendError(error);}
}
self.onmessage=async({data})=> {
  try {
    if(data.type==='init') {
      const {FallSimulation}=await import('./fall-physics.mjs');
      descriptors=data.descriptors;
      simulation=new FallSimulation(descriptors,data.options);
      self.postMessage({type:'ready',engine:simulation.engine,workerThreads:simulation.workerThreads});
    } else if(data.type==='start' && !running) {
      running=true;pendingTime=0;startTime=lastTime=performance.now();
      timer=setTimeout(tick,1000/60);
    }
  } catch(error){sendError(error);}
};

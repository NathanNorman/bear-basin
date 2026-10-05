let simulation;
self.onmessage = async ({data}) => {
  try {
    if (data.type === 'init') {
      const {FallSimulation} = await import('./fall-physics.mjs');
      simulation = new FallSimulation(data.descriptors);
      simulation.descriptors=data.descriptors;
      self.postMessage({type:'ready'});
    } else if (data.type === 'step') {
      self.postMessage({type:'poses', poses:simulation.step(data.seconds),
        elapsed:simulation.elapsed, active:simulation.active,
        awake:simulation.records.flatMap((r,i)=>(r.nodes||[r.body]).some(b=>!b.raw.isSleeping()) ? [simulation.descriptors[i].part] : [])});
    }
  } catch (error) {
    self.postMessage({type:'error', message:error.message});
  }
};

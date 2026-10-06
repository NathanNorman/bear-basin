// The worker advances against its own clock; rendering interpolates its snapshots.
export class WorkerSimulation {
  constructor(descriptors,options={}) {
    this.elapsed=0;
    this.active=true;
    this.ready=false;
    this.started=false;
    this.alpha=1;
    this.interval=1/60;
    this.updates=0;
    this.costs=[];
    this.poses=descriptors.map(d=>d.points?{points:d.points.map(p=>[...p])}:
      {position:[...d.center],quaternion:[...d.quaternion]});
    this.worker=new Worker(new URL('./physics-worker.mjs',import.meta.url),{type:'module'});
    this.worker.onmessage=({data})=> {
      if(data.type==='error'){this.error=new Error(data.message);return;}
      if(data.type==='ready'){this.ready=true;this.engine=data.engine;this.workerThreads=data.workerThreads;return;}
      if(data.type!=='poses')return;
      this.from=this.target||this.poses.map(p=>p.points?{points:p.points.map(v=>[...v])}:{position:[...p.position],quaternion:[...p.quaternion]});
      this.target=data.poses;
      this.interval=Math.max(1/60,Math.min(.05,data.elapsed-this.elapsed));
      this.alpha=0;
      this.elapsed=data.elapsed;
      this.finished=!data.active;
      this.awake=data.awake;
      this.workerMs=data.workerMs;
      this.costs.push(data.workerMs);
      this.wallSeconds=data.wallSeconds;
      this.lagMs=Math.max(0,(this.wallSeconds-this.elapsed)*1000);
      this.updates++;
    };
    this.worker.onerror=event=>{this.error=new Error(event.message);};
    this.worker.postMessage({type:'init',descriptors,options});
  }
  step(dt) {
    if(this.error)throw this.error;
    if(this.ready&&!this.started){this.started=true;this.worker.postMessage({type:'start'});}
    if(this.target) {
      this.alpha=Math.min(1,this.alpha+Math.max(0,dt)/this.interval);
      const a=this.alpha;
      this.poses.forEach((pose,i)=> {
        const from=this.from[i],to=this.target[i];
        if(pose.points)pose.points.forEach((p,j)=>p.forEach((_,k)=>p[k]=from.points[j][k]+a*(to.points[j][k]-from.points[j][k])));
        else {
          pose.position.forEach((_,k)=>pose.position[k]=from.position[k]+a*(to.position[k]-from.position[k]));
          const sign=from.quaternion.reduce((sum,v,k)=>sum+v*to.quaternion[k],0)<0?-1:1;
          pose.quaternion.forEach((_,k)=>pose.quaternion[k]=from.quaternion[k]+a*(sign*to.quaternion[k]-from.quaternion[k]));
          const length=Math.hypot(...pose.quaternion);
          pose.quaternion.forEach((_,k)=>pose.quaternion[k]/=length);
        }
      });
    }
    this.active=!this.finished||this.alpha<1;
    return this.poses;
  }
  dispose(){this.worker.terminate();}
}

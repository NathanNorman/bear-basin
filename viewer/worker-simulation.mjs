// Keep the contact solver off the rendering thread. Only one update is in flight.
export class WorkerSimulation {
  constructor(descriptors) {
    this.elapsed = 0;
    this.active = true;
    this.pending = 0;
    this.busy = true;
    this.alpha = 1;
    this.interval = 1/60;
    this.receivedAt = performance.now();
    this.poses = descriptors.map(d => d.points ? {points:d.points.map(p=>[...p])} :
      {position:[...d.center],quaternion:[...d.quaternion]});
    this.worker = new Worker(new URL('./physics-worker.mjs',import.meta.url),{type:'module'});
    this.worker.onmessage = ({data}) => {
      if(data.type === 'error') {this.error = new Error(data.message); this.busy = false; return;}
      if(data.type === 'poses') {
        this.from = this.poses.map(p=>p.points ? {points:p.points.map(v=>[...v])} :
          {position:[...p.position],quaternion:[...p.quaternion]});
        this.target = data.poses;
        const now=performance.now();
        this.interval=Math.max(1/60,Math.min(.1,(now-this.receivedAt)/1000));
        this.receivedAt=now;
        this.alpha=0;
        this.elapsed = data.elapsed;
        this.finished = !data.active;
        this.awake = data.awake;
      }
      this.busy = false;
    };
    this.worker.onerror = event => {this.error = new Error(event.message); this.busy = false;};
    this.worker.postMessage({type:'init',descriptors});
  }
  step(dt) {
    if(this.error) throw this.error;
    this.pending = Math.min(.1,this.pending + Math.max(0,dt));
    if(!this.busy && !this.finished && this.active && this.pending >= 1/60) {
      const seconds = Math.min(.05,this.pending);
      this.pending -= seconds;
      this.busy = true;
      this.worker.postMessage({type:'step',seconds});
    }
    if(this.target) {
      this.alpha=Math.min(1,this.alpha+dt/this.interval);
      this.poses.forEach((pose,i)=> {
        const from=this.from[i],to=this.target[i],a=this.alpha;
        if(pose.points) pose.points.forEach((p,j)=>p.forEach((_,k)=>p[k]=from.points[j][k]+a*(to.points[j][k]-from.points[j][k])));
        else {
          pose.position.forEach((_,k)=>pose.position[k]=from.position[k]+a*(to.position[k]-from.position[k]));
          const sign=from.quaternion.reduce((sum,v,k)=>sum+v*to.quaternion[k],0)<0?-1:1;
          pose.quaternion.forEach((_,k)=>pose.quaternion[k]=from.quaternion[k]+a*(sign*to.quaternion[k]-from.quaternion[k]));
          const length=Math.hypot(...pose.quaternion);
          pose.quaternion.forEach((_,k)=>pose.quaternion[k]/=length);
        }
      });
    }
    this.active = !this.finished || this.alpha < 1;
    return this.poses;
  }
  dispose() {this.worker.terminate();}
}

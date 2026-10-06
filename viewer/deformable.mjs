// XPBD tension constraints: Macklin, Muller and Chentanez (2016).
// Contacts are unilateral position constraints; velocities are reconstructed
// after solving, then receive Coulomb friction. No animation targets or timers
// prescribe the resting pose.
export class Deformable {
  constructor(descriptor,random) {
    this.positions=Float64Array.from(descriptor.points.flat());
    this.previous=this.positions.slice();
    this.velocities=new Float64Array(this.positions.length);
    this.normals=new Float64Array(this.positions.length);
    this.radius=descriptor.radius||.004;
    this.inverseMass=descriptor.points.length/descriptor.mass;
    this.drag=descriptor.surface?1.8:.8;
    this.compliance=descriptor.surface?2e-6:1e-7;
    this.faces=[];
    for(let i=0;i<(descriptor.surface?.length||0);i+=3)this.faces.push(descriptor.surface.slice(i,i+3));
    this.edges=(descriptor.edges||descriptor.points.slice(1).map((_,i)=>[i,i+1])).map(([a,b])=> {
      const i=a*3,j=b*3,p=this.positions;
      return {i,j,length:Math.hypot(p[j]-p[i],p[j+1]-p[i+1],p[j+2]-p[i+2]),lambda:0};
    });
    for(let i=0;i<this.velocities.length;i+=3){
      this.velocities[i]=(random?random()-.5:Math.sin(i*1.7))*.12;
      this.velocities[i+2]=(random?random()-.5:Math.cos(i*1.3))*.12;
    }
    this.sleeping=false;
    this.quietTime=0;
  }
  isSleeping(){return this.sleeping;}
  particlePosition(index){const i=index*3,p=this.positions;return {x:p[i],y:p[i+1],z:p[i+2]};}
  particleVelocity(index){const i=index*3,v=this.velocities;return {x:v[i],y:v[i+1],z:v[i+2]};}
  particlePositions(){return this.positions;}
  particleVelocities(){return this.velocities;}
  contact(world,i) {
    const p=this.positions,n=this.normals,r=this.radius;
    if(p[i+1]<r){p[i+1]=r;n[i]=0;n[i+1]=1;n[i+2]=0;}
    const point={x:p[i],y:p[i+1],z:p[i+2]};
    const start={...point};
    for(const contact of world.sphereContacts(point,r)){
      const normal=contact.normal;
      const moved=(point.x-start.x)*normal.x+(point.y-start.y)*normal.y+(point.z-start.z)*normal.z;
      const correction=contact.depth-moved;
      if(correction<-.0001)continue;
      if(correction>0){
        point.x+=normal.x*(correction+.0001);point.y+=normal.y*(correction+.0001);point.z+=normal.z*(correction+.0001);
        p[i]=point.x;p[i+1]=point.y;p[i+2]=point.z;
      }
      n[i]=normal.x;n[i+1]=normal.y;n[i+2]=normal.z;
    }
    if(p[i+1]<r){p[i+1]=r;n[i]=0;n[i+1]=1;n[i+2]=0;}
  }
  surfaceContacts(world,swept=false){
    const p=this.positions,n=this.normals;
    for(const face of this.faces){
      const [a,b,c]=face.map(index=>this.particlePosition(index));
      const u=[b.x-a.x,b.y-a.y,b.z-a.z],v=[c.x-a.x,c.y-a.y,c.z-a.z];
      const dot=(a,b)=>a.reduce((sum,x,i)=>sum+x*b[i],0);
      const uu=dot(u,u),uv=dot(u,v),vv=dot(v,v),denominator=uu*vv-uv*uv;
      if(denominator<1e-14)continue;
      const previous=swept?face.map(index=>{const i=index*3;return {x:this.previous[i],y:this.previous[i+1],z:this.previous[i+2]};}):null;
      for(const contact of world.triangleContacts(a,b,c,this.radius,previous)){
        if(contact.depth<=0)continue;
        const q=[contact.point.x-a.x,contact.point.y-a.y,contact.point.z-a.z];
        const bu=(vv*dot(q,u)-uv*dot(q,v))/denominator;
        const bv=(uu*dot(q,v)-uv*dot(q,u))/denominator;
        const weights=[1-bu-bv,bu,bv].map(w=>Math.max(0,Math.min(1,w)));
        const total=weights.reduce((s,w)=>s+w,0);
        if(total<1e-9)continue;
        for(let j=0;j<3;j++)weights[j]/=total;
        const squared=dot(weights,weights);
        const normal=contact.normal;
        // Account for earlier contacts on this face before applying another.
        const moved=face.reduce((sum,index,j)=>sum+weights[j]*((p[index*3]-[a,b,c][j].x)*normal.x+(p[index*3+1]-[a,b,c][j].y)*normal.y+(p[index*3+2]-[a,b,c][j].z)*normal.z),0);
        const depth=contact.depth-moved;
        if(depth<=0)continue;
        for(let j=0;j<3;j++){
          const i=face[j]*3,correction=(depth+.0001)*weights[j]/squared;
          p[i]+=normal.x*correction;p[i+1]+=normal.y*correction;p[i+2]+=normal.z*correction;
          if(weights[j]>1e-5){n[i]=normal.x;n[i+1]=normal.y;n[i+2]=normal.z;}
        }
      }
    }
  }
  step(dt,world,rigidActive) {
    if(this.sleeping){
      if(!rigidActive)return;
      for(let i=0;i<this.positions.length && this.sleeping;i+=3){
        if(world.sphereContacts(this.particlePosition(i/3),this.radius).some(contact=>contact.moving)){
          this.sleeping=false;this.quietTime=0;
        }
      }
      if(this.sleeping&&this.faces.some(face=>world.triangleContacts(...face.map(index=>this.particlePosition(index)),this.radius).some(contact=>contact.moving))){this.sleeping=false;this.quietTime=0;}
      if(this.sleeping)return;
    }
    const p=this.positions,v=this.velocities,old=this.previous,n=this.normals;
    old.set(p);n.fill(0);
    const damping=Math.exp(-this.drag*dt);
    for(let i=0;i<p.length;i+=3){
      v[i]*=damping;v[i+1]=(v[i+1]-9.81*dt)*damping;v[i+2]*=damping;
      const start={x:p[i],y:p[i+1],z:p[i+2]};
      const delta={x:v[i]*dt,y:v[i+1]*dt,z:v[i+2]*dt};
      const hit=world.sweepSphere(start,delta,this.radius);
      const t=hit && hit.time_of_impact>1e-6?Math.max(0,hit.time_of_impact-.001):1;
      p[i]+=delta.x*t;p[i+1]+=delta.y*t;p[i+2]+=delta.z*t;
      if(hit&&t<1){n[i]=hit.normal1.x;n[i+1]=hit.normal1.y;n[i+2]=hit.normal1.z;}
    }
    this.surfaceContacts(world,true);
    for(const edge of this.edges)edge.lambda=0;
    const alpha=this.compliance/(dt*dt),weight=this.inverseMass;
    for(let iteration=0;iteration<8;iteration++){
      for(const edge of this.edges){
        const {i,j}=edge;
        const x=p[j]-p[i],y=p[j+1]-p[i+1],z=p[j+2]-p[i+2],length=Math.hypot(x,y,z);
        if(length<1e-9)continue;
        const correction=(-(length-edge.length)-alpha*edge.lambda)/(2*weight+alpha);
        const next=Math.min(0,edge.lambda+correction),change=(next-edge.lambda)*weight/length;
        edge.lambda=next;
        p[i]-=x*change;p[i+1]-=y*change;p[i+2]-=z*change;
        p[j]+=x*change;p[j+1]+=y*change;p[j+2]+=z*change;
      }
      if(iteration===7)this.surfaceContacts(world);
      for(let i=0;i<p.length;i+=3)this.contact(world,i);
    }
    let maxSpeed=0,contacts=0;
    for(let i=0;i<p.length;i+=3){
      v[i]=(p[i]-old[i])/dt;v[i+1]=(p[i+1]-old[i+1])/dt;v[i+2]=(p[i+2]-old[i+2])/dt;
      if(n[i]||n[i+1]||n[i+2]){
        contacts++;
        const normal=v[i]*n[i]+v[i+1]*n[i+1]+v[i+2]*n[i+2];
        if(normal<0){v[i]-=normal*n[i];v[i+1]-=normal*n[i+1];v[i+2]-=normal*n[i+2];}
        const speed=Math.hypot(v[i],v[i+1],v[i+2]);
        const friction=Math.max(0,1-.65*9.81*dt/(speed||1));
        v[i]*=friction;v[i+1]*=friction;v[i+2]*=friction;
      }
      maxSpeed=Math.max(maxSpeed,Math.hypot(v[i],v[i+1],v[i+2]));
    }
    // Contact-supported low kinetic energy, sustained for 0.75 s, permits sleep.
    // An unsupported body, a moving neighbour or renewed motion resets it.
    this.maxSpeed=maxSpeed;
    this.contacts=contacts;
    this.quietTime=contacts && !rigidActive && maxSpeed<.025?this.quietTime+dt:0;
    if(this.quietTime>=.75){this.sleeping=true;v.fill(0);}
  }
}

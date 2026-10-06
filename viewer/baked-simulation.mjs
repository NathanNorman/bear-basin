export function trajectoryKey(descriptors) {
  const rounded = values => values?.flat().map(value=>Math.round(value*10000));
  const text=JSON.stringify(descriptors.map(d=>[d.part,Math.round(d.mass*10000),
    rounded(d.center),rounded(d.quaternion),rounded(d.halfExtents),rounded(d.vertices),rounded(d.points),d.edges,d.surface]));
  let hash=2166136261;
  for(let i=0;i<text.length;i++)hash=Math.imul(hash^text.charCodeAt(i),16777619)>>>0;
  return `${descriptors.length}:${hash.toString(16)}`;
}

export function decodeTrajectory(buffer) {
  const length=new DataView(buffer).getUint32(0,true);
  const header=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,4,length)));
  const offset=4+Math.ceil(length/4)*4;
  let values;
  if(header.encoding==='delta-i32') {
    const encoded=new Int32Array(buffer,offset),previous=new Int32Array(header.stride);
    values=new Float32Array(encoded.length);
    for(let i=0;i<encoded.length;i++)values[i]=(previous[i%header.stride]+=encoded[i])/header.scale;
  } else values=new Float32Array(buffer,offset);
  if(header.version!==1 || !header.nativeSleep || values.length!==header.frames*header.stride)
    throw new Error('Invalid physics trajectory');
  return {header,values};
}

export async function loadTrajectory() {
  try {
    const response=await fetch(new URL('./fall-trajectory.bin.gz',import.meta.url));
    if(!response.ok) return null;
    const stream=response.body.pipeThrough(new DecompressionStream('gzip'));
    const cache=decodeTrajectory(await new Response(stream).arrayBuffer());
    for(const [file,expected] of Object.entries(cache.header.sources || {})) {
      const source=await fetch(new URL(file,import.meta.url));
      const digest=await crypto.subtle.digest('SHA-256',await source.arrayBuffer());
      const actual=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
      if(actual!==expected)throw new Error('Physics source changed; regenerate the trajectory');
    }
    return cache;
  } catch(error) {
    console.warn('Cached physics unavailable; using the live solver.',error);
    return null;
  }
}

// Recorded frames end only after the physics solver reports a resting scene.
export class BakedSimulation {
  constructor(descriptors,cache) {
    this.cache=cache;
    this.elapsed=0;
    this.active=true;
    this.awake=[];
    this.poses=descriptors.map(d=>d.points?{points:d.points.map(p=>[...p])}:
      {position:[...d.center],quaternion:[...d.quaternion]});
  }
  step(dt) {
    const {header,values}=this.cache;
    this.elapsed=Math.min((header.frames-1)/header.fps,this.elapsed+Math.max(0,dt));
    const duration=(header.frames-1)/header.fps;
    const frame=this.elapsed>=duration?header.frames-1:this.elapsed*header.fps;
    const lo=Math.min(header.frames-1,Math.floor(frame)),hi=Math.min(header.frames-1,lo+1),alpha=frame-lo;
    let offset=0;
    const read=(component)=>values[lo*header.stride+component]*(1-alpha)+values[hi*header.stride+component]*alpha;
    this.poses.forEach(pose=> {
      if(pose.points)for(const point of pose.points)for(let j=0;j<3;j++)point[j]=read(offset++);
      else {
        for(let j=0;j<3;j++)pose.position[j]=read(offset++);
        const first=lo*header.stride+offset,second=hi*header.stride+offset;
        const sign=values[first]*values[second]+values[first+1]*values[second+1]+
          values[first+2]*values[second+2]+values[first+3]*values[second+3]<0?-1:1;
        for(let j=0;j<4;j++)pose.quaternion[j]=values[first+j]*(1-alpha)+sign*values[second+j]*alpha;
        const length=Math.hypot(...pose.quaternion);
        for(let j=0;j<4;j++)pose.quaternion[j]/=length;
        offset+=4;
      }
    });
    this.active=lo<header.frames-1;
    return this.poses;
  }
  dispose() {}
}

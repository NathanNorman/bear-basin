const dot=(a,b)=>a.reduce((sum,n,i)=>sum+n*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
export function exactBox(vertices) {
  if(vertices?.length!==8)return null;
  const edges=vertices.slice(1).map(p=>p.map((n,i)=>n-vertices[0][i])).map(e=> {
    const length=Math.hypot(...e);return e.map(n=>n/length);
  });
  for(let i=0;i<edges.length;i++)for(let j=i+1;j<edges.length;j++)for(let k=j+1;k<edges.length;k++){
    const axes=[edges[i],edges[j],edges[k]];
    if(Math.abs(dot(axes[0],axes[1]))>1e-5||Math.abs(dot(axes[0],axes[2]))>1e-5||Math.abs(dot(axes[1],axes[2]))>1e-5)continue;
    if(dot(cross(axes[0],axes[1]),axes[2])<0)axes[2]=axes[2].map(n=>-n);
    const half=axes.map(axis=>Math.max(...vertices.map(p=>Math.abs(dot(p,axis)))));
    if(!vertices.every(p=>axes.every((axis,index)=>Math.abs(Math.abs(dot(p,axis))-half[index])<1e-5)))continue;
    const corners=new Set(vertices.map(p=>axes.map(axis=>dot(p,axis)>0?1:0).join('')));
    if(corners.size!==8)continue;
    const [x,y,z]=axes;
    const m00=x[0],m01=y[0],m02=z[0],m10=x[1],m11=y[1],m12=z[1],m20=x[2],m21=y[2],m22=z[2];
    const trace=m00+m11+m22;
    let q;
    if(trace>0){const s=Math.sqrt(trace+1)*2;q=[(m21-m12)/s,(m02-m20)/s,(m10-m01)/s,s/4];}
    else if(m00>m11&&m00>m22){const s=Math.sqrt(1+m00-m11-m22)*2;q=[s/4,(m01+m10)/s,(m02+m20)/s,(m21-m12)/s];}
    else if(m11>m22){const s=Math.sqrt(1+m11-m00-m22)*2;q=[(m01+m10)/s,s/4,(m12+m21)/s,(m02-m20)/s];}
    else {const s=Math.sqrt(1+m22-m00-m11)*2;q=[(m02+m20)/s,(m12+m21)/s,s/4,(m10-m01)/s];}
    return {half,quaternion:{x:q[0],y:q[1],z:q[2],w:q[3]}};
  }
  return null;
}

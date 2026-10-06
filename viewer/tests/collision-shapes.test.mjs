import test from 'node:test';
import assert from 'node:assert/strict';
import {exactBox} from '../collision-shapes.mjs';
const corners=half=>[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>[x*half[0],y*half[1],z*half[2]])));
const rotate=(p,q)=>{
  const [x,y,z]=p,{x:a,y:b,z:c,w:d}=q;
  const tx=2*(b*z-c*y),ty=2*(c*x-a*z),tz=2*(a*y-b*x);
  return [x+d*tx+b*tz-c*ty,y+d*ty+c*tx-a*tz,z+d*tz+a*ty-b*tx];
};
test('rotated rectangular hulls become equivalent analytic boxes',()=> {
  const q={x:.2,y:.4,z:.1,w:.8};const norm=Math.hypot(q.x,q.y,q.z,q.w);
  for(const key of Object.keys(q))q[key]/=norm;
  const vertices=corners([.03,.12,1.4]).map(p=>rotate(p,q));
  const box=exactBox(vertices);
  assert.ok(box);
  const inverse={...box.quaternion,x:-box.quaternion.x,y:-box.quaternion.y,z:-box.quaternion.z};
  for(const vertex of vertices)rotate(vertex,inverse).forEach((n,i)=>assert.ok(Math.abs(Math.abs(n)-box.half[i])<1e-6));
});
test('a taper or missing corner retains its hull',()=> {
  const vertices=corners([.03,.12,1.4]);vertices[0][0]+=.01;
  assert.equal(exactBox(vertices),null);
  assert.equal(exactBox(vertices.slice(1)),null);
});

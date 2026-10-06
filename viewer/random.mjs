// A stored seed makes a surprising fall reproducible for debugging.
export function randomFromSeed(seed) {
  let state=seed>>>0;
  return () => {
    state=(state+0x6d2b79f5)>>>0;
    let value=Math.imul(state^(state>>>15),state|1);
    value^=value+Math.imul(value^(value>>>7),value|61);
    return ((value^(value>>>14))>>>0)/4294967296;
  };
}
export function freshSeed() {
  return crypto.getRandomValues(new Uint32Array(1))[0];
}
export function poseSignature(poses) {
  let hash=2166136261;
  for(const pose of poses)for(const vector of pose.points||[pose.position,pose.quaternion])
    for(const value of vector)hash=Math.imul(hash^Math.round(value*10000),16777619)>>>0;
  return hash.toString(16).padStart(8,'0');
}

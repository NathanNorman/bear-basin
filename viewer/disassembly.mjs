// Deterministic paths: scrubbing either direction samples the same pose.
const clamp = (n) => Math.max(0, Math.min(1, n));
export const smooth = (n) => { const t = clamp(n); return t * t * (3 - 2 * t); };
export function partPath(center, group, identity) {
  let hash = 2166136261;
  for (const char of identity) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  const angle = (hash % 6283) / 1000;
  const hardware = group === 'Fasteners';
  const roof = group === 'Roof';
  const x = center[0] + .5, z = center[2] - .3;
  const length = Math.hypot(x, z) || 1;
  const spread = hardware ? 2.4 : 1.4;
  return {
    delay: hardware ? 0 : roof ? .12 : .25,
    offset: [x / length * spread + Math.cos(angle) * (hardware ? .5 : .22),
      (roof ? 2.8 : hardware ? .7 : .4) + Math.max(0, center[1]) * .35,
      z / length * spread + Math.sin(angle) * (hardware ? .5 : .22)],
    turn: hardware ? [(hash % 7 - 3) * .08, .3, .15] : [0, 0, 0],
    phase: angle,
  };
}
export function samplePath(path, progress) {
  const t = smooth((clamp(progress) - path.delay) / (1 - path.delay));
  // A small sideways arc gives separation a weightless feel without drifting at rest.
  const arc = t === 0 || t === 1 ? 0 : Math.sin(Math.PI * t) * .18;
  return {
    offset: path.offset.map((value, i) => value * t +
      (i === 0 ? Math.cos(path.phase) * arc : i === 2 ? Math.sin(path.phase) * arc : 0)),
    turn: path.turn.map((value) => value * t),
  };
}

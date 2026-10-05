export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'three') return {url:new URL('../viewer/vendor/three.mjs',import.meta.url).href,shortCircuit:true};
  return nextResolve(specifier, context);
}

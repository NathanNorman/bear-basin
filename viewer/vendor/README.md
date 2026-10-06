# Local viewer dependencies

Three.js 0.160.0 and its GLTFLoader/controls/ConvexHull modules are vendored for offline rendering. License: `three.LICENSE`.

Jolt Physics JavaScript 1.1.0 is from the official npm `jolt-physics` package. License: `jolt.LICENSE`. Source and examples: https://github.com/jrouwe/JoltPhysics.js.

- `jolt.mjs`: unmodified `dist/jolt-physics.wasm-compat.js`, single-thread fallback.
- `jolt-physics.multithread.wasm-compat.js`: multithreaded WebAssembly/SIMD build. Its original filename must be retained because it starts pthread workers using that relative URL.
- One Node-only bootstrap fix parenthesizes the awaited dynamic import before reading `workerData`. Without it, the original expression reads a property from the import promise and headless pthread workers never initialize. Browser behavior and embedded WebAssembly are unchanged. Both builds expose the same physics API.

Tarball: https://registry.npmjs.org/jolt-physics/-/jolt-physics-1.1.0.tgz

Verified npm SHA-512 integrity: `sha512-Erl+X0yK2f9/8Wrl55Nb2y9FYS5xDx375EabnHq+TbSDYEuPZBLvpaLV4nbc1M5gyA5Llbug81wSj1zSMRUr7Q==`.

Original multithread module SHA-256: `a4b78fc46e2576fd06342802af13173f41fd034141891d264eacad6a6e8791d6`.

Patched multithread module SHA-256: `79485cef6a1173d5ed9791cff5e9e2e27af7b2715a4c4caa486a1f5c9c283a8e`.

Rapier 0.21.0 and `rapier.LICENSE` remain from the preserved historical implementation; current live physics uses Jolt.

## GitHub Pages isolation

`../coi-serviceworker.js` is coi-serviceworker v0.1.7 from gzuidhof/coi-serviceworker commit `7b1d2a092d0d2dd2b7270b6f12f13605de26f214`. MIT license: `coi-serviceworker.LICENSE`. It supplies COOP/COEP on static hosting and scopes itself to the viewer directory. Local changes: asset fetches use `cache: "no-cache"` and returned responses carry `Cache-Control: no-store`, preventing old viewer modules from surviving a deployment reload.

import {freshSeed,poseSignature} from './random.mjs';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { isCoordinate, isVisible, readPartMetadata, SelectionHighlight } from './model-state.mjs';
import { partPath, samplePath, smooth } from './disassembly.mjs';
import { PhysicsView } from './physics-view.mjs';
import { HardwareInstances } from './hardware-instances.mjs';

export function startViewer(state) {
  const get = (id) => document.getElementById(id);
  const viewport = get('viewport');
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  viewport.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xc9ced6);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.02, 200);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.screenSpacePanning = true;
  controls.zoomSpeed = 5;
  controls.zoomToCursor = true;
  controls.panSpeed = 1.5;
  const listeners = new AbortController();
  const listen = (target, event, handler) => target.addEventListener(event, handler, { signal: listeners.signal });
  const groups = new Map();
  const pickables = [];
  const highlight = new SelectionHighlight();
  let frame = 0;
  let disposed = false;
  let contextLost = false;
  let pieces = [];
  let progress = 0;
  let animation = null;
  let fall = null;
  let releaseAt = null;
  let lastPhysicsFrame = null;
  let hardwareInstances = null;
  let previousFrame = null;
  const frameIntervals = [];

  function requestRender() {
    if (frame || disposed || contextLost || document.hidden) return;
    frame = requestAnimationFrame((now) => {
      frame = 0;
      if ((animation || lastPhysicsFrame !== null || releaseAt !== null) && previousFrame !== null && now - previousFrame < 250) {
        frameIntervals.push(now - previousFrame);
        if (frameIntervals.length > 120) frameIntervals.shift();
        if (frameIntervals.length >= 15) viewport.dataset.animationFps =
          (1000 / (frameIntervals.reduce((sum, value) => sum + value, 0) / frameIntervals.length)).toFixed(1);
      }
      previousFrame = now;
      if (animation) {
        animation.start ??= now;
        const elapsed = Math.min(1, (now - animation.start) / 1800);
        setDisassembly(animation.from + (animation.to - animation.from) * smooth(elapsed));
        if (elapsed === 1) {
          if (animation.to === 1) { prepareFall(); releaseAt = performance.now() + 650; }
          animation = null;
        }
        else requestRender();
      }
      if (releaseAt !== null) {
        if (now >= releaseAt) {
          releaseAt = null;
          get('gravity').disabled = true;
          prepareFall();
          lastPhysicsFrame = now;
          ground.visible = true;
          ground.material.opacity = 1;
          grid.visible = true;
          get('explode-value').textContent = 'GRAVITY RELEASE';
        }
        requestRender();
      }
      if (fall && lastPhysicsFrame !== null) {
        const dt = Math.min(.05, (now - lastPhysicsFrame) / 1000);
        let active;
        try {
          const updateStart=performance.now();
          active = fall.step(dt);
          viewport.dataset.poseUpdateMs=(performance.now()-updateStart).toFixed(2);
        }
        catch(error) {
          resetFall();
          get('explode-value').textContent = 'PHYSICS ERROR';
          modelStatus(`Physics failed: ${error.message}`);
          renderer.render(scene,camera);
          return;
        }
        viewport.dataset.physicsSeconds = fall.simulation.elapsed.toFixed(2);
        viewport.dataset.physicsEngine=fall.simulation.engine||'initializing';
        viewport.dataset.physicsThreads=String(fall.simulation.workerThreads||0);
        viewport.dataset.physicsWorkerMs=String(fall.simulation.workerMs?.toFixed(2)||'');
        viewport.dataset.physicsWallSeconds=String(fall.simulation.wallSeconds?.toFixed(2)||'');
        viewport.dataset.physicsLagMs=String(fall.simulation.lagMs?.toFixed(2)||'');
        viewport.dataset.physicsUpdates=String(fall.simulation.updates||0);
        viewport.dataset.awakeParts = JSON.stringify(fall.simulation.awake || []);
        if (fall.simulation.elapsed < 1.8) {
          controls.target.y += (.45 - controls.target.y) * Math.min(1, dt * 2);
        }
        lastPhysicsFrame = now;
        if (active) requestRender();
        else {
          lastPhysicsFrame = null;
          get('explode-value').textContent = 'SETTLED';
          viewport.dataset.physicsResult=poseSignature(fall.simulation.poses);
          const costs=fall.simulation.costs.filter(Number.isFinite).sort((a,b)=>a-b);
          viewport.dataset.physicsMeanMs=(costs.reduce((sum,n)=>sum+n,0)/costs.length).toFixed(2);
          viewport.dataset.physicsP95Ms=costs[Math.floor((costs.length-1)*.95)].toFixed(2);
        }
      }
      // OrbitControls emits change while damping settles, scheduling the next frame.
      controls.update();
      hardwareInstances?.update(highlight.object);
      renderer.render(scene, camera);
      viewport.dataset.drawCalls = String(renderer.info.render.calls);
    });
  }
  controls.addEventListener('change', requestRender);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x665544, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(6, 10, 4);
  scene.add(sun);
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(30, 30),
    new THREE.MeshLambertMaterial({ color: 0x5a4d38 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.001;
  const grid = new THREE.GridHelper(30, 30, 0x777777, 0x6a5e48);
  ground.material.transparent = true;
  scene.add(ground, grid);

  function setDisassembly(value) {
    progress = Math.max(0, Math.min(1, value));
    for (const piece of pieces) {
      if (progress === 0) {
        piece.object.position.copy(piece.position);
        piece.object.quaternion.copy(piece.rotation);
        continue;
      }
      const pose = samplePath(piece.path, progress);
      const displaced = piece.world.clone().add(new THREE.Vector3(...pose.offset));
      piece.object.position.copy(piece.object.parent.worldToLocal(displaced));
      piece.object.quaternion.copy(piece.rotation).multiply(
        new THREE.Quaternion().setFromEuler(new THREE.Euler(...pose.turn)));
    }
    scene.background.set(0xc9ced6).lerp(new THREE.Color(0x081b2b), smooth(progress));
    ground.material.opacity = 1 - smooth(progress);
    ground.visible = progress < 1;
    grid.visible = progress < .3;
    get('explode').value = String(Math.round(progress * 1000));
    const percent = Math.round(progress * 100);
    get('explode-value').textContent = `${percent === 0 ? 'ASSEMBLED' : percent === 100 ? 'SUSPENDED' : animation?.to === 0 ? 'REASSEMBLING' : 'SEPARATING'} · ${percent}%`;
    state.disassembly = progress;
    requestRender();
  }
  function enterFieldMode() {
    document.body.classList.add('field-mode');
    get('inspect').textContent = 'Show inspector';
  }
  function animateDisassembly(to) {
    resetFall();
    setDisassembly(progress);
    if (to > 0) enterFieldMode();
    animation = { from: progress, to, start: null };
    requestRender();
  }
  function prepareFall() {
    if(fall)return;
    for(const key of ['physicsResult','physicsMeanMs','physicsP95Ms'])delete viewport.dataset[key];
    const start=performance.now();
    const override=new URLSearchParams(location.search).get('seed');
    const seed=override!==null&&/^\d+$/.test(override)?Number(override)>>>0:freshSeed();
    fall = new PhysicsView(pieces, {useWorker:true,seed});
    viewport.dataset.physicsSeed=String(seed);
    if(new URLSearchParams(location.search).has('physics-debug')) {
      const dump=document.createElement('script');
      dump.id='physics-descriptors';dump.type='application/json';
      dump.textContent=JSON.stringify(fall.entries.map(e=>e.descriptor));
      document.getElementById(dump.id)?.remove();
      document.body.appendChild(dump);
    }
    viewport.dataset.physicsMode=fall.cached?'cached':'live';
    viewport.dataset.physicsInitMs=(performance.now()-start).toFixed(2);
  }
  function resetFall() {
    releaseAt = null;
    lastPhysicsFrame = null;
    fall?.reset();
    fall = null;
    get('gravity').disabled = pieces.length === 0;
  }
  listen(get('explode'), 'pointerdown', () => {
    resetFall();
    animation = null;
    setDisassembly(progress);
    if (progress === 0) enterFieldMode();
  });
  listen(get('explode'), 'input', (event) => {
    animation = null;
    resetFall();
    if (progress === 0 && Number(event.target.value) > 0) enterFieldMode();
    setDisassembly(Number(event.target.value) / 1000);
    if (progress === 1) { prepareFall(); releaseAt = performance.now() + 650; }
  });
  listen(get('disassemble'), 'click', () => animateDisassembly(1));
  listen(get('assemble'), 'click', () => animateDisassembly(0));
  listen(get('gravity'), 'click', () => {
    if (lastPhysicsFrame !== null) return;
    animation = null;
    enterFieldMode();
    prepareFall();
    viewport.dataset.gravityReleaseProgress = String(progress);
    get('gravity').disabled = true;
    releaseAt = performance.now();
    requestRender();
  });
  listen(get('inspect'), 'click', () => {
    const hidden = document.body.classList.toggle('field-mode');
    get('inspect').textContent = hidden ? 'Show inspector' : 'Hide inspector';
  });

  function moveCamera(position, target) {
    // Finish pending damping first so a scripted camera move lands exactly.
    const damping = controls.enableDamping;
    controls.enableDamping = false;
    controls.update();
    camera.position.copy(position);
    controls.target.copy(target);
    controls.update();
    controls.enableDamping = damping;
    requestRender();
  }
  const home = () => moveCamera(new THREE.Vector3(1.5, 3.2, -9.5), new THREE.Vector3(-0.5, 1.5, 0.3));
  // Public camera API uses Blender coordinates (z up), retained for saved workflows.
  state.look = (position, target) => {
    if (!isCoordinate(position) || !isCoordinate(target)) {
      throw new TypeError('look expects two arrays of three finite Blender coordinates.');
    }
    moveCamera(
      new THREE.Vector3(position[0], position[2], -position[1]),
      new THREE.Vector3(target[0], target[2], -target[1]),
    );
  };
  home();
  listen(get('reset'), 'click', home);
  listen(get('bracket-view'), 'click', () =>
    state.look([-4.33, 0.17, 1.86], [-3.03, 0.17, 1.86]));

  function modelStatus(message, error = false) {
    get('model-status').textContent = message;
    get('model-status').dataset.error = String(error);
  }

  function select(object, point = null) {
    highlight.set(object);
    if (!object) {
      state.selected = null;
      get('sel').textContent = 'nothing';
    } else {
      const coordinates = point ? [point.x, -point.z, point.y].map((value) => value.toFixed(2)) : [];
      state.selected = {
        name: object.userData.part,
        code: object.userData.code,
        group: object.userData.grp,
        point_xyz_blender: coordinates,
      };
      const selected = state.selected;
      get('sel').textContent = `${selected.name}\npart code: ${selected.code || '-'}\ngroup: ${selected.group}\nclicked at (x,y,z): ${coordinates.join(', ')}`;
    }
    requestRender();
  }

  function renderGroups() {
    const labels = [...groups.keys()].sort().map((name) => {
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = true;
      listen(checkbox, 'change', () => {
        const objects = groups.get(name);
        objects.forEach((object) => { object.visible = checkbox.checked; });
        if (highlight.object && !isVisible(highlight.object)) select(null);
        if (!fall) setDisassembly(progress);
        requestRender();
      });
      label.append(checkbox, ` ${name.replace(/_/g, ' ')} (${groups.get(name).length})`);
      return label;
    });
    get('groups').replaceChildren(...labels);
  }

  async function loadModel() {
    state.status = 'loading';
    get('retry').hidden = true;
    modelStatus('Loading model…');
    let model = null;
    try {
      const url = new URL('bear_basin.glb', import.meta.url);
      url.searchParams.set('t', String(Date.now()));
      model = (await new GLTFLoader().loadAsync(url.href)).scene;
      if (disposed) {
        disposeObject(model);
        return;
      }
      model.traverse((object) => {
        if (!object.isMesh) return;
        Object.assign(object.userData, readPartMetadata(object));
        const group = object.userData.grp;
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group).push(object);
        pickables.push(object);
      });
      if (!pickables.length) throw new Error('The model contains no selectable meshes.');
      scene.add(model);
      model.updateWorldMatrix(true, true);
      pieces = pickables.map((object) => ({
        object, position: object.position.clone(), rotation: object.quaternion.clone(),
        world: object.getWorldPosition(new THREE.Vector3()),
        center: new THREE.Box3().setFromObject(object).getCenter(new THREE.Vector3()).toArray(),
        path: partPath(new THREE.Box3().setFromObject(object).getCenter(new THREE.Vector3()).toArray(),
          object.userData.grp, object.userData.part),
      }));
      hardwareInstances = new HardwareInstances(pickables, scene);
      for (const id of ['explode', 'assemble', 'disassemble', 'gravity']) get(id).disabled = false;
      renderGroups();
      state.status = 'ready';
      modelStatus(`${pickables.length.toLocaleString()} meshes loaded.`);
      requestRender();
    } catch (error) {
      if (model) {
        scene.remove(model);
        disposeObject(model);
      }
      groups.clear();
      pickables.length = 0;
      if (disposed) return;
      state.status = 'error';
      modelStatus('Model could not be loaded. Rebuild the model or check the server, then retry.', true);
      get('retry').hidden = false;
      console.error('Model loading failed:', error);
    }
  }
  listen(get('retry'), 'click', loadModel);
  void loadModel();

  const ray = new THREE.Raycaster();
  ray.layers.enable(1);
  const mouse = new THREE.Vector2();
  let down = null;
  listen(renderer.domElement, 'pointerdown', (event) => {
    down = event.isPrimary && event.button === 0 && !event.shiftKey && !event.ctrlKey && !event.metaKey
      ? { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false }
      : null;
  });
  listen(renderer.domElement, 'pointermove', (event) => {
    if (down?.id === event.pointerId && Math.hypot(event.clientX - down.x, event.clientY - down.y) > 4) {
      down.moved = true;
    }
  });
  listen(renderer.domElement, 'pointercancel', () => { down = null; });
  listen(renderer.domElement, 'pointerup', (event) => {
    const click = down;
    down = null;
    if (!click || click.id !== event.pointerId || click.moved || event.button !== 0
      || Math.hypot(event.clientX - click.x, event.clientY - click.y) > 4) return;
    const bounds = renderer.domElement.getBoundingClientRect();
    mouse.set(((event.clientX - bounds.left) / bounds.width) * 2 - 1,
      -((event.clientY - bounds.top) / bounds.height) * 2 + 1);
    ray.setFromCamera(mouse, camera);
    const hit = ray.intersectObjects(pickables.filter(isVisible), false)[0];
    select(hit?.object || null, hit?.point || null);
  });

  function resize() {
    const width = viewport.clientWidth;
    const height = viewport.clientHeight;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    requestRender();
  }
  listen(window, 'resize', resize);
  listen(document, 'visibilitychange', requestRender);
  listen(renderer.domElement, 'webglcontextlost', (event) => {
    event.preventDefault();
    contextLost = true;
    cancelAnimationFrame(frame);
    frame = 0;
    modelStatus('Graphics context lost. Waiting for the browser to restore it…', true);
  });
  listen(renderer.domElement, 'webglcontextrestored', () => {
    contextLost = false;
    if (state.status === 'ready') modelStatus(`${pickables.length.toLocaleString()} meshes loaded.`);
    requestRender();
  });
  listen(window, 'pagehide', (event) => {
    if (event.persisted) return; // Keep the scene usable when restored from the back/forward cache.
    disposed = true;
    resetFall();
    cancelAnimationFrame(frame);
    listeners.abort();
    controls.dispose();
    highlight.clear();
    disposeObject(scene);
    renderer.dispose();
  });
  resize();
}

function disposeObject(root) {
  const resources = new Set();
  root.traverse((object) => {
    if (object.geometry) resources.add(object.geometry);
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach((material) => {
      resources.add(material);
      Object.values(material).filter((value) => value?.isTexture).forEach((texture) => resources.add(texture));
    });
  });
  resources.forEach((resource) => resource.dispose());
}

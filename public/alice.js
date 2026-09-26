import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const $ = id => document.getElementById(id);
const host = $('canvas-container');
const scene = new THREE.Scene();
const group = new THREE.Group(); scene.add(group);
const message = (text, error = false) => { $('message').textContent = text; $('message').hidden = !text; $('message').style.borderColor = error ? '#a45958' : ''; };
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
} catch (error) {
  message('WebGL indisponível neste navegador. Não foi carregada uma imagem substituta para a malha 3D.', true);
  throw error;
}
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;
host.appendChild(renderer.domElement);
const pmrem = new THREE.PMREMGenerator(renderer);
const environment = pmrem.fromScene(new RoomEnvironment(), 0.05);
scene.environment = environment.texture;
const key = new THREE.DirectionalLight(0xffe7ca, 2.4); key.position.set(3, 5, 4); scene.add(key);
const fill = new THREE.DirectionalLight(0xbac9e0, 1.1); fill.position.set(-4, 2, 3); scene.add(fill);
const rim = new THREE.DirectionalLight(0xe7ddc7, 2); rim.position.set(2, 3, -4); scene.add(rim);
scene.add(new THREE.HemisphereLight(0xe1e7f4, 0x25202b, 0.7));
const grid = new THREE.GridHelper(6, 30, 0x686159, 0x383942); grid.material.transparent = true; grid.material.opacity = 0.18; scene.add(grid);
const perspective = new THREE.PerspectiveCamera(35, 1, 0.001, 100);
const orthographic = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.001, 100);
let camera = orthographic;
let controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
let data, selectedModel, model, mixer, helper, box, currentView = 'front', mode = 'pbr';
let loadingToken = 0, busy = false;
const originals = new Map(), modes = new Map();
const clock = new THREE.Clock();
const overlayImage = new Image();
overlayImage.style.cssText = 'position:absolute;pointer-events:none;z-index:1;display:none;object-fit:fill';
host.appendChild(overlayImage);

async function api(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}

function disposeObject(object) {
  if (!object) return;
  const textures = new Set(), materials = new Set(), geometries = new Set();
  object.traverse(o => {
    if (o.geometry) geometries.add(o.geometry);
    for (const material of (Array.isArray(o.material) ? o.material : [o.material]).filter(Boolean)) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  for (const value of [...textures, ...materials, ...geometries]) value.dispose();
}

function updateBounds() {
  if (!model) return;
  model.updateMatrixWorld(true);
  model.traverse(o => { if (o.isSkinnedMesh) { o.skeleton.update(); o.computeBoundingBox(); } });
  box = new THREE.Box3().setFromObject(model, true);
}

function framing() {
  const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  const h = size.y;
  const bands = { full: [0, 1], face: [0.77, 1.02], torso: [0.49, 0.81], skirt: [0.20, 0.65], boots: [-0.015, 0.29] };
  const [low, high] = bands[$('focus').value];
  const height = (high - low) * h;
  return { center: new THREE.Vector3(center.x, box.min.y + (low + high) * h / 2, center.z),
    height, width: $('focus').value === 'full' ? Math.max(size.x, size.z) : height * 1.25 };
}

function fitView(view = currentView) {
  if (!box) return;
  currentView = view;
  const { center, height, width } = framing();
  const aspect = host.clientWidth / Math.max(1, host.clientHeight);
  const span = Math.max(height * 1.45, width / aspect * 1.2);
  center.y -= span * 0.06;
  camera = $('projection').value === 'perspective' ? perspective : orthographic;
  controls.dispose(); controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
  const directions = { front: [0, 0, 1], side: [1, 0, 0], back: [0, 0, -1], threequarter: [-0.6, 0.12, 1] };
  const direction = new THREE.Vector3(...directions[view]).normalize();
  camera.near = Math.max(height / 1000, 0.0001); camera.far = Math.max(height * 100, 100);
  if (camera.isOrthographicCamera) {
    camera.left = -span * aspect / 2; camera.right = span * aspect / 2;
    camera.top = span / 2; camera.bottom = -span / 2; camera.zoom = 1;
    camera.position.copy(center).addScaledVector(direction, Math.max(height * 3, 4));
  } else {
    camera.aspect = aspect;
    const vertical = height * 1.45 / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
    const horizontal = width * 1.2 / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * aspect);
    camera.position.copy(center).addScaledVector(direction, Math.max(vertical, horizontal));
  }
  camera.updateProjectionMatrix(); controls.target.copy(center); camera.lookAt(center); controls.update();
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  $('view-name').textContent = `${view === 'threequarter' ? '¾' : data.profile.calibration.views[view].label} / ${camera.isOrthographicCamera ? 'ortográfica' : 'perspectiva'}`;
  if (view !== 'threequarter') showReference(view);
  updateOverlay();
}

function showReference(view) {
  $('reference').src = `/api/alice/reference/${view}`;
  $('reference').alt = `${data.profile.calibration.views[view].label} original de Alice Liddell`;
  document.querySelectorAll('[data-ref]').forEach(b => b.classList.toggle('active', b.dataset.ref === view));
}

function applyMode(newMode) {
  mode = newMode;
  if (!model) return;
  model.traverse(o => {
    if (!o.isMesh) return;
    const original = originals.get(o.uuid);
    if (!modes.has(o.uuid)) {
      const materials = (Array.isArray(original) ? original : [original]).map(m => ({
        clay: new THREE.MeshStandardMaterial({ color: 0xaca49a, roughness: 0.85, side: m.side }),
        wire: new THREE.MeshBasicMaterial({ color: 0xd5c9af, wireframe: true, side: THREE.DoubleSide }),
        albedo: new THREE.MeshBasicMaterial({ color: m.color, map: m.map, side: m.side, transparent: m.transparent,
          opacity: m.opacity, alphaTest: m.alphaTest, toneMapped: false })
      }));
      modes.set(o.uuid, materials);
    }
    o.material = mode === 'pbr' ? original : (Array.isArray(original)
      ? modes.get(o.uuid).map(m => m[mode]) : modes.get(o.uuid)[0][mode]);
  });
}

async function loadModel(info) {
  const token = ++loadingToken;
  message('Carregando geometria, texturas e rig…');
  $('capture').disabled = true; $('download').removeAttribute('href');
  try {
    const gltf = await new GLTFLoader().loadAsync(info.url);
    if (token !== loadingToken) { disposeObject(gltf.scene); return; }
    if (mixer) { mixer.stopAllAction(); mixer.uncacheRoot(model); }
    if (helper) { scene.remove(helper); helper.dispose(); helper = null; }
    // Restore originals before disposal so every original texture is freed.
    if (model) {
      model.traverse(o => { if (originals.has(o.uuid)) o.material = originals.get(o.uuid); });
      group.remove(model); disposeObject(model);
    }
    for (const materials of modes.values()) for (const material of materials)
      for (const value of Object.values(material)) value.dispose();
    modes.clear(); originals.clear(); model = gltf.scene; selectedModel = info;
    model.traverse(o => { if (o.isMesh) originals.set(o.uuid, o.material); });
    group.add(model); group.rotation.set(0, 0, 0); updateBounds();
    const center = box.getCenter(new THREE.Vector3());
    model.position.x -= center.x; model.position.y -= box.min.y; model.position.z -= center.z;
    updateBounds();
    mixer = new THREE.AnimationMixer(model);
    $('animation').replaceChildren(new Option('Pose de referência', ''));
    $('animation').disabled = gltf.animations.length === 0;
    $('rig').disabled = info.joints === 0;
    gltf.animations.forEach((clip, index) => $('animation').add(new Option(clip.name || `Animação ${index + 1}`, String(index))));
    $('animation').onchange = () => {
      mixer.stopAllAction();
      if ($('animation').value !== '') mixer.clipAction(gltf.animations[Number($('animation').value)]).reset().play();
      updateBounds(); fitView();
    };
    helper = new THREE.SkeletonHelper(model); helper.visible = $('rig').checked; scene.add(helper);
    const size = box.getSize(new THREE.Vector3());
    $('stats').textContent = `${info.triangles.toLocaleString('pt-BR')} triângulos · ${info.joints} juntas · ${size.y.toFixed(2)} m de altura · ${size.z.toFixed(2)} m de profundidade`;
    $('provenance').textContent = info.id === 'source' ? 'Geometria importada do Project Alice. O vestido original não tem mapa de cor.' :
      info.id === 'detail' ? 'FBX original do Project Alice, LOD3, atlas UV de 2048 px recuperado. Malha estática; não tem rig nem física de tecido.' :
      info.restoration ? 'Geometria do Project Alice + projeção de cor das três vistas. O perfil direito usa informação espelhada do esquerdo.' : 'Geometria importada. A fidelidade ainda precisa ser comparada com a referência.';
    $('status').textContent = 'Fidelidade a verificar';
    $('capture').disabled = false;
    $('download').href = `${info.url}?download=1`;
    $('evidence').textContent = 'Nenhuma inspeção registrada desta versão.';
    applyMode($('render-mode').value); fitView(); message('');
  } catch (error) { message(`Não foi possível carregar a malha: ${error.message}`, true); }
}

function updateOverlay() {
  const enabled = $('overlay').checked && model && camera.isOrthographicCamera && currentView !== 'threequarter' &&
    !$('rotate').checked && $('focus').value === 'full' && $('animation').value === '';
  // Only fixed matching cameras have a meaningful reference overlay.
  if (!enabled) { overlayImage.style.display = 'none'; return; }
  const expected = new THREE.Vector3(...data.profile.calibration.views[currentView].camera);
  const actual = camera.position.clone().sub(controls.target).normalize();
  if (expected.dot(actual) < 0.999) { overlayImage.style.display = 'none'; return; }
  const cal = data.profile.calibration, view = cal.views[currentView];
  const scale = host.clientHeight / ((camera.top - camera.bottom) / camera.zoom) / cal.pixelsPerMetre;
  const [left, top, width, height] = view.crop;
  const worldCenter = new THREE.Vector3(0, (cal.groundPixel - top - height / 2) / cal.pixelsPerMetre, 0);
  const projected = worldCenter.project(camera);
  overlayImage.src = `/api/alice/reference/${currentView}`;
  overlayImage.style.display = 'block'; overlayImage.style.width = `${width * scale}px`; overlayImage.style.height = `${height * scale}px`;
  overlayImage.style.left = `${(projected.x + 1) * host.clientWidth / 2 + (left + width / 2 - view.centerPixel) * scale - width * scale / 2}px`;
  overlayImage.style.top = `${(1 - projected.y) * host.clientHeight / 2 - height * scale / 2}px`;
  overlayImage.style.opacity = Number($('opacity').value) / 100;
}

async function captureViews() {
  if (!model || busy) return;
  busy = true; $('capture').disabled = true;
  const oldMode = mode, oldRotation = group.rotation.clone(), oldRig = helper.visible, oldGrid = grid.visible;
  const animation = $('animation').value;
  const output = {}, size = renderer.getSize(new THREE.Vector2()), pixelRatio = renderer.getPixelRatio();
  message('Enquadrando e registrando três renders reais da malha…');
  try {
    mixer.stopAllAction(); group.rotation.set(0, 0, 0); helper.visible = false; grid.visible = false;
    applyMode('albedo'); updateBounds();
    renderer.setPixelRatio(1); renderer.setSize(440, 850, false);
    const cal = data.profile.calibration;
    for (const [view, settings] of Object.entries(cal.views)) {
      const [left, top, width, height] = settings.crop;
      const leftPad = (440 - width) / 2;
      const c = new THREE.OrthographicCamera((left - settings.centerPixel - leftPad) / cal.pixelsPerMetre,
        (left - settings.centerPixel - leftPad + 440) / cal.pixelsPerMetre,
        (cal.groundPixel - top) / cal.pixelsPerMetre,
        (cal.groundPixel - top - height) / cal.pixelsPerMetre, 0.01, 100);
      c.position.set(...settings.camera).multiplyScalar(5); c.lookAt(0, 0, 0); c.updateMatrixWorld();
      renderer.render(scene, c); output[view] = renderer.domElement.toDataURL('image/png');
    }
    const result = await api('/api/alice/evidence', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modelId: selectedModel.id, modelSha256: selectedModel.sha256, renders: output }) });
    $('evidence').replaceChildren();
    const label = document.createElement('p'); label.textContent = 'Três vistas registradas. A revisão visual continua pendente.'; $('evidence').append(label);
    for (const [view, info] of Object.entries(result.views)) {
      const link = document.createElement('a'); link.href = info.url; link.target = '_blank'; link.textContent = data.profile.calibration.views[view].label; $('evidence').append(link);
    }
    const report = document.createElement('a'); report.href = result.reportUrl; report.target = '_blank'; report.textContent = 'Relatório JSON ↗'; $('evidence').append(report);
    message('');
  } catch (error) { message(`Registro falhou: ${error.message}`, true); }
  finally {
    renderer.setPixelRatio(pixelRatio); renderer.setSize(size.x, size.y, false);
    applyMode(oldMode); group.rotation.copy(oldRotation); helper.visible = oldRig; grid.visible = oldGrid;
    if (animation !== '') $('animation').onchange();
    busy = false; $('capture').disabled = false;
  }
}

function choose(info) {
  if (!data.models.some(m => m.id === info.id)) { data.models.push(info); $('model').add(new Option(info.label, info.id)); }
  $('model').value = info.id; loadModel(info);
}

$('model').onchange = () => { if (!busy) loadModel(data.models.find(m => m.id === $('model').value)); };
$('render-mode').onchange = () => { if (!busy) applyMode($('render-mode').value); };
$('projection').onchange = () => fitView(); $('focus').onchange = () => fitView(); $('fit').onclick = () => fitView();
$('rotate').onchange = () => { controls.autoRotate = $('rotate').checked; updateOverlay(); };
$('rig').onchange = () => { if (helper) helper.visible = $('rig').checked; };
$('overlay').onchange = () => { if ($('overlay').checked) fitView(); updateOverlay(); }; $('opacity').oninput = updateOverlay;
controls.addEventListener('change', updateOverlay);
document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => { $('rotate').checked = false; fitView(b.dataset.view); });
document.querySelectorAll('[data-ref]').forEach(b => b.onclick = () => fitView(b.dataset.ref));
$('capture').onclick = captureViews;
$('import').onchange = async () => {
  if (!$('import').files[0] || busy) return;
  try { const form = new FormData(); form.append('model', $('import').files[0]); message('Validando a geometria importada…'); choose(await api('/api/alice/import', { method: 'POST', body: form })); }
  catch (error) { message(error.message, true); }
  finally { $('import').value = ''; }
};
$('reconstruct').onclick = async () => {
  if (busy) return; busy = true; $('reconstruct').disabled = true; message('Enviando as três vistas ao serviço de reconstrução…');
  try { choose(await api('/api/alice/reconstruct', { method: 'POST' })); }
  catch (error) { message(error.message, true); }
  finally { busy = false; $('reconstruct').disabled = !data.reconstructionAvailable; }
};

const observer = new ResizeObserver(() => {
  if (busy) return;
  renderer.setSize(host.clientWidth, host.clientHeight);
  if (box) fitView();
}); observer.observe(host);

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  if (busy) return;
  if (mixer) mixer.update(dt);
  controls.autoRotate = $('rotate').checked; controls.update(); updateOverlay();
  renderer.render(scene, camera);
}
animate();

try {
  data = await api('/api/alice');
  $('model').replaceChildren(); data.models.forEach(m => $('model').add(new Option(m.label, m.id))); $('model').disabled = false;
  $('reconstruct').disabled = !data.reconstructionAvailable;
  $('service').textContent = data.reconstructionAvailable ? 'Serviço multivista configurado. O resultado exigirá inspeção.' : 'Reconstrução por IA indisponível neste ambiente. As versões abaixo usam a malha existente do projeto.';
  for (const limitation of data.profile.limitations) { const li = document.createElement('li'); li.textContent = limitation; $('limits').append(li); }
  const focusByDetail = { face: 'face', hair: 'face', sleeves: 'torso', corset: 'torso', apron: 'skirt', skirt: 'skirt', embroidery: 'skirt', bow: 'skirt', bracers: 'torso', boots: 'boots' };
  for (const detail of data.profile.details) {
    const button = document.createElement('button'); button.textContent = detail.label;
    button.onclick = () => { $('focus').value = focusByDetail[detail.id]; fitView(detail.id === 'bow' ? 'back' : detail.views[0]); };
    $('details').append(button);
  }
  const requested = new URLSearchParams(location.search).get('model');
  choose(data.models.find(m => m.id === requested) || data.models.find(m => m.id === 'detail') || data.models.find(m => m.id === 'restored') || data.models[0]);
} catch (error) { message(`Estúdio indisponível: ${error.message}`, true); }

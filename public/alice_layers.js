import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
const $=id=>document.getElementById(id), host=$('canvas-container');
const scene=new THREE.Scene(), camera=new THREE.OrthographicCamera(-1,1,1,-1,.001,100);
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.setClearColor(0,0);host.appendChild(renderer.domElement);
const pmrem=new THREE.PMREMGenerator(renderer), env=pmrem.fromScene(new RoomEnvironment(),.05);
scene.environment=env.texture;scene.add(new THREE.HemisphereLight(0xffffff,0x444444,1));
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
let stages=[], model=null, mixer=null, token=0, center=new THREE.Vector3(), span=2, view='front';
let followBone=null, followOffset=new THREE.Vector3(), referenceCenter=new THREE.Vector3();
const originals=new Map(), temporaryMaterials=[];
const names={alice_base:'Alice Base',alice_chapeleiro:'Alice Chapeleiro',alice_cheshire:'Alice Cheshire',alice_coelho:'Alice Coelho',alice_lagarta:'Alice Lagarta',alice_rainha:'Alice Rainha'};
const directions={front:[0,0,1],side:[1,0,0],back:[0,0,-1],threequarter:[.65,.15,1]};
function fit(name=view){
  view=name;const aspect=Math.max(host.clientWidth,1)/Math.max(host.clientHeight,1);
  camera.left=-span*aspect/2;camera.right=span*aspect/2;camera.top=span/2;camera.bottom=-span/2;camera.zoom=1;
  camera.position.copy(center).addScaledVector(new THREE.Vector3(...directions[name]).normalize(),span*4);
  camera.far=Math.max(100,span*20);camera.updateProjectionMatrix();camera.lookAt(center);controls.target.copy(center);controls.update();
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===name));
  $('view-name').textContent=`${{front:'Frente',side:'Perfil',back:'Costas',threequarter:'¾'}[name]} / ortográfica`;
}
function dispose(object){
  object?.traverse(o=>{if(!o.isMesh)return;o.geometry.dispose();const materials=originals.get(o.uuid)||o.material;
    for(const m of Array.isArray(materials)?materials:[materials]){for(const value of Object.values(m))if(value?.isTexture)value.dispose();m.dispose();}});
}
function clearModel(){followBone=null;if(mixer){mixer.stopAllAction();mixer.uncacheRoot(model);mixer=null;}if(model){scene.remove(model);dispose(model);model=null;}for(const m of temporaryMaterials)m.dispose();temporaryMaterials.length=0;originals.clear();$('stats').textContent='';$('animation').replaceChildren(new Option('Sem animação disponível',''));$('animation').disabled=true;$('rig-status').textContent='Rig e acompanhamento do tecido pendentes.';}
function surface(){
  for(const m of temporaryMaterials)m.dispose();temporaryMaterials.length=0;
  model?.traverse(o=>{if(!o.isMesh)return;const original=originals.get(o.uuid);
    function convert(m){if($('surface').value==='pbr')return m;
      const replacement=$('surface').value==='wire'?new THREE.MeshBasicMaterial({color:0xd7c7aa,wireframe:true,side:THREE.DoubleSide}):
        $('surface').value==='clay'?new THREE.MeshStandardMaterial({color:0xaaa49b,roughness:.85,side:m.side}):
        new THREE.MeshBasicMaterial({map:m.map,color:m.color,vertexColors:m.vertexColors,side:m.side,transparent:m.transparent,opacity:m.opacity,alphaTest:m.alphaTest});
      temporaryMaterials.push(replacement);return replacement;}
    o.material=Array.isArray(original)?original.map(convert):convert(original);});
}
async function selectStage(){
  const current=++token;clearModel();$('rotate').checked=false;
  const stage=stages.find(s=>s.id===$('stage').value);if(!stage)return;
  $('stage-label').textContent=stage.label;$('reference-title').textContent=`${names[stage.variant]} · ${String(stage.number).padStart(2,'0')}`;
  $('reference').src=stage.referenceUrl;$('reference').alt=`${names[stage.variant]}: foto original de ${stage.label}`;$('reference').hidden=false;
  $('original').href=stage.referenceUrl;$('original').hidden=false;
  $('origin').textContent=`Foto identificada por SHA-256: ${stage.sourcePhotoSha256.slice(0,16)}…`;
  $('reference-note').textContent='Esta é a foto da etapa selecionada. Abra em tamanho completo para conferir os detalhes.';
  $('review').textContent=stage.review?.visibleDifferences?.join('\n')||'Ainda sem revisão visual desta etapa.';
  $('comparison').hidden=!stage.comparisonUrl;if(stage.comparisonUrl)$('comparison').href=stage.comparisonUrl;
  $('status').textContent=stage.status==='rejected_fidelity'?'Fidelidade rejeitada':'Etapa pendente';
  $('message').hidden=false;$('message').textContent=stage.model?'Carregando a malha nova desta foto…':'Esta etapa ainda não tem malha nova. A foto permanece disponível para a construção.';
  if(!stage.model)return;
  try{
    const gltf=await new GLTFLoader().loadAsync(stage.model.url);
    if(current!==token){dispose(gltf.scene);return;}
    model=gltf.scene;model.rotation.y={'+x':-Math.PI/2,'-x':Math.PI/2,'+y':Math.PI,'-y':0}[stage.model.frontAxis]??0;scene.add(model);
    mixer=new THREE.AnimationMixer(model);
    $('animation').replaceChildren(new Option('Pose de referência',''),...gltf.animations.map((a,i)=>new Option(a.name||`Teste ${i+1}`,String(i))));
    $('animation').disabled=!gltf.animations.length;
    $('animation').onchange=()=>{mixer.stopAllAction();if($('animation').value!=='')mixer.clipAction(gltf.animations[Number($('animation').value)]).reset().play();else{mixer.update(0);center.copy(referenceCenter);fit();}};
    $('rig-status').textContent=stage.model.joints?`${stage.model.joints} juntas. Corrida, caminhada, salto, ataque e colisões ainda precisam de validação.`:'Esta malha está estática. Falta rig e acompanhamento do tecido nos movimentos.';
    model.traverse(o=>{if(o.isMesh)originals.set(o.uuid,o.material);});
    model.updateMatrixWorld(true);
    // Bones must have world matrices before skin bounds are measured. Otherwise the
    // camera frames an undeformed origin while the rendered skin is elsewhere.
    model.traverse(o=>{if(o.isSkinnedMesh){o.skeleton.update();o.computeBoundingBox();o.computeBoundingSphere();o.frustumCulled=false;}});
    const box=new THREE.Box3().setFromObject(model), size=box.getSize(new THREE.Vector3());
    center=box.getCenter(new THREE.Vector3());span=Math.max(size.y,size.x*host.clientHeight/Math.max(host.clientWidth,1))*1.15;
    referenceCenter.copy(center);followBone=model.getObjectByProperty('isBone',true)||null;
    if(followBone)followOffset.copy(center).sub(followBone.getWorldPosition(new THREE.Vector3()));
    $('stats').textContent=`${stage.model.triangles.toLocaleString('pt-BR')} triângulos · profundidade ${size.z.toFixed(3)} · geometria nova a conferir`;
    surface();fit();$('message').hidden=true;
    if(stage.status!=='rejected_fidelity')$('status').textContent='Fidelidade a verificar';
  }catch(error){if(current===token){$('message').hidden=false;$('message').textContent=`Malha indisponível: ${error.message}`;}}
}
function selectVariant(){
  $('stage').replaceChildren(...stages.filter(s=>s.variant===$('variant').value).map(s=>new Option(`${String(s.number).padStart(2,'0')} · ${s.label}`,s.id)));
  selectStage();
}
$('variant').onchange=selectVariant;$('stage').onchange=selectStage;$('surface').onchange=surface;
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>fit(b.dataset.view));
new ResizeObserver(()=>{renderer.setSize(host.clientWidth,host.clientHeight);if(model)fit();}).observe(host);
const clock=new THREE.Clock();renderer.setAnimationLoop(()=>{const delta=clock.getDelta();mixer?.update(delta);
  if(followBone&&$('animation').value!==''){model.updateMatrixWorld(true);const target=followBone.getWorldPosition(new THREE.Vector3()).add(followOffset);camera.position.add(target.clone().sub(controls.target));controls.target.copy(target);center.copy(target);}
  if(model&&$('rotate').checked)model.rotation.y+=delta*.3;controls.update();renderer.render(scene,camera);});
try{
  const response=await fetch('/api/alice/stages');const result=await response.json();if(!response.ok)throw new Error(result.error||response.status);
  stages=result.stages;$('variant').replaceChildren(...[...new Set(stages.map(s=>s.variant))].map(id=>new Option(names[id]||id,id)));
  $('variant').disabled=$('stage').disabled=!stages.length;
  if(stages.length)selectVariant();else{$('message').textContent='As fotos das etapas ainda não foram configuradas neste servidor.';$('status').textContent='Referências pendentes';}
}catch(error){$('message').textContent=`Não foi possível ler as etapas: ${error.message}`;}

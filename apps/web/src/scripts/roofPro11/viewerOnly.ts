/**
 * WJ25/WJ27 — VISIONNEUSE 3D EN LECTURE SEULE du toit du client (proposition).
 *
 * Dessine le `ViewerModel` PUR calculé côté serveur par lib/proposition.ts
 * (buildViewerModel) : bâtiment + pans + panneaux, avec orbite/zoom/pan
 * (souris + tactile via OrbitControls). AUCUNE UI d'édition, AUCUNE carte,
 * AUCUN optimiseur — et AUCUN import de scene3d.ts / du builder : ce module
 * est volontairement AUTONOME (la géométrie/les teintes minimales nécessaires
 * sont dupliquées ici, cf. consigne de lane).
 *
 * Chargé par import() DYNAMIQUE depuis /proposition/[token] (jamais dans le
 * bundle initial). Durcissement WJ27 :
 *  - DPR plafonné (1,5 bas de gamme / 2 sinon), antialias coupé en bas de gamme ;
 *  - rendu À LA DEMANDE (aucune boucle RAF permanente : on ne rend que pendant
 *    l'interaction + l'amortissement, et à l'init/resize) ;
 *  - récupération de PERTE DE CONTEXTE WebGL (preventDefault + rebuild) ;
 *  - prefers-reduced-motion : aucun amortissement, aucune rotation automatique
 *    (orbite manuelle uniquement) ;
 *  - dispose() libère TOUT (géométries, matériaux, renderer, écouteurs).
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { ViewerModel, ViewerZone } from '../../lib/proposition';

/** Hauteur de mur (m) — même lecture visuelle que le builder (2 niveaux × 3 m),
 *  valeur dupliquée (constants.ts appartient au builder — non importé). */
const WALL_H_M = 6;
const PANEL_THICK_M = 0.04;
const FLAT_STAND_M = 0.12;
const DEG2RAD = Math.PI / 180;

export interface ViewerInitOptions {
  /** prefers-reduced-motion : pas d'amortissement, pas d'auto-rotation. */
  reducedMotion: boolean;
  /** Appareil modeste (mémoire ≤ 4 Go ou ≤ 4 cœurs) : DPR/AA réduits. */
  lowEnd: boolean;
  /** Appelé quand la 3D est PRÊTE (premier rendu peint) — masque le poster. */
  onReady?: () => void;
  /** Appelé si le contexte WebGL est perdu sans restauration possible. */
  onFail?: () => void;
}

export interface ViewerHandle {
  dispose: () => void;
}

/** Cap DPR : net sur mobile sans surcharger le GPU (WJ27). Exporté pour test. */
export function viewerDprCap(devicePixelRatio: number, lowEnd: boolean): number {
  const dpr = Number.isFinite(devicePixelRatio) && devicePixelRatio > 0 ? devicePixelRatio : 1;
  return Math.min(dpr, lowEnd ? 1.5 : 2);
}

/** Sonde WebGL SANS créer de renderer (repli poster propre quand absent). */
export function webglAvailable(): boolean {
  try {
    const probe = document.createElement('canvas');
    return !!(probe.getContext('webgl2') || probe.getContext('webgl'));
  } catch {
    return false;
  }
}

/** Hauteur du plan incliné au point (x,y) d'un pan (0 à l'égout, monte vers l'amont). */
function pitchedRiseAt(
  x: number,
  y: number,
  f: [number, number],
  dEave: number,
  tiltRad: number,
): number {
  const d = x * f[0] + y * f[1];
  return Math.max(0, (dEave - d) * Math.tan(tiltRad));
}

/** Construit tous les meshes d'une zone dans `root`. Renvoie les ressources à libérer. */
function buildZone(root: THREE.Group, zone: ViewerZone, disposables: Array<{ dispose: () => void }>): void {
  const ring = zone.ringENU;
  if (ring.length < 3) return;

  const shape = new THREE.Shape();
  ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
  shape.closePath();

  // Bâtiment (mêmes teintes de lecture que le builder — valeurs dupliquées).
  const buildingMat = new THREE.MeshStandardMaterial({ color: 0xe2e7f2, roughness: 0.85, metalness: 0 });
  const buildingGeo = new THREE.ExtrudeGeometry(shape, { depth: WALL_H_M, bevelEnabled: false });
  const building = new THREE.Mesh(buildingGeo, buildingMat);
  root.add(building);
  disposables.push(buildingGeo, buildingMat);

  const az = zone.azimuthDeg * DEG2RAD;
  const f: [number, number] = [Math.sin(az), Math.cos(az)];
  const tiltRad = zone.tiltDeg * DEG2RAD;
  const pitched = zone.roofType === 'pitched';
  // Égout = point le plus AVAL (projection max sur la direction de face).
  let dEave = -Infinity;
  for (const [x, y] of ring) dEave = Math.max(dEave, x * f[0] + y * f[1]);

  // Dalle / pan : plan horizontal (plat) ou incliné (pente) — sommets relevés.
  const deckGeo = new THREE.ShapeGeometry(shape);
  if (pitched) {
    const pos = deckGeo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      pos.setZ(i, pitchedRiseAt(pos.getX(i), pos.getY(i), f, dEave, tiltRad));
    }
    pos.needsUpdate = true;
    deckGeo.computeVertexNormals();
  }
  const deckMat = new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 });
  const deck = new THREE.Mesh(deckGeo, deckMat);
  deck.position.z = WALL_H_M + 0.02;
  root.add(deck);
  disposables.push(deckGeo, deckMat);

  // Pente : jupe périmétrique simple pour fermer le volume sous le pan incliné.
  if (pitched) {
    const positions: number[] = [];
    const n = ring.length;
    for (let i = 0; i < n; i++) {
      const [ax, ay] = ring[i];
      const [bx, by] = ring[(i + 1) % n];
      const za = 0.02 + pitchedRiseAt(ax, ay, f, dEave, tiltRad);
      const zb = 0.02 + pitchedRiseAt(bx, by, f, dEave, tiltRad);
      positions.push(ax, ay, 0, bx, by, 0, bx, by, zb);
      positions.push(ax, ay, 0, bx, by, zb, ax, ay, za);
    }
    const skirtGeo = new THREE.BufferGeometry();
    skirtGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    skirtGeo.computeVertexNormals();
    const skirtMat = new THREE.MeshStandardMaterial({
      color: 0xe2e7f2,
      roughness: 0.85,
      metalness: 0,
      side: THREE.DoubleSide,
    });
    const skirt = new THREE.Mesh(skirtGeo, skirtMat);
    skirt.position.z = WALL_H_M;
    root.add(skirt);
    disposables.push(skirtGeo, skirtMat);
  }

  // Obstacles : boîtes discrètes (lecture seule, non manipulables).
  for (const o of zone.obstaclesENU) {
    const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, 0.9);
    const mat = new THREE.MeshStandardMaterial({ color: 0x9aa3b4, roughness: 0.8, metalness: 0 });
    const mesh = new THREE.Mesh(geo, mat);
    const zTop = pitched ? pitchedRiseAt(o.x, o.y, f, dEave, tiltRad) : 0;
    mesh.position.set(o.x, o.y, WALL_H_M + zTop + 0.45);
    root.add(mesh);
    disposables.push(geo, mat);
  }

  // Panneaux : InstancedMesh unique (verre sombre — lecture immédiate « panneau »).
  if (zone.panels.length > 0) {
    const panelGeo = new THREE.BoxGeometry(zone.panelAlongM, zone.panelDepthM / Math.cos(tiltRad) || zone.panelDepthM, PANEL_THICK_M);
    const panelMat = new THREE.MeshStandardMaterial({ color: 0x14263f, roughness: 0.25, metalness: 0.35 });
    const im = new THREE.InstancedMesh(panelGeo, panelMat, zone.panels.length);
    const rowAngle = Math.atan2(f[0], -f[1]); // rangée ⟂ face
    const qz = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), rowAngle);
    const qx = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), tiltRad);
    const q = qz.clone().multiply(qx);
    const scl = new THREE.Vector3(1, 1, 1);
    const rise = (zone.panelDepthM / Math.cos(tiltRad) || zone.panelDepthM) * Math.sin(tiltRad);
    const m = new THREE.Matrix4();
    for (let i = 0; i < zone.panels.length; i++) {
      const p = zone.panels[i];
      const zBase = pitched
        ? WALL_H_M + 0.02 + pitchedRiseAt(p.x, p.y, f, dEave, tiltRad) + 0.06
        : WALL_H_M + FLAT_STAND_M + rise / 2 + 0.07;
      m.compose(new THREE.Vector3(p.x, p.y, zBase), q, scl);
      im.setMatrixAt(i, m);
    }
    im.instanceMatrix.needsUpdate = true;
    root.add(im);
    disposables.push(panelGeo, panelMat, im);
  }
}

/**
 * Monte la visionneuse dans `container` (le canvas est créé ici, positionné en
 * absolu — le conteneur DOIT déjà réserver sa hauteur : zéro CLS). Renvoie un
 * handle `dispose()` ou `null` si WebGL est indisponible.
 */
export function createRoofViewer(
  container: HTMLElement,
  model: ViewerModel,
  opts: ViewerInitOptions,
): ViewerHandle | null {
  if (!webglAvailable()) return null;
  if (!model || !Array.isArray(model.zones) || model.zones.length === 0) return null;

  const canvas = document.createElement('canvas');
  canvas.style.position = 'absolute';
  canvas.style.inset = '0';
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  canvas.setAttribute('aria-label', 'Vue 3D interactive de votre toiture — faites glisser pour tourner, pincez ou molette pour zoomer');
  canvas.setAttribute('role', 'img');
  container.appendChild(canvas);

  let renderer: THREE.WebGLRenderer | null = null;
  let glLost = false;
  let disposed = false;

  const scene = new THREE.Scene();
  const root = new THREE.Group();
  scene.add(root);
  scene.add(new THREE.AmbientLight(0xb9c8ee, 0.55));
  scene.add(new THREE.HemisphereLight(0xcfe0ff, 0x20242e, 0.6));
  const sun = new THREE.DirectionalLight(0xfff2d6, 2.2);
  sun.position.set(-40, -60, 80);
  scene.add(sun);

  const disposables: Array<{ dispose: () => void }> = [];
  for (const zone of model.zones) buildZone(root, zone, disposables);

  const radius = Math.max(model.radiusM, 6);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, radius * 40);
  camera.up.set(0, 0, 1); // Z vertical (frame ENU)
  camera.position.set(radius * 1.2, -radius * 1.6, radius * 1.3 + WALL_H_M);

  function buildRenderer(): boolean {
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: !opts.lowEnd, alpha: true });
    } catch {
      return false;
    }
    renderer.setPixelRatio(viewerDprCap(window.devicePixelRatio, opts.lowEnd));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    resize();
    return true;
  }

  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 0, WALL_H_M);
  controls.enableDamping = !opts.reducedMotion;
  controls.dampingFactor = 0.08;
  controls.autoRotate = false; // jamais de rotation automatique (lecture calme)
  controls.minDistance = Math.max(4, radius * 0.5);
  controls.maxDistance = radius * 8;
  controls.maxPolarAngle = Math.PI / 2 - 0.05; // jamais sous le sol
  controls.enablePan = true;
  controls.update();

  // ── Rendu À LA DEMANDE (WJ27) : on ne rend que quand quelque chose a changé.
  let rafId = 0;
  let dampingUntil = 0;
  function renderOnce(): void {
    if (disposed || glLost || !renderer) return;
    renderer.render(scene, camera);
  }
  function tick(): void {
    rafId = 0;
    if (disposed || glLost) return;
    const damping = controls.enableDamping && performance.now() < dampingUntil;
    controls.update();
    renderOnce();
    if (damping) scheduleRender();
  }
  function scheduleRender(): void {
    if (!rafId && !disposed) rafId = requestAnimationFrame(tick);
  }
  controls.addEventListener('change', scheduleRender);
  controls.addEventListener('start', () => {
    dampingUntil = Number.MAX_SAFE_INTEGER;
    scheduleRender();
  });
  controls.addEventListener('end', () => {
    // Laisse l'amortissement s'éteindre (~1 s) puis stoppe toute boucle.
    dampingUntil = performance.now() + (controls.enableDamping ? 1000 : 0);
    scheduleRender();
  });

  function resize(): void {
    if (!renderer) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (w === 0 || h === 0) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    scheduleRender();
  }
  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
  ro?.observe(container);

  // ── WJ27 — perte / restauration de contexte WebGL (mobile arrière-plan).
  function onContextLost(e: Event): void {
    e.preventDefault(); // impératif : sans lui, jamais de webglcontextrestored
    glLost = true;
    renderer?.dispose();
    renderer = null;
  }
  function onContextRestored(): void {
    if (disposed) return;
    if (buildRenderer()) {
      glLost = false;
      scheduleRender();
    } else {
      opts.onFail?.();
    }
  }
  canvas.addEventListener('webglcontextlost', onContextLost, false);
  canvas.addEventListener('webglcontextrestored', onContextRestored, false);

  if (!buildRenderer()) {
    canvas.remove();
    controls.dispose();
    for (const d of disposables) d.dispose();
    return null;
  }
  renderOnce();
  opts.onReady?.();

  function dispose(): void {
    if (disposed) return;
    disposed = true;
    if (rafId) cancelAnimationFrame(rafId);
    ro?.disconnect();
    canvas.removeEventListener('webglcontextlost', onContextLost, false);
    canvas.removeEventListener('webglcontextrestored', onContextRestored, false);
    controls.dispose();
    for (const d of disposables) d.dispose();
    renderer?.dispose();
    renderer = null;
    canvas.remove();
  }

  return { dispose };
}

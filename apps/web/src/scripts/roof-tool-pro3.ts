/**
 * Estimateur de toiture PILOTÉ PAR LA FACTURE — preview privé
 * /preview/toiture-3d-pro-3.
 *
 * Reprend le rendu haute fidélité de pro-2 (vrais panneaux Canadian Solar 720 W,
 * Three.js dans une couche MapLibre, vrai sud géo-ancré, vrai soleil/ombres) et y
 * branche le CERVEAU (src/lib/estimatorBrain.ts) : à partir du tracé + de la
 * latitude + de la facture, il classe les configurations (Sud optimal, Sud basse
 * inclinaison, Est-Ouest dos à dos), recommande la meilleure dimensionnée au
 * besoin, et rend en 3D la config choisie (Sud sur châssis lestés, ou Est-Ouest
 * en chevrons faces E/O). Chaque réglage RE-CALCULE depuis la table de productible
 * committée (instantané, aucun appel réseau par réglage) ; PVGIS live n'affine
 * qu'UNE fois la recommandation. Le diagnostic enrichi est seulement PRÉ-REMPLI
 * (jamais de lead posté). Aucune nouvelle dépendance.
 *
 * Voir apps/web/ESTIMATOR_BRAIN_NOTES.md et apps/web/SOLAR_3D_PRO2_NOTES.md.
 */
import maplibregl from 'maplibre-gl';
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import * as THREE from 'three';
import { PANEL2_THICK_M } from '../lib/roofPro2';
import {
  recommend,
  packConfig,
  productionKwh,
  billToAnnualKwh,
  annualSavingsMad,
  type Recommendation,
  type PackResult,
  type PanelGrid,
  type ConfigFamily,
} from '../lib/estimatorBrain';
import { type LngLat } from '../lib/roof';
import {
  obstacleRing,
  obstacleFromDrag,
  defaultObstacle,
  scaledObstacle,
  resizedObstacle,
  ringDimsM,
  OBSTACLE_STEP_FACTOR,
  type Obstacle,
} from '../lib/obstacles';

interface InitOptions {
  maptilerKey: string;
  reducedMotion: boolean;
  initialQuery?: string;
  onReady?: () => void;
}

const GOLD = '#f3cc66';
const MOROCCO_CENTER: [number, number] = [-7.09, 31.79];
const FLOOR_HEIGHT_M = 3;
const PITCH_VIEW = 58;
const DECK_THK = 0.06;
const FLOORS = 2;
const OBSTACLE_BOX_H_M = 0.8; // hauteur du volume d'obstacle rendu en 3D
const OBSTACLE_TAP_PX = 8; // en deçà : un clic/tap, au-delà : un glissé
const DEG2RAD = Math.PI / 180;
const WGS84_RADIUS = 6378137;
const DEG2M = DEG2RAD * WGS84_RADIUS;

let booted = false;

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);
const fmtMad = (n: number) => `${fmt(Math.round(n))} MAD`;

function makeCanadianPanelTexture(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 280;
  const ctx = c.getContext('2d')!;
  const g = ctx.createLinearGradient(0, 0, 512, 280);
  g.addColorStop(0, '#0c0c0f');
  g.addColorStop(1, '#050507');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 512, 280);
  const cols = 24;
  const rowsHalf = 3;
  const pad = 14;
  const seam = 6;
  const w = 512 - pad * 2;
  const hHalf = (280 - pad * 2 - seam) / 2;
  const cw = w / cols;
  const ch = hHalf / rowsHalf;
  ctx.strokeStyle = 'rgba(40,46,60,0.55)';
  ctx.lineWidth = 1;
  for (let half = 0; half < 2; half++) {
    const y0 = half === 0 ? pad : pad + hHalf + seam;
    for (let i = 0; i <= cols; i++) {
      const x = pad + i * cw;
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y0 + hHalf);
      ctx.stroke();
    }
    for (let j = 0; j <= rowsHalf; j++) {
      const y = y0 + j * ch;
      ctx.beginPath();
      ctx.moveTo(pad, y);
      ctx.lineTo(pad + w, y);
      ctx.stroke();
    }
  }
  ctx.strokeStyle = 'rgba(20,24,34,0.9)';
  ctx.lineWidth = seam;
  ctx.beginPath();
  ctx.moveTo(pad, 140);
  ctx.lineTo(512 - pad, 140);
  ctx.stroke();
  ctx.strokeStyle = 'rgba(150,156,168,0.85)';
  ctx.lineWidth = 10;
  ctx.strokeRect(5, 5, 502, 270);
  const tex = new THREE.Texture(c);
  tex.needsUpdate = true;
  tex.anisotropy = 8;
  return tex;
}

type TiltMode = 'reco' | number;
type OrientMode = 'auto' | 'portrait' | 'landscape';

export function initRoofToolPro3(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) {
    throw new Error('WebGL indisponible');
  }

  const nav = navigator as Navigator & { deviceMemory?: number };
  const lowEnd = (nav.deviceMemory != null && nav.deviceMemory <= 4) || (navigator.hardwareConcurrency || 8) <= 4;
  const shadowSize = lowEnd ? 1024 : 2048;

  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = maplibreCssUrl;
  document.head.appendChild(cssLink);

  const mapEl = $('rp3-map');
  const statusEl = $('rp3-status');
  const billEl = $<HTMLInputElement>('rp3-bill');
  const billKwhEl = $('rp3-bill-kwh');
  const finishBtn = $<HTMLButtonElement>('rp3-finish');
  const clearBtn = $<HTMLButtonElement>('rp3-clear');
  const searchForm = $<HTMLFormElement>('rp3-search');
  const addressEl = $<HTMLInputElement>('rp3-address');
  const configPanel = $('rp3-config');
  const compassArrow = $('rp3-compass-arrow');
  const obstacleBtn = $<HTMLButtonElement>('rp3-obstacle');
  const obstacleClearBtn = $<HTMLButtonElement>('rp3-obstacle-clear');
  const obsEditPanel = $('rp3-obs-edit');
  const obsLengthEl = $<HTMLInputElement>('rp3-obs-length');
  const obsWidthEl = $<HTMLInputElement>('rp3-obs-width');
  const obsDimsEl = $('rp3-obs-dims');
  const obsDeleteBtn = $<HTMLButtonElement>('rp3-obs-delete');
  const obsPlusBtn = $<HTMLButtonElement>('rp3-obs-plus');
  const obsMinusBtn = $<HTMLButtonElement>('rp3-obs-minus');
  if (!mapEl) return;

  const setStatus = (msg: string) => {
    if (statusEl) statusEl.textContent = msg;
  };

  // — État —
  let vertices: LngLat[] = [];
  let closed = false;
  let clickTimer: ReturnType<typeof setTimeout> | null = null;
  let obstacleMode = false;
  let obstacles: Obstacle[] = [];
  let selectedObsId: string | null = null;
  let obsCounter = 0;
  // Glissé en cours pour dessiner un obstacle.
  let drawStart: { lngLat: LngLat; point: maplibregl.Point } | null = null;
  let drawing = false;
  let suppressClick = false; // ignore le « click » de synthèse après un glissé
  let rec: Recommendation | null = null;

  // Les obstacles sont stockés par centre + dimensions ; le cerveau reçoit leurs
  // rectangles lng/lat comme obstructions (zones d'exclusion).
  const obstructionRings = (): LngLat[][] => obstacles.map(obstacleRing);
  const fmt1 = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const dimsLabel = (o: Obstacle) => `${fmt1(o.lengthM)} × ${fmt1(o.widthM)} m`;
  let centroid: LngLat = [0, 0];
  let centroidLat = 33.5;
  let useRecommended = true;
  let sel: { family: ConfigFamily; tilt: TiltMode; orient: OrientMode } = { family: 'south', tilt: 'reco', orient: 'auto' };
  let pvgisKwh: number | null = null; // affinage live de la recommandation

  const monthlyBill = (): number => {
    const raw = parseFloat((billEl?.value || '').replace(/\s/g, '').replace(',', '.'));
    return Number.isFinite(raw) && raw > 0 ? raw : 0;
  };

  // — Three.js —
  const map = new maplibregl.Map({
    container: mapEl,
    style: `https://api.maptiler.com/maps/hybrid/style.json?key=${encodeURIComponent(opts.maptilerKey)}`,
    center: MOROCCO_CENTER,
    zoom: 5,
    pitch: 0,
    maxPitch: 75,
    attributionControl: { compact: true },
    fadeDuration: opts.reducedMotion ? 0 : 300,
  });
  opts.onReady?.();

  map.on('error', (e: unknown) => {
    const msg = (e as { error?: { message?: string } } | undefined)?.error?.message ?? e;
    console.warn('[roof-tool-pro3] erreur carte (non bloquante) :', msg);
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.doubleClickZoom.disable();

  const updateCompass = () => {
    if (compassArrow) compassArrow.style.transform = `rotate(${-map.getBearing()}deg)`;
  };
  map.on('rotate', updateCompass);
  map.on('pitch', updateCompass);
  updateCompass();

  let renderer: THREE.WebGLRenderer | null = null;
  let scene: THREE.Scene | null = null;
  let sceneRoot: THREE.Group | null = null;
  let threeCamera: THREE.Camera | null = null;
  let sun: THREE.DirectionalLight | null = null;
  let modelMatrix: THREE.Matrix4 | null = null;
  const panelTex = makeCanadianPanelTexture();

  const AXIS_X = new THREE.Vector3(1, 0, 0);
  const AXIS_Z = new THREE.Vector3(0, 0, 1);
  const _q = new THREE.Quaternion();
  const _qz = new THREE.Quaternion();
  const _qx = new THREE.Quaternion();
  const _scl = new THREE.Vector3(1, 1, 1);
  const compose = (px: number, py: number, pz: number, rotZ: number, rotX: number): THREE.Matrix4 => {
    _qz.setFromAxisAngle(AXIS_Z, rotZ);
    _qx.setFromAxisAngle(AXIS_X, rotX);
    _q.copy(_qz).multiply(_qx);
    return new THREE.Matrix4().compose(new THREE.Vector3(px, py, pz), _q, _scl);
  };

  const empty = { type: 'FeatureCollection', features: [] } as const;

  const customLayer = {
    id: 'rp3-3d',
    type: 'custom' as const,
    renderingMode: '3d' as const,
    onAdd(_m: maplibregl.Map, gl: WebGLRenderingContext | WebGL2RenderingContext) {
      threeCamera = new THREE.Camera();
      scene = new THREE.Scene();
      sceneRoot = new THREE.Group();
      scene.add(sceneRoot);
      scene.add(new THREE.AmbientLight(0xb9c8ee, 0.5));
      scene.add(new THREE.HemisphereLight(0xcfe0ff, 0x20242e, 0.5));
      sun = new THREE.DirectionalLight(0xfff2d6, 2.5);
      sun.castShadow = true;
      sun.shadow.mapSize.set(shadowSize, shadowSize);
      sun.shadow.bias = -0.0005;
      sun.shadow.normalBias = 0.03;
      scene.add(sun);
      scene.add(sun.target);
      renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: !lowEnd });
      renderer.autoClear = false;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
    },
    render(_gl: WebGLRenderingContext | WebGL2RenderingContext, args: maplibregl.CustomRenderMethodInput) {
      if (!renderer || !scene || !threeCamera || !modelMatrix) return;
      const m = new THREE.Matrix4().fromArray(Array.from(args.defaultProjectionData.mainMatrix));
      threeCamera.projectionMatrix = m.multiply(modelMatrix);
      renderer.resetState();
      renderer.render(scene, threeCamera);
    },
  };

  function disposeScene() {
    if (!sceneRoot) return;
    for (const child of [...sceneRoot.children]) {
      const mesh = child as THREE.Mesh;
      mesh.geometry?.dispose?.();
      const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
      else mat?.dispose?.();
      sceneRoot.remove(child);
    }
  }

  function setOrigin(origin: LngLat) {
    const mc = maplibregl.MercatorCoordinate.fromLngLat(origin, 0);
    const sUnit = mc.meterInMercatorCoordinateUnits();
    modelMatrix = new THREE.Matrix4().makeTranslation(mc.x, mc.y, mc.z).scale(new THREE.Vector3(sUnit, -sUnit, sUnit));
  }

  function makeIM(geo: THREE.BufferGeometry, mat: THREE.Material | THREE.Material[], matrices: THREE.Matrix4[], cast = true, receive = false): THREE.InstancedMesh | null {
    if (!matrices.length) return null;
    const im = new THREE.InstancedMesh(geo, mat as THREE.Material, matrices.length);
    im.castShadow = cast;
    im.receiveShadow = receive;
    for (let i = 0; i < matrices.length; i++) im.setMatrixAt(i, matrices[i]);
    im.instanceMatrix.needsUpdate = true;
    return im;
  }

  // — Rendu d'une config (Sud sur châssis OU Est-Ouest en chevrons) —
  function renderScene(pack: PackResult, grid: PanelGrid, tiltDeg: number, family: ConfigFamily, maxCount: number) {
    if (!sceneRoot || !sun) return;
    setOrigin(pack.origin);
    disposeScene();

    const wallH = FLOORS * FLOOR_HEIGHT_M;
    const ring = pack.ringENU;

    // Bâtiment
    const shape = new THREE.Shape();
    ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
    shape.closePath();
    const building = new THREE.Mesh(
      new THREE.ExtrudeGeometry(shape, { depth: wallH, bevelEnabled: false }),
      new THREE.MeshStandardMaterial({ color: 0xe2e7f2, roughness: 0.85, metalness: 0 }),
    );
    building.castShadow = true;
    building.receiveShadow = true;
    sceneRoot.add(building);

    const baseZ = wallH + DECK_THK;
    const deck = new THREE.Mesh(
      new THREE.ShapeGeometry(shape),
      new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 }),
    );
    deck.position.z = wallH + 0.02;
    deck.receiveShadow = true;
    sceneRoot.add(deck);

    // Axes de visée à partir de l'azimut de la famille.
    const azRad = pack.azimuthDeg * DEG2RAD;
    const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
    const u: [number, number] = [-f[1], f[0]];
    const rowAngleRad = Math.atan2(u[1], u[0]);
    const ca = Math.cos(rowAngleRad);
    const sa = Math.sin(rowAngleRad);
    const rx = (lx: number, ly: number): [number, number] => [lx * ca - ly * sa, lx * sa + ly * ca];

    const alongRow = grid.rowWidthM;
    const slope = grid.slopeLenM;
    const tilt = tiltDeg * DEG2RAD;
    const rise = slope * Math.sin(tilt);
    const depthFootprint = slope * Math.cos(tilt);
    const frontStrut = 0.1;
    const halfAlong = alongRow / 2;
    const halfDepth = depthFootprint / 2;

    const glassMat = new THREE.MeshPhysicalMaterial({ map: panelTex, color: 0xffffff, metalness: 0.1, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08 });
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x9aa0aa, metalness: 0.85, roughness: 0.35 });
    const backMat = new THREE.MeshStandardMaterial({ color: 0xe6e8ee, metalness: 0.1, roughness: 0.6 });
    const panelMats = [frameMat, frameMat, frameMat, frameMat, glassMat, backMat];
    const panelGeo = new THREE.BoxGeometry(alongRow, slope, PANEL2_THICK_M);
    const jboxGeo = new THREE.BoxGeometry(0.4, 0.12, 0.035);
    jboxGeo.translate(0, 0, -(PANEL2_THICK_M / 2 + 0.02));
    const jboxMat = new THREE.MeshStandardMaterial({ color: 0x15171c, metalness: 0.3, roughness: 0.6 });
    const rackMat = new THREE.MeshStandardMaterial({ color: 0x40454f, metalness: 0.75, roughness: 0.4 });
    const ballastMat = new THREE.MeshStandardMaterial({ color: 0x9b9a90, metalness: 0, roughness: 0.95 });

    const panels = grid.panels.slice(0, Math.max(0, maxCount));
    const panelMatsArr: THREE.Matrix4[] = [];
    const frontMats: THREE.Matrix4[] = [];
    const backMats: THREE.Matrix4[] = [];
    const railMats: THREE.Matrix4[] = [];
    const ballastMats: THREE.Matrix4[] = [];
    const railGeo = new THREE.BoxGeometry(0.05, slope, 0.05);
    const frontGeo = new THREE.BoxGeometry(0.06, 0.06, frontStrut);
    const backGeo = new THREE.BoxGeometry(0.06, 0.06, frontStrut + rise);
    const ballastGeo = new THREE.BoxGeometry(0.34, 0.18, 0.12);
    const ends = [-halfAlong + 0.08, 0, halfAlong - 0.08];

    for (const p of panels) {
      // Pour l'Est-Ouest : le sens d'inclinaison vient de la FACE du panneau
      // (chevrons dos à dos faces E/O), fournie par le cerveau. Sud : tilt simple.
      const signedTilt = family === 'eastwest' ? (p.face === 'E' ? -tilt : tilt) : tilt;
      const pZ = baseZ + frontStrut + rise / 2 + 0.07;
      panelMatsArr.push(compose(p.cx, p.cy, pZ, rowAngleRad, signedTilt));
      for (const xe of ends) {
        const lowDepth = signedTilt >= 0 ? -halfDepth : halfDepth;
        const highDepth = -lowDepth;
        const fpt = rx(xe, lowDepth);
        frontMats.push(compose(p.cx + fpt[0], p.cy + fpt[1], baseZ + frontStrut / 2, rowAngleRad, 0));
        const bpt = rx(xe, highDepth);
        backMats.push(compose(p.cx + bpt[0], p.cy + bpt[1], baseZ + (frontStrut + rise) / 2, rowAngleRad, 0));
        const cpt = rx(xe, 0);
        railMats.push(compose(p.cx + cpt[0], p.cy + cpt[1], baseZ + frontStrut + rise / 2, rowAngleRad, signedTilt));
      }
      for (const xe of [-halfAlong + 0.08, halfAlong - 0.08]) {
        const bf = rx(xe, -halfDepth - 0.02);
        ballastMats.push(compose(p.cx + bf[0], p.cy + bf[1], baseZ + 0.06, rowAngleRad, 0));
        const bb = rx(xe, halfDepth + 0.02);
        ballastMats.push(compose(p.cx + bb[0], p.cy + bb[1], baseZ + 0.06, rowAngleRad, 0));
      }
    }

    const meshes = [
      makeIM(panelGeo, panelMats, panelMatsArr, true, false),
      makeIM(jboxGeo, jboxMat, panelMatsArr, true, false),
      makeIM(frontGeo, rackMat, frontMats, true, false),
      makeIM(backGeo, rackMat, backMats, true, false),
      makeIM(railGeo, rackMat, railMats, true, false),
      makeIM(ballastGeo, ballastMat, ballastMats, true, true),
    ];
    for (const me of meshes) if (me) sceneRoot.add(me);

    // Obstacles marqués : un volume sombre par obstacle, à sa VRAIE taille
    // (largeur E-O × longueur N-S), posé sur le toit, qui projette une ombre.
    if (obstacles.length) {
      const obsMat = new THREE.MeshStandardMaterial({ color: 0x2a2f3a, metalness: 0.2, roughness: 0.8 });
      const cosLat = Math.cos(pack.origin[1] * DEG2RAD);
      for (const o of obstacles) {
        const ox = (o.centerLng - pack.origin[0]) * DEG2M * cosLat;
        const oy = (o.centerLat - pack.origin[1]) * DEG2M;
        const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, OBSTACLE_BOX_H_M);
        const mesh = new THREE.Mesh(geo, obsMat);
        mesh.position.set(ox, oy, wallH + OBSTACLE_BOX_H_M / 2 + 0.05);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        sceneRoot.add(mesh);
      }
    }

    // — Soleil d'affichage (matin clair, élévation liée à la latitude) —
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const [x, y] of ring) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
    const cxm = (minX + maxX) / 2;
    const cym = (minY + maxY) / 2;
    const span = Math.max(maxX - minX, maxY - minY, wallH) + 8;
    const roofZ = wallH + 0.5;
    const latAbs = Math.abs(pack.origin[1]);
    const dispElevDeg = Math.max(28, (90 - latAbs) * 0.62);
    const dispAzDeg = pack.azimuthDeg - 45;
    const azR = dispAzDeg * DEG2RAD;
    const elR = dispElevDeg * DEG2RAD;
    const dist = span * 2.5;
    sun.target.position.set(cxm, cym, roofZ);
    sun.position.set(cxm + Math.sin(azR) * Math.cos(elR) * dist, cym + Math.cos(azR) * Math.cos(elR) * dist, roofZ + Math.sin(elR) * dist);
    const sc = sun.shadow.camera as THREE.OrthographicCamera;
    sc.left = -span;
    sc.right = span;
    sc.top = span;
    sc.bottom = -span;
    sc.near = 0.5;
    sc.far = dist * 2;
    sc.updateProjectionMatrix();

    map.triggerRepaint();
  }

  // — Carte / tracé —
  map.on('load', () => {
    map.addSource('rp3-line', { type: 'geojson', data: empty as never });
    map.addSource('rp3-pts', { type: 'geojson', data: empty as never });
    map.addSource('rp3-obs', { type: 'geojson', data: empty as never });
    map.addSource('rp3-obs-preview', { type: 'geojson', data: empty as never });
    map.addLayer({ id: 'rp3-line', type: 'line', source: 'rp3-line', paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] } });
    map.addLayer({ id: 'rp3-pts', type: 'circle', source: 'rp3-pts', paint: { 'circle-radius': 5, 'circle-color': GOLD, 'circle-stroke-color': '#070b1d', 'circle-stroke-width': 1.5 } });
    // Obstacles : remplissage (plus vif si sélectionné) + contour + étiquette L×l.
    map.addLayer({
      id: 'rp3-obs',
      type: 'fill',
      source: 'rp3-obs',
      paint: { 'fill-color': '#ff6b6b', 'fill-opacity': ['case', ['get', 'selected'], 0.5, 0.3] },
    });
    map.addLayer({
      id: 'rp3-obs-outline',
      type: 'line',
      source: 'rp3-obs',
      paint: { 'line-color': ['case', ['get', 'selected'], GOLD, '#ff6b6b'], 'line-width': ['case', ['get', 'selected'], 3, 1.5] },
    });
    map.addLayer({
      id: 'rp3-obs-label',
      type: 'symbol',
      source: 'rp3-obs',
      layout: { 'text-field': ['get', 'dims'], 'text-size': 13, 'text-font': ['Open Sans Bold', 'Noto Sans Bold'], 'text-allow-overlap': true, 'symbol-placement': 'point' },
      paint: { 'text-color': '#ffffff', 'text-halo-color': '#070b1d', 'text-halo-width': 1.6 },
    });
    map.addLayer({
      id: 'rp3-obs-preview',
      type: 'line',
      source: 'rp3-obs-preview',
      paint: { 'line-color': GOLD, 'line-width': 2, 'line-dasharray': [1.5, 1] },
    });
    map.addLayer(customLayer);
    updateCompass();
    if (opts.initialQuery) void geocode(opts.initialQuery);
    else setStatus('Cherchez votre adresse, puis cliquez les coins de votre toit.');
  });

  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  function redrawTrace() {
    srcOf('rp3-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: vertices }, properties: {} } as never);
    srcOf('rp3-pts')?.setData({ type: 'FeatureCollection', features: vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })) } as never);
    if (finishBtn) finishBtn.disabled = vertices.length < 3 || closed;
  }

  function redrawObstacles() {
    srcOf('rp3-obs')?.setData({
      type: 'FeatureCollection',
      features: obstacles.map((o) => {
        const ring = obstacleRing(o);
        return {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[...ring, ring[0]]] },
          properties: { id: o.id, selected: o.id === selectedObsId, dims: dimsLabel(o) },
        };
      }),
    } as never);
  }

  function setPreviewRect(a: LngLat, b: LngLat) {
    const ring: LngLat[] = [a, [b[0], a[1]], b, [a[0], b[1]], a];
    srcOf('rp3-obs-preview')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: ring }, properties: {} } as never);
  }
  function clearPreview() {
    srcOf('rp3-obs-preview')?.setData(empty as never);
  }

  function addVertex(v: LngLat) {
    if (closed) return;
    vertices.push(v);
    redrawTrace();
    if (vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit et lancer le calcul.');
    else setStatus(`Coin ${vertices.length} placé — continuez à tracer le contour.`);
  }

  // — Sélection + édition d'un obstacle —
  function syncObsEdit() {
    const o = obstacles.find((x) => x.id === selectedObsId) ?? null;
    if (obsEditPanel) obsEditPanel.hidden = !o;
    if (!o) return;
    if (obsLengthEl && document.activeElement !== obsLengthEl) obsLengthEl.value = fmt1(o.lengthM);
    if (obsWidthEl && document.activeElement !== obsWidthEl) obsWidthEl.value = fmt1(o.widthM);
    if (obsDimsEl) obsDimsEl.textContent = dimsLabel(o);
  }

  function selectObstacle(id: string | null) {
    selectedObsId = id;
    redrawObstacles();
    syncObsEdit();
  }

  /** Remplace l'obstacle sélectionné par une version transformée, puis recalcule. */
  function updateSelected(transform: (o: Obstacle) => Obstacle) {
    const idx = obstacles.findIndex((x) => x.id === selectedObsId);
    if (idx < 0) return;
    obstacles[idx] = transform(obstacles[idx]);
    redrawObstacles();
    syncObsEdit();
    recompute();
  }

  function deleteSelected() {
    if (!selectedObsId) return;
    obstacles = obstacles.filter((x) => x.id !== selectedObsId);
    selectedObsId = null;
    redrawObstacles();
    syncObsEdit();
    recompute();
  }

  function addObstacle(o: Obstacle) {
    obstacles.push(o);
    selectedObsId = o.id;
    redrawObstacles();
    syncObsEdit();
    recompute();
  }

  /** Obstacle touché au point écran `pt`, ou null. */
  function obstacleAtPoint(pt: maplibregl.Point): string | null {
    const hits = map.queryRenderedFeatures(pt, { layers: ['rp3-obs'] });
    const id = hits[0]?.properties?.id;
    return typeof id === 'string' ? id : null;
  }

  // — Sélection de config → grille —
  function tiltOf(family: ConfigFamily): number {
    if (sel.tilt === 'reco') {
      if (useRecommended && rec) return rec.recommended.tiltDeg;
      return family === 'eastwest' ? 10 : (rec?.maxPerPanelTiltDeg ?? 29);
    }
    return sel.tilt;
  }

  function gridFor(pack: PackResult): PanelGrid {
    if (sel.orient === 'portrait') return pack.portrait;
    if (sel.orient === 'landscape') return pack.landscape;
    return pack.best;
  }

  function renderSelection() {
    if (!closed || vertices.length < 3 || !rec) return;
    const ring: LngLat[] = [...vertices];

    if (useRecommended) {
      const r = rec.recommended;
      const pack = packConfig(ring, centroidLat, { family: r.family, tiltDeg: r.tiltDeg, obstructions: obstructionRings() });
      const grid = r.panelOrientation === 'portrait' ? pack.portrait : pack.landscape;
      renderScene(pack, grid, r.tiltDeg, r.family, r.count);
      paintRecoCard();
      highlightRow(r.id);
      return;
    }

    const family = sel.family;
    const tiltDeg = tiltOf(family);
    const pack = packConfig(ring, centroidLat, { family, tiltDeg, obstructions: obstructionRings() });
    const grid = gridFor(pack);
    const annualKwh = productionKwh(centroidLat, family, tiltDeg, grid.kwc);
    const target = billToAnnualKwh(monthlyBill());
    const savings = annualSavingsMad(annualKwh, target); // plafonné à la conso
    renderScene(pack, grid, tiltDeg, family, grid.count);
    paintCard({
      title: `${family === 'eastwest' ? 'Est-Ouest' : 'Plein sud'} ${tiltDeg}° · ${grid.panelOrientation === 'portrait' ? 'portrait' : 'paysage'}`,
      isReco: false,
      count: grid.count,
      kwc: grid.kwc,
      annualKwh,
      pct: target > 0 ? (annualKwh / target) * 100 : 0,
      savingsLow: savings.low,
      savingsHigh: savings.high,
      why: 'Vous explorez une configuration manuelle. Le « Recommandé » reste le meilleur compromis pour votre facture.',
    });
    highlightRow(null);
  }

  interface CardData {
    title: string;
    isReco: boolean;
    count: number;
    kwc: number;
    annualKwh: number;
    pct: number;
    savingsLow: number;
    savingsHigh: number;
    why: string;
  }

  function paintCard(d: CardData, sourceLabel?: string) {
    const set = (id: string, v: string) => {
      const el = $(id);
      if (el) el.textContent = v;
    };
    set('rp3-reco-title', d.isReco ? `${d.title}  ·  ✓ recommandé` : d.title);
    set('rp3-reco-kwc', `${d.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
    set('rp3-reco-panels', `${fmt(d.count)} × 720 W`);
    set('rp3-reco-prod', d.annualKwh > 0 ? `${fmt(Math.round(d.annualKwh))} kWh/an` : '—');
    set('rp3-reco-cover', d.pct > 0 ? `${Math.round(d.pct)} %` : '—');
    set('rp3-reco-savings', `${fmtMad(d.savingsLow)} – ${fmtMad(d.savingsHigh)}/an`);
    const why = $('rp3-reco-why');
    if (why) why.textContent = d.why + (sourceLabel ? ` ${sourceLabel}` : '');
    const bif = $('rp3-reco-bifacial');
    if (bif) {
      const gain = d.annualKwh * 0.05;
      bif.textContent = d.annualKwh > 0 ? `+ gain bifacial (estimation prudente, ~+5 %) : ~${fmt(Math.round(gain))} kWh/an — non compté dans le chiffre ci-dessus.` : '';
    }
    $('rp3-results')?.classList.add('rp3-results--ready');
    const cta = $<HTMLButtonElement>('rp3-cta');
    if (cta && d.count > 0) {
      cta.hidden = false;
      cta.onclick = () => prefillLead(d);
    }
  }

  function paintRecoCard() {
    if (!rec) return;
    const r = rec.recommended;
    const annual = pvgisKwh ?? r.annualKwh;
    const target = rec.targetAnnualKwh;
    const savings = annualSavingsMad(annual, target); // plafonné à la conso
    paintCard(
      {
        title: r.label,
        isReco: true,
        count: r.count,
        kwc: r.kwc,
        annualKwh: annual,
        pct: target > 0 ? (annual / target) * 100 : r.pctOfTarget,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why: r.notes,
      },
      pvgisKwh != null ? '(production affinée via PVGIS)' : '(production estimée — table par latitude)',
    );
    const maxline = $('rp3-maxline');
    if (maxline) {
      maxline.textContent = `Rendement max par panneau : ~${rec.maxPerPanelTiltDeg}° plein sud. Énergie totale max sur CE toit : ~${rec.maxRoofEnergyTiltDeg}° (un toit limité gagne à être plus plat pour loger plus de panneaux).`;
    }
  }

  // — Comparatif —
  function paintComparison() {
    if (!rec) return;
    const tbody = $('rp3-compare');
    const wrap = $('rp3-compare-wrap');
    if (!tbody) return;
    tbody.innerHTML = '';
    for (const c of rec.comparison) {
      const tr = document.createElement('tr');
      tr.dataset.id = c.id;
      const cover = rec.targetAnnualKwh > 0 ? Math.round((c.annualKwh / rec.targetAnnualKwh) * 100) : 0;
      tr.innerHTML =
        `<td>${c.label}${c.id === rec.recommended.id ? ' <span style="color:var(--color-brass-300)">✓</span>' : ''}</td>` +
        `<td class="num">${fmt(c.count)}</td>` +
        `<td class="num">${c.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })}</td>` +
        `<td class="num">${fmt(Math.round(c.annualKwh))}</td>` +
        `<td class="num">${cover} %</td>` +
        `<td class="num">${fmtMad(c.savingsLow)} – ${fmtMad(c.savingsHigh)}</td>`;
      tr.addEventListener('click', () => {
        useRecommended = false;
        sel = { family: c.family, tilt: c.tiltDeg, orient: 'auto' };
        syncChips();
        renderSelection();
        highlightRow(c.id);
      });
      tbody.appendChild(tr);
    }
    if (wrap) wrap.hidden = false;
  }

  function highlightRow(id: string | null) {
    const tbody = $('rp3-compare');
    if (!tbody) return;
    for (const tr of Array.from(tbody.querySelectorAll('tr'))) {
      (tr as HTMLElement).dataset.active = (id != null && (tr as HTMLElement).dataset.id === id) ? 'true' : 'false';
    }
  }

  // — Recalcul complet (cerveau) —
  function recompute() {
    if (!closed || vertices.length < 3) return;
    const ring: LngLat[] = [...vertices];
    const bill = monthlyBill();
    rec = recommend(ring, centroidLat, bill, obstructionRings());
    pvgisKwh = null;
    paintComparison();
    renderSelection();
    if (rec.recommended.count === 0) {
      setStatus('Surface trop petite pour une rangée — élargissez le tracé.');
    } else if (rec.roofLimited) {
      setStatus('Calcul prêt. Ce toit ne couvre pas toute la facture : l’Est-Ouest maximise ce qui est possible.');
    } else {
      setStatus('Calcul prêt. Comparez les configurations, faites pivoter la 3D, puis recevez l’étude.');
    }
    // Affinage PVGIS (une seule fois) de la recommandation.
    if (rec.recommended.count > 0) void refinePvgis();
  }

  async function refinePvgis() {
    if (!rec) return;
    const r = rec.recommended;
    const legs =
      r.family === 'eastwest'
        ? [
            { kwc: r.kwc / 2, tiltDeg: r.tiltDeg, aspect: -90 },
            { kwc: r.kwc / 2, tiltDeg: r.tiltDeg, aspect: 90 },
          ]
        : [{ kwc: r.kwc, tiltDeg: r.tiltDeg, aspect: 0 }];
    try {
      const res = await fetch('/api/roof-yield', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat: centroid[1], lon: centroid[0], legs }),
      });
      const data = await res.json();
      if (res.ok && data.ok && typeof data.annualKwh === 'number') {
        pvgisKwh = data.annualKwh;
        if (useRecommended) paintRecoCard();
      }
    } catch {
      /* la table committée a déjà fourni un chiffre — pas d'erreur visible */
    }
  }

  function prefillLead(d: CardData) {
    // Pré-remplit le diagnostic enrichi — RÉUTILISE le même formulaire et toute sa
    // plomberie (seuil 1 000 MAD, consentement, webhook, CAPI) : on n'écrit que
    // dans ses champs, on ne poste AUCUN lead ici.
    const area = $<HTMLInputElement>('lf-area');
    const orient = $<HTMLSelectElement>('lf-orient');
    const kwc = $<HTMLInputElement>('lf-kwc-est');
    if (area) area.value = String(Math.round(geodesicArea()));
    if (orient) orient.value = 'sud'; // Sud et Est-Ouest se rapportent tous deux au sud
    if (kwc) kwc.value = String(Math.round(d.kwc * 100) / 100);
    const details = (area?.closest('details') as HTMLDetailsElement | null) ?? null;
    if (details) details.open = true;
    document.getElementById('simulateur')?.scrollIntoView({ behavior: opts.reducedMotion ? 'auto' : 'smooth', block: 'start' });
  }

  function geodesicArea(): number {
    // surface tracée (m²) pour pré-remplir le champ « surface toit »
    const ring = vertices;
    if (ring.length < 3) return 0;
    let total = 0;
    for (let i = 0; i < ring.length; i++) {
      const [lng1, lat1] = ring[i];
      const [lng2, lat2] = ring[(i + 1) % ring.length];
      total += (lng2 - lng1) * DEG2RAD * (2 + Math.sin(lat1 * DEG2RAD) + Math.sin(lat2 * DEG2RAD));
    }
    return Math.abs((total * WGS84_RADIUS * WGS84_RADIUS) / 2);
  }

  // — Fermeture du tracé —
  function close() {
    if (closed || vertices.length < 3) return;
    closed = true;
    if (finishBtn) finishBtn.disabled = true;
    let lng = 0;
    let lat = 0;
    for (const [x, y] of vertices) {
      lng += x;
      lat += y;
    }
    centroid = [lng / vertices.length, lat / vertices.length];
    centroidLat = centroid[1];
    srcOf('rp3-line')?.setData(empty as never);
    srcOf('rp3-pts')?.setData(empty as never);
    if (configPanel) configPanel.hidden = false;
    go3DView();
    recompute();
  }

  function go3DView() {
    const target = { center: centroid, pitch: PITCH_VIEW } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 1100, essential: true });
  }

  function reset() {
    vertices = [];
    closed = false;
    obstacles = [];
    selectedObsId = null;
    setObstacleMode(false);
    drawing = false;
    drawStart = null;
    rec = null;
    pvgisKwh = null;
    useRecommended = true;
    sel = { family: 'south', tilt: 'reco', orient: 'auto' };
    srcOf('rp3-line')?.setData(empty as never);
    srcOf('rp3-pts')?.setData(empty as never);
    clearPreview();
    redrawObstacles();
    syncObsEdit();
    disposeScene();
    modelMatrix = null;
    map.triggerRepaint();
    if (configPanel) configPanel.hidden = true;
    if (finishBtn) finishBtn.disabled = true;
    const wrap = $('rp3-compare-wrap');
    if (wrap) wrap.hidden = true;
    $('rp3-results')?.classList.remove('rp3-results--ready');
    const cta = $<HTMLButtonElement>('rp3-cta');
    if (cta) cta.hidden = true;
    syncChips();
    const target = { pitch: 0, bearing: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 600 });
    updateCompass();
    setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
  }

  // — Mode obstacle : on désactive le pan pour glisser-dessiner le rectangle —
  function setObstacleMode(on: boolean) {
    obstacleMode = on;
    obstacleBtn?.setAttribute('aria-pressed', String(on));
    if (on) {
      map.dragPan.disable();
      map.getCanvas().style.cursor = 'crosshair';
    } else {
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      drawing = false;
      drawStart = null;
      clearPreview();
    }
  }

  let lastDraw: LngLat | null = null;
  function beginDraw(lngLat: LngLat, point: maplibregl.Point) {
    if (!obstacleMode || !closed) return;
    drawStart = { lngLat, point };
    drawing = true;
    lastDraw = lngLat;
  }
  function moveDraw(lngLat: LngLat) {
    if (!drawing || !drawStart) return;
    lastDraw = lngLat;
    setPreviewRect(drawStart.lngLat, lngLat);
  }
  function endDraw(lngLat: LngLat, point: maplibregl.Point) {
    if (!drawing || !drawStart) return;
    drawing = false;
    clearPreview();
    const start = drawStart;
    drawStart = null;
    suppressClick = true;
    const end = lngLat ?? lastDraw ?? start.lngLat;
    const dx = Math.abs(point.x - start.point.x);
    const dy = Math.abs(point.y - start.point.y);
    const id = `obs-${++obsCounter}`;
    if (dx < OBSTACLE_TAP_PX && dy < OBSTACLE_TAP_PX) {
      // simple tap : sélectionne un obstacle existant, sinon en crée un par défaut
      const hit = obstacleAtPoint(point);
      if (hit) {
        setObstacleMode(false);
        selectObstacle(hit);
        setStatus('Obstacle sélectionné — ajustez sa taille au doigt ou au clavier.');
        return;
      }
      addObstacle(defaultObstacle(id, end));
    } else {
      addObstacle(obstacleFromDrag(id, start.lngLat, end));
    }
    setObstacleMode(false);
    setStatus('Obstacle ajouté — le calepinage l’évite. Touchez-le pour l’ajuster, ou ajoutez-en un autre.');
  }

  // — Interactions carte —
  map.on('mousedown', (e) => {
    suppressClick = false;
    if (obstacleMode) beginDraw([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('mousemove', (e) => {
    if (drawing) moveDraw([e.lngLat.lng, e.lngLat.lat]);
  });
  map.on('mouseup', (e) => {
    if (drawing) endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('touchstart', (e) => {
    suppressClick = false;
    if (obstacleMode) beginDraw([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('touchmove', (e) => {
    if (drawing) {
      e.preventDefault();
      moveDraw([e.lngLat.lng, e.lngLat.lat]);
    }
  });
  map.on('touchend', (e) => {
    if (drawing) endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
  });

  map.on('click', (e) => {
    if (suppressClick) {
      suppressClick = false;
      return;
    }
    if (obstacleMode) return; // le glissé gère le dessin
    const lngLat: LngLat = [e.lngLat.lng, e.lngLat.lat];
    if (closed) {
      // sélection/désélection d'un obstacle existant
      selectObstacle(obstacleAtPoint(e.point));
      return;
    }
    if (clickTimer) return;
    clickTimer = setTimeout(() => {
      clickTimer = null;
      addVertex(lngLat);
    }, 240);
  });
  map.on('dblclick', (e) => {
    e.preventDefault();
    if (clickTimer) {
      clearTimeout(clickTimer);
      clickTimer = null;
    }
    close();
  });

  finishBtn?.addEventListener('click', close);
  clearBtn?.addEventListener('click', reset);

  // — Facture —
  function updateBillKwh() {
    const kwh = billToAnnualKwh(monthlyBill());
    if (billKwhEl) billKwhEl.textContent = kwh > 0 ? `${fmt(Math.round(kwh))} kWh` : '—';
  }
  billEl?.addEventListener('input', () => {
    updateBillKwh();
    if (closed) recompute();
  });
  updateBillKwh();

  // — Chips de config —
  function syncChips() {
    document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => {
      const active = !useRecommended && b.dataset.family === sel.family;
      b.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll<HTMLButtonElement>('[data-tilt]').forEach((b) => {
      const val = b.dataset.tilt === 'reco' ? 'reco' : Number(b.dataset.tilt);
      const active = useRecommended ? b.dataset.tilt === 'reco' : sel.tilt === val;
      b.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) => {
      // En mode recommandé, l'orientation panneau est « auto » par défaut.
      const effOrient = useRecommended ? 'auto' : sel.orient;
      b.setAttribute('aria-pressed', String(b.dataset.orient === effOrient));
    });
  }

  document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => {
    b.addEventListener('click', () => {
      useRecommended = false;
      sel = { ...sel, family: b.dataset.family as ConfigFamily };
      if (sel.tilt === 'reco') sel.tilt = sel.family === 'eastwest' ? 10 : (rec?.maxPerPanelTiltDeg ?? 29);
      syncChips();
      renderSelection();
    });
  });
  document.querySelectorAll<HTMLButtonElement>('[data-tilt]').forEach((b) => {
    b.addEventListener('click', () => {
      if (b.dataset.tilt === 'reco') {
        useRecommended = true;
        sel = { family: rec?.recommended.family ?? 'south', tilt: 'reco', orient: 'auto' };
      } else {
        useRecommended = false;
        sel = { ...sel, tilt: Number(b.dataset.tilt) };
      }
      syncChips();
      renderSelection();
    });
  });
  document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) => {
    b.addEventListener('click', () => {
      useRecommended = false;
      sel = { ...sel, orient: b.dataset.orient as OrientMode };
      syncChips();
      renderSelection();
    });
  });

  obstacleBtn?.addEventListener('click', () => {
    if (!closed) {
      setStatus('Fermez d’abord le tracé du toit, puis ajoutez vos obstacles.');
      return;
    }
    setObstacleMode(!obstacleMode);
    selectObstacle(null);
    setStatus(
      obstacleMode
        ? 'Glissez sur le toit pour dessiner un obstacle (cheminée, climatiseur, lanterneau…).'
        : 'Ajout d’obstacle annulé.',
    );
  });
  obstacleClearBtn?.addEventListener('click', () => {
    if (!obstacles.length) return;
    obstacles = [];
    selectedObsId = null;
    setObstacleMode(false);
    redrawObstacles();
    syncObsEdit();
    if (closed) recompute();
    setStatus('Obstacles effacés — le calepinage reprend tout le toit.');
  });

  // — Édition de l'obstacle sélectionné (saisie exacte + boutons + / − + suppr.) —
  const parseNum = (s: string): number => parseFloat((s || '').replace(/\s/g, '').replace(',', '.'));
  obsLengthEl?.addEventListener('input', () => {
    if (!selectedObsId) return;
    const L = parseNum(obsLengthEl.value);
    if (!Number.isFinite(L)) return;
    updateSelected((o) => resizedObstacle(o, L, o.widthM));
  });
  obsWidthEl?.addEventListener('input', () => {
    if (!selectedObsId) return;
    const w = parseNum(obsWidthEl.value);
    if (!Number.isFinite(w)) return;
    updateSelected((o) => resizedObstacle(o, o.lengthM, w));
  });
  obsLengthEl?.addEventListener('blur', syncObsEdit);
  obsWidthEl?.addEventListener('blur', syncObsEdit);
  obsPlusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, OBSTACLE_STEP_FACTOR)));
  obsMinusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, 1 / OBSTACLE_STEP_FACTOR)));
  obsDeleteBtn?.addEventListener('click', deleteSelected);

  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = addressEl?.value.trim();
    if (q) void geocode(q);
  });

  async function geocode(query: string) {
    setStatus('Recherche de l’adresse…');
    try {
      const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json?key=${encodeURIComponent(opts.maptilerKey)}&country=ma&limit=1&language=fr`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('geocode');
      const data = (await res.json()) as { features?: Array<{ center?: [number, number] }> };
      const center = data.features?.[0]?.center;
      if (!center) {
        setStatus('Adresse introuvable. Précisez la ville ou déplacez la carte à la main.');
        return;
      }
      const target = { center, zoom: 19, pitch: 0 } as const;
      if (opts.reducedMotion) map.jumpTo(target);
      else map.flyTo({ ...target, essential: true });
      setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer et lancer le calcul.');
    } catch {
      setStatus('Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.');
    }
  }
}

/**
 * Estimateur de toiture — VARIANTE HAUTE FIDÉLITÉ « pro 2 » (preview privé
 * /preview/toiture-3d-pro-2).
 *
 * Reprend la version « pro » (panneaux inclinés sur châssis lestés, Three.js dans
 * une couche personnalisée MapLibre) et la rend BEAUCOUP plus réaliste :
 *   1. vrais panneaux Canadian Solar 720 W (CS7N-690-720TB-AG, 2384×1303×33 mm,
 *      tout noir, grille 132 demi-cellules + couture centrale, cadre, boîtier de
 *      jonction, verre brillant) ;
 *   2. inclinaison vers le VRAI sud (azimut réel, GÉO-ANCRÉ : en tournant la carte,
 *      les panneaux gardent le cap sud) + boussole ;
 *   3. vrai SOLEIL positionné selon la LATITUDE du toit, vraies OMBRES portées, et
 *      espacement des rangées calculé pour qu'aucune n'ombrage la suivante ;
 *   4. matériaux PBR, ombres douces, InstancedMesh (fluide sur mobile, LOD léger).
 *
 * Même carte/tracé/PVGIS (/api/roof-estimate)/lead (pré-remplit le diagnostic, sans
 * jamais poster) que les autres previews. Le nombre de vrais panneaux 720 W posés
 * pilote kWc → production → économies (src/lib/roofPro2.ts). Aucune NOUVELLE
 * dépendance (Three.js déjà présent). Chargé À LA DEMANDE : ce module n'est importé
 * que par sa page ; aucune autre page ne télécharge la carte ni Three.js.
 *
 * Voir apps/web/SOLAR_3D_PRO2_NOTES.md.
 */
import maplibregl from 'maplibre-gl';
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import * as THREE from 'three';
import { layoutProRows2, PANEL2_THICK_M, type ProLayout2 } from '../lib/roofPro2';
import type { LngLat } from '../lib/roof';

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
const ROOF_PITCH_DEG = 18; // pente du toit « villa » (pose affleurante)
const DEG2RAD = Math.PI / 180;

let booted = false;

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);

// — Texture du vrai panneau Canadian Solar : tout noir, 132 demi-cellules,
//   couture centrale, fin cadre. Créée une seule fois. —
function makeCanadianPanelTexture(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 280;
  const ctx = c.getContext('2d')!;
  // Verre noir (léger dégradé pour le volume).
  const g = ctx.createLinearGradient(0, 0, 512, 280);
  g.addColorStop(0, '#0c0c0f');
  g.addColorStop(1, '#050507');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 512, 280);

  // Cellules demi-coupées : ~24 colonnes (grand côté) × 6 lignes (petit côté),
  // séparées en deux par la couture centrale (demi-cellules). Tout noir, lignes
  // de grille très discrètes (pas de busbars apparents sur ce modèle).
  const cols = 24;
  const rowsHalf = 3; // 3 + 3 de part et d'autre de la couture = 6
  const pad = 14;
  const seam = 6; // épaisseur de la couture centrale
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
  // Couture centrale (demi-cellules) un peu plus marquée.
  ctx.strokeStyle = 'rgba(20,24,34,0.9)';
  ctx.lineWidth = seam;
  ctx.beginPath();
  ctx.moveTo(pad, 140);
  ctx.lineTo(512 - pad, 140);
  ctx.stroke();
  // Cadre argenté fin.
  ctx.strokeStyle = 'rgba(150,156,168,0.85)';
  ctx.lineWidth = 10;
  ctx.strokeRect(5, 5, 502, 270);

  const tex = new THREE.Texture(c);
  tex.needsUpdate = true;
  tex.anisotropy = 8;
  return tex;
}

export function initRoofToolPro2(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) {
    throw new Error('WebGL indisponible');
  }

  // LOD léger : appareils modestes → ombres plus petites, pas d'antialias.
  const nav = navigator as Navigator & { deviceMemory?: number };
  const lowEnd = (nav.deviceMemory != null && nav.deviceMemory <= 4) || (navigator.hardwareConcurrency || 8) <= 4;
  const shadowSize = lowEnd ? 1024 : 2048;

  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = maplibreCssUrl;
  document.head.appendChild(cssLink);

  const mapEl = $('rp2-map');
  const statusEl = $('rp2-status');
  const orientEl = $<HTMLSelectElement>('rp2-orient');
  const floorsEl = $<HTMLSelectElement>('rp2-floors');
  const pitchEl = $<HTMLInputElement>('rp2-pitch');
  const finishBtn = $<HTMLButtonElement>('rp2-finish');
  const clearBtn = $<HTMLButtonElement>('rp2-clear');
  const searchForm = $<HTMLFormElement>('rp2-search');
  const addressEl = $<HTMLInputElement>('rp2-address');
  const buildPanel = $('rp2-build-controls');
  const compassArrow = $('rp2-compass-arrow');
  if (!mapEl) return;

  const setStatus = (msg: string) => {
    if (statusEl) statusEl.textContent = msg;
  };

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
    console.warn('[roof-tool-pro2] erreur carte (non bloquante) :', msg);
  });

  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.doubleClickZoom.disable();

  // Boussole : l'aiguille « N » pivote avec le cap → la carte sait où est le sud.
  const updateCompass = () => {
    if (compassArrow) compassArrow.style.transform = `rotate(${-map.getBearing()}deg)`;
  };
  map.on('rotate', updateCompass);
  map.on('pitch', updateCompass);
  updateCompass();

  let vertices: LngLat[] = [];
  let closed = false;
  let clickTimer: ReturnType<typeof setTimeout> | null = null;
  let lastLayout: ProLayout2 | null = null;

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
    id: 'rp2-3d',
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
      // On NE programme AUCUN nouveau rendu ici : pas de boucle continue (batterie
      // + aucun mouvement « tout seul »). MapLibre re-rend la couche à chaque
      // interaction caméra ; un seul rafraîchissement depuis buildScene suffit.
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
    modelMatrix = new THREE.Matrix4()
      .makeTranslation(mc.x, mc.y, mc.z)
      .scale(new THREE.Vector3(sUnit, -sUnit, sUnit));
  }

  function makeIM(
    geo: THREE.BufferGeometry,
    mat: THREE.Material | THREE.Material[],
    matrices: THREE.Matrix4[],
    cast = true,
    receive = false,
  ): THREE.InstancedMesh | null {
    if (!matrices.length) return null;
    const im = new THREE.InstancedMesh(geo, mat as THREE.Material, matrices.length);
    im.castShadow = cast;
    im.receiveShadow = receive;
    for (let i = 0; i < matrices.length; i++) im.setMatrixAt(i, matrices[i]);
    im.instanceMatrix.needsUpdate = true;
    return im;
  }

  function buildScene(layout: ProLayout2) {
    if (!sceneRoot || !sun) return;
    setOrigin(layout.origin);
    disposeScene();

    const floors = Math.max(1, Math.min(3, parseInt(floorsEl?.value || '2', 10) || 2));
    const wallH = floors * FLOOR_HEIGHT_M;
    const pitched = !!pitchEl?.checked;
    const ring = layout.ringENU;

    // — Bâtiment : massing propre —
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

    const ra = layout.rowAngleRad;
    const ca = Math.cos(ra);
    const sa = Math.sin(ra);
    const s0 = Math.sin(ra);
    const s1 = -Math.cos(ra);
    const rx = (lx: number, ly: number): [number, number] => [lx * ca - ly * sa, lx * sa + ly * ca];

    const { alongRow, slope, depthFootprint, rise, frontStrut } = layout.dims;
    const tilt = layout.tiltRad;

    // — Matériaux du vrai panneau (verre noir devant, cadre alu, dos clair) —
    const glassMat = new THREE.MeshPhysicalMaterial({
      map: panelTex,
      color: 0xffffff,
      metalness: 0.1,
      roughness: 0.22,
      clearcoat: 1,
      clearcoatRoughness: 0.08,
    });
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x9aa0aa, metalness: 0.85, roughness: 0.35 });
    const backMat = new THREE.MeshStandardMaterial({ color: 0xe6e8ee, metalness: 0.1, roughness: 0.6 });
    // Ordre des faces d'une BoxGeometry : +X,-X,+Y,-Y,+Z,-Z → verre sur +Z, dos sur -Z.
    const panelMats = [frameMat, frameMat, frameMat, frameMat, glassMat, backMat];
    const panelGeo = new THREE.BoxGeometry(alongRow, slope, PANEL2_THICK_M);
    // Boîtier de jonction (au dos, sous le centre du panneau).
    const jboxGeo = new THREE.BoxGeometry(0.4, 0.12, 0.035);
    jboxGeo.translate(0, 0, -(PANEL2_THICK_M / 2 + 0.02));
    const jboxMat = new THREE.MeshStandardMaterial({ color: 0x15171c, metalness: 0.3, roughness: 0.6 });

    if (pitched) {
      // — Toit en pente (villa) : pose affleurante, sans châssis ni lest —
      const vOf = (x: number, y: number) => x * s0 + y * s1;
      let vRef = Infinity;
      for (const [x, y] of ring) vRef = Math.min(vRef, vOf(x, y));
      const tan = Math.tan(tilt);
      const baseZ = wallH;

      const slabGeo = new THREE.ShapeGeometry(shape);
      const pos = slabGeo.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i);
        const y = pos.getY(i);
        pos.setZ(i, baseZ + (vOf(x, y) - vRef) * tan + 0.02);
      }
      slabGeo.computeVertexNormals();
      const slab = new THREE.Mesh(
        slabGeo,
        new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0, side: THREE.DoubleSide }),
      );
      slab.receiveShadow = true;
      sceneRoot.add(slab);

      const panelMatsArr: THREE.Matrix4[] = [];
      for (const p of layout.panels) {
        const pz = baseZ + (vOf(p.cx, p.cy) - vRef) * tan + 0.06;
        panelMatsArr.push(compose(p.cx, p.cy, pz, ra, tilt));
      }
      const pm = makeIM(panelGeo, panelMats, panelMatsArr, true, false);
      if (pm) sceneRoot.add(pm);
      const jb = makeIM(jboxGeo, jboxMat, panelMatsArr, true, false);
      if (jb) sceneRoot.add(jb);
    } else {
      // — Toit plat : vrais panneaux inclinés sur châssis triangulaires lestés —
      const baseZ = wallH + DECK_THK;
      const backH = frontStrut + rise;
      const halfAlong = alongRow / 2;
      const halfDepth = depthFootprint / 2;

      const deck = new THREE.Mesh(
        new THREE.ShapeGeometry(shape),
        new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 }),
      );
      deck.position.z = wallH + 0.02;
      deck.receiveShadow = true;
      sceneRoot.add(deck);

      const rackMat = new THREE.MeshStandardMaterial({ color: 0x40454f, metalness: 0.75, roughness: 0.4 });
      const ballastMat = new THREE.MeshStandardMaterial({ color: 0x9b9a90, metalness: 0, roughness: 0.95 });
      const frontGeo = new THREE.BoxGeometry(0.06, 0.06, frontStrut);
      const backGeo = new THREE.BoxGeometry(0.06, 0.06, backH);
      const railGeo = new THREE.BoxGeometry(0.05, slope, 0.05);
      const ballastGeo = new THREE.BoxGeometry(0.34, 0.18, 0.12);

      const panelMatsArr: THREE.Matrix4[] = [];
      const frontMats: THREE.Matrix4[] = [];
      const backMats: THREE.Matrix4[] = [];
      const railMats: THREE.Matrix4[] = [];
      const ballastMats: THREE.Matrix4[] = [];
      // Châssis aux deux extrémités + un au milieu (le grand panneau 2,38 m le mérite).
      const ends = [-halfAlong + 0.08, 0, halfAlong - 0.08];

      for (const p of layout.panels) {
        const pZ = baseZ + frontStrut + rise / 2 + 0.07;
        panelMatsArr.push(compose(p.cx, p.cy, pZ, ra, tilt));
        for (const xe of ends) {
          const f = rx(xe, -halfDepth);
          frontMats.push(compose(p.cx + f[0], p.cy + f[1], baseZ + frontStrut / 2, ra, 0));
          const b = rx(xe, halfDepth);
          backMats.push(compose(p.cx + b[0], p.cy + b[1], baseZ + backH / 2, ra, 0));
          const c = rx(xe, 0);
          railMats.push(compose(p.cx + c[0], p.cy + c[1], baseZ + frontStrut + rise / 2, ra, tilt));
        }
        // Lest aux quatre coins de l'embase.
        for (const xe of [-halfAlong + 0.08, halfAlong - 0.08]) {
          const bf = rx(xe, -halfDepth - 0.02);
          ballastMats.push(compose(p.cx + bf[0], p.cy + bf[1], baseZ + 0.06, ra, 0));
          const bb = rx(xe, halfDepth + 0.02);
          ballastMats.push(compose(p.cx + bb[0], p.cy + bb[1], baseZ + 0.06, ra, 0));
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
    }

    // — Vrai soleil : direction depuis l'azimut & l'élévation (latitude du toit) —
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
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
    // Soleil d'AFFICHAGE : matin clair (à l'est de la visée), élévation liée à la
    // latitude — assez bas pour des ombres visibles, plus haut que l'élévation de
    // DESIGN (solstice) qui a servi à espacer les rangées → on VOIT que les rangées
    // ne s'ombragent pas (jour de sole entre les rangées).
    const latAbs = Math.abs(layout.latitudeDeg);
    const dispElevDeg = Math.max(layout.designElevDeg + 5, (90 - latAbs) * 0.62);
    const dispAzDeg = layout.azimuthDeg - 45;
    const azR = dispAzDeg * DEG2RAD;
    const elR = dispElevDeg * DEG2RAD;
    const dist = span * 2.5;
    sun.target.position.set(cxm, cym, roofZ);
    sun.position.set(
      cxm + Math.sin(azR) * Math.cos(elR) * dist,
      cym + Math.cos(azR) * Math.cos(elR) * dist,
      roofZ + Math.sin(elR) * dist,
    );
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

  map.on('load', () => {
    map.addSource('rp2-line', { type: 'geojson', data: empty as never });
    map.addSource('rp2-pts', { type: 'geojson', data: empty as never });
    map.addLayer({
      id: 'rp2-line',
      type: 'line',
      source: 'rp2-line',
      paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] },
    });
    map.addLayer({
      id: 'rp2-pts',
      type: 'circle',
      source: 'rp2-pts',
      paint: {
        'circle-radius': 5,
        'circle-color': GOLD,
        'circle-stroke-color': '#070b1d',
        'circle-stroke-width': 1.5,
      },
    });
    map.addLayer(customLayer);
    updateCompass();

    if (opts.initialQuery) void geocode(opts.initialQuery);
    else setStatus('Cherchez votre adresse, puis cliquez les coins de votre toit.');
  });

  const src = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  function redrawTrace() {
    src('rp2-line')?.setData({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: vertices },
      properties: {},
    } as never);
    src('rp2-pts')?.setData({
      type: 'FeatureCollection',
      features: vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })),
    } as never);
    if (finishBtn) finishBtn.disabled = vertices.length < 3 || closed;
  }

  function addVertex(v: LngLat) {
    if (closed) return;
    vertices.push(v);
    redrawTrace();
    if (vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit et voir l’installation réelle.');
    else setStatus(`Coin ${vertices.length} placé — continuez à tracer le contour.`);
  }

  function currentOpts() {
    return pitchEl?.checked ? { tiltDeg: ROOF_PITCH_DEG, flush: true } : {};
  }

  function buildAt(ring: LngLat[]): ProLayout2 {
    // Latitude du toit = latitude du centroïde du tracé.
    let lat = 0;
    for (const [, y] of ring) lat += y;
    lat /= ring.length;
    return layoutProRows2(ring, orientEl?.value || 'sud', lat, currentOpts());
  }

  function reset() {
    vertices = [];
    closed = false;
    lastLayout = null;
    src('rp2-line')?.setData(empty as never);
    src('rp2-pts')?.setData(empty as never);
    disposeScene();
    modelMatrix = null;
    map.triggerRepaint();
    showResults(null);
    if (buildPanel) buildPanel.hidden = true;
    if (finishBtn) finishBtn.disabled = true;
    const target = { pitch: 0, bearing: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 600 });
    updateCompass();
    setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
  }

  function go3DView(layout: ProLayout2) {
    const target = { center: layout.origin, pitch: PITCH_VIEW } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 1100, essential: true });
  }

  function close() {
    if (closed || vertices.length < 3) return;
    closed = true;
    if (finishBtn) finishBtn.disabled = true;
    const ring: LngLat[] = [...vertices];
    src('rp2-line')?.setData(empty as never);
    src('rp2-pts')?.setData(empty as never);

    const layout = buildAt(ring);
    lastLayout = layout;
    buildScene(layout);
    go3DView(layout);
    if (buildPanel) buildPanel.hidden = false;

    if (layout.count === 0) {
      setStatus('Surface trop petite pour une rangée — élargissez le tracé (« Effacer » pour recommencer).');
      showResults({ ...layout, annualKwh: null, savings: null });
      return;
    }
    setStatus('Installation réelle en 3D. Faites glisser pour pivoter ; les panneaux gardent le cap sud. Estimation en cours…');
    showResults({ ...layout, annualKwh: null, savings: null });
    void estimate(ring, layout);
  }

  map.on('click', (e) => {
    if (closed) return;
    if (clickTimer) return;
    const lngLat: LngLat = [e.lngLat.lng, e.lngLat.lat];
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

  floorsEl?.addEventListener('change', () => {
    if (closed && lastLayout) buildScene(lastLayout);
  });

  const relayout = () => {
    if (!closed || vertices.length < 3) return;
    const layout = buildAt([...vertices]);
    lastLayout = layout;
    buildScene(layout);
    showResults({ ...layout, annualKwh: null, savings: null });
    if (layout.count > 0) void estimate([...vertices], layout);
  };
  pitchEl?.addEventListener('change', relayout);
  orientEl?.addEventListener('change', relayout);

  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = addressEl?.value.trim();
    if (q) void geocode(q);
  });

  async function geocode(query: string) {
    setStatus('Recherche de l’adresse…');
    try {
      const url =
        `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json` +
        `?key=${encodeURIComponent(opts.maptilerKey)}&country=ma&limit=1&language=fr`;
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
      setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer et voir la 3D.');
    } catch {
      setStatus('Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.');
    }
  }

  async function estimate(ring: LngLat[], layout: ProLayout2) {
    let lng = 0;
    let lat = 0;
    for (const [x, y] of ring) {
      lng += x;
      lat += y;
    }
    lng /= ring.length;
    lat /= ring.length;
    const orientation = orientEl?.value || 'sud';
    try {
      const res = await fetch('/api/roof-estimate', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat, lon: lng, kwc: layout.kwc, orientation }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        showResults({ ...layout, annualKwh: data.annualKwh, savings: data.savings, source: data.source });
        setStatus('Estimation prête. Faites pivoter l’installation, puis recevez l’étude sur WhatsApp.');
        return;
      }
    } catch {
      /* repli ci-dessous */
    }
    showResults({ ...layout, annualKwh: null, savings: null });
    setStatus('Production momentanément indisponible — la taille du système reste indicative.');
  }

  interface Results {
    count: number;
    kwc: number;
    areaM2: number;
    annualKwh: number | null;
    savings: { low: number; high: number } | null;
    source?: string;
  }
  function showResults(r: Results | null) {
    const panel = $('rp2-results');
    const cta = $<HTMLButtonElement>('rp2-cta');
    const set = (id: string, v: string) => {
      const el = $(id);
      if (el) el.textContent = v;
    };
    if (!r || r.count === 0) {
      set('rp2-res-kwc', '—');
      set('rp2-res-panels', '—');
      set('rp2-res-area', '—');
      set('rp2-res-prod', '—');
      set('rp2-res-savings', '—');
      set('rp2-res-note', r && r.count === 0 ? 'Tracé trop petit pour une rangée de panneaux.' : 'Tracez votre toit pour découvrir votre potentiel solaire.');
      if (cta) cta.hidden = true;
      panel?.classList.remove('rp2-results--ready');
      return;
    }
    set('rp2-res-kwc', `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
    set('rp2-res-panels', `${fmt(r.count)} panneaux 720 W`);
    set('rp2-res-area', `${fmt(Math.round(r.areaM2))} m²`);
    set('rp2-res-prod', r.annualKwh != null ? `${fmt(r.annualKwh)} kWh/an` : 'estimation en cours…');
    set('rp2-res-savings', r.savings ? `${fmt(r.savings.low)} – ${fmt(r.savings.high)} MAD/an` : '—');
    set(
      'rp2-res-note',
      r.source === 'pvgis'
        ? 'Production PVGIS (Commission européenne) — vrais panneaux 720 W, rangées espacées anti-ombrage, fourchette indicative, pas un devis.'
        : r.annualKwh != null
          ? 'Production estimée (productible moyen Maroc) — fourchette indicative, pas un devis.'
          : 'Taille du système estimée — la production sera précisée par l’étude.',
    );
    panel?.classList.add('rp2-results--ready');

    // Pré-remplit le diagnostic enrichi — RÉUTILISE EXACTEMENT le même formulaire et
    // sa plomberie (seuil 1 000 MAD, consentement, webhook, CAPI) : on n'écrit que
    // dans ses champs, on ne poste aucun lead ici.
    if (cta) {
      cta.hidden = false;
      cta.onclick = () => {
        const area = $<HTMLInputElement>('lf-area');
        const orient = $<HTMLSelectElement>('lf-orient');
        const kwc = $<HTMLInputElement>('lf-kwc-est');
        if (area) area.value = String(Math.round(r.areaM2));
        if (orient) orient.value = orientEl?.value || 'sud';
        if (kwc) kwc.value = String(Math.round(r.kwc * 100) / 100);
        const details = (area?.closest('details') as HTMLDetailsElement | null) ?? null;
        if (details) details.open = true;
        document.getElementById('simulateur')?.scrollIntoView({
          behavior: opts.reducedMotion ? 'auto' : 'smooth',
          block: 'start',
        });
      };
    }
  }
}

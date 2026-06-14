/**
 * Estimateur de toiture — VARIANTE 3D RÉALISTE « pro » (preview privé
 * /preview/toiture-3d-pro).
 *
 * Même carte (MapLibre + tuiles satellite MapTiler), même tracé, MÊME flux lead
 * (pré-remplit le diagnostic enrichi de production, sans jamais poster de lead)
 * et MÊME proxy serveur PVGIS (/api/roof-estimate) que les versions 2D et 3D.
 * Ce qui change : le RENDU. Sur toit plat, on dessine des panneaux INCLINÉS sur
 * des CHÂSSIS TRIANGULAIRES LESTÉS, en RANGÉES espacées — comme une vraie pose
 * lestée — avec de vraies ombres douces, via Three.js dans une COUCHE
 * PERSONNALISÉE MapLibre (`fill-extrusion` ne sait faire que des boîtes droites).
 *
 * Le calepinage espacé/incliné (src/lib/roofPro.ts) détermine le nombre réel de
 * panneaux → kWc → production → économies : c'est PLUS juste (les rangées exigent
 * des jeux) et le nombre peut être un peu plus bas que la version « collée à plat ».
 *
 * Three.js est la SEULE dépendance ajoutée, chargée À LA DEMANDE : ce module
 * (avec roof-tool.ts / roof-tool-3d.ts) est le seul à importer MapLibre, et le
 * seul à importer Three.js. Il n'est JAMAIS importé statiquement — uniquement via
 * `import()` dynamique depuis la page. Vite l'isole donc dans un chunk chargé
 * seulement sur cette page ; aucune autre page ne télécharge la carte ni Three.js.
 *
 * Décisions géométriques : voir apps/web/SOLAR_3D_RATIONALE.md.
 */
import maplibregl from 'maplibre-gl';
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import * as THREE from 'three';
import { layoutProRows, type ProLayout } from '../lib/roofPro';
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
const PITCH_VIEW = 58; // inclinaison caméra en vue 3D
const DECK_THK = 0.06; // épaisseur de la dalle de toit (toit plat)
const ROOF_PITCH_DEG = 18; // pente du toit « villa » (pose affleurante)

let booted = false;

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);

// — Texture procédurale de panneau (cellules + cadre), créée une seule fois —
function makePanelTexture(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = 256;
  c.height = 256;
  const ctx = c.getContext('2d')!;
  // Fond bleu nuit très sombre, vitré.
  const g = ctx.createLinearGradient(0, 0, 256, 256);
  g.addColorStop(0, '#0e1b3e');
  g.addColorStop(1, '#0a1230');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  // Grille de cellules.
  ctx.strokeStyle = 'rgba(120,150,220,0.35)';
  ctx.lineWidth = 2;
  const cols = 6;
  const rows = 10;
  for (let i = 1; i < cols; i++) {
    const x = (i / cols) * 256;
    ctx.beginPath();
    ctx.moveTo(x, 6);
    ctx.lineTo(x, 250);
    ctx.stroke();
  }
  for (let j = 1; j < rows; j++) {
    const y = (j / rows) * 256;
    ctx.beginPath();
    ctx.moveTo(6, y);
    ctx.lineTo(250, y);
    ctx.stroke();
  }
  // Cadre clair.
  ctx.strokeStyle = 'rgba(200,210,230,0.7)';
  ctx.lineWidth = 8;
  ctx.strokeRect(4, 4, 248, 248);
  const tex = new THREE.Texture(c);
  tex.needsUpdate = true;
  tex.anisotropy = 4;
  return tex;
}

export function initRoofToolPro(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  // Repli immédiat si WebGL est indisponible : on lève, la page bascule au repli.
  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) {
    throw new Error('WebGL indisponible');
  }

  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = maplibreCssUrl;
  document.head.appendChild(cssLink);

  const mapEl = $('rp-map');
  const statusEl = $('rp-status');
  const orientEl = $<HTMLSelectElement>('rp-orient');
  const floorsEl = $<HTMLSelectElement>('rp-floors');
  const pitchEl = $<HTMLInputElement>('rp-pitch');
  const finishBtn = $<HTMLButtonElement>('rp-finish');
  const clearBtn = $<HTMLButtonElement>('rp-clear');
  const searchForm = $<HTMLFormElement>('rp-search');
  const addressEl = $<HTMLInputElement>('rp-address');
  const buildPanel = $('rp-build-controls');
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
    console.warn('[roof-tool-pro] erreur carte (non bloquante) :', msg);
  });

  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.doubleClickZoom.disable();

  let vertices: LngLat[] = [];
  let closed = false;
  let clickTimer: ReturnType<typeof setTimeout> | null = null;
  let lastLayout: ProLayout | null = null;

  // — État Three.js (couche personnalisée) —
  let renderer: THREE.WebGLRenderer | null = null;
  let scene: THREE.Scene | null = null;
  let sceneRoot: THREE.Group | null = null;
  let threeCamera: THREE.Camera | null = null;
  let sun: THREE.DirectionalLight | null = null;
  let modelMatrix: THREE.Matrix4 | null = null;
  const panelTex = makePanelTexture();

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

  // — Couche personnalisée Three.js : pont MapLibre ↔ Three —
  const customLayer = {
    id: 'rp-3d',
    type: 'custom' as const,
    renderingMode: '3d' as const,
    onAdd(_m: maplibregl.Map, gl: WebGLRenderingContext | WebGL2RenderingContext) {
      threeCamera = new THREE.Camera();
      scene = new THREE.Scene();
      sceneRoot = new THREE.Group();
      scene.add(sceneRoot);

      // Lumières : ambiance bleu-nuit douce + soleil directionnel chaud (ombres).
      scene.add(new THREE.AmbientLight(0xb9c8ee, 0.55));
      scene.add(new THREE.HemisphereLight(0xcfe0ff, 0x202634, 0.45));
      sun = new THREE.DirectionalLight(0xfff1d4, 2.3);
      sun.castShadow = true;
      sun.shadow.mapSize.set(2048, 2048);
      sun.shadow.bias = -0.0006;
      sun.shadow.normalBias = 0.02;
      scene.add(sun);
      scene.add(sun.target);

      renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: true });
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
      // On NE programme AUCUN nouveau rendu ici : pas de boucle continue
      // (économie batterie + aucun mouvement « tout seul »). MapLibre re-rend la
      // couche à chaque interaction caméra ; un seul rafraîchissement, déclenché
      // depuis buildScene après (re)construction, suffit.
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
    const s = mc.meterInMercatorCoordinateUnits();
    // ENU (x=est, y=nord, z=haut) en mètres → mercator (y vers le bas → -s).
    modelMatrix = new THREE.Matrix4()
      .makeTranslation(mc.x, mc.y, mc.z)
      .scale(new THREE.Vector3(s, -s, s));
  }

  function makeIM(
    geo: THREE.BufferGeometry,
    mat: THREE.Material,
    matrices: THREE.Matrix4[],
    cast = true,
    receive = false,
  ): THREE.InstancedMesh | null {
    if (!matrices.length) return null;
    const im = new THREE.InstancedMesh(geo, mat, matrices.length);
    im.castShadow = cast;
    im.receiveShadow = receive;
    for (let i = 0; i < matrices.length; i++) im.setMatrixAt(i, matrices[i]);
    im.instanceMatrix.needsUpdate = true;
    return im;
  }

  // (Re)construit toute la scène 3D depuis le tracé + réglages courants.
  function buildScene(layout: ProLayout) {
    if (!sceneRoot || !sun) return;
    setOrigin(layout.origin);
    disposeScene();

    const floors = Math.max(1, Math.min(3, parseInt(floorsEl?.value || '2', 10) || 2));
    const wallH = floors * FLOOR_HEIGHT_M;
    const pitched = !!pitchEl?.checked;
    const ring = layout.ringENU;

    // — Bâtiment : prisme vertical du contour (massing propre) —
    const shape = new THREE.Shape();
    ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
    shape.closePath();
    const buildingGeo = new THREE.ExtrudeGeometry(shape, { depth: wallH, bevelEnabled: false });
    const buildingMat = new THREE.MeshStandardMaterial({ color: 0xe2e7f2, roughness: 0.85, metalness: 0 });
    const building = new THREE.Mesh(buildingGeo, buildingMat);
    building.castShadow = true;
    building.receiveShadow = true;
    sceneRoot.add(building);

    // Repère de pente : s = axe vers l'orientation (cf. roofPro).
    const ra = layout.rowAngleRad;
    const ca = Math.cos(ra);
    const sa = Math.sin(ra);
    const s0 = Math.sin(ra);
    const s1 = -Math.cos(ra);
    const rx = (lx: number, ly: number): [number, number] => [lx * ca - ly * sa, lx * sa + ly * ca];

    const { alongRow, slope, depthFootprint, rise, frontStrut } = layout.dims;
    const tilt = layout.tiltRad;
    const panelMat = new THREE.MeshPhysicalMaterial({
      map: panelTex,
      color: 0xffffff,
      metalness: 0.25,
      roughness: 0.18,
      clearcoat: 1,
      clearcoatRoughness: 0.12,
    });
    const panelGeo = new THREE.BoxGeometry(alongRow, slope, 0.04);

    if (pitched) {
      // — Toit en pente (villa) : pose AFFLEURANTE, sans châssis ni lest —
      const vOf = (x: number, y: number) => x * s0 + y * s1;
      let vRef = Infinity;
      for (const [x, y] of ring) vRef = Math.min(vRef, vOf(x, y));
      const tan = Math.tan(tilt);
      const baseZ = wallH;

      // Dalle de toit inclinée (suit l'empreinte) — capte les ombres.
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

      const panelMats: THREE.Matrix4[] = [];
      for (const p of layout.panels) {
        const vC = vOf(p.cx, p.cy);
        const pz = baseZ + (vC - vRef) * tan + 0.06;
        panelMats.push(compose(p.cx, p.cy, pz, ra, tilt));
      }
      const pm = makeIM(panelGeo, panelMat, panelMats, true, false);
      if (pm) sceneRoot.add(pm);
    } else {
      // — Toit plat : panneaux inclinés sur châssis triangulaires lestés, en rangées —
      const baseZ = wallH + DECK_THK;
      const backH = frontStrut + rise;
      const halfAlong = alongRow / 2;
      const halfDepth = depthFootprint / 2;

      // Dalle de toit (capte les ombres des châssis et panneaux).
      const deckGeo = new THREE.ShapeGeometry(shape);
      const deck = new THREE.Mesh(
        deckGeo,
        new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 }),
      );
      deck.position.z = wallH + 0.02;
      deck.receiveShadow = true;
      sceneRoot.add(deck);

      const frameMat = new THREE.MeshStandardMaterial({ color: 0x40454f, metalness: 0.7, roughness: 0.45 });
      const ballastMat = new THREE.MeshStandardMaterial({ color: 0x9b9a90, metalness: 0, roughness: 0.95 });
      const frontGeo = new THREE.BoxGeometry(0.05, 0.05, frontStrut);
      const backGeo = new THREE.BoxGeometry(0.05, 0.05, backH);
      const railGeo = new THREE.BoxGeometry(0.04, slope, 0.04);
      const ballastGeo = new THREE.BoxGeometry(0.3, 0.16, 0.1);

      const panelMats: THREE.Matrix4[] = [];
      const frontMats: THREE.Matrix4[] = [];
      const backMats: THREE.Matrix4[] = [];
      const railMats: THREE.Matrix4[] = [];
      const ballastMats: THREE.Matrix4[] = [];
      const ends = [-halfAlong + 0.06, halfAlong - 0.06];

      for (const p of layout.panels) {
        panelMats.push(compose(p.cx, p.cy, baseZ + frontStrut + rise / 2 + 0.06, ra, tilt));
        for (const xe of ends) {
          const f = rx(xe, -halfDepth);
          frontMats.push(compose(p.cx + f[0], p.cy + f[1], baseZ + frontStrut / 2, ra, 0));
          const b = rx(xe, halfDepth);
          backMats.push(compose(p.cx + b[0], p.cy + b[1], baseZ + backH / 2, ra, 0));
          const c = rx(xe, 0);
          railMats.push(compose(p.cx + c[0], p.cy + c[1], baseZ + frontStrut + rise / 2, ra, tilt));
          const bf = rx(xe, -halfDepth - 0.02);
          ballastMats.push(compose(p.cx + bf[0], p.cy + bf[1], baseZ + 0.05, ra, 0));
          const bb = rx(xe, halfDepth + 0.02);
          ballastMats.push(compose(p.cx + bb[0], p.cy + bb[1], baseZ + 0.05, ra, 0));
        }
      }
      const meshes = [
        makeIM(panelGeo, panelMat, panelMats, true, false),
        makeIM(frontGeo, frameMat, frontMats, true, false),
        makeIM(backGeo, frameMat, backMats, true, false),
        makeIM(railGeo, frameMat, railMats, true, false),
        makeIM(ballastGeo, ballastMat, ballastMats, true, true),
      ];
      for (const me of meshes) if (me) sceneRoot.add(me);
    }

    // — Soleil + cadrage des ombres sur l'emprise —
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
    sun.target.position.set(cxm, cym, wallH);
    sun.position.set(cxm - span * 0.6, cym - span * 0.85, wallH + span * 1.25);
    const sc = sun.shadow.camera as THREE.OrthographicCamera;
    sc.left = -span;
    sc.right = span;
    sc.top = span;
    sc.bottom = -span;
    sc.near = 0.5;
    sc.far = span * 4;
    sc.updateProjectionMatrix();

    map.triggerRepaint();
  }

  // — Tracé (vue de dessus) : ligne + points GeoJSON —
  map.on('load', () => {
    map.addSource('rp-line', { type: 'geojson', data: empty as never });
    map.addSource('rp-pts', { type: 'geojson', data: empty as never });
    map.addLayer({
      id: 'rp-line',
      type: 'line',
      source: 'rp-line',
      paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] },
    });
    map.addLayer({
      id: 'rp-pts',
      type: 'circle',
      source: 'rp-pts',
      paint: {
        'circle-radius': 5,
        'circle-color': GOLD,
        'circle-stroke-color': '#070b1d',
        'circle-stroke-width': 1.5,
      },
    });
    map.addLayer(customLayer);

    if (opts.initialQuery) void geocode(opts.initialQuery);
    else setStatus('Cherchez votre adresse, puis cliquez les coins de votre toit.');
  });

  const src = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  function redrawTrace() {
    src('rp-line')?.setData({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: vertices },
      properties: {},
    } as never);
    src('rp-pts')?.setData({
      type: 'FeatureCollection',
      features: vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })),
    } as never);
    if (finishBtn) finishBtn.disabled = vertices.length < 3 || closed;
  }

  function addVertex(v: LngLat) {
    if (closed) return;
    vertices.push(v);
    redrawTrace();
    if (vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit et le voir en 3D réaliste.');
    else setStatus(`Coin ${vertices.length} placé — continuez à tracer le contour.`);
  }

  function currentOpts() {
    return pitchEl?.checked ? { tiltDeg: ROOF_PITCH_DEG, rowGapFactor: 0 } : {};
  }

  function reset() {
    vertices = [];
    closed = false;
    lastLayout = null;
    src('rp-line')?.setData(empty as never);
    src('rp-pts')?.setData(empty as never);
    disposeScene();
    modelMatrix = null;
    map.triggerRepaint();
    showResults(null);
    if (buildPanel) buildPanel.hidden = true;
    if (finishBtn) finishBtn.disabled = true;
    const target = { pitch: 0, bearing: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 600 });
    setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
  }

  function go3DView(layout: ProLayout) {
    const target = { center: layout.origin, pitch: PITCH_VIEW } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 1100, essential: true });
  }

  function close() {
    if (closed || vertices.length < 3) return;
    closed = true;
    if (finishBtn) finishBtn.disabled = true;
    const ring: LngLat[] = [...vertices];
    src('rp-line')?.setData(empty as never);
    src('rp-pts')?.setData(empty as never);

    const layout = layoutProRows(ring, orientEl?.value || 'sud', currentOpts());
    lastLayout = layout;
    buildScene(layout);
    go3DView(layout);
    if (buildPanel) buildPanel.hidden = false;

    if (layout.count === 0) {
      setStatus('Surface trop petite pour une rangée — élargissez le tracé (« Effacer » pour recommencer).');
      showResults({ ...layout, annualKwh: null, savings: null });
      return;
    }
    setStatus('Toit en 3D réaliste. Faites glisser pour pivoter/incliner. Estimation en cours…');
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

  // Étages : reconstruit la scène (hauteur du bâtiment), SANS réestimer
  // (le nombre de panneaux ne dépend pas des étages).
  floorsEl?.addEventListener('change', () => {
    if (closed && lastLayout) buildScene(lastLayout);
  });

  // Toit plat/pente ET orientation changent le CALEPINAGE → on recalcule la
  // disposition, on reconstruit, et on réestime (le nombre de panneaux change).
  const relayout = () => {
    if (!closed || vertices.length < 3) return;
    const layout = layoutProRows([...vertices], orientEl?.value || 'sud', currentOpts());
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

  // — Production via le proxy serveur PVGIS (jamais d'appel PVGIS direct) —
  async function estimate(ring: LngLat[], layout: ProLayout) {
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

  // — Rendu du panneau de résultats (espace réservé → aucun saut de page) —
  interface Results {
    count: number;
    kwc: number;
    areaM2: number;
    annualKwh: number | null;
    savings: { low: number; high: number } | null;
    source?: string;
  }
  function showResults(r: Results | null) {
    const panel = $('rp-results');
    const cta = $<HTMLButtonElement>('rp-cta');
    const set = (id: string, v: string) => {
      const el = $(id);
      if (el) el.textContent = v;
    };
    if (!r || r.count === 0) {
      set('rp-res-kwc', '—');
      set('rp-res-panels', '—');
      set('rp-res-area', '—');
      set('rp-res-prod', '—');
      set('rp-res-savings', '—');
      set('rp-res-note', r && r.count === 0 ? 'Tracé trop petit pour une rangée de panneaux.' : 'Tracez votre toit pour découvrir votre potentiel solaire.');
      if (cta) cta.hidden = true;
      panel?.classList.remove('rp-results--ready');
      return;
    }
    set('rp-res-kwc', `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
    set('rp-res-panels', `${fmt(r.count)} panneaux`);
    set('rp-res-area', `${fmt(Math.round(r.areaM2))} m²`);
    set('rp-res-prod', r.annualKwh != null ? `${fmt(r.annualKwh)} kWh/an` : 'estimation en cours…');
    set('rp-res-savings', r.savings ? `${fmt(r.savings.low)} – ${fmt(r.savings.high)} MAD/an` : '—');
    set(
      'rp-res-note',
      r.source === 'pvgis'
        ? 'Production PVGIS (Commission européenne) — rangées espacées réelles, fourchette indicative, pas un devis.'
        : r.annualKwh != null
          ? 'Production estimée (productible moyen Maroc) — fourchette indicative, pas un devis.'
          : 'Taille du système estimée — la production sera précisée par l’étude.',
    );
    panel?.classList.add('rp-results--ready');

    // Pré-remplit le diagnostic enrichi — RÉUTILISE EXACTEMENT le même formulaire
    // et toute sa plomberie (seuil 1 000 MAD, consentement, webhook, CAPI) que les
    // versions 2D/3D : on n'écrit que dans ses champs, on ne poste aucun lead ici.
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

/**
 * Estimateur de toiture PILOTÉ PAR LA FACTURE — preview privé
 * /preview/toiture-3d-pro-4 (V2 du cerveau).
 *
 * COPIE de roof-tool-pro3.ts : pro-3 reste la baseline intacte. Cette version
 * branche le CERVEAU V2 (src/lib/estimatorBrainV2.ts) qui, sur un toit LIMITÉ,
 * peut recommander une inclinaison Sud plus PLATE pour loger plus de panneaux
 * (plus de production totale, jamais au-delà du besoin), et ajoute un CONTRÔLE
 * D'INCLINAISON (curseur 5–30° + bouton « reco ») pour explorer.
 *
 * Reprend le rendu haute fidélité de pro-2 (vrais panneaux Canadian Solar 720 W,
 * Three.js dans une couche MapLibre, vrai sud géo-ancré, vrai soleil/ombres).
 * Chaque réglage RE-CALCULE depuis la table de productible committée (instantané,
 * aucun appel réseau par réglage) ; PVGIS live n'affine qu'UNE fois la
 * recommandation. Le diagnostic enrichi est seulement PRÉ-REMPLI (jamais de lead
 * posté). Aucune nouvelle dépendance.
 *
 * Voir apps/web/BRAIN_V2_NOTES.md et apps/web/SOLAR_3D_PRO2_NOTES.md.
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
  neededPanelsForTarget,
  TILT_SWEEP_MIN,
  type Recommendation,
  type PackResult,
  type PanelGrid,
  type ConfigFamily,
} from '../lib/estimatorBrainV2';
import { roofAreaLabel, ringBBox, type LngLat } from '../lib/roof';
import {
  obstacleRing,
  obstacleFromDrag,
  defaultObstacle,
  scaledObstacle,
  resizedObstacle,
  OBSTACLE_STEP_FACTOR,
  type Obstacle,
} from '../lib/obstacles';
import { buildSatelliteStyle, roofImageRequest, roofVertexUV, mapboxStaticRoofImageUrl } from '../lib/roofConfig';

interface InitOptions {
  maptilerKey: string;
  mapboxToken?: string;
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

export function initRoofToolPro4(opts: InitOptions): void {
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
  const areaValueEl = $('rp3-area-value');
  const needInputEl = $<HTMLInputElement>('rp3-need-input');
  const needMinusEl = $<HTMLButtonElement>('rp3-need-minus');
  const needPlusEl = $<HTMLButtonElement>('rp3-need-plus');
  const needNoteEl = $('rp3-need-note');
  // V2 : contrôle d'inclinaison (curseur 5–35° + bouton « reco »).
  const tiltRangeEl = $<HTMLInputElement>('rp3-tilt-range');
  const tiltValueEl = $('rp3-tilt-value');
  const tiltRecoBtn = $<HTMLButtonElement>('rp3-tilt-reco');
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

  // Readout « surface du toit » : aire BRUTE du tracé (obstacles non déduits),
  // mise à jour à chaque sommet/retracé, effacée quand le tracé est vide.
  const updateAreaReadout = () => {
    if (areaValueEl) areaValueEl.textContent = roofAreaLabel(vertices) ?? '—';
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
  // Change C : déplacement (glissé) d'un obstacle existant. Delta-based (newCenter =
  // centre de départ + déplacement lng/lat) → robuste au parallaxe en vue inclinée.
  let moveObs: { id: string; startLng: number; startLat: number; centerLng: number; centerLat: number; moved: boolean } | null = null;
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
  // Affinage PVGIS stocké en rendement (kWh/kWc/an) pour suivre le nombre de
  // panneaux RÉELLEMENT posé (qui peut descendre sous le besoin si le toit/les
  // obstacles contraignent) — jamais un kWh absolu figé sur le besoin.
  let pvgisPerKwc: number | null = null;
  // Plafond « panneaux nécessaires » (Change A) : dicté par la facture, PERSISTE à
  // travers les bascules d'orientation/calepinage et l'édition d'obstacles. Posés =
  // min(neededPanels, ce qui tient). `neededAuto` : tant que vrai, on le redérive de
  // la facture ; un réglage manuel (+/−/saisie) le fige jusqu'au prochain changement
  // de facture ou nouveau tracé.
  let neededPanels = 0;
  let neededAuto = true;

  const monthlyBill = (): number => {
    const raw = parseFloat((billEl?.value || '').replace(/\s/g, '').replace(',', '.'));
    return Number.isFinite(raw) && raw > 0 ? raw : 0;
  };

  // — Three.js —
  const map = new maplibregl.Map({
    container: mapEl,
    // Imagerie satellite : Mapbox (Maxar Vivid, plus nette sur le Maroc) si un
    // token PUBLIC_MAPBOX_TOKEN est posé, sinon REPLI inchangé sur le style
    // hybride MapTiler. La géolocalisation/recherche reste sur MapTiler (clé
    // toujours requise) — Mapbox n'apporte QUE l'imagerie.
    style: buildSatelliteStyle({ maptilerKey: opts.maptilerKey, mapboxToken: opts.mapboxToken }) as maplibregl.StyleSpecification | string,
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
    console.warn('[roof-tool-pro4] erreur carte (non bloquante) :', msg);
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
  // Change B : photo satellite posée sur la face supérieure du toit. Texture mise en
  // cache par bbox (chargée UNE fois par tracé) ; matériau du deck courant suivi pour
  // l'appliquer dès l'arrivée de l'image. Repli silencieux (deck gris) si pas de token
  // Mapbox ou échec de chargement.
  let roofTex: THREE.Texture | null = null;
  let roofTexKey = '';
  let deckMaterial: THREE.MeshStandardMaterial | null = null;
  // Change C : meshes d'obstacles 3D (transparents) suivis par id pour les DÉPLACER
  // en direct pendant un glissé, et l'origine ENU de la scène courante (centroïde).
  const obstacleMeshes = new Map<string, THREE.Mesh>();
  let sceneOrigin: LngLat = [0, 0];

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

  /** Libère un objet (et sa géométrie/ses matériaux). L'étiquette d'obstacle porte
   *  une texture canvas UNIQUE par rendu → libérée ici ; les textures PARTAGÉES
   *  (texture de panneau, photo de toit en cache) ne sont jamais touchées. */
  function disposeObject(obj: THREE.Object3D) {
    const holder = obj as THREE.Mesh & { material?: THREE.Material | THREE.Material[] };
    const isSprite = (obj as THREE.Sprite).isSprite === true;
    // La géométrie d'un Sprite est PARTAGÉE (interne à three) → ne pas la libérer.
    if (!isSprite) holder.geometry?.dispose?.();
    const mat = holder.material;
    const mats = Array.isArray(mat) ? mat : mat ? [mat] : [];
    for (const m of mats) {
      if (isSprite) (m as THREE.SpriteMaterial).map?.dispose?.(); // texture canvas unique
      m.dispose();
    }
  }

  function disposeScene() {
    if (!sceneRoot) return;
    for (const child of [...sceneRoot.children]) {
      child.traverse(disposeObject); // inclut les arêtes/étiquettes enfants
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

  /** UV de la face supérieure du toit = VRAIE position (Web Mercator) de chaque
   *  sommet dans l'étendue EXACTE de l'image satellite (calculée par
   *  roofImageRequest, et NON la bbox demandée — l'endpoint Static élargit la bbox).
   *  Le sommet, en ENU, est reprojeté en lng/lat via l'origine de la scène puis en
   *  UV. Le mesh ÉTANT le polygone tracé (ShapeGeometry), seule l'imagerie du
   *  contour est peinte, alignée au pixel près sur le calepinage et les obstacles. */
  function setDeckUVs(geo: THREE.BufferGeometry, origin: LngLat, extent: [number, number, number, number]) {
    const cosLat = Math.cos(origin[1] * DEG2RAD);
    const pos = geo.attributes.position;
    const uv = new Float32Array(pos.count * 2);
    for (let i = 0; i < pos.count; i++) {
      const lng = origin[0] + pos.getX(i) / (DEG2M * cosLat);
      const lat = origin[1] + pos.getY(i) / DEG2M;
      const [u, v] = roofVertexUV(lng, lat, extent);
      uv[i * 2] = u;
      uv[i * 2 + 1] = v;
    }
    geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  }

  /** Pose (ou réapplique) la photo satellite sur la face supérieure du toit. Image
   *  demandée par centre+zoom (étendue déterministe) → cachée par cette étendue,
   *  chargée une seule fois par tracé. Sans token Mapbox ou en cas d'échec : deck
   *  gris inchangé (gracieux). */
  function applyRoofPhoto(deck: THREE.Mesh, mat: THREE.MeshStandardMaterial, origin: LngLat) {
    deckMaterial = mat;
    if (!opts.mapboxToken || vertices.length < 3) return;
    const req = roofImageRequest(ringBBox(vertices));
    setDeckUVs(deck.geometry, origin, req.extent);
    const key = req.extent.map((n) => n.toFixed(6)).join(',');
    if (roofTex && roofTexKey === key) {
      mat.map = roofTex;
      mat.color.set(0xffffff);
      mat.needsUpdate = true;
      return;
    }
    const url = mapboxStaticRoofImageUrl(opts.mapboxToken, req.center, req.zoom, req.w, req.h);
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const tex = new THREE.Texture(img);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 8;
      tex.needsUpdate = true;
      roofTex = tex;
      roofTexKey = key;
      // Réapplique sur le deck COURANT (un bascule a pu le recréer entre-temps).
      if (deckMaterial) {
        deckMaterial.map = tex;
        deckMaterial.color.set(0xffffff);
        deckMaterial.needsUpdate = true;
        map.triggerRepaint();
      }
    };
    img.onerror = () => {
      /* imagerie indisponible → on garde le deck gris, sans erreur visible */
    };
    img.src = url;
  }

  /** Étiquette de taille (« L × l m ») dessinée sur un canevas → sprite 3D posé SUR
   *  la boîte d'obstacle (Change B). Enfant du mesh : suit la boîte quand on la
   *  déplace. Toujours face caméra, sans test de profondeur (lisible par-dessus la
   *  3D, jamais masquée par le bâtiment), dimensionnée en mètres réels (lisible sur
   *  mobile sans écraser la boîte ni les panneaux). */
  function makeDimSprite(text: string): THREE.Sprite {
    const fontPx = 60;
    const padX = 26;
    const padY = 16;
    const font = `bold ${fontPx}px "Inter", system-ui, -apple-system, Segoe UI, sans-serif`;
    const measure = document.createElement('canvas').getContext('2d');
    if (measure) measure.font = font;
    const textW = measure ? measure.measureText(text).width : text.length * fontPx * 0.55;
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(textW + padX * 2);
    canvas.height = fontPx + padY * 2;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.font = font;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const r = 18;
      const w = canvas.width;
      const h = canvas.height;
      ctx.beginPath();
      ctx.moveTo(r, 0);
      ctx.arcTo(w, 0, w, h, r);
      ctx.arcTo(w, h, 0, h, r);
      ctx.arcTo(0, h, 0, 0, r);
      ctx.arcTo(0, 0, w, 0, r);
      ctx.closePath();
      ctx.fillStyle = 'rgba(7, 11, 29, 0.84)';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = 'rgba(243, 204, 102, 0.7)'; // teinte laiton (GOLD) discrète
      ctx.stroke();
      ctx.lineWidth = 6;
      ctx.strokeStyle = 'rgba(7, 11, 29, 0.95)';
      ctx.strokeText(text, w / 2, h / 2 + 2);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, w / 2, h / 2 + 2);
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    tex.needsUpdate = true;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
    const worldW = 1.9; // largeur ~1,9 m → lisible sans masquer la boîte/les panneaux
    sprite.scale.set(worldW, (worldW * canvas.height) / canvas.width, 1);
    sprite.renderOrder = 20;
    return sprite;
  }

  // — Rendu d'une config (Sud sur châssis OU Est-Ouest en chevrons) —
  function renderScene(pack: PackResult, grid: PanelGrid, tiltDeg: number, family: ConfigFamily, maxCount: number) {
    if (!sceneRoot || !sun) return;
    setOrigin(pack.origin);
    sceneOrigin = pack.origin;
    obstacleMeshes.clear();
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
    const deckMat = new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 });
    const deck = new THREE.Mesh(new THREE.ShapeGeometry(shape), deckMat);
    deck.position.z = wallH + 0.02;
    deck.receiveShadow = true;
    sceneRoot.add(deck);
    // Change B : pose la photo satellite (géo-alignée, détourée au tracé) sur la
    // face supérieure. L'origine de la scène sert à reprojeter les sommets en lng/lat.
    applyRoofPhoto(deck, deckMat, pack.origin);

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

    // Obstacles marqués (Change C) : volume SEMI-TRANSPARENT à la VRAIE taille
    // (largeur E-O × longueur N-S), posé sur le toit, avec une arête visible — la
    // photo satellite dessous (le vrai climatiseur/cheminée) transparaît, ce qui
    // confirme que la boîte est bien posée dessus. Sélectionné → teinte or.
    if (obstacles.length) {
      const cosLat = Math.cos(pack.origin[1] * DEG2RAD);
      for (const o of obstacles) {
        const ox = (o.centerLng - pack.origin[0]) * DEG2M * cosLat;
        const oy = (o.centerLat - pack.origin[1]) * DEG2M;
        const selected = o.id === selectedObsId;
        const tint = selected ? 0xf3cc66 : 0xff6b6b;
        const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, OBSTACLE_BOX_H_M);
        const mat = new THREE.MeshStandardMaterial({
          color: tint,
          metalness: 0.1,
          roughness: 0.7,
          transparent: true,
          opacity: selected ? 0.5 : 0.42,
          depthWrite: false, // laisse la texture du toit transparaître
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(ox, oy, wallH + OBSTACLE_BOX_H_M / 2 + 0.05);
        mesh.renderOrder = 3;
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color: tint, transparent: true, opacity: 0.95 }),
        );
        mesh.add(edges);
        // Change B : taille affichée SUR la boîte, en 3D (plus de libellé « en
        // dessous » sur la carte). Enfant du mesh → suit la boîte au déplacement.
        const label = makeDimSprite(dimsLabel(o));
        label.position.set(0, 0, OBSTACLE_BOX_H_M / 2 + 0.6);
        mesh.add(label);
        sceneRoot.add(mesh);
        obstacleMeshes.set(o.id, mesh);
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
    // Aucun « tapis » sombre : le fond satellite réel (les vrais environs) reste
    // visible autour du bâtiment, qui se lit comme un volume 3D posé dans son
    // contexte, son toit texturé sur le dessus (détouré au tracé). La photo du toit
    // (surélevée) et le sol viennent de la même imagerie source.
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
    // Change B : la taille de l'obstacle s'affiche désormais SUR la boîte en 3D
    // (sprite, cf. makeDimSprite) — plus de libellé de cote « en dessous » posé au
    // sol sur la carte, qui sortait du cadre en vue inclinée.
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
    updateAreaReadout();
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

  // — Plafond « panneaux nécessaires » (Change A) —
  const clampNeeded = (n: number): number => Math.max(1, Math.min(400, Math.round(n)));
  /** Posés = min(plafond besoin, ce qui tient). Sans facture (besoin 0) il n'y a
   *  pas de besoin à plafonner → on montre ce qui tient (comportement historique). */
  const placedFor = (grid: PanelGrid): number =>
    neededPanels > 0 ? Math.max(0, Math.min(neededPanels, grid.count)) : grid.count;

  /** Synchronise le contrôle éditable + sa note honnête (besoin vs ce qui tient). */
  function syncNeedControl(fitCount: number, familyLabel: string) {
    const active = neededPanels > 0;
    if (needInputEl) {
      needInputEl.disabled = !active;
      if (document.activeElement !== needInputEl) needInputEl.value = active ? fmt(neededPanels) : '—';
    }
    if (needMinusEl) needMinusEl.disabled = !active || neededPanels <= 1;
    if (needPlusEl) needPlusEl.disabled = !active || neededPanels >= 400;
    if (!needNoteEl) return;
    if (!active) {
      needNoteEl.textContent = 'Indiquez votre facture pour dimensionner le nombre de panneaux.';
      return;
    }
    const placed = Math.min(neededPanels, fitCount);
    if (placed < neededPanels) {
      needNoteEl.textContent = `${fmt(neededPanels)} nécessaires — ${fmt(placed)} tiennent en ${familyLabel} (toit ou obstacles). On pose ${fmt(placed)}.`;
    } else if (fitCount > neededPanels) {
      needNoteEl.textContent = `${fmt(neededPanels)} couvrent votre facture (+10 %) — il reste de la place sur le toit, laissée libre.`;
    } else {
      needNoteEl.textContent = `On pose ${fmt(placed)} panneaux.`;
    }
  }

  interface RenderConfigOpts {
    pack: PackResult;
    grid: PanelGrid;
    family: ConfigFamily;
    tiltDeg: number;
    isReco: boolean;
    title: string;
    why: string;
    sourceLabel?: string;
    rowId: string | null;
  }

  /** Rendu UNIFIÉ : pose min(besoin, ce qui tient), recalcule kWc/kWh/économies
   *  depuis ce nombre POSÉ (jamais la capacité max de la config). */
  function renderConfig(o: RenderConfigOpts) {
    const placed = placedFor(o.grid);
    const kwc = o.grid.count > 0 ? (o.grid.kwc * placed) / o.grid.count : 0;
    const tableAnnual = productionKwh(centroidLat, o.family, o.tiltDeg, kwc);
    // Affinage PVGIS : rendement par kWc × kWc POSÉ (suit le plafond/contrainte).
    const annualKwh = o.isReco && pvgisPerKwc != null ? pvgisPerKwc * kwc : tableAnnual;
    const target = rec ? rec.targetAnnualKwh : billToAnnualKwh(monthlyBill());
    const savings = annualSavingsMad(annualKwh, target); // plafonné à la conso
    renderScene(o.pack, o.grid, o.tiltDeg, o.family, placed);
    paintCard(
      {
        title: o.title,
        isReco: o.isReco,
        count: placed,
        kwc,
        annualKwh,
        pct: target > 0 ? (annualKwh / target) * 100 : 0,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why: o.why,
      },
      o.sourceLabel,
    );
    syncNeedControl(o.grid.count, o.family === 'eastwest' ? 'Est-Ouest' : 'plein sud');
    syncTiltControl(o.tiltDeg, o.isReco);
    if (o.isReco) paintMaxLine();
    highlightRow(o.rowId);
  }

  /** Reflète l'inclinaison RÉELLEMENT dessinée dans le curseur + son libellé.
   *  Ne touche pas le curseur pendant que l'utilisateur le manipule. */
  function syncTiltControl(tiltDeg: number, isReco: boolean) {
    const t = Math.round(tiltDeg);
    if (tiltRangeEl && document.activeElement !== tiltRangeEl) tiltRangeEl.value = String(t);
    if (tiltValueEl) tiltValueEl.textContent = `${t}°${isReco ? ' · reco' : ''}`;
    if (tiltRecoBtn) tiltRecoBtn.setAttribute('aria-pressed', String(isReco && useRecommended));
  }

  function renderSelection() {
    if (!closed || vertices.length < 3 || !rec) return;
    const ring: LngLat[] = [...vertices];

    if (useRecommended) {
      const r = rec.recommended;
      const pack = packConfig(ring, centroidLat, { family: r.family, tiltDeg: r.tiltDeg, obstructions: obstructionRings() });
      const grid = r.panelOrientation === 'portrait' ? pack.portrait : pack.landscape;
      renderConfig({
        pack,
        grid,
        family: r.family,
        tiltDeg: r.tiltDeg,
        isReco: true,
        title: r.label,
        why: r.notes,
        sourceLabel: pvgisPerKwc != null ? '(production affinée via PVGIS)' : '(production estimée — table par latitude)',
        rowId: r.id,
      });
      return;
    }

    const family = sel.family;
    const tiltDeg = tiltOf(family);
    const pack = packConfig(ring, centroidLat, { family, tiltDeg, obstructions: obstructionRings() });
    const grid = gridFor(pack);
    renderConfig({
      pack,
      grid,
      family,
      tiltDeg,
      isReco: false,
      title: `${family === 'eastwest' ? 'Est-Ouest' : 'Plein sud'} ${tiltDeg}° · ${grid.panelOrientation === 'portrait' ? 'portrait' : 'paysage'}`,
      why: 'Vous explorez une configuration manuelle. Le « Recommandé » reste le meilleur compromis pour votre facture.',
      rowId: null,
    });
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

  function paintMaxLine() {
    if (!rec) return;
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
      // Le comparatif respecte le plafond « besoin » : on montre le nombre POSÉ
      // (min(besoin, ce qui tient pour cette config)) et recalcule kWc/kWh/économies
      // dessus — jamais la capacité max. Sans facture (besoin 0), on montre la
      // capacité de chaque config à titre indicatif.
      const placed = neededPanels > 0 ? Math.min(neededPanels, c.count) : c.count;
      const scale = c.count > 0 ? placed / c.count : 0;
      const kwc = c.kwc * scale;
      const annualKwh = c.annualKwh * scale;
      // Économies recalculées sur la production posée (plafond ONEE non linéaire) —
      // pas un simple produit en croix.
      const savings = scale >= 1 ? { low: c.savingsLow, high: c.savingsHigh } : annualSavingsMad(annualKwh, rec.targetAnnualKwh);
      const cover = rec.targetAnnualKwh > 0 ? Math.round((annualKwh / rec.targetAnnualKwh) * 100) : 0;
      tr.innerHTML =
        `<td>${c.label}${c.id === rec.recommended.id ? ' <span style="color:var(--color-brass-300)">✓</span>' : ''}</td>` +
        `<td class="num">${fmt(placed)}</td>` +
        `<td class="num">${kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })}</td>` +
        `<td class="num">${fmt(Math.round(annualKwh))}</td>` +
        `<td class="num">${cover} %</td>` +
        `<td class="num">${fmtMad(savings.low)} – ${fmtMad(savings.high)}</td>`;
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
    pvgisPerKwc = null;
    // Plafond « besoin » : redérivé de la facture tant que l'utilisateur ne l'a pas
    // figé. INDÉPENDANT des obstacles — eux ne changent que « ce qui tient », pas le
    // besoin énergétique — donc une édition d'obstacle ne réécrit jamais ce nombre.
    if (neededAuto) {
      const n = neededPanelsForTarget(rec.targetAnnualKwh, centroidLat);
      neededPanels = n > 0 ? clampNeeded(n) : 0;
    }
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
      if (res.ok && data.ok && typeof data.annualKwh === 'number' && r.kwc > 0) {
        // Stocke le rendement (kWh/kWc) — réappliqué au nombre POSÉ, qui peut être
        // sous le besoin si le toit/les obstacles contraignent.
        pvgisPerKwc = data.annualKwh / r.kwc;
        if (useRecommended) renderSelection();
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
    moveObs = null;
    rec = null;
    pvgisPerKwc = null;
    roofTex?.dispose();
    roofTex = null;
    roofTexKey = '';
    deckMaterial = null;
    neededPanels = 0;
    neededAuto = true;
    if (needInputEl) {
      needInputEl.value = '—';
      needInputEl.disabled = true;
    }
    if (needMinusEl) needMinusEl.disabled = true;
    if (needPlusEl) needPlusEl.disabled = true;
    if (needNoteEl) needNoteEl.textContent = '';
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
    updateAreaReadout();
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

  // — Déplacement d'un obstacle (glissé), Change C —
  /** Tente de saisir un obstacle sous le pointeur pour le déplacer. Renvoie true si
   *  un glissé de déplacement démarre (→ on neutralise le pan de la carte). */
  function tryBeginMove(lngLat: LngLat, point: maplibregl.Point): boolean {
    if (!closed || obstacleMode) return false;
    const hit = obstacleAtPoint(point);
    if (!hit) return false;
    const o = obstacles.find((x) => x.id === hit);
    if (!o) return false;
    selectObstacle(hit);
    moveObs = { id: hit, startLng: lngLat[0], startLat: lngLat[1], centerLng: o.centerLng, centerLat: o.centerLat, moved: false };
    map.dragPan.disable();
    return true;
  }
  function doMove(lngLat: LngLat) {
    if (!moveObs) return;
    const idx = obstacles.findIndex((x) => x.id === moveObs!.id);
    if (idx < 0) return;
    // Delta lng/lat : annule le parallaxe absolu de la vue inclinée.
    const centerLng = moveObs.centerLng + (lngLat[0] - moveObs.startLng);
    const centerLat = moveObs.centerLat + (lngLat[1] - moveObs.startLat);
    moveObs.moved = true;
    obstacles[idx] = { ...obstacles[idx], centerLng, centerLat };
    redrawObstacles();
    // Déplacement 3D EN DIRECT du seul mesh concerné (pas de re-pavage par image).
    const mesh = obstacleMeshes.get(moveObs.id);
    if (mesh) {
      const cosLat = Math.cos(sceneOrigin[1] * DEG2RAD);
      mesh.position.x = (centerLng - sceneOrigin[0]) * DEG2M * cosLat;
      mesh.position.y = (centerLat - sceneOrigin[1]) * DEG2M;
      map.triggerRepaint();
    }
  }
  function endMove() {
    if (!moveObs) return;
    const moved = moveObs.moved;
    moveObs = null;
    map.dragPan.enable();
    suppressClick = true; // évite la désélection au click de synthèse
    // Re-pavage + recalcul seulement si l'obstacle a réellement bougé.
    if (moved) recompute();
  }

  // — Interactions carte —
  map.on('mousedown', (e) => {
    suppressClick = false;
    if (obstacleMode) {
      beginDraw([e.lngLat.lng, e.lngLat.lat], e.point);
      return;
    }
    tryBeginMove([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('mousemove', (e) => {
    if (drawing) moveDraw([e.lngLat.lng, e.lngLat.lat]);
    else if (moveObs) doMove([e.lngLat.lng, e.lngLat.lat]);
  });
  map.on('mouseup', (e) => {
    if (drawing) endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
    else if (moveObs) endMove();
  });
  map.on('touchstart', (e) => {
    suppressClick = false;
    if (obstacleMode) {
      beginDraw([e.lngLat.lng, e.lngLat.lat], e.point);
      return;
    }
    if (!e.points || e.points.length === 1) tryBeginMove([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('touchmove', (e) => {
    if (drawing) {
      e.preventDefault();
      moveDraw([e.lngLat.lng, e.lngLat.lat]);
    } else if (moveObs) {
      e.preventDefault();
      doMove([e.lngLat.lng, e.lngLat.lat]);
    }
  });
  map.on('touchend', (e) => {
    if (drawing) endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
    else if (moveObs) endMove();
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
    // Changer la facture = nouveau besoin : on relâche le réglage manuel éventuel.
    neededAuto = true;
    if (closed) recompute();
  });
  updateBillKwh();

  // — Plafond « panneaux nécessaires » : +/− et saisie directe (Change A) —
  function setNeeded(n: number) {
    neededPanels = clampNeeded(n);
    neededAuto = false; // figé sur le choix de l'utilisateur jusqu'au prochain changement de facture/tracé
    renderSelection();
  }
  needMinusEl?.addEventListener('click', () => {
    if (neededPanels > 0) setNeeded(neededPanels - 1);
  });
  needPlusEl?.addEventListener('click', () => setNeeded(neededPanels + 1));
  needInputEl?.addEventListener('input', () => {
    const v = parseInt((needInputEl.value || '').replace(/\D/g, ''), 10);
    if (Number.isFinite(v) && v > 0) setNeeded(v);
  });
  needInputEl?.addEventListener('blur', () => {
    if (needInputEl) needInputEl.value = neededPanels > 0 ? fmt(neededPanels) : '—';
  });

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

  // — V2 : curseur d'inclinaison (exploration fine) + bouton « reco » —
  if (tiltRangeEl) {
    tiltRangeEl.min = String(TILT_SWEEP_MIN);
    tiltRangeEl.max = '35';
    tiltRangeEl.step = '1';
    const onTilt = () => {
      const v = Number(tiltRangeEl.value);
      if (!Number.isFinite(v)) return;
      // En quittant le mode « reco » par le curseur, conserver la famille
      // RÉELLEMENT affichée (la reco peut être Est-Ouest) ; n'imposer que
      // l'inclinaison. Évite un basculement surprise vers le Sud.
      const fam: ConfigFamily = useRecommended ? (rec?.recommended.family ?? sel.family) : sel.family;
      useRecommended = false;
      sel = { ...sel, family: fam, tilt: v };
      if (tiltValueEl) tiltValueEl.textContent = `${Math.round(v)}°`;
      syncChips();
      renderSelection();
    };
    tiltRangeEl.addEventListener('input', onTilt);
  }
  tiltRecoBtn?.addEventListener('click', () => {
    useRecommended = true;
    sel = { family: rec?.recommended.family ?? 'south', tilt: 'reco', orient: 'auto' };
    syncChips();
    renderSelection();
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

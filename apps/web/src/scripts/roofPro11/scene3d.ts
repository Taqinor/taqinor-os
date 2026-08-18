/**
 * Scène 3D Three.js du builder pro-11 (couche WebGL personnalisée MapLibre).
 * Extraite de roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement
 * INCHANGÉ, octet pour octet.
 *
 * Contient : la COUCHE PERSONNALISÉE MapLibre (`onAdd` qui bâtit le
 * `WebGLRenderer`/scène/caméra/lumières/ombres, `render`, et `onRemove` qui
 * libère TOUTES les ressources GPU — garde W70 conservée à l'identique), les
 * utilitaires de scène (`disposeObject`/`disposeScene`/`makeIM`/`setOrigin`),
 * la texture/photo de toit (`setDeckUVs`/`applyRoofPhoto`), l'étiquette de
 * taille (`makeDimSprite`), le chemin de construction d'une zone
 * (`buildZoneMeshes`), le re-rendu des autres zones (`appendOtherZones`) et le
 * rendu complet d'une zone active (`renderScene`).
 *
 * L'entrée garde la construction de la carte et le boot `map.on('load')` (qui
 * AJOUTE `customLayer`) ; la couche elle-même + ses callbacks viennent d'ici.
 * Les fonctions inter-modules (renderConfig de l'optimiseur, etc.) ne sont pas
 * appelées d'ici ; l'état partagé (obstacles/zones/disposition) passe par `ctx`.
 */
import maplibregl from 'maplibre-gl';
import * as THREE from 'three';
import { PANEL2_THICK_M, sunDirection } from '../../lib/roofPro2';
import {
  type PackResult,
  type PanelGrid,
  type ConfigFamily,
} from '../../lib/estimatorBrainV2';
import {
  PITCHED_FLUSH_STANDOFF_M,
  eaveUpSlopeCoord,
  flushPanelCenterAt,
  pitchedDeckZ,
  upSlopeCoord,
  pitchedRise,
} from '../../lib/estimatorBrainV6';
import { ringBBox, type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import { roofImageRequest, roofVertexUV, mapboxStaticRoofImageUrl } from '../../lib/roofConfig';
import {
  FLOOR_HEIGHT_M,
  DECK_THK,
  FLOORS,
  OBSTACLE_BOX_H_M,
  DEG2RAD,
  DEG2M,
} from './constants';
import { type ZoneRenderPlan } from './types';
import { makeCanadianPanelTexture } from './panelTexture';
import { type Ctx } from './context';

/** Dépendances injectées (carte + capacités de l'appareil, figées au boot). */
export interface Scene3dDeps {
  /** La carte MapLibre (canvas WebGL, triggerRepaint pour les images de toit asynchrones). */
  map: maplibregl.Map;
  /** Appareil modeste (mémoire ≤ 4 Go ou ≤ 4 cœurs) → antialias coupé, ombres réduites. */
  lowEnd: boolean;
  /** Côté de la carte d'ombre (1024 en bas de gamme, 2048 sinon). */
  shadowSize: number;
  /**
   * VISIONNEUSE (lecture seule, page publique /proposition) — additif, défaut
   * false : le rendu de l'ERP reste octet pour octet inchangé sans ce drapeau.
   * Le module n'écoute AUCUN geste utilisateur (il ne fait que dessiner), donc
   * ce drapeau ne coupe aucune interaction ; il retire les deux marques qui
   * n'ont de sens que pendant l'ÉDITION :
   *  1. les pans NON actifs ne sont plus atténués (dans l'ERP le pan en cours
   *     d'édition ressort ; le client, lui, doit voir TOUTE son installation
   *     avec les mêmes matériaux — mêmes panneaux, mêmes rails, même éclat) ;
   *  2. les étiquettes de TAILLE posées sur les boîtes d'obstacle (« 2,0 × 1,2 m »,
   *     l'aide au placement) ne sont plus dessinées — les boîtes, elles, restent.
   */
  readOnly?: boolean;
}

export interface Scene3d {
  /** Couche personnalisée MapLibre (ajoutée par l'entrée dans map.on('load')). */
  customLayer: maplibregl.CustomLayerInterface;
  /** Libère les meshes/matériaux de la scène (sans toucher les textures partagées). */
  disposeScene: () => void;
  /** Positionne l'origine ENU de la matrice modèle (lng/lat du pack actif). */
  setOrigin: (origin: LngLat) => void;
  /** Re-dessine les AUTRES zones (subduées) ; renvoie leurs anneaux translatés. */
  appendOtherZones: (activeOrigin: LngLat) => [number, number][][];
  /** Rendu complet de la zone ACTIVE (bâtiment + dalle + panneaux + obstacles + soleil). */
  renderScene: (
    pack: PackResult,
    grid: PanelGrid,
    tiltDeg: number,
    family: ConfigFamily,
    maxCount: number,
    flush?: boolean,
    occupiedSet?: Set<number>,
  ) => void;
  /** Réinitialise la photo de toit + la matrice modèle (appelé par clearEditorState). */
  resetTextures: () => void;
  /** W88 — surligne le panneau de la zone active correspondant à `cellIndex` (or = sélection),
   *  ou efface tout surlignage (cellIndex null). Pose les couleurs d'instance + repeint. */
  setPanelHighlight: (cellIndex: number | null) => void;
  /** WJ21 — teinte CHAQUE panneau de la zone active par son accès solaire (0–1) via
   *  `colorFor(cellIndex)` (rouge=faible → vert=plein soleil), ou remet tout à blanc si
   *  `colorFor` est null (heatmap désactivée). Réutilise le buffer instanceColor. */
  setSolarAccessHeatmap: (colorFor: ((cellIndex: number) => { r: number; g: number; b: number }) | null) => void;
  /** W115 — instantané PNG (data URL) de la 3D rendue, ou null si le renderer/canvas
   *  est indisponible. Le renderer partage le canvas MapLibre (map.getCanvas()). */
  snapshot: () => string | null;
}

// ════════════════════════ W107 — faîtière commune (pans connectés) ════════════════════════
// Deux pans EN PENTE qui partagent une arête doivent se rejoindre sur une FAÎTIÈRE commune,
// pas flotter comme deux couvercles indépendants. On détecte l'adjacence en ENU (mètres, frame
// commune de la scène), on calcule la hauteur de faîtière NATURELLE de chaque pan (rive amont)
// et on remonte chaque pan connecté d'un `ridgeLiftM` constant pour que les arêtes de faîtière
// du groupe coïncident à la hauteur MAX du groupe (le plan monte sans changer de pente → l'égout
// reste ≥ wallH). Tout est PUR (numbers in, numbers out), sans Three ni DOM.

/** Un pan en pente candidat à l'alignement de faîtière (ring ENU dans la frame de scène). */
export interface RidgePan {
  /** Anneau ENU (mètres) du pan, déjà translaté dans la frame commune de la scène active. */
  ringENU: [number, number][];
  /** Azimut de face (= pack.azimuthDeg du pavage affleurant). */
  facingAzimuthDeg: number;
  /** Pente (°) du pan. */
  tiltDeg: number;
}

/** Longueur (m) du segment de RECOUVREMENT entre deux arêtes quasi-collinéaires/coïncidentes
 *  en ENU, ou 0 si elles ne sont pas une arête partagée (écart trop grand, angle trop large,
 *  recouvrement trop court). Mêmes tolérances que roofAdjacency (1,5 m / 12° / 0,5 m). */
function enuSharedEdgeOverlapM(
  a1: [number, number],
  a2: [number, number],
  b1: [number, number],
  b2: [number, number],
): number {
  const MAX_GAP_M = 1.5;
  const MAX_ANGLE_DEG = 12;
  const MIN_OVERLAP_M = 0.5;
  const da: [number, number] = [a2[0] - a1[0], a2[1] - a1[1]];
  const db: [number, number] = [b2[0] - b1[0], b2[1] - b1[1]];
  const la = Math.hypot(da[0], da[1]);
  const lb = Math.hypot(db[0], db[1]);
  if (la <= 0 || lb <= 0) return 0;
  // Angle d'arête (non-orienté, mod 180°).
  const angA = Math.atan2(da[1], da[0]) * (180 / Math.PI);
  const angB = Math.atan2(db[1], db[0]) * (180 / Math.PI);
  let diff = Math.abs(angA - angB) % 180;
  if (diff > 90) diff = 180 - diff;
  if (diff > MAX_ANGLE_DEG) return 0;
  // Écart moyen point→segment (robuste aux longueurs différentes).
  const distPS = (p: [number, number], s: [number, number], e: [number, number]): number => {
    const se: [number, number] = [e[0] - s[0], e[1] - s[1]];
    const len2 = se[0] * se[0] + se[1] * se[1];
    if (len2 === 0) return Math.hypot(p[0] - s[0], p[1] - s[1]);
    let t = ((p[0] - s[0]) * se[0] + (p[1] - s[1]) * se[1]) / len2;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(p[0] - (s[0] + se[0] * t), p[1] - (s[1] + se[1] * t));
  };
  const gap = (distPS(b1, a1, a2) + distPS(b2, a1, a2) + distPS(a1, b1, b2) + distPS(a2, b1, b2)) / 4;
  if (gap > MAX_GAP_M) return 0;
  // Recouvrement : projette les 4 extrémités sur la direction unitaire de l'arête A.
  const ux = da[0] / la;
  const uy = da[1] / la;
  const proj = (p: [number, number]): number => (p[0] - a1[0]) * ux + (p[1] - a1[1]) * uy;
  const lo2 = Math.min(proj(b1), proj(b2));
  const hi2 = Math.max(proj(b1), proj(b2));
  const overlap = Math.min(la, hi2) - Math.max(0, lo2);
  return overlap >= MIN_OVERLAP_M ? overlap : 0;
}

/** Deux pans ENU partagent-ils une arête ? (au moins une paire d'arêtes coïncidentes). */
function pansSharedEdge(a: RidgePan, b: RidgePan): boolean {
  const ra = a.ringENU;
  const rb = b.ringENU;
  for (let i = 0; i < ra.length; i++) {
    const a1 = ra[i];
    const a2 = ra[(i + 1) % ra.length];
    for (let j = 0; j < rb.length; j++) {
      const b1 = rb[j];
      const b2 = rb[(j + 1) % rb.length];
      if (enuSharedEdgeOverlapM(a1, a2, b1, b2) > 0) return true;
    }
  }
  return false;
}

/** Hauteur de faîtière NATURELLE d'un pan (rive amont) au-dessus de sa base : (rive amont −
 *  égout) × tan(pente) — la montée du plan incliné sur toute sa profondeur. */
function naturalRidgeHeightM(pan: RidgePan): number {
  let minUp = Infinity;
  let maxUp = -Infinity;
  for (const [x, y] of pan.ringENU) {
    const u = upSlopeCoord(x, y, pan.facingAzimuthDeg);
    if (u < minUp) minUp = u;
    if (u > maxUp) maxUp = u;
  }
  if (!Number.isFinite(minUp) || !Number.isFinite(maxUp)) return 0;
  return pitchedRise(maxUp - minUp, pan.tiltDeg);
}

/**
 * W107 — pour chaque pan EN PENTE, le lift vertical (m) à appliquer pour que les pans
 * CONNECTÉS se rejoignent sur une faîtière commune. On regroupe les pans par adjacence
 * (composantes connexes via arêtes partagées) ; dans chaque groupe de ≥ 2 pans, la faîtière
 * commune est la hauteur MAX des faîtières naturelles du groupe, et chaque pan reçoit
 * `lift = ridgeCommun − faîtièreNaturelle` (≥ 0 ; le plan monte, l'égout reste ≥ base). Un
 * pan isolé (groupe de 1) ou non-pente garde lift 0 → rendu inchangé. Pur.
 */
export function computeRidgeLifts(pans: RidgePan[]): number[] {
  const n = pans.length;
  const lifts = new Array<number>(n).fill(0);
  if (n < 2) return lifts;
  // Composantes connexes (union-find léger via parcours).
  const parent = Array.from({ length: n }, (_, i) => i);
  const find = (x: number): number => {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]];
      x = parent[x];
    }
    return x;
  };
  const union = (a: number, b: number) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent[ra] = rb;
  };
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (pansSharedEdge(pans[i], pans[j])) union(i, j);
    }
  }
  // Faîtière naturelle par pan + max par groupe.
  const natural = pans.map(naturalRidgeHeightM);
  const groupMax = new Map<number, number>();
  const groupSize = new Map<number, number>();
  for (let i = 0; i < n; i++) {
    const g = find(i);
    groupMax.set(g, Math.max(groupMax.get(g) ?? -Infinity, natural[i]));
    groupSize.set(g, (groupSize.get(g) ?? 0) + 1);
  }
  for (let i = 0; i < n; i++) {
    const g = find(i);
    if ((groupSize.get(g) ?? 1) < 2) continue; // pan isolé → pas de lift
    lifts[i] = Math.max(0, (groupMax.get(g) ?? natural[i]) - natural[i]);
  }
  return lifts;
}

// ═══════════ STRUCTURE RÉELLE TAQINOR — toit plat (fiche géométrique du 18/08) ═══════════
// Relevé sur les photos de chantier du dépôt (`equipe-pose-structure`, `mesure-rails`,
// `champ-villa`) : la structure n'appartient PAS au panneau. Ce n'est ni un bac lesté
// continu ni un trio de montants par module, mais un TRIANGLE RECTANGLE assemblé sur
// place — trois pièces boulonnées en profilé C galvanisé PERFORÉ — posé à CHAQUE
// jointure de panneaux, chaque pied sur sa propre bordure béton préfabriquée.

/** Profilé C galvanisé perforé : section 41 × 41 mm (rail type Unistrut — la seule
 *  section vue sur TOUS les chantiers : ni tube rond, ni cornière alu). */
const PROFILE_M = 0.041;
/** Platine acier plate boulonnée au pied de chaque montant : 120 × 60 mm, 8 mm. */
const PLATINE_L_M = 0.12;
const PLATINE_W_M = 0.06;
const PLATINE_T_M = 0.008;
/** Bordure béton préfabriquée = le SOCLE, discontinu : 100 × 20 × 12 cm, gris clair. */
const SOCLE_L_M = 1.0;
const SOCLE_W_M = 0.2;
const SOCLE_H_M = 0.12;
/** Perforation du profilé : fentes oblongues ~11 mm de large, une tous les 30 mm ;
 *  ~20 mm de fente laissent ~10 mm de matière entre deux trous, comme sur les rails
 *  photographiés. C'est LA signature visuelle de la structure. */
const PERF_PITCH_M = 0.03;
const PERF_SLOT_W_M = 0.011;
const PERF_SLOT_L_M = 0.02;
/** Jeu MAXIMAL toléré entre deux panneaux encore tenus pour CONTIGUS le long d'une
 *  rangée. Le jeu de pose réel vaut 2 cm ; 25 cm absorbe les marges de l'optimiseur sans
 *  jamais souder deux rangées distinctes. Au-delà, le tronçon est coupé et chaque morceau
 *  reçoit ses propres triangles d'extrémité — un panneau ISOLÉ porte donc un triangle à
 *  chacun de ses deux bords. */
const CONTIG_GAP_M = 0.25;

/** Un panneau POSÉ ramené dans le repère LOCAL de la pose — la matière première de la
 *  détection de contiguïté qui place les triangles aux jointures. */
interface PanelFoot {
  /** Abscisse du centre le long de la rangée (m). */
  la: number;
  /** Profondeur de la rangée (m) — les panneaux d'une même rangée la partagent. */
  ld: number;
  /** Demi-largeur du module le long de la rangée (m) — propre à SA pose (PV62). */
  halfA: number;
  /** Longueur de pente du module (m) — donne la longueur du rail incliné. */
  slopeP: number;
  /** Montée du module (m) — donne la hauteur du montant arrière. */
  riseP: number;
  /** Demi-empreinte au sol (m) — donne la longueur de la traverse basse. */
  halfDepthP: number;
  /** Inclinaison SIGNÉE (rad) : négative sur la face E d'un chevron Est-Ouest. */
  signedTilt: number;
}

/**
 * Texture PROCÉDURALE du profilé C galvanisé PERFORÉ (aucun asset externe, aucune
 * dépendance nouvelle). Une TUILE = un module de perforation : les 41 mm de largeur de
 * la face sur l'axe U, les 30 mm d'entraxe des trous sur l'axe V. On y peint un fond
 * galva mate-brillant (lèvres pliées du C plus claires, fines rayures de laminage) et
 * une fente oblongue sombre. Bakée UNE fois sur un canvas 64 × 64 — puissance de deux,
 * donc `RepeatWrapping` sûr jusque sur un contexte WebGL 1 — puis répétée le long de
 * chaque pièce par `stretchProfileUVs`.
 */
function makeGalvaProfileTexture(): THREE.Texture {
  const S = 64;
  const c = document.createElement('canvas');
  c.width = S;
  c.height = S;
  const g = c.getContext('2d')!;
  // Dégradé TRANSVERSAL (U = les 41 mm de la face) : les deux lèvres pliées du profilé
  // accrochent la lumière, le fond de la face reste plus mat.
  const grad = g.createLinearGradient(0, 0, S, 0);
  grad.addColorStop(0, '#e4e8ec');
  grad.addColorStop(0.18, '#bcc3ca');
  grad.addColorStop(0.5, '#a3abb3');
  grad.addColorStop(0.82, '#bcc3ca');
  grad.addColorStop(1, '#e4e8ec');
  g.fillStyle = grad;
  g.fillRect(0, 0, S, S);
  // Rayures de laminage — trois filets clairs très peu contrastés (galva mate-brillant).
  g.strokeStyle = 'rgba(255,255,255,0.16)';
  g.lineWidth = 1;
  for (const x of [S * 0.3, S * 0.5, S * 0.7]) {
    g.beginPath();
    g.moveTo(x, 0);
    g.lineTo(x, S);
    g.stroke();
  }
  // La fente oblongue, aux cotes réelles rapportées à la tuile.
  const sw = (PERF_SLOT_W_M / PROFILE_M) * S;
  const sh = (PERF_SLOT_L_M / PERF_PITCH_M) * S;
  const x0 = (S - sw) / 2;
  const y0 = (S - sh) / 2;
  const r = sw / 2;
  g.beginPath();
  g.moveTo(x0 + r, y0);
  g.arcTo(x0 + sw, y0, x0 + sw, y0 + sh, r);
  g.arcTo(x0 + sw, y0 + sh, x0, y0 + sh, r);
  g.arcTo(x0, y0 + sh, x0, y0, r);
  g.arcTo(x0, y0, x0 + sw, y0, r);
  g.closePath();
  g.fillStyle = '#2b3036'; // le trou : on voit l'ombre à l'intérieur du profilé
  g.fill();
  g.lineWidth = 1.5;
  g.strokeStyle = 'rgba(240,244,248,0.75)'; // tranche de tôle éclairée
  g.stroke();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 8;
  tex.needsUpdate = true;
  return tex;
}

/**
 * Étale la texture de perforations sur la LONGUEUR réelle d'un profilé, pour que le pas
 * de 30 mm reste physique quelle que soit la pièce (rail de 2,40 m ou montant de 0,77 m).
 * Les 24 sommets d'une `BoxGeometry` non segmentée sont ordonnés par face — +X, −X, +Y,
 * −Y, +Z, −Z — et chaque face mappe `u` sur son premier axe de plan et `v` sur le second :
 * (±X) → (z, y), (±Y) → (x, z), (±Z) → (x, y). Toutes nos pièces sont bâties LONGUES SUR
 * Y, donc les quatre faces LONGUES (±X, ±Z) portent `v` le long de la pièce : on y répète
 * la tuile `longueur / 30 mm` fois et on laisse `u` couvrir exactement la face. Les deux
 * faces de BOUT (±Y, 41 × 41 mm) restent en 0..1 — invisibles à l'échelle de la carte.
 */
function stretchProfileUVs(geo: THREE.BoxGeometry, lengthM: number) {
  const uv = geo.attributes.uv as THREE.BufferAttribute;
  if (!uv || uv.count < 24) return;
  const reps = Math.max(1, Math.round(lengthM / PERF_PITCH_M));
  for (const face of [0, 1, 4, 5]) {
    for (let i = face * 4; i < face * 4 + 4; i++) uv.setY(i, uv.getY(i) * reps);
  }
  uv.needsUpdate = true;
}

export function createScene3d(ctx: Ctx, deps: Scene3dDeps): Scene3d {
  const { map, lowEnd, shadowSize } = deps;
  // Absent (ERP) → false : toutes les branches gardées ci-dessous sont inertes.
  const readOnly = deps.readOnly === true;
  const opts = ctx.opts;

  const fmt1 = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const dimsLabel = (o: Obstacle) => `${fmt1(o.lengthM)} × ${fmt1(o.widthM)} m`;

  let renderer: THREE.WebGLRenderer | null = null;
  let scene: THREE.Scene | null = null;
  let sceneRoot: THREE.Group | null = null;
  let threeCamera: THREE.Camera | null = null;
  let sun: THREE.DirectionalLight | null = null;
  let modelMatrix: THREE.Matrix4 | null = null;
  const panelTex = makeCanadianPanelTexture();
  // Texture du profilé galvanisé PERFORÉ, PARTAGÉE par toutes les pièces de structure et
  // bakée une seule fois (patron W71 : jamais dans le chemin de rendu). En mode bas de
  // gamme on ne la fabrique PAS — le profilé garde une couleur galva unie : zéro canvas,
  // zéro upload GPU, zéro échantillonnage supplémentaire.
  const galvaTex: THREE.Texture | null = lowEnd ? null : makeGalvaProfileTexture();
  // Change B : photo satellite posée sur la face supérieure du toit. Texture mise en
  // cache par bbox (chargée UNE fois par tracé) ; matériau du deck courant suivi pour
  // l'appliquer dès l'arrivée de l'image. Repli silencieux (deck gris) si pas de token
  // Mapbox ou échec de chargement.
  let roofTex: THREE.Texture | null = null;
  let roofTexKey = '';
  let deckMaterial: THREE.MeshStandardMaterial | null = null;
  // W107 — lift de faîtière commune par zone (id → mètres), recalculé à chaque renderScene
  // dans la frame ENU de la zone active. Vide / 0 → rendu inchangé (pans isolés, toit plat).
  let ridgeLifts = new Map<string, number>();

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

  /**
   * PV62 — comme `compose`, plus deux réglages LOCAUX (appliqués APRÈS l'orientation du
   * panneau, donc dans son propre repère) : `spinZ` = rotation autour de sa NORMALE (une
   * pose tournée de 90° = le même module en paysage au lieu de portrait) et une ÉCHELLE
   * locale (longueur de rail / de montant adaptée à cette pose). Sans ces réglages
   * (spinZ = 0, échelles = 1) le résultat est EXACTEMENT `compose` — les pavages
   * uniformes ne passent d'ailleurs jamais par ici.
   */
  const composeLocal = (
    px: number,
    py: number,
    pz: number,
    rotZ: number,
    rotX: number,
    spinZ: number,
    sx = 1,
    sy = 1,
    sz = 1,
  ): THREE.Matrix4 => {
    const m = compose(px, py, pz, rotZ, rotX);
    if (spinZ !== 0) m.multiply(new THREE.Matrix4().makeRotationZ(spinZ));
    if (sx !== 1 || sy !== 1 || sz !== 1) m.multiply(new THREE.Matrix4().makeScale(sx, sy, sz));
    return m;
  };

  // W71 — CACHE des matériaux + géométries STATIQUES du système panneau (verre/cadre/
  // dos/boîtier + profilé galvanisé perforé/platine/bordure béton de la structure, et la
  // TEXTURE de perforations). Avant le split ils étaient ré-alloués DANS buildZoneMeshes
  // à CHAQUE rendu (glissé du curseur d'inclinaison, déplacement d'obstacle, édition de
  // disposition) → chaque MeshPhysicalMaterial (verre, clearcoat) reprovoquait une
  // recompilation de shader. On les fabrique UNE fois ici (variantes active + `dim`,
  // distinctes car `dim` mute couleur/opacité en place) et on les réutilise tel quel.
  // disposeScene ne touche QUE les meshes par zone ; ce cache n'est libéré qu'à
  // onRemove (disposeSharedCache). Les matériaux bâtiment/dalle restent par rendu (la
  // dalle porte la photo satellite, et leur géométrie varie de toute façon par zone).
  // Les géométries panneau/rail/montant/traverse dépendent de grid (alongRow/slope/rise/
  // empreinte au sol) → restent par rendu ; seules les BoxGeometry à arêtes CONSTANTES
  // (boîtier, platine, bordure béton) sont cachées.
  // Ressources PARTAGÉES (matériaux + géométries cachés) : disposeObject ne doit JAMAIS
  // les libérer (un rendu suivant les réutilise) ; seul disposeSharedCache le fait.
  const sharedResources = new WeakSet<THREE.Material | THREE.BufferGeometry>();
  interface PanelMatSet {
    glassMat: THREE.MeshPhysicalMaterial;
    frameMat: THREE.MeshStandardMaterial;
    backMat: THREE.MeshStandardMaterial;
    panelMats: THREE.Material[];
    jboxMat: THREE.MeshStandardMaterial;
    /** Profilé C galvanisé perforé — rails inclinés, montants, traverses ET platines. */
    rackMat: THREE.MeshStandardMaterial;
    /** Bordure béton préfabriquée (le socle discontinu sous chaque pied). */
    socleMat: THREE.MeshStandardMaterial;
  }
  const buildPanelMatSet = (dim: boolean): PanelMatSet => {
    const glassMat = new THREE.MeshPhysicalMaterial({ map: panelTex, color: 0xffffff, metalness: 0.1, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08 });
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x9aa0aa, metalness: 0.85, roughness: 0.35 });
    const backMat = new THREE.MeshStandardMaterial({ color: 0xe6e8ee, metalness: 0.1, roughness: 0.6 });
    if (dim) {
      // Panneaux légèrement désaturés/assombris pour les zones non actives.
      glassMat.color.set(0xb8bcc6);
      frameMat.color.set(0x70757e);
      backMat.color.set(0xb0b3ba);
    }
    const jboxMat = new THREE.MeshStandardMaterial({ color: 0x15171c, metalness: 0.3, roughness: 0.6 });
    // Galvanisé mate-brillant : la texture perforée porte la teinte (couleur neutre pour
    // ne pas l'assombrir) ; sans texture (lowEnd) on peint la même teinte galva en aplat.
    const rackMat = new THREE.MeshStandardMaterial({
      map: galvaTex,
      color: galvaTex ? 0xffffff : 0xb0b7be,
      metalness: 0.78,
      roughness: 0.38,
    });
    // Béton préfabriqué gris CLAIR (bordure de chantier), totalement mat.
    const socleMat = new THREE.MeshStandardMaterial({ color: 0xc2c0b6, metalness: 0, roughness: 0.95 });
    for (const m of [glassMat, frameMat, backMat, jboxMat, rackMat, socleMat]) sharedResources.add(m);
    return { glassMat, frameMat, backMat, panelMats: [frameMat, frameMat, frameMat, frameMat, glassMat, backMat], jboxMat, rackMat, socleMat };
  };
  let panelMatsActive: PanelMatSet | null = null;
  let panelMatsDim: PanelMatSet | null = null;
  const panelMatSet = (dim: boolean): PanelMatSet => {
    if (dim) return (panelMatsDim ??= buildPanelMatSet(true));
    return (panelMatsActive ??= buildPanelMatSet(false));
  };

  // Géométries STATIQUES (arêtes constantes) du système panneau : boîtier de jonction,
  // platine de pied, bordure béton. Indépendantes de grid → cachées une fois.
  let jboxGeoCache: THREE.BoxGeometry | null = null;
  let plateGeoCache: THREE.BoxGeometry | null = null;
  let socleGeoCache: THREE.BoxGeometry | null = null;
  const jboxGeoOf = (): THREE.BoxGeometry => {
    if (!jboxGeoCache) {
      jboxGeoCache = new THREE.BoxGeometry(0.4, 0.12, 0.035);
      jboxGeoCache.translate(0, 0, -(PANEL2_THICK_M / 2 + 0.02));
      sharedResources.add(jboxGeoCache);
    }
    return jboxGeoCache;
  };
  /** Platine acier plate (120 × 60 × 8 mm) boulonnée sous chaque pied de triangle. */
  const plateGeoOf = (): THREE.BoxGeometry => {
    if (!plateGeoCache) sharedResources.add((plateGeoCache = new THREE.BoxGeometry(PLATINE_L_M, PLATINE_W_M, PLATINE_T_M)));
    return plateGeoCache;
  };
  /** Bordure béton préfabriquée (100 × 20 × 12 cm), longueur ALIGNÉE sur la rangée. */
  const socleGeoOf = (): THREE.BoxGeometry => {
    if (!socleGeoCache) sharedResources.add((socleGeoCache = new THREE.BoxGeometry(SOCLE_L_M, SOCLE_W_M, SOCLE_H_M)));
    return socleGeoCache;
  };

  /** Libère le cache W71 (matériaux + géométries statiques partagés). Appelé UNIQUEMENT
   *  à onRemove — jamais par disposeScene (sinon le rendu suivant perdrait son cache). */
  function disposeSharedCache() {
    for (const set of [panelMatsActive, panelMatsDim]) {
      if (!set) continue;
      set.glassMat.dispose();
      set.frameMat.dispose();
      set.backMat.dispose();
      set.jboxMat.dispose();
      set.rackMat.dispose();
      set.socleMat.dispose();
    }
    panelMatsActive = null;
    panelMatsDim = null;
    jboxGeoCache?.dispose();
    plateGeoCache?.dispose();
    socleGeoCache?.dispose();
    jboxGeoCache = null;
    plateGeoCache = null;
    socleGeoCache = null;
  }

  // W89 — récupération de perte de contexte WebGL. Sur mobile (mise en arrière-plan /
  // retour au premier plan), le GPU peut PERDRE le contexte WebGL : sans gestionnaire,
  // la 3D reste DÉFINITIVEMENT blanche. On écoute `webglcontextlost` (preventDefault →
  // autorise la restauration) et `webglcontextrestored` (reconstruit le WebGLRenderer
  // sur le contexte frais + re-rend). `glLost` met `render` en no-op tant que le contexte
  // est perdu (rien à dessiner sans GPU).
  let glLost = false;
  let glCanvas: HTMLCanvasElement | null = null;

  /** (Re)construit le WebGLRenderer Three.js sur le contexte GL fourni + (re)configure
   *  ses options de rendu. Extrait de onAdd pour être réutilisable à la restauration. */
  function buildRenderer(gl: WebGLRenderingContext | WebGL2RenderingContext) {
    renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: !lowEnd });
    renderer.autoClear = false;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
  }

  function onContextLost(e: Event) {
    // preventDefault impératif : sans cela le navigateur n'émettra JAMAIS
    // `webglcontextrestored` et la 3D resterait perdue à jamais.
    e.preventDefault();
    glLost = true;
    renderer?.dispose();
    renderer = null;
  }

  function onContextRestored() {
    if (!glCanvas) return;
    // Récupère le contexte frais du canvas MapLibre (même attributs) et reconstruit le
    // renderer ; la scène (meshes/lumières/soleil) survit en mémoire JS → un simple
    // re-rendu via triggerRepaint la repeint avec le GPU restauré.
    const gl = (glCanvas.getContext('webgl2') || glCanvas.getContext('webgl')) as
      | WebGLRenderingContext
      | WebGL2RenderingContext
      | null;
    if (!gl) return;
    buildRenderer(gl);
    glLost = false;
    map.triggerRepaint();
  }

  const customLayer = {
    id: 'rp9-3d',
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
      buildRenderer(gl);
      // W89 — branche les gestionnaires de perte/restauration de contexte sur le canvas
      // MapLibre (un seul et même canvas WebGL partagé). preventDefault à la perte, rebuild
      // à la restauration.
      glCanvas = map.getCanvas();
      glCanvas.addEventListener('webglcontextlost', onContextLost as EventListener, false);
      glCanvas.addEventListener('webglcontextrestored', onContextRestored as EventListener, false);
    },
    render(_gl: WebGLRenderingContext | WebGL2RenderingContext, args: maplibregl.CustomRenderMethodInput) {
      if (glLost || !renderer || !scene || !threeCamera || !modelMatrix) return;
      const m = new THREE.Matrix4().fromArray(Array.from(args.defaultProjectionData.mainMatrix));
      threeCamera.projectionMatrix = m.multiply(modelMatrix);
      renderer.resetState();
      renderer.render(scene, threeCamera);
    },
    // W70 — libère TOUTES les ressources GPU quand la couche est retirée (navigation
    // client Astro, démontage de la carte) : meshes/matériaux de scène (disposeScene),
    // textures partagées (panneau + photo de toit) et le WebGLRenderer lui-même. Sans
    // cela le renderer + ses textures fuient à chaque départ de la page.
    onRemove(_m: maplibregl.Map, _gl: WebGLRenderingContext | WebGL2RenderingContext) {
      disposeScene();
      disposeSharedCache(); // W71 — cache matériaux/géométries partagés (jamais dans disposeScene)
      panelTex.dispose();
      galvaTex?.dispose(); // texture procédurale du profilé perforé (absente en lowEnd)
      roofTex?.dispose();
      roofTex = null;
      renderer?.dispose();
      renderer = null;
      // W89 — détache les gestionnaires de perte/restauration de contexte (pas de fuite
      // d'écouteur sur le canvas après le démontage de la couche).
      if (glCanvas) {
        glCanvas.removeEventListener('webglcontextlost', onContextLost as EventListener, false);
        glCanvas.removeEventListener('webglcontextrestored', onContextRestored as EventListener, false);
        glCanvas = null;
      }
    },
  };

  /** Libère un objet (et sa géométrie/ses matériaux). L'étiquette d'obstacle porte
   *  une texture canvas UNIQUE par rendu → libérée ici ; les textures PARTAGÉES
   *  (texture de panneau, photo de toit en cache) ne sont jamais touchées. */
  function disposeObject(obj: THREE.Object3D) {
    const holder = obj as THREE.Mesh & { material?: THREE.Material | THREE.Material[] };
    const isSprite = (obj as THREE.Sprite).isSprite === true;
    // La géométrie d'un Sprite est PARTAGÉE (interne à three) → ne pas la libérer.
    // W71 — les géométries STATIQUES cachées (jbox/front/lest) sont partagées entre
    // rendus → jamais libérées ici (sinon corruption au rendu suivant) ; seul
    // disposeSharedCache les libère à onRemove. Les géométries par rendu (panneau/rail/
    // arrière, bâtiment/dalle, boîtes d'obstacle) restent libérées normalement.
    if (!isSprite && holder.geometry && !sharedResources.has(holder.geometry)) holder.geometry.dispose();
    const mat = holder.material;
    const mats = Array.isArray(mat) ? mat : mat ? [mat] : [];
    for (const m of mats) {
      if (isSprite) (m as THREE.SpriteMaterial).map?.dispose?.(); // texture canvas unique
      // W71 — matériaux cachés (système panneau, active + dim) partagés → non libérés ici.
      if (!sharedResources.has(m)) m.dispose();
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
    if (!opts.mapboxToken || ctx.vertices.length < 3) return;
    const req = roofImageRequest(ringBBox(ctx.vertices));
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
      // W70 — libère l'ANCIENNE texture de toit avant de la remplacer (fuite GPU à chaque
      // re-tracé sur une nouvelle bbox). On NE libère QUE l'orpheline : si la texture courante
      // est encore montée sur le matériau du deck (.map), three la libérera à la prochaine
      // recomposition du matériau — la libérer ici corromprait le rendu en cours.
      if (roofTex && roofTex !== tex && roofTex !== deckMaterial?.map) roofTex.dispose();
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
    const ctx2d = canvas.getContext('2d');
    if (ctx2d) {
      ctx2d.font = font;
      ctx2d.textAlign = 'center';
      ctx2d.textBaseline = 'middle';
      const r = 18;
      const w = canvas.width;
      const h = canvas.height;
      ctx2d.beginPath();
      ctx2d.moveTo(r, 0);
      ctx2d.arcTo(w, 0, w, h, r);
      ctx2d.arcTo(w, h, 0, h, r);
      ctx2d.arcTo(0, h, 0, 0, r);
      ctx2d.arcTo(0, 0, w, 0, r);
      ctx2d.closePath();
      ctx2d.fillStyle = 'rgba(7, 11, 29, 0.84)';
      ctx2d.fill();
      ctx2d.lineWidth = 2;
      ctx2d.strokeStyle = 'rgba(243, 204, 102, 0.7)'; // teinte laiton (GOLD) discrète
      ctx2d.stroke();
      ctx2d.lineWidth = 6;
      ctx2d.strokeStyle = 'rgba(7, 11, 29, 0.95)';
      ctx2d.strokeText(text, w / 2, h / 2 + 2);
      ctx2d.fillStyle = '#ffffff';
      ctx2d.fillText(text, w / 2, h / 2 + 2);
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

  /** CHEMIN DE CONSTRUCTION UNIQUE d'une zone : bâtiment + dalle (deck) + panneaux
   *  (+ triangles de structure et bordures béton en toit plat, rien en pose
   *  affleurante). Utilisé par renderScene pour la zone ACTIVE
   *  (offX=offY=0, dim=false → octet pour octet identique à avant) ET par
   *  appendOtherZones pour les AUTRES zones (offset GPS→ENU + dim=true subdué). Tout
   *  est ajouté à `sceneRoot`. NE touche PAS `setOrigin`/`disposeScene` (renderScene
   *  en reste propriétaire) ni la photo satellite (zone active uniquement). En dim, les
   *  obstacles de la zone (depuis `plan.obstacles`) sont rendus en boîtes subduées sans
   *  étiquette ni enregistrement (non manipulables). Renvoie la dalle (+ son matériau,
   *  pour la photo) et l'anneau TRANSLATÉ (pour l'enveloppe d'ombre). */
  function buildZoneMeshes(
    plan: ZoneRenderPlan,
    offX: number,
    offY: number,
    dim: boolean,
    occupiedSet?: Set<number>,
    // `isOtherZone` = « ce n'est PAS le pan actif ». C'était jusqu'ici la même
    // chose que `dim` (seuls les autres pans étaient atténués) et le défaut le
    // garde tel quel — les deux appelants historiques passent donc exactement la
    // même valeur qu'avant. Les deux notions ne se séparent qu'en mode
    // VISIONNEUSE, où les autres pans ne sont plus atténués mais restent « autres »
    // (ils ne doivent ni voler la référence de pick des panneaux à la zone active,
    // ni perdre leurs propres obstacles).
    isOtherZone: boolean = dim,
  ): { deck: THREE.Mesh; deckMat: THREE.MeshStandardMaterial; ring: [number, number][] } {
    const { pack, grid, tiltDeg, family, flush } = plan;
    const wallH = FLOORS * FLOOR_HEIGHT_M;
    const ring: [number, number][] = pack.ringENU.map(([x, y]) => [x + offX, y + offY]);
    // W107 — lift de faîtière commune : le pan incliné monte de `ridgeLiftM` (sans changer
    // de pente) pour rejoindre la faîtière partagée d'un pan voisin. 0 (défaut / pan isolé /
    // toit plat) → rendu inchangé, octet pour octet.
    const ridgeLiftM = flush ? Math.max(0, plan.ridgeLiftM ?? 0) : 0;

    // Bâtiment
    const shape = new THREE.Shape();
    ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
    shape.closePath();
    const buildingMat = new THREE.MeshStandardMaterial({ color: 0xe2e7f2, roughness: 0.85, metalness: 0 });
    if (dim) {
      // Zone NON active : bâtiment subdué (plus sombre + légèrement transparent) pour
      // que la zone ACTIVE (en cours d'édition) ressorte clairement.
      buildingMat.color.set(0x9aa3b4);
      buildingMat.transparent = true;
      buildingMat.opacity = 0.55;
    }
    const building = new THREE.Mesh(
      new THREE.ExtrudeGeometry(shape, { depth: wallH, bevelEnabled: false }),
      buildingMat,
    );
    building.castShadow = true;
    building.receiveShadow = true;
    sceneRoot!.add(building);

    const baseZ = wallH + DECK_THK;
    // FIX 1 (V6) — en pente (flush), réf. d'égout (le point le plus AVAL du tracé) :
    // la pente monte à partir de l'égout, rien ne passe sous le toit.
    const pitchEaveCoord = flush ? eaveUpSlopeCoord(ring, pack.azimuthDeg) : 0;
    const deckMat = new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 });
    if (dim) {
      deckMat.color.set(0x8b9099);
      deckMat.transparent = true;
      deckMat.opacity = 0.7;
    }
    const deckGeo = new THREE.ShapeGeometry(shape);
    if (flush) {
      // FIX 1 (V6) — la SURFACE DE TOIT elle-même devient un plan INCLINÉ : chaque
      // sommet de la dalle est relevé à la hauteur du plan (pente × distance à
      // l'égout). La photo détourée, mappée par position HORIZONTALE (applyRoofPhoto),
      // reste géo-alignée. Plat : dalle horizontale (inchangé).
      const dpos = deckGeo.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < dpos.count; i++) {
        // W107 — + ridgeLiftM : tout le plan incliné monte vers la faîtière commune.
        dpos.setZ(i, pitchedDeckZ(dpos.getX(i), dpos.getY(i), pitchEaveCoord, ridgeLiftM, tiltDeg, pack.azimuthDeg));
      }
      dpos.needsUpdate = true;
      deckGeo.computeVertexNormals();
    }
    const deck = new THREE.Mesh(deckGeo, deckMat);
    deck.position.z = wallH + 0.02;
    deck.receiveShadow = true;
    sceneRoot!.add(deck);

    // W90 — MASSING DU TOIT EN PENTE (pignons/jupe de rive). En pente (flush) la dalle
    // est un PLAN INCLINÉ posé au-dessus du toit plat du bâtiment (z = wallH) : sans rien
    // d'autre, le coin amont « flotte » au-dessus d'une boîte à toit plat. On ferme le
    // volume en bâtissant une JUPE périmétrique : pour chaque arête (a→b) de l'anneau, un
    // quadrilatère vertical du toit plat (wallH) jusqu'au dessous de la dalle inclinée
    // (wallH + pitchedDeckZ au sommet). Le pan aval (où la dalle touche presque wallH) n'a
    // qu'un mince mur ; le pan amont monte en triangle → lecture « pignon/croupe » fermée
    // pour toute empreinte tracée. Toit PLAT : non exécuté → INCHANGÉ.
    if (flush) {
      const n = ring.length;
      const positions: number[] = [];
      // z du dessous de la dalle inclinée à un sommet (repère local du mur, base z=0).
      // W107 — + ridgeLiftM : la jupe monte jusqu'à la dalle relevée vers la faîtière commune.
      const deckRiseAt = (x: number, y: number) =>
        0.02 + ridgeLiftM + pitchedDeckZ(x, y, pitchEaveCoord, 0, tiltDeg, pack.azimuthDeg);
      for (let i = 0; i < n; i++) {
        const [ax, ay] = ring[i];
        const [bx, by] = ring[(i + 1) % n];
        const za = deckRiseAt(ax, ay);
        const zb = deckRiseAt(bx, by);
        // Deux triangles (a-bas, b-bas, b-haut) + (a-bas, b-haut, a-haut). Les normales
        // sont recalculées (computeVertexNormals) ; double face pour rester visible quel
        // que soit le sens de parcours de l'anneau.
        positions.push(ax, ay, 0, bx, by, 0, bx, by, zb);
        positions.push(ax, ay, 0, bx, by, zb, ax, ay, za);
      }
      const skirtGeo = new THREE.BufferGeometry();
      skirtGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
      skirtGeo.computeVertexNormals();
      // Murs de pignon = même teinte que le bâtiment (continuité du volume), double face.
      const skirtMat = new THREE.MeshStandardMaterial({
        color: dim ? 0x9aa3b4 : 0xe2e7f2,
        roughness: 0.85,
        metalness: 0,
        side: THREE.DoubleSide,
        transparent: dim,
        opacity: dim ? 0.55 : 1,
      });
      const skirt = new THREE.Mesh(skirtGeo, skirtMat);
      skirt.position.z = wallH; // base posée sur le toit plat du bâtiment
      skirt.castShadow = true;
      skirt.receiveShadow = true;
      sceneRoot!.add(skirt);
    }

    // Axes de visée à partir de l'azimut de la famille.
    const azRad = pack.azimuthDeg * DEG2RAD;
    const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
    const u: [number, number] = [-f[1], f[0]];
    const rowAngleRad = Math.atan2(u[1], u[0]);
    const ca = Math.cos(rowAngleRad);
    const sa = Math.sin(rowAngleRad);
    const rx = (lx: number, ly: number): [number, number] => [lx * ca - ly * sa, lx * sa + ly * ca];
    /** Monde → repère local de la pose (inverse EXACTE de `rx`) : abscisse le long de la
     *  rangée, puis profondeur. Sert à regrouper les panneaux par rangée. */
    const invRx = (wx: number, wy: number): [number, number] => [wx * ca + wy * sa, -wx * sa + wy * ca];

    const alongRow = grid.rowWidthM;
    const slope = grid.slopeLenM;
    const tilt = tiltDeg * DEG2RAD;
    const rise = slope * Math.sin(tilt);
    const depthFootprint = slope * Math.cos(tilt);
    // Hauteur libre du pied AVANT (m) = la PILE réelle sous le rail incliné : bordure béton
    // (12 cm) + platine (8 mm) + demi-section du profilé C (20,5 mm) ≈ 0,149 m. C'est la cote
    // « pied avant 0,10-0,15 m » de la fiche du 18/08, et elle redonne exactement le montant
    // arrière de 0,77 m relevé à Marrakech (0,62 de montée + 0,15 de socle) sur un module de
    // 2,40 m incliné à 15°.
    const frontStrut = SOCLE_H_M + PLATINE_T_M + PROFILE_M / 2;
    const halfAlong = alongRow / 2;
    const halfDepth = depthFootprint / 2;

    // W71 — matériaux du système panneau réutilisés depuis le cache (variante active ou
    // `dim`) au lieu d'être ré-alloués à chaque rendu (plus de recompilation de shader
    // MeshPhysicalMaterial sur un simple glissé). Rendu visuel identique.
    const { glassMat, frameMat, backMat, panelMats, jboxMat, rackMat, socleMat } = panelMatSet(dim);
    const panelGeo = new THREE.BoxGeometry(alongRow, slope, PANEL2_THICK_M);
    const jboxGeo = jboxGeoOf();

    // Cellules POSÉES : disposition personnalisée explicite (zone active en mode
    // calepinage → ces cellules exactes, possiblement non contiguës) sinon les
    // `plan.count` premières cellules du pavage (comportement historique).
    // W88 — on garde aussi l'INDEX de lattice de chaque panneau rendu (ordre des instances),
    // pour relier un panneau 3D survolé/tapé à sa cellule (highlight + suppression ciblée).
    const panelCellIndices: number[] = [];
    const panels = grid.panels.filter((_, i) => {
      const keep = occupiedSet ? occupiedSet.has(i) : i < Math.max(0, plan.count);
      if (keep) panelCellIndices.push(i);
      return keep;
    });
    const panelMatsArr: THREE.Matrix4[] = [];
    const railMats: THREE.Matrix4[] = []; // hypoténuses — rails inclinés porteurs
    const backMats: THREE.Matrix4[] = []; // montants arrière VERTICAUX
    const crossMats: THREE.Matrix4[] = []; // traverses basses horizontales au sol
    const plateMats: THREE.Matrix4[] = []; // platines acier aux deux pieds
    const socleMats: THREE.Matrix4[] = []; // bordures béton sous chaque pied
    // Les TROIS profilés du triangle sont bâtis LONGS SUR Y (`stretchProfileUVs` en dépend)
    // et leur longueur suit grid/tilt (pente, empreinte au sol, montée) → géométries PAR
    // RENDU. Platine et bordure béton ont des arêtes CONSTANTES → cache W71.
    const railGeo = new THREE.BoxGeometry(PROFILE_M, slope, PROFILE_M);
    stretchProfileUVs(railGeo, slope);
    const backGeo = new THREE.BoxGeometry(PROFILE_M, frontStrut + rise, PROFILE_M);
    stretchProfileUVs(backGeo, frontStrut + rise);
    const crossGeo = new THREE.BoxGeometry(PROFILE_M, depthFootprint, PROFILE_M);
    stretchProfileUVs(crossGeo, depthFootprint);
    const plateGeo = plateGeoOf();
    const socleGeo = socleGeoOf();
    // Toit plat : les panneaux posés, en coordonnées LOCALES, d'où l'on déduira ensuite les
    // jointures. En pose affleurante (toit en pente) la liste reste vide → aucun triangle.
    const feet: PanelFoot[] = [];
    // PV62 — pavage MIXTE : un panneau peut porter SA pose (`orient`), différente de la
    // pose DOMINANTE qui a dimensionné les géométries partagées. C'est le MÊME module,
    // tourné de 90° dans son plan : on fait tourner son instance autour de sa propre
    // normale et on adapte par ÉCHELLE la longueur du rail et du montant arrière. Sur un
    // pavage uniforme (`orient` absent) `swapped` est toujours faux → rendu inchangé.
    const dominantIsPortrait = slope >= alongRow;

    for (const p of panels) {
      const cx = p.cx + offX;
      const cy = p.cy + offY;
      const swapped = !!p.orient && (p.orient === 'portrait') !== dominantIsPortrait;
      const slopeP = swapped ? alongRow : slope;
      const alongRowP = swapped ? slope : alongRow;
      const riseP = swapped ? slopeP * Math.sin(tilt) : rise;
      const halfAlongP = swapped ? alongRowP / 2 : halfAlong;
      const halfDepthP = swapped ? (slopeP * Math.cos(tilt)) / 2 : halfDepth;
      const spinZ = swapped ? Math.PI / 2 : 0;
      // Pour l'Est-Ouest : le sens d'inclinaison vient de la FACE du panneau
      // (chevrons dos à dos faces E/O), fournie par le cerveau. Sud : tilt simple.
      const signedTilt = family === 'eastwest' ? (p.face === 'E' ? -tilt : tilt) : tilt;
      // Toit plat : panneau surélevé sur châssis (frontStrut + montée d'ombre).
      // Toit en pente (flush) : FIX 1 (V6) — panneau COPLANAIRE, AFFLEURANT sur le
      // plan incliné. compose(yaw, tilt) donne déjà au panneau la normale du toit
      // (donc tous les panneaux sont coplanaires) ; flushPanelCenterAt pose le CENTRE
      // sur le plan + un décalage CONSTANT le long de la normale → le centre monte
      // avec la pente (vrai plan incliné, pas un calepinage plat de panneaux inclinés).
      if (flush) {
        // W107 — baseZ + ridgeLiftM : les panneaux montent avec le plan vers la faîtière commune.
        const c = flushPanelCenterAt(p.cx, p.cy, pitchEaveCoord, baseZ + ridgeLiftM, tiltDeg, pack.azimuthDeg, PITCHED_FLUSH_STANDOFF_M);
        panelMatsArr.push(composeLocal(c.x + offX, c.y + offY, c.z, rowAngleRad, signedTilt, spinZ));
      } else {
        const pZ = baseZ + frontStrut + riseP / 2 + 0.07;
        panelMatsArr.push(composeLocal(cx, cy, pZ, rowAngleRad, signedTilt, spinZ));
      }
      // Toit plat : la structure ne se dessine PAS ici. On mémorise seulement le panneau
      // dans le repère local de la pose ; les triangles seront placés APRÈS la boucle, aux
      // JOINTURES entre panneaux voisins (un triangle porte les deux bords à la fois).
      if (!flush) {
        const [la, ld] = invRx(cx, cy);
        feet.push({ la, ld, halfA: halfAlongP, slopeP, riseP, halfDepthP, signedTilt });
      }
    }

    // ── TRIANGLES À CHAQUE JOINTURE (toit plat uniquement) ────────────────────────────
    // Sur les chantiers TAQINOR le triangle est posé à CHAQUE jointure de panneaux ET aux
    // deux extrémités de rangée, chaque triangle portant le bord de ses deux voisins :
    // N panneaux CONTIGUS donnent N+1 triangles, d'où l'entraxe d'une largeur de module
    // (~1,15 m) mesuré sur les photos. Chaque triangle = 3 pièces boulonnées en profilé C
    // galvanisé perforé (rail incliné, montant arrière vertical, traverse basse au sol),
    // 2 platines et 2 bordures béton — jamais un bac lesté continu.
    if (!flush && feet.length) {
      // Rangées : les panneaux d'une même rangée partagent leur profondeur locale, arrondie
      // au décimètre (le pavage aligne les rangées à la maille près).
      const rows = new Map<number, PanelFoot[]>();
      for (const ft of feet) {
        const key = Math.round(ft.ld * 10) / 10;
        const bucket = rows.get(key);
        if (bucket) bucket.push(ft);
        else rows.set(key, [ft]);
      }
      /** Pose les 7 pièces d'UN triangle à l'abscisse `xa` de la rangée du panneau `r`. */
      const addTriangle = (xa: number, r: PanelFoot) => {
        // Côté BAS (aval) = celui vers lequel le panneau descend ; l'inclinaison signée d'un
        // chevron Est-Ouest retourne simplement le triangle, sans autre changement.
        const lowDepth = r.signedTilt >= 0 ? -r.halfDepthP : r.halfDepthP;
        const highDepth = -lowDepth;
        const axis = rx(xa, r.ld); // milieu de la traverse / du rail incliné
        const foot = rx(xa, r.ld + lowDepth); // pied AVANT
        const heel = rx(xa, r.ld + highDepth); // pied ARRIÈRE (sous le montant)
        // 1. HYPOTÉNUSE — le rail incliné qui PORTE le panneau ; longueur = pente du module
        //    (échelle locale en y quand ce panneau n'est pas dans la pose dominante).
        const railZ = baseZ + frontStrut + r.riseP / 2;
        const railScale = r.slopeP / slope;
        railMats.push(
          composeLocal(axis[0], axis[1], railZ, rowAngleRad, r.signedTilt, 0, 1, railScale, 1),
        );
        // 2. MONTANT ARRIÈRE VERTICAL — du sol jusqu'au bout haut du rail. `rotX = π/2`
        //    DRESSE le profilé (bâti long sur Y) sans changer sa perforation ; sa hauteur
        //    dérive de la montée du panneau, donc de l'inclinaison signée.
        const backH = frontStrut + r.riseP;
        const backScale = backH / (frontStrut + rise);
        backMats.push(
          composeLocal(heel[0], heel[1], baseZ + backH / 2, rowAngleRad, Math.PI / 2, 0, 1, backScale, 1),
        );
        // 3. TRAVERSE BASSE HORIZONTALE — relie le pied avant au pied du montant, posée sur
        //    les deux platines : d'où z = baseZ + frontStrut, la hauteur exacte de la pile
        //    bordure + platine + demi-profilé.
        const crossScale = depthFootprint > 0 ? (2 * r.halfDepthP) / depthFootprint : 1;
        crossMats.push(
          composeLocal(axis[0], axis[1], baseZ + frontStrut, rowAngleRad, 0, 0, 1, crossScale, 1),
        );
        // 4. PLATINES acier plates (120 × 60 mm) boulonnées aux DEUX pieds, sur la bordure.
        const plateZ = baseZ + SOCLE_H_M + PLATINE_T_M / 2;
        plateMats.push(compose(foot[0], foot[1], plateZ, rowAngleRad, 0));
        plateMats.push(compose(heel[0], heel[1], plateZ, rowAngleRad, 0));
        // 5. SOCLES DISCONTINUS — une bordure béton (100 × 20 × 12 cm) sous le pied AVANT,
        //    une sous le pied ARRIÈRE. Longue de 1 m pour un entraxe de ~1,15 m : la ligne
        //    de socles reste VISIBLEMENT interrompue, comme sur les photos de chantier.
        const socleZ = baseZ + SOCLE_H_M / 2;
        socleMats.push(compose(foot[0], foot[1], socleZ, rowAngleRad, 0));
        socleMats.push(compose(heel[0], heel[1], socleZ, rowAngleRad, 0));
      };
      for (const row of rows.values()) {
        row.sort((a, b) => a.la - b.la);
        let i = 0;
        while (i < row.length) {
          // Fin du TRONÇON contigu : deux voisins se touchent tant que l'écart de leurs
          // centres ne dépasse pas la somme de leurs demi-largeurs + le jeu toléré.
          let j = i;
          while (
            j + 1 < row.length &&
            row[j + 1].la - row[j].la <= row[j].halfA + row[j + 1].halfA + CONTIG_GAP_M
          ) j++;
          // Bord AMONT du tronçon, puis le MILIEU de chaque jointure interne, puis le bord
          // AVAL : exactement N+1 triangles pour les N panneaux contigus du tronçon.
          addTriangle(row[i].la - row[i].halfA, row[i]);
          for (let k = i; k < j; k++) {
            addTriangle((row[k].la + row[k].halfA + row[k + 1].la - row[k + 1].halfA) / 2, row[k]);
          }
          addTriangle(row[j].la + row[j].halfA, row[j]);
          i = j + 1;
        }
      }
    }

    const panelIM = makeIM(panelGeo, panelMats, panelMatsArr, true, false);
    // UN InstancedMesh par TYPE de pièce (7 au plus en toit plat, 2 en pose affleurante) :
    // le nombre de draw-calls ne dépend pas du nombre de panneaux. Seules les bordures
    // béton reçoivent l'ombre — elles sont la seule pièce posée à même la dalle.
    const meshes = [
      panelIM,
      makeIM(jboxGeo, jboxMat, panelMatsArr, true, false),
      makeIM(railGeo, rackMat, railMats, true, false),
      makeIM(backGeo, rackMat, backMats, true, false),
      makeIM(crossGeo, rackMat, crossMats, true, false),
      makeIM(plateGeo, rackMat, plateMats, true, false),
      makeIM(socleGeo, socleMat, socleMats, true, true),
    ];
    for (const me of meshes) if (me) sceneRoot!.add(me);

    // W88 — pick/highlight des panneaux : SEULEMENT pour la zone ACTIVE (non dim). On dote
    // l'InstancedMesh des panneaux d'un buffer instanceColor (tous blancs = teinte d'origine ;
    // MeshStandardMaterial multiplie sa couleur par instanceColor) pour pouvoir surligner un
    // panneau sans recréer le mesh, et on mémorise sur ctx le mesh + le mapping instance→cellule
    // afin que l'éditeur de disposition relie un panneau 3D à sa cellule de lattice.
    if (!isOtherZone) {
      if (panelIM) {
        panelIM.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(panelCellIndices.length * 3).fill(1), 3);
        panelIM.instanceColor.needsUpdate = true;
      }
      ctx.activePanelMesh = panelIM;
      ctx.activePanelCellIndex = panelCellIndices;
    }

    // Zones NON actives : obstacles rendus en boîtes subduées (sans étiquette ni drag),
    // à leur vraie position relative. La zone active gère ses obstacles vivants ailleurs.
    // En VISIONNEUSE (autre pan non atténué), les mêmes boîtes prennent la teinte
    // « vive » de la zone active — l'unique différence, et elle est cohérente : le
    // client voit tous ses pans avec le même rendu.
    if (isOtherZone && plan.obstacles.length) {
      const cosLat = Math.cos(pack.origin[1] * DEG2RAD);
      for (const o of plan.obstacles) {
        const ox = (o.centerLng - pack.origin[0]) * DEG2M * cosLat + offX;
        const oy = (o.centerLat - pack.origin[1]) * DEG2M + offY;
        const tint = dim ? 0xc06464 : 0xff6b6b;
        const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, OBSTACLE_BOX_H_M);
        const mat = new THREE.MeshStandardMaterial({
          color: tint,
          metalness: 0.1,
          roughness: 0.7,
          transparent: true,
          opacity: dim ? 0.3 : 0.42,
          depthWrite: false,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(ox, oy, wallH + OBSTACLE_BOX_H_M / 2 + 0.05);
        mesh.renderOrder = 3;
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color: tint, transparent: true, opacity: dim ? 0.6 : 0.95 }),
        );
        mesh.add(edges);
        sceneRoot!.add(mesh);
      }
    }

    return { deck, deckMat, ring };
  }

  /** W78 — bâtiment SUBDUÉ « nu » (sans panneaux) d'une zone qui n'a pas encore de
   *  `renderPlan` : une zone finie posée à 0 panneau (placedCount===0) est comptée dans
   *  les totaux mais n'aurait, sans cela, AUCUN mesh → elle disparaîtrait de la vue
   *  multi-zones (totaux et 3D en désaccord). On bâtit alors au moins son VOLUME depuis
   *  `vertices` (lng/lat → ENU relatif à l'origine active), même teinte subduée que les
   *  autres zones. Renvoie l'anneau ENU translaté (pour l'enveloppe d'ombre), ou null si
   *  le tracé n'a pas au moins 3 sommets. */
  function buildBareZoneRing(vertices: LngLat[], activeOrigin: LngLat): [number, number][] | null {
    if (vertices.length < 3) return null;
    const cosLat = Math.cos(activeOrigin[1] * DEG2RAD);
    const ring: [number, number][] = vertices.map(([lng, lat]) => [
      (lng - activeOrigin[0]) * DEG2M * cosLat,
      (lat - activeOrigin[1]) * DEG2M,
    ]);
    const wallH = FLOORS * FLOOR_HEIGHT_M;
    const shape = new THREE.Shape();
    ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
    shape.closePath();
    // Zone NON active sans panneaux : bâtiment subdué (même teinte que les autres zones).
    const buildingMat = new THREE.MeshStandardMaterial({ color: 0x9aa3b4, roughness: 0.85, metalness: 0, transparent: true, opacity: 0.55 });
    const building = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: wallH, bevelEnabled: false }), buildingMat);
    building.castShadow = true;
    building.receiveShadow = true;
    sceneRoot!.add(building);
    // Dalle nue subduée posée sur le toit (lecture « toit plat sans panneaux »).
    const deckMat = new THREE.MeshStandardMaterial({ color: 0x8b9099, roughness: 0.95, metalness: 0, transparent: true, opacity: 0.7 });
    const deck = new THREE.Mesh(new THREE.ShapeGeometry(shape), deckMat);
    deck.position.z = wallH + 0.02;
    deck.receiveShadow = true;
    sceneRoot!.add(deck);
    return ring;
  }

  /** W107 — (re)calcule le lift de faîtière commune de CHAQUE zone (id → m), recensant tous
   *  les pans EN PENTE (active + autres avec renderPlan flush) dans la frame ENU de la zone
   *  active, puis appariant les pans connectés (`computeRidgeLifts`). Pans isolés/non-pente →
   *  0. Appelée une fois en tête de renderScene ; lue par buildZoneMeshes via `ridgeLifts`. */
  function computeAllRidgeLifts(activeOrigin: LngLat, activePack: PackResult, activeTiltDeg: number, activeFlush: boolean) {
    ridgeLifts = new Map<string, number>();
    const cosLat = Math.cos(activeOrigin[1] * DEG2RAD);
    const entries: { id: string; pan: RidgePan }[] = [];
    // Zone ACTIVE (offset nul), seulement si en pente.
    if (activeFlush) {
      entries.push({
        id: ctx.activeAreaId,
        pan: { ringENU: activePack.ringENU.map(([x, y]) => [x, y]), facingAzimuthDeg: activePack.azimuthDeg, tiltDeg: activeTiltDeg },
      });
    }
    // Autres zones EN PENTE avec un renderPlan, translatées dans la frame active.
    for (const a of ctx.areas) {
      if (a.id === ctx.activeAreaId) continue;
      const plan = a.renderPlan;
      if (!plan || !plan.flush) continue;
      const offX = (plan.pack.origin[0] - activeOrigin[0]) * DEG2M * cosLat;
      const offY = (plan.pack.origin[1] - activeOrigin[1]) * DEG2M;
      entries.push({
        id: a.id,
        pan: { ringENU: plan.pack.ringENU.map(([x, y]) => [x + offX, y + offY]), facingAzimuthDeg: plan.pack.azimuthDeg, tiltDeg: plan.tiltDeg },
      });
    }
    if (entries.length < 2) return; // pan isolé → aucun lift (rendu inchangé)
    const lifts = computeRidgeLifts(entries.map((e) => e.pan));
    entries.forEach((e, i) => ridgeLifts.set(e.id, lifts[i]));
  }

  /** Re-dessine TOUTES les zones SAUF l'active, à leur vraie position relative (« toutes
   *  les zones empilées »). Pour chaque zone disposant d'un `renderPlan`, on calcule
   *  l'offset ENU entre son origine GPS et celle de la zone active, puis on construit ses
   *  meshes (subdués) via le MÊME chemin que la zone active. W78 — pour une zone SANS
   *  `renderPlan` mais finie (≥ 3 sommets), on bâtit au moins son volume nu depuis ses
   *  `vertices`, pour qu'une zone comptée à 0 panneau reste VISIBLE en 3D (parité totaux ↔
   *  vue). N'appelle JAMAIS disposeScene/setOrigin (propriété de renderScene). Renvoie les
   *  anneaux TRANSLATÉS des autres zones, pour étendre l'enveloppe d'ombre. No-op (→ [])
   *  tant qu'il n'y a qu'une zone ou qu'aucune autre n'est dessinable. */
  function appendOtherZones(activeOrigin: LngLat): [number, number][][] {
    if (!sceneRoot) return [];
    const rings: [number, number][][] = [];
    const cosLat = Math.cos(activeOrigin[1] * DEG2RAD);
    for (const a of ctx.areas) {
      if (a.id === ctx.activeAreaId) continue;
      if (a.renderPlan) {
        const plan = a.renderPlan;
        const offX = (plan.pack.origin[0] - activeOrigin[0]) * DEG2M * cosLat;
        const offY = (plan.pack.origin[1] - activeOrigin[1]) * DEG2M;
        // W107 — applique le lift de faîtière commune de cette zone (copie superficielle pour
        // ne pas muter le renderPlan stocké). 0 par défaut → rendu inchangé.
        const liftedPlan: ZoneRenderPlan = { ...plan, ridgeLiftM: ridgeLifts.get(a.id) ?? 0 };
        // VISIONNEUSE : `dim` false → ce pan est bâti avec les MÊMES matériaux que
        // le pan actif (verre, cadres, rails, châssis) ; `isOtherZone` reste true →
        // il ne touche pas la référence de pick et garde ses propres obstacles.
        const built = buildZoneMeshes(liftedPlan, offX, offY, !readOnly, undefined, true);
        rings.push(built.ring);
      } else {
        // W78 — pas de plan de rendu (zone finie à 0 panneau) : on dessine son volume nu.
        const bare = buildBareZoneRing(a.vertices, activeOrigin);
        if (bare) rings.push(bare);
      }
    }
    return rings;
  }

  // — Rendu d'une config (Sud sur châssis OU Est-Ouest en chevrons). `flush` (V3,
  //   toit en pente) pose les panneaux AFFLEURANTS sur la pente : pas de châssis ni
  //   de lest, panneau couché à l'inclinaison du toit. flush=false ⇒ rendu toit plat
  //   octet pour octet identique à pro-5. —
  function renderScene(pack: PackResult, grid: PanelGrid, tiltDeg: number, family: ConfigFamily, maxCount: number, flush = false, occupiedSet?: Set<number>) {
    if (!sceneRoot || !sun) return;
    // W69 — un rendu SANS occupation explicite vient de l'optimiseur : on mémorise le
    // plan gagnant (pack/grid/tilt/family/flush) + le comptage optimal, pour pouvoir
    // re-rendre une disposition PERSONNALISÉE (occupation non contiguë) sur le MÊME plan.
    if (!occupiedSet) {
      ctx.layoutPlan = { pack, grid, tiltDeg, family, flush };
      ctx.layoutOptimalCount = Math.max(0, Math.min(grid.panels.length, Math.round(maxCount)));
      // Un rendu optimiseur = le PLAN a (peut-être) changé : la disposition personnalisée
      // courante n'a plus de sens (cellules différentes) → on la repart de l'optimum.
      ctx.layoutState = null;
      ctx.layoutSel = null;
    }
    setOrigin(pack.origin);
    ctx.sceneOrigin = pack.origin;
    ctx.obstacleMeshes.clear();
    // W88 — l'ancien InstancedMesh des panneaux va être libéré (disposeScene) : on oublie sa
    // référence + son mapping avant le re-rendu (buildZoneMeshes les ré-attribue pour la zone
    // active). Évite de garder un pick/highlight sur un mesh disposé.
    ctx.activePanelMesh = null;
    ctx.activePanelCellIndex = [];
    disposeScene();

    const wallH = FLOORS * FLOOR_HEIGHT_M;

    // W69 — disposition personnalisée : si un ensemble d'index occupés est fourni, on
    // rend EXACTEMENT ces cellules (potentiellement non contiguës) ; sinon on garde le
    // comportement historique (les `maxCount` premières cellules du pavage).
    const drawnPanels = occupiedSet
      ? grid.panels.filter((_, i) => occupiedSet.has(i))
      : grid.panels.slice(0, Math.max(0, maxCount));

    // W107 — recense les pans EN PENTE connectés (active + autres) et calcule leur lift de
    // faîtière commune AVANT de bâtir les meshes (lu par buildZoneMeshes via `ridgeLifts`).
    computeAllRidgeLifts(pack.origin, pack, tiltDeg, flush);

    // Bâtiment + dalle + panneaux de la zone ACTIVE : MÊME chemin de construction que les
    // autres zones (buildZoneMeshes), à offset NUL et sans atténuation → octet pour octet
    // identique à avant. Les obstacles VIVANTS (tinte sélection + étiquette + drag) et la
    // photo satellite restent gérés ici car ils dépendent de l'état d'édition courant.
    const activePlan: ZoneRenderPlan = { pack, grid, tiltDeg, family, flush, count: drawnPanels.length, obstacles: ctx.obstacles, ridgeLiftM: ridgeLifts.get(ctx.activeAreaId) ?? 0 };
    const built = buildZoneMeshes(activePlan, 0, 0, false, occupiedSet);
    // Change B : pose la photo satellite (géo-alignée, détourée au tracé) sur la
    // face supérieure. L'origine de la scène sert à reprojeter les sommets en lng/lat.
    applyRoofPhoto(built.deck, built.deckMat, pack.origin);

    // Obstacles marqués (Change C) : volume SEMI-TRANSPARENT à la VRAIE taille
    // (largeur E-O × longueur N-S), posé sur le toit, avec une arête visible — la
    // photo satellite dessous (le vrai climatiseur/cheminée) transparaît, ce qui
    // confirme que la boîte est bien posée dessus. Sélectionné → teinte or. Zone active
    // uniquement : étiquette de taille + enregistrement pour le glissé en direct.
    if (ctx.obstacles.length) {
      const cosLat = Math.cos(pack.origin[1] * DEG2RAD);
      for (const o of ctx.obstacles) {
        const ox = (o.centerLng - pack.origin[0]) * DEG2M * cosLat;
        const oy = (o.centerLat - pack.origin[1]) * DEG2M;
        const selected = o.id === ctx.selectedObsId;
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
        // VISIONNEUSE : aucune étiquette de cote — c'est une aide au PLACEMENT
        // (l'obstacle lui-même reste visible, à sa vraie taille).
        if (!readOnly) {
          const label = makeDimSprite(dimsLabel(o));
          label.position.set(0, 0, OBSTACLE_BOX_H_M / 2 + 0.6);
          mesh.add(label);
        }
        sceneRoot.add(mesh);
        ctx.obstacleMeshes.set(o.id, mesh);
      }
    }

    // WJ19 — obstructions DÉDUITES des ombres tracées (arbres/immeubles voisins) :
    // volume gris translucide à sa VRAIE hauteur estimée, posé AU SOL (l'ombre a été
    // tracée au sol), qui PROJETTE une vraie ombre Three.js sur le bâtiment et les
    // panneaux — la preuve visuelle du dérate horaire. Liste vide → rendu inchangé.
    if (ctx.shadeObstructions.length) {
      const cosLat = Math.cos(pack.origin[1] * DEG2RAD);
      for (const o of ctx.shadeObstructions) {
        const ox = (o.base[0] - pack.origin[0]) * DEG2M * cosLat;
        const oy = (o.base[1] - pack.origin[1]) * DEG2M;
        const h = Math.max(0.5, o.heightM);
        const side = Math.max(0.6, o.halfWidthM * 2);
        const geo = new THREE.BoxGeometry(side, side, h);
        const mat = new THREE.MeshStandardMaterial({
          color: 0x6b7280,
          metalness: 0,
          roughness: 0.9,
          transparent: true,
          opacity: 0.35,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(ox, oy, h / 2); // posé au sol (z = 0), pas sur le toit
        mesh.castShadow = true; // la vraie ombre portée Three.js
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color: 0x8f9bb8, transparent: true, opacity: 0.8 }),
        );
        mesh.add(edges);
        sceneRoot.add(mesh);
      }
    }

    // W-MULTI : mémorise le plan de re-rendu de la zone ACTIVE pour que les AUTRES
    // zones puissent être re-dessinées (subduées) à leur vraie position relative.
    const aRec = ctx.activeArea();
    if (aRec) aRec.renderPlan = { pack, grid, tiltDeg, family, flush, count: drawnPanels.length, obstacles: ctx.obstacles.map((o) => ({ ...o })) };

    // — Soleil d'affichage (matin clair, élévation liée à la latitude) —
    // Bornes d'ombre = enveloppe de TOUTES les zones rendues (active + autres), pour que
    // l'ombre ne soit pas tronquée quand plusieurs zones coexistent. `appendOtherZones`
    // (appelée plus bas) ajoute les anneaux translatés des autres zones à cette liste.
    const shadowRings: [number, number][][] = [built.ring];
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const otherRings = appendOtherZones(pack.origin);
    for (const r of otherRings) shadowRings.push(r);
    for (const r of shadowRings) for (const [x, y] of r) {
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
    // W87 — VRAI soleil : position astronomique à la latitude du toit, pour l'heure
    // solaire (ctx.sunHour) et le jour (ctx.sunDay) choisis. Défaut = midi au solstice
    // d'hiver (jour 355), où l'élévation rejoint l'élévation de design de l'espacement
    // anti-ombrage → les rangées se dégagent VISIBLEMENT (l'ombre portée prouve le pas).
    // Plus de soleil arbitraire (ancien « visée − 45° » + élévation factice) : l'ombre
    // rendue correspond désormais à une vraie heure. On garde le soleil au moins à 6°
    // au-dessus de l'horizon pour que la scène reste éclairée si l'utilisateur choisit
    // une heure proche du lever/coucher (ombres longues mais lisibles, jamais noir).
    const lat = pack.origin[1];
    const realSun = sunDirection(lat, ctx.sunDay, ctx.sunHour);
    const dispElevDeg = Math.max(6, realSun.elevationDeg);
    // Azimut RÉEL du soleil, ramené dans le repère ENU de la scène (0 = Nord, sens
    // horaire vers l'Est) — même convention que pack.azimuthDeg.
    const dispAzDeg = realSun.azimuthDeg;
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

  /** Réinitialise la photo de toit + la matrice modèle (« Effacer »/clearEditorState).
   *  Mêmes opérations qu'avant le split : libère la texture de toit, oublie sa clé et
   *  le matériau du deck, et remet la matrice modèle à null (la scène a déjà été vidée
   *  par disposeScene appelé par l'entrée). */
  function resetTextures() {
    roofTex?.dispose();
    roofTex = null;
    roofTexKey = '';
    deckMaterial = null;
    modelMatrix = null;
  }

  /** W88 — surligne (or) l'instance de panneau dont la cellule de lattice est `cellIndex`,
   *  toutes les autres à leur teinte d'origine (blanc = pas de modification). `cellIndex`
   *  null → tout remis à blanc (aucun panneau sélectionné). No-op sans mesh de panneaux. */
  function setPanelHighlight(cellIndex: number | null) {
    const mesh = ctx.activePanelMesh;
    if (!mesh || !mesh.instanceColor) return;
    const col = mesh.instanceColor as THREE.InstancedBufferAttribute;
    const map = ctx.activePanelCellIndex;
    for (let i = 0; i < map.length; i++) {
      if (cellIndex != null && map[i] === cellIndex) {
        // teinte laiton (GOLD) : panneau sélectionné/survolé bien visible.
        col.setXYZ(i, 1.0, 0.78, 0.32);
      } else {
        col.setXYZ(i, 1, 1, 1); // teinte d'origine (instanceColor neutre)
      }
    }
    col.needsUpdate = true;
    map3dRepaint();
  }

  /** WJ21 — teinte les instances de panneaux de la zone active par leur accès solaire.
   *  `colorFor(cellIndex)` renvoie une couleur RVB (0–1) par cellule de lattice ; null
   *  remet toutes les instances à blanc (teinte d'origine, heatmap OFF). Réutilise le
   *  buffer instanceColor (MeshStandardMaterial multiplie sa couleur par instanceColor). */
  function setSolarAccessHeatmap(colorFor: ((cellIndex: number) => { r: number; g: number; b: number }) | null) {
    const mesh = ctx.activePanelMesh;
    if (!mesh || !mesh.instanceColor) return;
    const col = mesh.instanceColor as THREE.InstancedBufferAttribute;
    const idxMap = ctx.activePanelCellIndex;
    for (let i = 0; i < idxMap.length; i++) {
      if (colorFor) {
        const c = colorFor(idxMap[i]);
        col.setXYZ(i, c.r, c.g, c.b);
      } else {
        col.setXYZ(i, 1, 1, 1);
      }
    }
    col.needsUpdate = true;
    map3dRepaint();
  }

  /** Repeint la scène 3D (déclenché après un changement de couleur d'instance). */
  function map3dRepaint() {
    map.triggerRepaint();
  }

  /** W115 — instantané PNG de la scène 3D. Le renderer Three.js partage le canvas
   *  MapLibre (map.getCanvas()), donc toDataURL renvoie la carte + la 3D composées.
   *  preserveDrawingBuffer n'est pas garanti : on force d'abord un rendu synchrone via
   *  triggerRepaint, puis on lit le canvas. Renvoie null si rien à lire (pas de GL). */
  function snapshot(): string | null {
    const canvas = renderer?.domElement ?? (glCanvas as HTMLCanvasElement | null) ?? null;
    if (!canvas || typeof canvas.toDataURL !== 'function') return null;
    map.triggerRepaint();
    try {
      return canvas.toDataURL('image/png');
    } catch {
      return null;
    }
  }

  return { customLayer, disposeScene, setOrigin, appendOtherZones, renderScene, resetTextures, setPanelHighlight, setSolarAccessHeatmap, snapshot };
}

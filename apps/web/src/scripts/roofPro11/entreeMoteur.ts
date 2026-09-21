/* ============================================================================
   CALX3 — L'ENTRÉE DU MOTEUR DE CALEPINAGE, COMPOSÉE DEPUIS LA SCÈNE VIVANTE.
   ----------------------------------------------------------------------------
   Constat : le constructeur 3D savait sérialiser SON document (`prefill.ts`,
   contrat v2 des zones) mais rien du document que la porte moteur attend
   (`POST /api/django/calepinage/moteur/calculer/`). Les panneaux d'atelier qui
   postent une `entree` n'avaient donc jamais rien à poster.

   CE MODULE EST PUR. Il ne connaît ni MapLibre, ni Three, ni le DOM : il prend
   une DESCRIPTION de la scène (contours, obstacles, zones, retraits, kit) et
   rend le document. C'est ce qui le rend testable, et c'est ce qui permet au
   chemin inverse (`centresDepuisPlan`) d'être vérifié sans navigateur.

   LE REPÈRE, UNE SEULE FOIS ET POUR TOUT LE DOCUMENT
   --------------------------------------------------
   Le moteur travaille en mètres, sur un repère dont `x` court LE LONG des
   rangées et `y` en travers. Trois décisions en découlent, toutes prises ici :

   1. **Un seul ancrage géographique pour tout le document** — le barycentre de
      l'ensemble des sommets des pans. Chaque pan, chaque obstacle et chaque
      zone est projeté dans CE repère : deux pans d'un même site partagent donc
      un système de coordonnées, et une zone tracée à cheval sur deux pans ne
      change pas de sens selon le pan qui la lit.
   2. **L'axe des rangées est DÉRIVÉ, jamais saisi** — `axeRangeeImpose` tient
      la règle du dépôt (`core/calepinage/orientation.py`) : une table à deux
      modules dos-à-dos impose un faîtage nord-sud, un module unique impose des
      rangées perpendiculaires à sa visée. Déclarer un autre axe produit un plan
      « plausible et faux » que le moteur refuse.
   3. **La conversion (est, nord) → (x, y) est faite ICI, une fois**
      (`versRepereRangee`), et son inverse `versEstNord` sert au retour de plan.

   ZÉRO CHIFFRE INVENTÉ (D-CALX 7)
   --------------------------------
   Tout ce que ce module écrit vient de la scène : les retraits de rive sont les
   quatre retraits SAISIS, les dégagements d'obstacle sont ceux de l'atelier, la
   géométrie et la puissance du module sont celles du pavage courant. Ce que la
   scène ne dit pas est OMIS (l'allée de maintenance, le pas de recherche, le
   plafond de puissance) : le moteur applique alors ses propres défauts, et
   personne ne lit une valeur que personne n'a saisie. Une hauteur d'obstacle
   non renseignée sort à `null`, jamais à 0.
   ========================================================================== */

import { type LngLat } from '../../lib/roof';
import { type Obstacle, type ObstacleType, type ObstacleProvenance } from '../../lib/obstacles';
import { type PerimeterSetbacks } from '../../lib/roofPro2';
import { type ExclusionZone, type ExclusionNature } from './zones';
import { ORDRE_RENDU_CALQUES, MAPLIBRE_LAYERS_PAR_CALQUE } from './mapDraw';
import { clearanceForType } from './types';

/** Rayon terrestre WGS84 (demi-grand axe) — projection ENU locale. */
const RAYON_TERRE_M = 6378137;
const DEG2RAD = Math.PI / 180;

/** Version du schéma d'échange du moteur (`core/calepinage/version.py`). */
export const SCHEMA_VERSION_MOTEUR = 1;

/** Les deux axes de rangée que le moteur connaît. */
export type AxeRangee = 'NORD_SUD' | 'EST_OUEST';

/** Pose du module dans la table, vocabulaire du moteur. */
export type OrientationModule = 'PORTRAIT' | 'PAYSAGE';

// ─────────────────────────────────────────────────────────── ce qu'on reçoit

/** Un pan de la scène vivante : son contour, ses obstacles, sa pose. */
export interface PanScene {
  id: string;
  label?: string;
  /** Contour `[lng, lat]`. Moins de 3 sommets ⇒ le pan est ignoré. */
  vertices: readonly LngLat[];
  obstacles?: readonly Obstacle[];
  pitchDeg: number;
  facingAzimuthDeg: number;
  /** Cible SAISIE de modules (l'auto ne produit aucun engagement). */
  neededPanels?: number;
  neededAuto?: boolean;
}

/** Le kit du pavage courant, lu sur la scène (jamais un catalogue deviné). */
export interface KitScene {
  code: string;
  libelle: string;
  moduleLongM: number;
  moduleCourtM: number;
  puissanceModuleWc: number;
  inclinaisonDeg: number;
  orientation: OrientationModule;
  /** Modules par table : 1 en pose module unique, 2 en chevron dos-à-dos. */
  modulesParTable: number;
}

/** La scène d'atelier, réduite à ce que le moteur sait lire. */
export interface SceneMoteur {
  /** Repère du relevé (identifiant du calepinage ou du devis). */
  repere: string;
  pans: readonly PanScene[];
  zonesExclusion?: readonly ExclusionZone[];
  /** Les quatre retraits de rive SAISIS. */
  retraits: PerimeterSetbacks;
  kit: KitScene;
}

// ────────────────────────────────────────────────────────── ce qu'on produit

export interface RivesMoteur {
  laterale_m: number;
  extremite_m: number;
  acrotere_m: number;
  joint_m: number;
}

export interface SurfaceMoteur {
  repere: string;
  type: 'polygone';
  contour: number[][];
  trous: number[][][];
  rives: RivesMoteur;
  axe_rangee: AxeRangee;
  niveau: number;
  pente_deg: number;
  azimut_deg: number;
  origine: number[];
  coupures: unknown[];
}

export interface KitMoteur {
  code: string;
  libelle: string;
  module_long_m: number;
  module_court_m: number;
  puissance_module_wc: number;
  inclinaison_deg: number;
  orientation: OrientationModule;
  modules_par_table: number;
  faitage_m: number;
}

export interface ParametresMoteur {
  kits: string[];
  rives: RivesMoteur;
  axe_rangee: AxeRangee;
  mode_pose: string;
  degagement_defaut_m: number;
}

export interface ObstacleMoteur {
  repere: string;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  type_obstacle: string;
  provenance: string;
  degagement_m: number;
  hauteur_m: number | null;
  regle_appliquee: string;
}

export interface ZoneMoteur {
  repere: string;
  nature: ExclusionNature;
  sommets: number[][];
  hauteur_m: number | null;
  retrait_m: number;
}

/** Le document POSTÉ à `moteur/calculer` — les neuf sections de la porte. */
export interface DocumentMoteur {
  schema_version: number;
  repere: string;
  contour: number[][];
  surfaces: SurfaceMoteur[];
  kits: KitMoteur[];
  parametres: ParametresMoteur;
  obstacles: ObstacleMoteur[];
  zones: ZoneMoteur[];
  engagements: Array<[string, number]>;
}

// ──────────────────────────────────────────────────────────────── projection

/** Ancrage ENU local : le point autour duquel tout le document est projeté. */
export interface Ancrage {
  lat0: number;
  lng0: number;
}

/**
 * Ancrage du document : le barycentre de TOUS les sommets de TOUS les pans
 * retenus. Déterministe pour une scène donnée, donc le chemin retour
 * (`centresDepuisPlan`) retrouve le même repère sans rien mémoriser.
 * `null` quand aucun pan n'est exploitable.
 */
export function ancrageDeLaScene(pans: readonly PanScene[]): Ancrage | null {
  let sLng = 0;
  let sLat = 0;
  let n = 0;
  for (const p of pansExploitables(pans)) {
    for (const [lng, lat] of p.vertices) {
      sLng += lng;
      sLat += lat;
      n += 1;
    }
  }
  if (!n) return null;
  return { lng0: sLng / n, lat0: sLat / n };
}

function metresParDegreLat(): number {
  return (RAYON_TERRE_M * Math.PI) / 180;
}

function metresParDegreLng(lat0: number): number {
  return metresParDegreLat() * Math.cos(lat0 * DEG2RAD);
}

/** `[lng, lat]` → `(est, nord)` en mètres autour de l'ancrage. */
export function versLocal(ancrage: Ancrage, lng: number, lat: number): [number, number] {
  return [
    (lng - ancrage.lng0) * metresParDegreLng(ancrage.lat0),
    (lat - ancrage.lat0) * metresParDegreLat(),
  ];
}

/** `(est, nord)` → `[lng, lat]` — la reprojection du plan rendu par le moteur. */
export function versGeo(ancrage: Ancrage, est: number, nord: number): LngLat {
  return [
    ancrage.lng0 + est / metresParDegreLng(ancrage.lat0),
    ancrage.lat0 + nord / metresParDegreLat(),
  ];
}

/**
 * `(est, nord)` → `(x, y)` du moteur, où `x` court LE LONG des rangées.
 * Sur rangées nord-sud, `x` est le NORD ; sur rangées est-ouest, `x` est l'EST.
 */
export function versRepereRangee(est: number, nord: number, axe: AxeRangee): [number, number] {
  return axe === 'NORD_SUD' ? [nord, est] : [est, nord];
}

/** L'inverse exact de `versRepereRangee` — sert au retour de plan. */
export function versEstNord(x: number, y: number, axe: AxeRangee): [number, number] {
  return axe === 'NORD_SUD' ? [y, x] : [x, y];
}

/**
 * L'axe que le KIT impose à ses rangées — la règle du dépôt, pas un choix :
 * une table dos-à-dos (≥ 2 modules) a ses faces est/ouest donc un faîtage
 * nord-sud ; un module unique impose des rangées perpendiculaires à sa visée.
 */
export function axeRangeeImpose(modulesParTable: number, azimutDeg: number): AxeRangee {
  if (modulesParTable >= 2) return 'NORD_SUD';
  const reste = Math.abs(Number(azimutDeg) || 0) % 180;
  return reste < 45 || reste > 135 ? 'EST_OUEST' : 'NORD_SUD';
}

// ───────────────────────────────────────────────────── vocabulaire obstacles

/**
 * Type d'obstacle de l'atelier → type du moteur. On ne traduit QUE ce qui
 * correspond sans ambiguïté ; tout le reste part en `NATURE_INCONNUE`, ce qui
 * est exact (le moteur ne devine rien) et sans conséquence sur le calcul
 * puisque le dégagement est écrit explicitement à côté.
 */
export function typeObstacleMoteur(type?: ObstacleType | null): string {
  switch (type) {
    case 'cheminee':
      return 'SOUCHE';
    case 'edicule':
      return 'EDICULE';
    case 'antenne':
      return 'ANTENNE';
    default:
      return 'NATURE_INCONNUE';
  }
}

/**
 * Provenance de l'atelier → provenance du moteur. Les deux vocabulaires du
 * dépôt désignent les mêmes états (MESURE ≡ RELEVE) ; une provenance absente
 * vaut `DECLARE_CLIENT`, le choix déjà retenu pour une géométrie dessinée à la
 * main — jamais `RELEVE` (qui affirmerait une visite de site) ni `DEVINE` (qui
 * rendrait tout compte non engageable sans raison).
 */
export function provenanceMoteur(provenance?: ObstacleProvenance | null): string {
  switch (provenance) {
    case 'MESURE':
      return 'RELEVE';
    case 'MESURE_DOUTEUX':
      return 'RELEVE_DOUTEUX';
    case 'RELEVE':
    case 'RELEVE_DOUTEUX':
    case 'PLAN':
    case 'DEVINE':
    case 'DECLARE_CLIENT':
    case 'ECARTE':
      return provenance;
    default:
      return 'DECLARE_CLIENT';
  }
}

// ──────────────────────────────────────────────────────────── la composition

function pansExploitables(pans: readonly PanScene[]): PanScene[] {
  return (pans ?? []).filter(
    (p) => p && Array.isArray(p.vertices) && p.vertices.length >= 3,
  );
}

function rivesDe(r: PerimeterSetbacks): RivesMoteur {
  const positif = (v: number) => (Number.isFinite(v) && v > 0 ? v : 0);
  return {
    laterale_m: positif(r?.lateralM),
    extremite_m: positif(r?.extremityM),
    acrotere_m: positif(r?.parapetM),
    joint_m: positif(r?.jointM),
  };
}

function kitDe(k: KitScene): KitMoteur {
  return {
    code: k.code,
    libelle: k.libelle,
    module_long_m: k.moduleLongM,
    module_court_m: k.moduleCourtM,
    puissance_module_wc: k.puissanceModuleWc,
    inclinaison_deg: k.inclinaisonDeg,
    orientation: k.orientation,
    modules_par_table: k.modulesParTable,
    faitage_m: 0,
  };
}

/** Rectangle d'un obstacle dans le repère des rangées (centre + demi-étendues). */
function obstacleDe(
  o: Obstacle,
  ancrage: Ancrage,
  axe: AxeRangee,
  repere: string,
): ObstacleMoteur {
  const [est, nord] = versLocal(ancrage, o.centerLng, o.centerLat);
  const [x, y] = versRepereRangee(est, nord, axe);
  // `widthM` est une étendue EST-OUEST, `lengthM` une étendue NORD-SUD : sur des
  // rangées nord-sud les deux échangent leur rôle en même temps que les axes.
  const [demiX, demiY] = versRepereRangee(o.widthM / 2, o.lengthM / 2, axe);
  const degagement = clearanceForType(o.type);
  return {
    repere,
    x0: x - Math.abs(demiX),
    x1: x + Math.abs(demiX),
    y0: y - Math.abs(demiY),
    y1: y + Math.abs(demiY),
    type_obstacle: typeObstacleMoteur(o.type),
    provenance: provenanceMoteur(o.provenance),
    degagement_m: degagement,
    hauteur_m: Number.isFinite(o.heightM as number) && (o.heightM as number) > 0
      ? (o.heightM as number)
      : null,
    regle_appliquee: `dégagement d'atelier ${degagement} m autour d'un obstacle dessiné sur le pan`,
  };
}

function zoneDe(z: ExclusionZone, ancrage: Ancrage, axe: AxeRangee): ZoneMoteur | null {
  if (!z || !Array.isArray(z.vertices) || z.vertices.length < 3) return null;
  if (z.nature !== 'INTERDITE' && z.nature !== 'RESERVEE' && z.nature !== 'PREFEREE') return null;
  return {
    repere: String(z.id),
    nature: z.nature,
    sommets: z.vertices.map(([lng, lat]) => {
      const [est, nord] = versLocal(ancrage, lng, lat);
      const [x, y] = versRepereRangee(est, nord, axe);
      return [x, y];
    }),
    hauteur_m: Number.isFinite(z.heightM as number) && (z.heightM as number) > 0
      ? (z.heightM as number)
      : null,
    retrait_m: Number.isFinite(z.setbackM) && z.setbackM > 0 ? z.setbackM : 0,
  };
}

/**
 * CALX3 — compose le document d'entrée du moteur depuis la scène vivante.
 * Rend `null` tant qu'aucun pan ne porte un contour d'au moins 3 sommets :
 * un relevé sans toiture n'est pas un document vide, c'est PAS de document.
 */
export function composerEntreeMoteur(scene: SceneMoteur): DocumentMoteur | null {
  const pans = pansExploitables(scene?.pans ?? []);
  if (!pans.length) return null;
  const ancrage = ancrageDeLaScene(pans);
  if (!ancrage) return null;

  const kit = kitDe(scene.kit);
  // L'axe vaut pour TOUT le document (le moteur refuse une surface dont l'axe
  // diverge des paramètres) : il est dérivé du kit et de la visée du 1ᵉʳ pan.
  const axe = axeRangeeImpose(kit.modules_par_table, pans[0].facingAzimuthDeg);
  const rives = rivesDe(scene.retraits);

  const surfaces: SurfaceMoteur[] = pans.map((p) => ({
    repere: p.id,
    type: 'polygone',
    contour: p.vertices.map(([lng, lat]) => {
      const [est, nord] = versLocal(ancrage, lng, lat);
      const [x, y] = versRepereRangee(est, nord, axe);
      return [x, y];
    }),
    trous: [],
    rives,
    axe_rangee: axe,
    niveau: 0,
    pente_deg: Number.isFinite(p.pitchDeg) ? p.pitchDeg : 0,
    azimut_deg: Number.isFinite(p.facingAzimuthDeg) ? p.facingAzimuthDeg : 180,
    origine: [0, 0],
    coupures: [],
  }));

  const obstacles: ObstacleMoteur[] = [];
  for (const p of pans) {
    (p.obstacles ?? []).forEach((o, i) => {
      if (!o || !Number.isFinite(o.centerLng) || !Number.isFinite(o.centerLat)) return;
      obstacles.push(obstacleDe(o, ancrage, axe, String(o.id || `${p.id}-OBS${i + 1}`)));
    });
  }

  const zones: ZoneMoteur[] = [];
  for (const z of scene.zonesExclusion ?? []) {
    const zm = zoneDe(z, ancrage, axe);
    if (zm) zones.push(zm);
  }

  // Un engagement n'existe que là où une cible a été SAISIE (`neededAuto` faux).
  const engagements: Array<[string, number]> = [];
  for (const p of pans) {
    const cible = Math.trunc(Number(p.neededPanels));
    if (p.neededAuto === false && Number.isFinite(cible) && cible > 0) {
      engagements.push([p.id, cible]);
    }
  }

  return {
    schema_version: SCHEMA_VERSION_MOTEUR,
    repere: String(scene.repere ?? ''),
    contour: surfaces[0].contour.map((pt) => [pt[0], pt[1]]),
    surfaces,
    kits: [kit],
    parametres: {
      kits: [kit.code],
      rives,
      axe_rangee: axe,
      // Le constructeur pose des rangées explicites : c'est le mode de pose du
      // moteur qui correspond à ce que l'atelier dessine.
      mode_pose: 'rangees_explicites_dp',
      degagement_defaut_m: clearanceForType(null),
    },
    obstacles,
    zones,
    engagements,
  };
}

// ───────────────────────────────────────────────── le retour : plan → scène

/** Une rangée telle que le moteur la publie. */
export interface RangeeMoteur {
  y0?: number;
  emprise_m?: number;
  modules?: number;
  kit?: string;
  troncons?: Array<[number, number] | number[]>;
  surface?: string;
}

/** Centre de module, en mètres, dans le repère ENU de l'ancrage du document. */
export interface CentreModule {
  cx: number;
  cy: number;
}

/**
 * Les rangées d'un résultat moteur, quelle que soit la forme sous laquelle il
 * les publie : `plan.rangees`, `plans[].rangees`, ou la liste à plat `rangees`.
 * Les trois existent dans le dépôt ; aucune n'est privilégiée en silence.
 */
export function rangeesDuResultat(resultat: unknown): RangeeMoteur[] {
  const r = resultat as
    | { plan?: { rangees?: RangeeMoteur[] }; plans?: Array<{ rangees?: RangeeMoteur[] }>; rangees?: RangeeMoteur[] }
    | null
    | undefined;
  if (!r || typeof r !== 'object') return [];
  if (Array.isArray(r.plan?.rangees) && r.plan!.rangees!.length) return r.plan!.rangees!;
  if (Array.isArray(r.plans) && r.plans.length) {
    const out: RangeeMoteur[] = [];
    for (const p of r.plans) if (Array.isArray(p?.rangees)) out.push(...p.rangees);
    if (out.length) return out;
  }
  if (Array.isArray(r.rangees)) return r.rangees;
  return [];
}

/**
 * CALX3 — les centres de modules qu'un résultat moteur décrit, ramenés en
 * mètres ENU autour de l'ancrage de la scène.
 *
 * Une rangée donne sa position transversale (`y0` + `emprise_m`), ses tronçons
 * libres et son compte de modules. Les modules sont posés à pas constant depuis
 * le début de chaque tronçon — le pas étant la largeur du module LE LONG de la
 * rangée, c'est-à-dire le petit côté en pose portrait et le grand en paysage.
 * Un compte qui déborde la capacité des tronçons est posé dans le prolongement
 * du dernier plutôt que perdu : le moteur a compté, on ne recompte pas.
 */
export function centresDepuisPlan(
  resultat: unknown,
  scene: SceneMoteur,
): { centres: CentreModule[]; ancrage: Ancrage; axe: AxeRangee } | null {
  const pans = pansExploitables(scene?.pans ?? []);
  if (!pans.length) return null;
  const ancrage = ancrageDeLaScene(pans);
  if (!ancrage) return null;
  const axe = axeRangeeImpose(scene.kit.modulesParTable, pans[0].facingAzimuthDeg);
  const pas = scene.kit.orientation === 'PORTRAIT' ? scene.kit.moduleCourtM : scene.kit.moduleLongM;
  if (!Number.isFinite(pas) || pas <= 0) return null;

  const centres: CentreModule[] = [];
  for (const rangee of rangeesDuResultat(resultat)) {
    const modules = Math.max(0, Math.trunc(Number(rangee?.modules) || 0));
    if (!modules) continue;
    const y0 = Number(rangee?.y0);
    if (!Number.isFinite(y0)) continue;
    const emprise = Number.isFinite(Number(rangee?.emprise_m)) ? Number(rangee?.emprise_m) : pas;
    const yc = y0 + emprise / 2;
    const troncons = (rangee?.troncons ?? [])
      .map((t) => [Number(t?.[0]), Number(t?.[1])] as [number, number])
      .filter((t) => Number.isFinite(t[0]) && Number.isFinite(t[1]) && t[1] > t[0]);
    let restants = modules;
    if (!troncons.length) continue;
    troncons.forEach(([a, b], i) => {
      if (restants <= 0) return;
      const capacite = Math.max(0, Math.floor((b - a + 1e-9) / pas));
      // Le DERNIER tronçon absorbe ce qui reste : le compte du moteur fait foi.
      const n = i === troncons.length - 1 ? restants : Math.min(restants, capacite);
      for (let k = 0; k < n; k += 1) {
        const x = a + pas * (k + 0.5);
        const [est, nord] = versEstNord(x, yc, axe);
        centres.push({ cx: est, cy: nord });
      }
      restants -= n;
    });
  }
  if (!centres.length) return null;
  return { centres, ancrage, axe };
}

/**
 * CALX3 — les mêmes centres, exprimés dans le repère ENU d'une ORIGINE
 * géographique donnée (celle du pavage courant), prêts à être re-snappés sur la
 * lattice. C'est la même translation que celle qu'applique le rechargement d'un
 * dossier : un simple changement de point d'appui, aucune rotation.
 */
export function versRepereDuPack(
  centres: readonly CentreModule[],
  ancrage: Ancrage,
  origine: readonly [number, number],
): CentreModule[] {
  const dx = (ancrage.lng0 - origine[0]) * metresParDegreLng(origine[1]);
  const dy = (ancrage.lat0 - origine[1]) * metresParDegreLat();
  return centres.map((c) => ({ cx: c.cx + dx, cy: c.cy + dy }));
}

// ────────────────────────────────────────────────────────────── les raccourcis

/**
 * CALX3 — les huit actions de l'aide-mémoire des raccourcis de l'atelier.
 * L'ordre est celui de la table de l'écran ; les identifiants sont son
 * vocabulaire, que le constructeur ne réécrit jamais de son côté.
 */
export const ACTIONS_RACCOURCIS = [
  'outilTrace',
  'outilObstacle',
  'outilZone',
  'outilMesure',
  'aimantation',
  'supprimer',
  'dupliquer',
  'pleinEcran',
] as const;

export type ActionRaccourci = (typeof ACTIONS_RACCOURCIS)[number];

/** Un geste du constructeur branché derrière une action de raccourci. */
export type GesteRaccourci = () => void;

/**
 * CALX3 — construit l'objet `raccourcis` exposé à l'écran : UNE clé par action,
 * TOUJOURS une fonction. Un geste que le constructeur n'offre pas (aperçu,
 * mode capture) reste une fonction sans effet plutôt qu'une clé manquante :
 * l'écran n'a ainsi jamais à tester la présence d'un gestionnaire pour décider
 * d'afficher son raccourci.
 */
export function construireRaccourcis(
  gestes: Partial<Record<ActionRaccourci, GesteRaccourci>>,
): Record<ActionRaccourci, GesteRaccourci> {
  const out = {} as Record<ActionRaccourci, GesteRaccourci>;
  for (const action of ACTIONS_RACCOURCIS) {
    const geste = gestes?.[action];
    out[action] = typeof geste === 'function' ? () => { geste(); } : () => {};
  }
  return out;
}

// ──────────────────────────────────────────────────────────────── les calques

/** Ce qu'une carte doit savoir faire pour qu'on puisse l'interroger. */
export interface CarteInterrogeable {
  getLayer?: (id: string) => unknown;
}

/**
 * CALX3 — les calques d'atelier RÉELLEMENT installés sur la carte, dans l'ordre
 * de rendu (du fond vers le dessus). Un calque est retenu quand au moins une de
 * ses couches MapLibre existe : en mode capture, en aperçu, ou avant le chargement
 * du style, la liste est simplement plus courte — jamais une exception, et jamais
 * un identifiant qui ne serait pas du vocabulaire de l'atelier.
 */
export function calquesDisponibles(
  carte: CarteInterrogeable | null | undefined,
  ordre: readonly string[] = ORDRE_RENDU_CALQUES,
  couches: Readonly<Record<string, readonly string[]>> = MAPLIBRE_LAYERS_PAR_CALQUE,
): string[] {
  if (!carte || typeof carte.getLayer !== 'function') return [];
  const out: string[] = [];
  for (const id of ordre) {
    for (const layerId of couches[id] ?? []) {
      let present = false;
      try {
        present = Boolean(carte.getLayer(layerId));
      } catch {
        present = false; /* style pas encore prêt : le calque n'est pas installé */
      }
      if (present) {
        out.push(id);
        break;
      }
    }
  }
  return out;
}

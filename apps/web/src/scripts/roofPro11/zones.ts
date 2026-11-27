/**
 * « Plusieurs zones » : instantané du résultat/géométrie de la zone active +
 * rendu du panneau de total agrégé. Extrait de roof-tool-pro11.ts (split
 * modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * Le RENDU 3D des autres zones (`appendOtherZones`, couplé à `buildZoneMeshes`)
 * reste dans roof-tool-pro11.ts tant que la scène n'est pas extraite.
 */
import { aggregateAreas, areaLabel, type AreaResult } from '../../lib/roofAreas';
import { annualSavingsMad } from '../../lib/estimatorBrainV2';
import { fmt, fmtMad, esc } from './dom';
import { type Ctx } from './context';
import { type AreaRecord, type GabaritZone } from './types';
import { type RoofShapePan, type RoofShapePreset } from './scene3d';
import { geodesicAreaM2, isSimplePolygon, pointInPolygon, type LngLat } from '../../lib/roof';
import { referenceContourRing } from './prefill'; // ACAL71 — le validateur de contour UNIQUE
import { economieAffichee, facteurDerateAnnuel } from './optimizer'; // ACAL356 — le dérate UNIQUE (ombrage × horizon)
import { type Obstacle } from '../../lib/obstacles';
import { pivoterSite } from './siteRotation'; // ACAL514
import { motifPanVerrouille } from './panVerrouille'; // ACAL520
import { phraseTaillesDuChiffrage, texteTotalProduction } from './affichageErp'; // ACAL1418, T4-X9-007
import { peindrePhraseTailles } from './tailleConception'; // T4-X9-007
import { poseAfficheeDuPan } from './poseEnregistree'; // T4-X2-010
import { anneeValide, motifPanExistant } from './panExistant'; // ACAL510, ACAL574
import { appliquerReglagesAuxPans, pansReglesAMain } from './jeuReglages'; // ACAL554
import { accesMoyenDuPan, mentionAcces, trierPansParAcces } from './triPans'; // ACAL728
import {
  centroideAnneau,
  dimensionsRectangleM,
  pivoterAnneau,
  pivoterPoint,
  redimensionnerRectangle,
} from './snap';
import { computePanStats, computeSiteStats, etiquettePanExistant, hasMultipleBuildings, htmlTableSite, libelleBatiment, type PanStat } from './panStats'; // CALX126, ACAL1431
// CALX109/CALX110 câblage — le catalogue de modules de la société et le module posé sur
// CHAQUE pan. `moduleSelect.ts` est PUR (aucun DOM) : c'est ici, dans le panneau du pan, que
// le choix devient visible, et c'est de là qu'il repart vers le pavage et le document.
import {
  MENTION_MODULE_DE_DEPART,
  MODULE_PAR_DEFAUT_ATELIER,
  cotesDeModule,
  estRefus,
  kwcDuPan,
  lireModulesDisponibles,
  moduleDeDepart,
  resoudreModuleDuPan,
  type CatalogueModules,
  type ModuleDisponible,
  type ModuleDocument,
  type SyntheseModules,
} from './moduleSelect';

/**
 * CAL56 — traduit les pans générés par `generateRoofShapePans` (scene3d.ts, géométrie pure)
 * en `AreaRecord[]` prêts à remplacer `ctx.areas` : un pan = une zone, exactement le même
 * objet que « + Ajouter une zone » crée à la main (mécanique multi-zones INCHANGÉE — chaque
 * pan reste ensuite éditable individuellement via le panneau « Zones »). `makeId` est injecté
 * (aucun Date.now()/Math.random() ici) pour rester pur et testable ; roofType = 'flat' pour
 * le préré 'flat', 'pitched' sinon (pente = `pitchDeg` saisi par l'utilisateur, inchangé — ce
 * module ne l'invente pas).
 */
export function buildAreasFromShape(
  pans: RoofShapePan[],
  shape: RoofShapePreset,
  pitchDeg: number,
  makeId: () => string,
): AreaRecord[] {
  return pans.map((pan) => ({
    id: makeId(),
    label: '',
    vertices: pan.vertices,
    obstacles: [],
    roofType: shape === 'flat' ? 'flat' : 'pitched',
    pitchDeg,
    facingAzimuthDeg: pan.facingAzimuthDeg,
    facingManual: shape !== 'flat',
    neededPanels: 0,
    neededAuto: true,
    result: null,
    renderPlan: null,
  }));
}

// ————————————————————————————————————————————————————————————————————————
// CALX97 — COTES EXACTES D'UN PAN ET ROTATION D'UN BLOC
//
// Un pan ne se modifiait qu'au glissé de ses sommets : aucune saisie de largeur/longueur,
// aucune rotation d'ensemble. Parité HelioScope (cotes exactes tapables + « Rotate Field
// Segments/Keepouts »). La géométrie est dans `snap.ts` ; ce bloc l'applique à un PAN —
// c'est-à-dire à son contour ET à ses obstacles — de façon PURE et testable.
//
// CE QUI SUIT LA ROTATION, ET CE QUI NE LA SUIT PAS : le CENTRE de chaque obstacle tourne
// autour du centroïde du pan, donc un obstacle reste au même endroit du toit. Son rectangle,
// lui, reste orienté nord-sud/est-ouest, parce que le document ne porte AUCUNE orientation
// d'obstacle (`lib/obstacles.ts` : `lengthM` = étendue nord-sud, `widthM` = est-ouest). On
// n'invente pas cette clé ici : ce serait un champ de document créé par une lane d'écran.
// ————————————————————————————————————————————————————————————————————————

/** La part d'un pan que CALX97 déplace : son contour et ses obstacles. */
export interface GeometriePan {
  vertices: LngLat[];
  obstacles: Obstacle[];
}

/** Verdict d'une transformation de pan — un refus NOMME le pan ET la raison. */
export type VerdictPan = { ok: true; geometrie: GeometriePan } | { ok: false; motif: string };

/**
 * CALX97 — fait pivoter un pan de `angleDeg` (sens horaire) autour du centroïde de son
 * contour : le contour ET les centres de ses obstacles suivent le même mouvement. Refus
 * NOMMÉ quand le contour n'a pas de quoi définir un centre, ou que l'angle est illisible.
 */
export function pivoterPan(pan: GeometriePan, angleDeg: number, nomDuPan: string): VerdictPan {
  if (!Array.isArray(pan?.vertices) || pan.vertices.length < 3) {
    return { ok: false, motif: `${nomDuPan} : rotation refusée — ce pan n’a pas encore de contour fermé.` };
  }
  if (!Number.isFinite(angleDeg)) {
    return { ok: false, motif: `${nomDuPan} : rotation refusée — saisissez un angle en degrés.` };
  }
  const centre = centroideAnneau(pan.vertices);
  if (!centre) {
    return { ok: false, motif: `${nomDuPan} : rotation refusée — le centre du pan est illisible.` };
  }
  const obstacles = (pan.obstacles ?? []).map((o) => {
    const c = pivoterPoint([o.centerLng, o.centerLat], angleDeg, centre);
    return { ...o, centerLng: c[0], centerLat: c[1] };
  });
  return { ok: true, geometrie: { vertices: pivoterAnneau(pan.vertices, angleDeg, centre), obstacles } };
}

/**
 * CALX97 — repose un pan RECTANGULAIRE aux cotes saisies, autour de son centroïde. Les
 * obstacles ne bougent PAS : ils sont posés à un endroit réel du toit, et les décaler avec
 * les cotes inventerait une position que personne n'a relevée. Refus NOMMÉ (avec le nom du
 * pan) quand le contour n'est pas un quadrilatère ou qu'une cote manque.
 */
export function redimensionnerPan(
  pan: GeometriePan,
  largeurM: number,
  longueurM: number,
  nomDuPan: string,
): VerdictPan {
  const verdict = redimensionnerRectangle(pan?.vertices ?? [], largeurM, longueurM);
  if (!verdict.ok) return { ok: false, motif: `${nomDuPan} : ${verdict.motif}` };
  return { ok: true, geometrie: { vertices: verdict.anneau, obstacles: (pan.obstacles ?? []).map((o) => ({ ...o })) } };
}

// ————————————————————————————————————————————————————————————————————————
// CALX98 — DUPLIQUER UN PAN AVEC SES OBSTACLES ET SES RÉGLAGES
//
// « + Ajouter une zone » crée toujours une zone VIDE, et la duplication n'existait que pour
// les obstacles — alors qu'une toiture industrielle répète le même sied dix fois. Parité
// HelioScope (« Clone designs »). PUR et testable : aucun DOM, aucune carte.
//
// ZÉRO CHIFFRE INVENTÉ : le décalage de la copie est SAISI. Tant qu'il ne l'est pas, la
// duplication est REFUSÉE avec son motif — on ne pose jamais la copie « un peu plus loin »
// d'une distance que personne n'a demandée.
// ————————————————————————————————————————————————————————————————————————

/** Verdict d'une duplication de pan — un refus NOMME toujours sa raison. */
export type VerdictDuplication = { ok: true; zone: AreaRecord } | { ok: false; motif: string };

/**
 * CALX98 — motif qui EMPÊCHE la duplication au pas saisi, ou `null` quand le pas est
 * exploitable. L'écran s'en sert pour garder le bouton inactif ET afficher la raison.
 */
export function motifPasDuplication(pasM: number): string | null {
  if (!Number.isFinite(pasM) || pasM <= 0) {
    return 'Saisissez le décalage de la copie, en mètres : aucun décalage n’est supposé.';
  }
  return null;
}

const REGLAGES_PHYSIQUES_COPIES = ['pitchSource', 'coupuresPavage', 'porteeEntrePieds', 'chassis'] as const;

/** Les réglages saisis du pan qu'une copie garde (clone profond ; clé absente = clé absente). */
function copieReglagesPhysiques(source: AreaRecord): Partial<AreaRecord> {
  const out: Record<string, unknown> = {};
  for (const cle of REGLAGES_PHYSIQUES_COPIES) {
    if (source[cle] !== undefined) out[cle] = JSON.parse(JSON.stringify(source[cle]));
  }
  return out as Partial<AreaRecord>;
}

/**
 * CALX98 — copie un pan dans une zone NEUVE, décalée du pas SAISI. Sont recopiés : le
 * contour, les obstacles (avec de nouveaux identifiants, dérivés de l'id de la zone, donc
 * sans collision), `roofType`, `pitchDeg`, `facingAzimuthDeg`, `facingManual`, `edges` et
 * `buildingId` et `moduleId` (R3-24 : sans lui la copie repasse au module par défaut de l'atelier,
 * et change de kWc). Ne sont PAS recopiés : le résultat et le plan de rendu — la copie n'a rien
 * de calculé tant que le moteur n'a pas tourné, et publier le compte de l'original serait un
 * chiffre inventé.
 *
 * Le décalage est une TRANSLATION RIGIDE vers l'est (même convention que la duplication
 * d'obstacle, CAL73) : le même écart de longitude, calculé à la latitude du centroïde, est
 * appliqué à TOUS les points — contour et obstacles — pour que la copie garde exactement la
 * forme de l'original.
 */
export function dupliquerPan(source: AreaRecord, nouvelId: string, pasM: number): VerdictDuplication {
  const motif = motifPasDuplication(pasM);
  if (motif) return { ok: false, motif };
  if (!source || !Array.isArray(source.vertices) || source.vertices.length < 3) {
    return { ok: false, motif: 'Duplication refusée : ce pan n’a pas encore de contour fermé.' };
  }
  const centre = centroideAnneau(source.vertices);
  if (!centre) return { ok: false, motif: 'Duplication refusée : le centre du pan est illisible.' };
  const cosLat = Math.max(1e-6, Math.cos(centre[1] * ZONE_DEG2RAD));
  const dLng = pasM / (ZONE_DEG2M * cosLat);
  return {
    ok: true,
    zone: {
      id: nouvelId,
      label: '',
      vertices: source.vertices.map(([lng, lat]) => [lng + dLng, lat] as LngLat),
      obstacles: (source.obstacles ?? []).map((o, i) => ({
        ...o,
        id: `${nouvelId}-obs-${i + 1}`,
        centerLng: o.centerLng + dLng,
      })),
      roofType: source.roofType,
      pitchDeg: source.pitchDeg,
      facingAzimuthDeg: source.facingAzimuthDeg,
      facingManual: source.facingManual,
      neededPanels: 0,
      neededAuto: true,
      result: null,
      renderPlan: null,
      ...(source.buildingId ? { buildingId: source.buildingId } : {}),
      ...(source.moduleId ? { moduleId: source.moduleId } : {}),
      ...(source.moduleId && (source as PanAuChoix).moduleChoisi ? { moduleChoisi: true } : {}), // ACAL1415 — la copie garde le choix
      ...(source.edges ? { edges: source.edges.map((e) => ({ ...e })) } : {}),
      // Réglages PHYSIQUES du pan (copies profondes) ; jamais `existant` / `anneeMiseEnService` /
      // `verrouille` : la copie est un pan NEUF et modifiable (recopier « existant » la sortirait du devis).
      ...copieReglagesPhysiques(source),
    },
  };
}

/**
 * ACAL64 — LA fabrique d'identifiants de l'atelier : `<prefixe>-<max(n)+1>` sur TOUS les
 * existants (pans, obstacles de tous les pans, zones d'exclusion, objets d'environnement).
 * Remplace les compteurs de session (`areaCounter`, `obsCounter`, `zoneCounter`,
 * `envCounter`) qui repartaient de zéro sur un dossier rouvert et recréaient `area-2`
 * alors qu'un `area-2` existait déjà — le nouveau pan prenait le contour de l'ancien.
 * PURE ; un identifiant d'une autre forme (`area-copie-1`, `sh-1`…) est ignoré.
 */
export function prochainId(prefixe: string, existants: Iterable<{ id?: string } | null | undefined>): string {
  const tete = `${prefixe}-`;
  let max = 0;
  for (const e of existants) {
    const id = typeof e?.id === 'string' ? e.id : '';
    if (!id.startsWith(tete)) continue;
    const reste = id.slice(tete.length);
    if (/^\d+$/.test(reste)) max = Math.max(max, Number(reste));
  }
  return `${prefixe}-${max + 1}`;
}

/** ACAL64 — tous les obstacles du site : ceux du pan actif ET ceux des pans figés. */
export function tousLesObstacles(ctx: Pick<Ctx, 'obstacles' | 'areas' | 'activeAreaId'>): Array<{ id: string }> {
  return [
    ...(ctx.obstacles ?? []),
    ...(ctx.areas ?? []).filter((a) => a.id !== ctx.activeAreaId).flatMap((a) => a.obstacles ?? []),
  ];
}

/** ACAL64 — deux pans de même identifiant dans un document : le premier doublon, ou null. */
export function idPanEnDouble(zones: readonly { id: string }[]): string | null {
  const vus = new Set<string>();
  for (const z of zones) {
    if (vus.has(z.id)) return z.id;
    vus.add(z.id);
  }
  return null;
}

/** ACAL1415 — un pan et son drapeau « module CHOISI » (contrat `zones[].geometry.moduleChoisi`, ACAL1401) : la
 *  seule source de « choisi ». Absent = module de départ, à confirmer ; `panVierge`/`poserModuleDeDepart` ne
 *  l'écrivent jamais. */
export type PanAuChoix = AreaRecord & { moduleChoisi?: boolean };

/** Pan NEUF aux valeurs par défaut (toit plat 22°, plein sud), identifiant issu de LA fabrique
 *  `prochainId` : l'unique définition, partagée par le builder (`roof-tool-pro11.ts`) et
 *  `nouveauPanDepuisContour` (jamais deux copies du littéral). */
export function panVierge(
  existants: readonly { id: string }[],
  vertices: AreaRecord['vertices'] = [],
  moduleDepart: ModuleDocument | null = null, // ACAL913 — absent : aucun `moduleId` (720 Wc NOMMÉ)
): AreaRecord {
  const id = prochainId('area', existants);
  return {
    id,
    label: areaLabel(existants.length), // ACAL1430 — le nom de son RANG (ajouté en fin), jamais celui de son identifiant
    vertices,
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 0,
    neededAuto: true,
    result: null,
    renderPlan: null,
    ...(moduleDepart ? { moduleId: moduleDepart.id } : {}),
  };
}

/**
 * ACAL71 — un contour GÉORÉFÉRENCÉ ([[lng, lat], …], plan importé calé, relevé…) devient
 * un NOUVEAU pan de l'atelier, identifiant tiré de `prochainId` (jamais un doublon). Mêmes
 * gardes que le tracé à la main : le validateur de contour UNIQUE (`referenceContourRing`,
 * bornes lat/lng, ≥ 3 sommets) puis le refus d'un contour qui se croise
 * (`isSimplePolygon`, comme `close()` de l'atelier). Refus ⇒ motif NOMMÉ, aucun pan. PURE.
 */
export function nouveauPanDepuisContour(
  contourLngLat: unknown,
  existants: readonly { id: string }[],
  moduleDepart: ModuleDocument | null = null, // ACAL1273 — comme `panVierge` : le module de départ du site
): { ok: true; pan: AreaRecord } | { ok: false; motif: string } {
  const points = Array.isArray(contourLngLat)
    ? (contourLngLat as unknown[]).map((p) =>
        Array.isArray(p) && p.length >= 2 ? { lng: Number(p[0]), lat: Number(p[1]) } : null)
    : [];
  if (points.some((p) => p === null)) {
    return { ok: false, motif: 'Contour illisible : chaque sommet doit être un couple [longitude, latitude].' };
  }
  const ring = referenceContourRing(points as Array<{ lat: number; lng: number }>);
  if (!ring || ring.length !== points.length) {
    return {
      ok: false,
      motif: 'Contour hors amplitude GPS ou de moins de 3 sommets valides : aucun pan n’est créé.',
    };
  }
  if (!isSimplePolygon(ring)) {
    return { ok: false, motif: 'Ce contour se croise : corrigez-le avant d’en faire un pan (aucun pan créé).' };
  }
  return { ok: true, pan: panVierge(existants, ring, moduleDepart) };
}

/** ACAL1273 — document relu SANS aucun module : le module de départ sur chaque pan (hors installation
 *  existante), donc écrit au premier enregistrement ; un document qui en désigne un reste tel quel. */
export function poserModuleDeDepart(
  pans: AreaRecord[],
  zonesDuDocument: readonly { geometry?: { moduleId?: unknown } }[] | null | undefined,
  depart: ModuleDocument | null,
): void {
  if (!depart || (zonesDuDocument ?? []).some((z) => z?.geometry?.moduleId)) return;
  for (const p of pans) if (!p.existant) p.moduleId = depart.id;
}

// ═══════════ ACAL1329 — un pan AJOUTÉ sur un toit existant, du premier clic au dernier point ═══════════
/** Vrai pendant l'ajout d'un pan : le pan actif n'est pas fermé et un autre pan a déjà son contour. */
export const ajoutDePanEnCours = (areas: readonly AreaRecord[], activeAreaId: string, closed: boolean): boolean =>
  !closed && areas.some((a) => a.id !== activeAreaId && (a.vertices?.length ?? 0) >= 3);

/** Le toit EXISTANT (pans fermés hors pan actif), en polygones : ce qui reste dessiné, grisé, sous le tracé. */
export function toitExistantGeoJSON(areas: readonly AreaRecord[], activeAreaId: string) {
  return {
    type: 'FeatureCollection' as const,
    features: areas.filter((a) => a.id !== activeAreaId && (a.vertices?.length ?? 0) >= 3).map((a) => ({
      type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [[...a.vertices, a.vertices[0]]] },
    })),
  };
}


/** Ce que le calque de référence lit/écrit de la carte MapLibre. */
interface CarteReference {
  getSource(id: string): { setData(d: never): unknown } | undefined;
  getLayer(id: string): unknown;
  setPaintProperty(id: string, nom: string, v: string): unknown;
  setLayoutProperty(id: string, nom: string, v: 'visible' | 'none'): unknown;
  on(type: string, fn: (e: { sourceId?: string }) => void): unknown;
}
const GRIS_TOIT_EXISTANT = '#9aa0bb';

/** Pendant l'ajout, le calque de référence (`rp9-ref-contour-*`, aucune seconde couche) montre le toit existant en
 *  gris ; à la fin (dernier point, Échap, autre pan), `restaurer` lui rend le tracé du client. Relu à chaque re-pose
 *  des sommets (`rp9-pts`). */
export function monterToitGriseSousTrace(
  map: CarteReference,
  lire: () => { areas: readonly AreaRecord[]; activeAreaId: string; closed: boolean },
  couleurReference: string,
  restaurer: () => void,
): void {
  let grise = false;
  const peindre = (couleur: string) => {
    if (map.getLayer('rp9-ref-contour-fill')) map.setPaintProperty('rp9-ref-contour-fill', 'fill-color', couleur);
    if (map.getLayer('rp9-ref-contour-line')) map.setPaintProperty('rp9-ref-contour-line', 'line-color', couleur);
  };
  map.on('sourcedata', (e) => {
    if (e?.sourceId !== 'rp9-pts') return;
    const { areas, activeAreaId, closed } = lire();
    if (ajoutDePanEnCours(areas, activeAreaId, closed)) {
      map.getSource('rp9-ref-contour')?.setData(toitExistantGeoJSON(areas, activeAreaId) as never);
      peindre(GRIS_TOIT_EXISTANT);
      for (const id of ['rp9-ref-contour-fill', 'rp9-ref-contour-line']) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'visible');
      grise = true;
    } else if (grise) {
      grise = false;
      peindre(couleurReference);
      restaurer();
    }
  });
}

/** CALX98 — identifiant de zone NEUF, dans un espace de noms (`area-copie-N`) que le
 *  compteur `area-<n>` de l'entrée ne produit jamais : aucune collision possible. */
export function idZoneCopie(existants: readonly { id: string }[]): string {
  const pris = new Set((existants ?? []).map((a) => a.id));
  let n = 1;
  while (pris.has(`area-copie-${n}`)) n++;
  return `area-copie-${n}`;
}

/** ACAL554 — bouton « Appliquer ces réglages à… » d'une ligne de pan : absent s'il n'y a qu'un pan. */
export function boutonReporterReglages(id: string, nbPans: number): string {
  if (nbPans < 2) return '';
  return `<button type="button" data-area-report="${esc(id)}" class="min-h-11 border border-white/25 px-2.5 py-1 text-xs font-semibold text-lune-soft hover:border-brass-400 hover:text-brass-300">Appliquer ces réglages à…</button>`;
}

export interface Zones {
  liveActiveResult: () => AreaResult | null;
  snapshotActiveAreaResult: () => void;
  snapshotActiveAreaGeometry: () => void;
  syncAddAreaButton: () => void;
  renderAreasPanel: () => void;
  /** CAL59 — assigne (ou efface, chaîne vide) le bâtiment d'une zone, puis re-rend le
   *  panneau. N'affecte ni le résultat ni la géométrie de la zone. */
  setAreaBuilding: (id: string, buildingId: string) => void;
  /** CALX97 — fait pivoter le pan ACTIF (contour + obstacles) de l'angle saisi. Renvoie
   *  false et n'applique RIEN quand c'est refusé ; le motif nomme le pan. */
  pivoterPanActif: (angleDeg: number) => boolean;
  /** ACAL515 — pivote TOUT le site d'un geste annulable ; false et rien ne bouge si refusé. */
  pivoterSiteActif: (angleDeg: number) => boolean;
  /** CALX97 — repose le pan ACTIF aux cotes saisies (pan rectangulaire seulement). */
  redimensionnerPanActif: (largeurM: number, longueurM: number) => boolean;
  /** CALX98 — duplique le pan ACTIF (contour, obstacles et réglages) dans une zone neuve
   *  décalée du pas SAISI. Renvoie false et ne crée RIEN sans pas saisi. */
  dupliquerPanActif: (pasM: number) => boolean;
  /** CALX109/CALX110 câblage — pose le modèle de module `moduleId` sur le pan ACTIF (chaîne
   *  vide = retour au module par défaut de l'atelier). Renvoie false et n'écrit RIEN quand le
   *  modèle est grisé, inconnu, ou sans cotes — le refus NOMME le pan et le motif. */
  choisirModuleDuPanActif: (moduleId: string | null | undefined) => boolean;
}

/**
 * CALX97 — crochets d'écran OPTIONNELS. Absents, `createZones` se comporte EXACTEMENT comme
 * avant (le seul appelant, `roof-tool-pro11.ts`, n'en passe aucun aujourd'hui) ; fournis,
 * une transformation de pan redessine et re-pave immédiatement.
 */
export interface ZonesDeps {
  /** Re-dessine la ligne + les pastilles de sommets du pan actif. */
  redrawTrace?: () => void;
  /** Re-dessine le calque des obstacles du pan actif. */
  redrawObstacles?: () => void;
  /** Re-pavage + production après un changement de géométrie. */
  recalc?: () => void;
  /** Bandeau de statut (refus nommés, confirmations). */
  setStatus?: (msg: string) => void;
  /** ACAL410 — appelé à chaque rendu de la liste des pans (les puces « Forme du toit » s'y recalent). */
  apresRendu?: () => void;
  /** ACAL554 — active un pan (« Voir » : charge et re-pave) ; absent, le report de réglages est indisponible. */
  selectArea?: (id: string) => void;
  /** ACAL728 — accès solaire moyen (0..1) du calcul VIVANT du pan actif ; absent, l'enregistré sert. */
  accesVivant?: () => number | null;
  /** ACAL853 — le kWh PEINT sur la carte Recommandation (par panneau) ; absent ou `null` (carte pas encore peinte), le calcul du solveur sert. */
  etatCarte?: () => { kwhParPanneau: number } | null;
}

/** CAL84 — libellé d'un bâtiment (repli « Bâtiment sans id » pour un groupe sans
 *  `buildingId` mélangé à des zones qui en portent un — cas limite, ne devrait pas
 *  arriver en pratique une fois CAL59 câblé, mais ne doit jamais planter l'affichage). */
export function buildingLabel(buildingId: string | null, rang = 1): string {
  return libelleBatiment(buildingId, rang); // ACAL981 — « Bâtiment <rang> », plus « Bâtiment sans id »
}

export function createZones(ctx: Ctx, deps: ZonesDeps = {}): Zones {
  // CAL84 — table des statistiques par pan, créée UNE fois si l'hôte ne la fournit pas déjà
  // (même pattern que le sélecteur de type d'obstacle, obstaclesUi.ts `ensureTypePicker`) :
  // aucune page n'a à être modifiée pour l'afficher.
  function ensureStatsTable(): HTMLElement | null {
    const existing = document.getElementById('rp9-areas-stats');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-areas-stats';
    el.className = 'mt-3 overflow-x-auto';
    areasWindowEl.appendChild(el);
    return el;
  }

  /** Résultat VIVANT de la zone active (gagnant de l'optimiseur courant) — plat
   *  (`liveResult.winner`) ou pente (`pitchedLiveResult.winner`). null si rien de calculé
   *  ou pose nulle (zone sans panneaux). */
  function liveActiveResult(): AreaResult | null {
    if (!ctx.closed || ctx.vertices.length < 3) return null;
    const res = ctx.roofType === 'pitched' ? ctx.pitchedLiveResult : ctx.liveResult;
    if (!res || ('northFacing' in res && res.northFacing)) return null;
    const w = res.winner;
    if (w.placedCount <= 0) return null;
    // ACAL356 — le dérate ombrage × horizon de la carte ; économies recalculées du kWh dératé,
    // plafonnées à la facture (1 ⇒ chiffres du solveur inchangés).
    const f = facteurDerateAnnuel(ctx);
    const eco = f < 1 ? annualSavingsMad(w.annualKwh * f, res.target) : { low: w.savingsLow, high: w.savingsHigh };
    // ACAL853 — le Total reprend le kWh peint sur la carte (un seul nombre à l'écran) ; sinon le calcul d'avant.
    const carte = deps.etatCarte?.();
    const annualKwh = carte ? carte.kwhParPanneau * w.placedCount : w.annualKwh * f;
    return { panels: w.placedCount, kwc: w.kwc, annualKwh, savingsLow: eco.low, savingsHigh: eco.high };
  }

  /** Écrit l'instantané du résultat vivant dans l'enregistrement de la zone active. */
  function snapshotActiveAreaResult() {
    const a = ctx.activeArea();
    if (a) a.result = liveActiveResult();
  }

  /** Capture la GÉOMÉTRIE + l'état d'édition courants de la zone active dans son
   *  enregistrement (sans toucher au résultat, géré par le snapshot ci-dessus). */
  function snapshotActiveAreaGeometry() {
    const a = ctx.activeArea();
    if (!a) return;
    a.vertices = [...ctx.vertices];
    a.obstacles = ctx.obstacles.map((o) => ({ ...o }));
    a.roofType = ctx.roofType;
    a.pitchDeg = ctx.pitchDeg;
    a.facingAzimuthDeg = ctx.facingAzimuthDeg;
    a.facingManual = ctx.facingManual; // W106 — l'override manuel par zone persiste
    a.neededPanels = ctx.neededPanels;
    a.neededAuto = ctx.neededAuto;
  }

  /** Active/désactive le bouton « + Ajouter une zone » : autorisé seulement quand la
   *  zone active est FERMÉE (un tracé valide existe). */
  function syncAddAreaButton() {
    const { addAreaBtn } = ctx.dom;
    if (addAreaBtn) addAreaBtn.disabled = !ctx.closed || ctx.vertices.length < 3;
    deps.apresRendu?.(); // ACAL410
  }

  /** Rend le panneau « Zones » : total agrégé (zone active = résultat LIVE, pas le snapshot
   *  potentiellement périmé) + une ligne par zone. Masqué tant qu'aucune zone n'a de résultat. */
  let triParAcces = false; // ACAL728
  function renderAreasPanel() {
    syncAddAreaButton();
    syncBoutonDisposition(); // ACAL574 — à chaque redessin (changement de pan actif compris)
    const { areasWindowEl, areasListEl, areasTotalPanelsEl, areasTotalKwcEl, areasTotalProdEl, areasTotalSavingsEl } = ctx.dom;
    if (!areasWindowEl) return;
    const areas = ctx.areas;
    areas.forEach((a, i) => { a.label = areaLabel(i); }); // ACAL1430 — UN nom par pan (son rang) : liste, cadenas, refus, document
    const activeAreaId = ctx.activeAreaId;
    const liveActive = liveActiveResult();
    // Résultats agrégés : la zone active prend son résultat LIVE, les autres leur snapshot.
    const results = areas.map((a) => (a.id === activeAreaId ? liveActive : a.result));
    const anyResult = results.some((r) => r != null);
    // ACAL410 (acceptation ACAL490) — plusieurs pans sans résultat (« 4 pans » dont le premier
    // regarde le nord) : la liste est quand même redessinée, jamais la ligne périmée d'avant.
    areasWindowEl.hidden = !anyResult && areas.length < 2;
    if (areasWindowEl.hidden) return;
    // WB20 — toutes les zones résolvent contre la MÊME facture globale (pas une part
    // par zone) : chaque `r.savings*` est déjà plafonné à TOUTE la facture, donc les
    // sommer sur-compterait jusqu'à N× sur un toit à N zones. On repasse la cible
    // annuelle globale (facture) à `aggregateAreas` pour qu'elle recalcule UNE seule
    // économie plafonnée à partir du kWh produit total.
    const targetAnnualKwh = ctx.roofType === 'pitched' ? ctx.pitchedRec?.targetAnnualKwh : ctx.rec?.targetAnnualKwh;
    const total = aggregateAreas(results, targetAnnualKwh, annualSavingsMad);
    // T4-X2-010 — un pan NON actif se lit sur sa pose ENREGISTRÉE (ce que le document émet) : rouvert, il n'a pas de
    // `result` et le tableau disait « 0 modules · à calculer » à côté d'une barre qui comptait ses panneaux.
    const posesAffichees = areas.map((a) => poseAfficheeDuPan(a, activeAreaId, liveActive));
    total.panels = posesAffichees.reduce((s, p) => s + (p?.panels ?? 0), 0);
    total.kwc = posesAffichees.reduce((s, p) => s + (p?.kwc ?? 0), 0);
    // ACAL851 — le module CHOISI de chaque pan (le kWc de zone du solveur pour un pan sans choix).
    const poses = areas.map((a, i) => {
      const m = a.moduleId ? resoudreModuleDuPan(catalogueAtelier.choisissables, a.moduleId) : null;
      const module = m && !estRefus(m) ? m : null;
      const r = posesAffichees[i];
      return { r, module, kwc: r && module ? kwcDuPan(r.panels, module) : r?.kwc ?? 0 };
    }).filter((p) => p.r != null && p.r.panels > 0);
    const watts = new Set(poses.map((p) => (p.module ?? MODULE_PAR_DEFAUT_ATELIER).pmaxWc));
    const watt = watts.size > 1 ? null : watts.size ? [...watts][0] : MODULE_PAR_DEFAUT_ATELIER.pmaxWc;
    if (areasTotalPanelsEl) areasTotalPanelsEl.textContent = watt ? `${fmt(total.panels)} × ${fmt(watt)} W` : `${fmt(total.panels)} panneaux`;
    // W97 §2 — 2 décimales : la somme des zones affichées == le total affiché (cf. optimizer.ts).
    const kwcTotal = poses.some((p) => p.module) ? (poses.some((p) => p.kwc == null) ? null
      : poses.reduce((s, p) => s + (p.kwc as number), 0)) : total.kwc;
    if (areasTotalKwcEl) areasTotalKwcEl.textContent = kwcTotal == null ? '—' : `${kwcTotal.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc`;
    if (areasTotalProdEl) areasTotalProdEl.textContent = texteTotalProduction(total.annualKwh, kwcTotal, ctx.opts?.chiffrage !== undefined, ctx.opts?.chiffrage); // ACAL1418 — la production servie, comme la carte
    if (ctx.opts?.chiffrage !== undefined) peindrePhraseTailles(areasTotalProdEl?.closest('dl'), 'rp9-areas-tailles', phraseTaillesDuChiffrage(ctx.opts?.chiffrage, kwcTotal)); // T4-X9-007 — UNE fois, sous le Total
    if (areasTotalSavingsEl) areasTotalSavingsEl.textContent = economieAffichee(ctx, 'total', total.savingsHigh > 0 ? `${fmtMad(total.savingsLow)} – ${fmtMad(total.savingsHigh)}/an` : '—', kwcTotal); // ACAL994 ; T4-X9-003 — contrôlée au kWc posé

    // CAL59 — statistiques par pan + totaux par bâtiment (colonnes toutes CALCULÉES).
    // CALX110 câblage — 3ᵉ argument : le MODULE de chaque pan. Sans lui, deux modèles posés
    // sur deux pans rendaient le même kWc (`nombre × 720 W` partout) ; avec lui, le kWc d'un
    // pan vaut `nombre × la puissance de SON module` et l'occupation se mesure sur SON
    // empreinte. Un pan sans choix rend `null` ⇒ colonnes identiques à aujourd'hui.
    // ACAL1420 — le pan ACTIF se mesure sur ses sommets VIVANTS (`ctx.vertices`), son enregistrement n'étant
    // synchronisé qu'au changement de pan (même patron que la sérialisation) : jamais « non tracé » à côté de son aire.
    const pansVivants = areas.map((a) => (a.id === activeAreaId ? { ...a, vertices: ctx.vertices } : a));
    const stats = computePanStats(pansVivants, (a) => poseAfficheeDuPan(a, activeAreaId, liveActive), moduleDuPan); // T4-X2-010
    const multiBuilding = hasMultipleBuildings(stats);

    if (areasListEl) {
      // ACAL728 — tri d'AFFICHAGE à la demande (jamais écrit) ; un seul pan ⇒ pas de bouton.
      const accesDe = (a: AreaRecord) => (a.id === activeAreaId ? deps.accesVivant?.() ?? null : null) ?? accesMoyenDuPan(a);
      const ordre = triParAcces ? trierPansParAcces(areas, accesDe) : areas;
      let triBtn = document.getElementById('rp9-areas-tri') as HTMLButtonElement | null;
      if (!triBtn) {
        triBtn = document.createElement('button');
        triBtn.id = 'rp9-areas-tri';
        triBtn.type = 'button';
        triBtn.className = 'mb-2 min-h-11 border border-white/25 px-3 py-1 text-xs font-semibold text-lune-soft hover:border-brass-400';
        triBtn.textContent = 'Trier par ensoleillement';
        triBtn.addEventListener('click', () => { triParAcces = !triParAcces; renderAreasPanel(); });
        areasListEl.insertAdjacentElement('beforebegin', triBtn);
      }
      triBtn.hidden = areas.length < 2;
      triBtn.setAttribute('aria-pressed', String(triParAcces));
      const rowHtml = (a: AreaRecord, i: number): string => {
        const r = poseAfficheeDuPan(a, activeAreaId, liveActive); // T4-X2-010
        const active = a.id === activeAreaId;
        const panels = r ? fmt(r.panels) : '—';
        const kwc = r ? `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc` : a.vertices.length >= 3 ? 'non calculé' : 'à tracer';
        const rowClass = active
          ? 'border-brass-400 bg-brass-400/10'
          : 'border-white/10 bg-nuit-900/40';
        const delBtn =
          areas.length > 1
            ? `<button type="button" data-area-del="${a.id}" aria-label="Supprimer ${esc(areaLabel(i))}" class="border border-alert-300/60 px-2.5 py-1 text-xs font-semibold text-alert-300 transition-colors hover:bg-alert-300/10">×</button>`
            : '';
        // ACAL520 — cadenas du pan (≥ 44 px, `aria-pressed`) : verrouillé, ses gestes refusent.
        const lockBtn = `<button type="button" data-area-lock="${a.id}" aria-pressed="${a.verrouille ? 'true' : 'false'}" aria-label="Verrouiller ${esc(areaLabel(i))}" class="min-h-11 min-w-11 border px-2.5 py-1 text-xs font-semibold ${a.verrouille ? 'border-brass-400 text-brass-300' : 'border-white/25 text-lune-soft'}">${a.verrouille ? 'Verrouillé' : 'Verrouiller'}</button>`;
        const viewBtn = active
          ? `<span class="text-xs font-semibold text-brass-300">● active</span>`
          : `<button type="button" data-area-select="${a.id}" class="border border-white/25 px-2.5 py-1 text-xs font-semibold text-lune-soft transition-colors hover:border-brass-400 hover:text-brass-300">Voir</button>`;
        // CAL59 — saisie du bâtiment : un input LIBRE (l'utilisateur nomme ses bâtiments,
        // aucune liste imposée) ; vide = bâtiment unique, comportement historique.
        const buildingInput = `<input type="text" data-area-building="${a.id}" value="${esc(a.buildingId ?? '')}"
          placeholder="bâtiment" aria-label="Bâtiment de ${esc(areaLabel(i))}"
          class="w-24 border border-white/15 bg-nuit-900/60 px-1.5 py-0.5 text-[11px] text-lune-soft focus:border-brass-400 focus:outline-none" />`;
        return `<li class="flex flex-wrap items-center gap-x-3 gap-y-1 border ${rowClass} p-3 text-sm" data-area-row="${a.id}">
          <span class="font-semibold text-white">${esc(areaLabel(i))}${etiquettePanExistant(a)}</span>
          <span class="text-xs text-lune-faint">${panels} panneaux · ${kwc}${triParAcces ? ` · ${mentionAcces(accesDe(a))}` : ''}</span>
          ${buildingInput}
          <span class="ml-auto flex items-center gap-2">${boutonReporterReglages(a.id, areas.length)}${lockBtn}${viewBtn}${delBtn}</span>
        </li>`;
      };
      if (!multiBuilding) {
        // CAL59 — aucune zone ne porte de `buildingId` : liste plate, octet pour octet
        // identique au comportement historique (aucun sous-total redondant).
        areasListEl.innerHTML = ordre.map((a) => rowHtml(a, areas.indexOf(a))).join('');
      } else {
        // CAL59 — un calepinage multi-bâtiments : une ligne d'en-tête de sous-total PAR
        // bâtiment (panneaux/kWc CALCULÉS, jamais saisis), suivie des zones du groupe.
        const indexOf = new Map(areas.map((a, i) => [a.id, i]));
        areasListEl.innerHTML = stats.byBuilding
          .map((b, rang) => {
            const rows = ordre.filter((a) => (a.buildingId ?? null) === b.buildingId);
            const header = `<li class="border border-white/20 bg-nuit-900/60 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-lune-faint" data-building-header="${esc(b.buildingId ?? '')}">
              ${esc(buildingLabel(b.buildingId, rang + 1))} — ${fmt(b.panels)} panneaux · ${b.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc
            </li>`;
            return header + rows.map((a) => rowHtml(a, indexOf.get(a.id) ?? 0)).join('');
          })
          .join('');
      }
    }

    // CAL84 — tableau par pan (modules/kWc/orientation/pente/surface utile/occupation),
    // totalisé par bâtiment puis par site. Masqué s'il n'y a qu'un seul pan sans intérêt
    // de tableau… non : affiché dès qu'un résultat existe (même règle que le reste du
    // panneau), pour que la somme des lignes reste visible et vérifiable.
    const statsEl = ensureStatsTable();
    if (statsEl) renderStatsTable(statsEl, stats.pans, multiBuilding);

    // CALX97 — les cotes affichées suivent le pan actif (lues, jamais devinées).
    syncGeometryPanel();
    // CALX109/CALX110 câblage — le sélecteur suit le pan actif, et la mention NOMME ce qui
    // est réellement posé (le module par défaut tant que rien n'est choisi, « plusieurs
    // modèles » dès que les pans divergent).
    syncModulePicker(stats.modules);
    if (statsEl) statsEl.insertAdjacentHTML('beforeend', htmlTableSite(computeSiteStats(stats, ctx.surfacesPose))); // CALX126 — totaux du site : pans de toit ET surfaces de pose, une ligne par surface, un total par bâtiment
  }

  /** Rend le tableau CAL84 : une ligne par pan, colonnes toutes calculées. */
  function renderStatsTable(el: HTMLElement, pans: PanStat[], multiBuilding: boolean): void {
    const fmtPct = (r: number | null) => (r == null ? '—' : `${Math.round(r * 100)} %`);
    const fmtDeg = (v: number | null) => (v == null ? '—' : `${Math.round(v)}°`);
    const groupes = [...new Set(pans.map((p) => p.buildingId))];
    const rows = pans
      .map(
        (p) => `<tr data-pan-stat="${esc(p.id)}">
          <td class="px-2 py-1 text-white">${esc(p.label || p.id)}${etiquettePanExistant(ctx.areas.find((a) => a.id === p.id))}</td>
          ${multiBuilding ? `<td class="px-2 py-1 text-lune-faint">${esc(buildingLabel(p.buildingId, groupes.indexOf(p.buildingId) + 1))}</td>` : ''}
          <td class="px-2 py-1 text-right">${p.panels ? fmt(p.panels) : `0 <span class="text-lune-faint">(${esc(p.zeroReason)})</span>`}</td>
          <td class="px-2 py-1 text-right">${p.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}</td>
          <td class="px-2 py-1 text-right">${fmtDeg(p.azimuthDeg)}</td>
          <td class="px-2 py-1 text-right">${fmtDeg(p.pitchDeg)}</td>
          <td class="px-2 py-1 text-right">${p.areaM2 > 0 ? Math.round(p.areaM2) : '—'}</td>
          <td class="px-2 py-1 text-right">${fmtPct(p.occupancyRate)}</td>
        </tr>`,
      )
      .join('');
    el.innerHTML = `<table class="w-full border-collapse text-xs text-lune-soft">
      <thead>
        <tr class="border-b border-white/15 text-left text-[11px] uppercase tracking-wide text-lune-faint">
          <th class="px-2 py-1">Pan</th>
          ${multiBuilding ? '<th class="px-2 py-1">Bâtiment</th>' : ''}
          <th class="px-2 py-1 text-right">Modules</th>
          <th class="px-2 py-1 text-right">kWc</th>
          <th class="px-2 py-1 text-right">Azimut</th>
          <th class="px-2 py-1 text-right">Pente</th>
          <th class="px-2 py-1 text-right">Surface m²</th>
          <th class="px-2 py-1 text-right">Occupation</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  // ————————————————————————————————————————————————————————————————————
  // CALX97 — panneau « Cotes et rotation du pan », créé ICI si l'hôte ne le fournit pas
  // (même patron qu'`ensureStatsTable`) : aucune page n'a à être modifiée. Il agit sur le
  // pan ACTIF — celui qui est à l'écran — et le NOMME dans chaque message.
  // ————————————————————————————————————————————————————————————————————
  function ensureGeometryPanel(): HTMLElement | null {
    const existing = document.getElementById('rp9-pan-geometry');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-pan-geometry';
    el.className = 'rp9-pan-geometry mt-3 flex flex-wrap items-center gap-2 text-xs';
    el.innerHTML =
      `<span class="font-semibold" id="rp9-pan-geometry-nom"></span>` +
      `<label class="flex min-w-0 flex-col gap-1" for="rp9-pan-largeur">Largeur (m)` +
      `<input type="text" id="rp9-pan-largeur" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<label class="flex min-w-0 flex-col gap-1" for="rp9-pan-longueur">Longueur (m)` +
      `<input type="text" id="rp9-pan-longueur" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<button type="button" id="rp9-pan-coter" class="rp9-btn">Appliquer les cotes</button>` +
      `<label class="flex min-w-0 flex-col gap-1" for="rp9-pan-rotation">Rotation (°)` +
      `<input type="text" id="rp9-pan-rotation" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<button type="button" id="rp9-pan-pivoter" class="rp9-btn">Pivoter le pan</button>` +
      `<label class="flex min-w-0 flex-col gap-1" for="rp9-site-rotation">Rotation du site (°)` +
      `<input type="text" id="rp9-site-rotation" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<button type="button" id="rp9-site-pivoter" class="rp9-btn">Pivoter le site</button>` +
      `<span id="rp9-pan-geometry-erreur" class="text-alert-300" role="alert" hidden></span>` +
      `<span id="rp9-site-erreur" class="text-alert-300" role="alert" hidden></span>` +
      // ACAL510 — case repliée « Pan existant » (modules déjà en place) + année SAISIE.
      `<details class="w-full"><summary class="min-h-11 cursor-pointer">Pan existant</summary>` +
      `<div class="flex flex-wrap items-center gap-2"><label class="inline-flex min-h-11 items-center gap-2"><input type="checkbox" id="rp9-pan-existant" /> Modules déjà en place</label>` +
      `<label class="inline-flex items-center gap-2" for="rp9-pan-annee">Année de mise en service` +
      `<input type="text" id="rp9-pan-annee" class="rp9-input w-20" inputmode="numeric" /></label></div>` +
      `<span id="rp9-pan-annee-erreur" class="block text-alert-300" role="alert" hidden></span></details>`;
    areasWindowEl.appendChild(el);
    return el;
  }
  const geometryPanelEl = ensureGeometryPanel();
  const panNomEl = document.getElementById('rp9-pan-geometry-nom');
  const panLargeurEl = document.getElementById('rp9-pan-largeur') as HTMLInputElement | null;
  const panLongueurEl = document.getElementById('rp9-pan-longueur') as HTMLInputElement | null;
  const panRotationEl = document.getElementById('rp9-pan-rotation') as HTMLInputElement | null;
  const panErreurEl = document.getElementById('rp9-pan-geometry-erreur');

  /** Nombre à la française (virgule décimale tolérée), comme partout dans l'atelier. */
  const nombreSaisi = (s: string | null | undefined): number =>
    parseFloat((s ?? '').replace(/\s/g, '').replace(',', '.'));

  /** Nom du pan ACTIF, tel qu'il est écrit dans la liste des zones. */
  function nomDuPanActif(): string {
    const i = ctx.areas.findIndex((a) => a.id === ctx.activeAreaId);
    return areaLabel(i >= 0 ? i : 0); // ACAL1430 — le nom de la liste, jamais un `label` périmé
  }

  /** Affiche (ou efface) un refus NOMMÉ, dans le panneau ET dans le bandeau de statut. */
  function direRefusGeometrie(motif: string | null, idErreur = 'rp9-pan-geometry-erreur') {
    const erreurEl = idErreur === 'rp9-pan-geometry-erreur' ? panErreurEl : document.getElementById(idErreur);
    if (erreurEl) {
      erreurEl.textContent = motif ?? '';
      erreurEl.hidden = !motif;
    }
    if (motif) deps.setStatus?.(motif);
  }

  /** ACAL574 — le refus (texte unique d'ACAL510) quand le pan ACTIF est « existant », sinon null. */
  function motifDuPanExistantActif(): string | null {
    const i = ctx.areas.findIndex((a) => a.id === ctx.activeAreaId);
    return motifPanExistant(ctx.areas[i], Math.max(0, i));
  }
  /** ACAL574 — « Déplacer les panneaux » grisé, avec sa raison, tant qu'un pan existant est actif. */
  function syncBoutonDisposition() {
    const btn = document.getElementById('rp9-layout-toggle') as HTMLButtonElement | null;
    const motif = motifDuPanExistantActif();
    if (!btn) return;
    btn.disabled = !!motif;
    if (motif) btn.title = motif; else if (btn.dataset.titrePanExistant) btn.removeAttribute('title');
    if (motif) btn.dataset.titrePanExistant = '1'; else delete btn.dataset.titrePanExistant;
    // ACAL1524 — le motif se LIT (au doigt le `title` n'existe pas) : une phrase écrite sous le bouton.
    const rangee = btn.parentElement;
    let ligne = document.getElementById('rp9-layout-toggle-motif');
    if (motif && rangee && !ligne) {
      ligne = document.createElement('p');
      ligne.id = 'rp9-layout-toggle-motif'; ligne.className = 'rp9-motif-refus'; ligne.setAttribute('role', 'status');
      rangee.insertAdjacentElement('afterend', ligne);
    }
    if (ligne) { ligne.textContent = motif ?? ''; ligne.hidden = !motif; }
  }

  /** Applique une géométrie transformée au pan ACTIF (contour + obstacles vivants). */
  function appliquerAuPanActif(geometrie: GeometriePan): boolean {
    const verrou = motifPanVerrouille(ctx.activeArea?.(), ctx.areas.findIndex((a) => a.id === ctx.activeAreaId)) ?? motifDuPanExistantActif(); // ACAL520, ACAL574
    if (verrou) { direRefusGeometrie(verrou); return false; }
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    ctx.vertices.splice(0, ctx.vertices.length, ...geometrie.vertices);
    ctx.obstacles.splice(0, ctx.obstacles.length, ...geometrie.obstacles);
    snapshotActiveAreaGeometry(); // l'enregistrement de la zone suit le pan vivant
    deps.redrawTrace?.();
    deps.redrawObstacles?.();
    deps.recalc?.();
    renderAreasPanel();
    return true;
  }

  function pivoterPanActif(angleDeg: number): boolean {
    const verdict = pivoterPan(
      { vertices: ctx.vertices, obstacles: ctx.obstacles },
      angleDeg,
      nomDuPanActif(),
    );
    if (!verdict.ok) {
      direRefusGeometrie(verdict.motif);
      return false;
    }
    direRefusGeometrie(null);
    if (!appliquerAuPanActif(verdict.geometrie)) return false;
    deps.setStatus?.(`${nomDuPanActif()} pivoté de ${angleDeg}° — ses obstacles ont suivi.`);
    return true;
  }

  /** ACAL515 — pivote TOUT le site (pans, obstacles, environnement, zones, mesures) d'un seul geste
   *  annulable. Refus NOMMÉ (panneaux posés, angle illisible…) : rien ne bouge. */
  function pivoterSiteActif(angleDeg: number): boolean {
    snapshotActiveAreaResult();
    snapshotActiveAreaGeometry();
    const verdict = pivoterSite({
      zones: ctx.areas.map((a) => ({
        label: a.label, vertices: a.vertices, obstacles: a.obstacles, facingAzimuthDeg: a.facingAzimuthDeg,
        geometry: a.geometrieEnregistree, result: a.result,
      })),
      environment: ctx.environment ?? [], exclusionZones: ctx.exclusionZones ?? [], measurements: ctx.measurements ?? [],
    }, angleDeg);
    if (!verdict.ok) {
      direRefusGeometrie(verdict.motif, 'rp9-site-erreur');
      return false;
    }
    direRefusGeometrie(null, 'rp9-site-erreur');
    ctx.pushWorkshopHistory?.(); // UN seul point d'historique pour tout le geste
    const tournees = verdict.site.zones as Array<Pick<AreaRecord, 'vertices' | 'obstacles' | 'facingAzimuthDeg' | 'geometrieEnregistree'> & { geometry?: AreaRecord['geometrieEnregistree'] }>;
    ctx.areas.forEach((a, i) => {
      a.vertices = tournees[i].vertices;
      a.obstacles = tournees[i].obstacles;
      a.facingAzimuthDeg = tournees[i].facingAzimuthDeg;
      if (tournees[i].geometry) a.geometrieEnregistree = tournees[i].geometry;
    });
    for (const k of ['environment', 'exclusionZones', 'measurements'] as const) {
      (ctx[k] as unknown[] | undefined)?.splice(0, Infinity, ...(verdict.site[k] as unknown[]));
    }
    const actif = ctx.activeArea();
    if (actif) {
      ctx.vertices.splice(0, ctx.vertices.length, ...actif.vertices);
      ctx.obstacles.splice(0, ctx.obstacles.length, ...actif.obstacles);
      ctx.facingAzimuthDeg = actif.facingAzimuthDeg;
    }
    deps.redrawTrace?.();
    deps.redrawObstacles?.();
    deps.recalc?.();
    renderAreasPanel();
    deps.setStatus?.(`Site pivoté de ${angleDeg}° — les obstacles gardent leur orientation nord-sud.`);
    return true;
  }

  function redimensionnerPanActif(largeurM: number, longueurM: number): boolean {
    const verdict = redimensionnerPan(
      { vertices: ctx.vertices, obstacles: ctx.obstacles },
      largeurM,
      longueurM,
      nomDuPanActif(),
    );
    if (!verdict.ok) {
      direRefusGeometrie(verdict.motif);
      return false;
    }
    direRefusGeometrie(null);
    if (!appliquerAuPanActif(verdict.geometrie)) return false;
    deps.setStatus?.(`${nomDuPanActif()} reposé aux cotes saisies — son centre n’a pas bougé.`);
    return true;
  }

  /** Remplit le panneau avec les cotes RÉELLES du pan actif (jamais une cote devinée). */
  function syncGeometryPanel() {
    if (!geometryPanelEl) return;
    geometryPanelEl.hidden = !ctx.closed || ctx.vertices.length < 3;
    if (geometryPanelEl.hidden) return;
    if (panNomEl) panNomEl.textContent = nomDuPanActif();
    const actif = ctx.areas.find((a) => a.id === ctx.activeAreaId); // ACAL510
    const caseEl = document.getElementById('rp9-pan-existant') as HTMLInputElement | null;
    if (caseEl) caseEl.checked = !!actif?.existant;
    const anneeEl = document.getElementById('rp9-pan-annee') as HTMLInputElement | null;
    if (anneeEl && document.activeElement !== anneeEl) anneeEl.value = actif?.anneeMiseEnService != null ? String(actif.anneeMiseEnService) : '';
    const dims = dimensionsRectangleM(ctx.vertices);
    const fmtDim = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 2 });
    if (panLargeurEl && document.activeElement !== panLargeurEl) {
      panLargeurEl.value = dims ? fmtDim(dims.largeurM) : '';
      // Pan non rectangulaire : les cotes n'existent pas, on ne les invente pas.
      panLargeurEl.disabled = !dims;
    }
    if (panLongueurEl && document.activeElement !== panLongueurEl) {
      panLongueurEl.value = dims ? fmtDim(dims.longueurM) : '';
      panLongueurEl.disabled = !dims;
    }
    if (!dims) {
      direRefusGeometrie(
        `${nomDuPanActif()} : la saisie largeur/longueur ne s’applique qu’à un pan à 4 côtés. La rotation, elle, reste disponible.`,
      );
    }
  }

  geometryPanelEl?.addEventListener('click', (e) => {
    const cible = (e.target as HTMLElement).closest<HTMLElement>('button');
    if (cible?.id === 'rp9-pan-coter') {
      redimensionnerPanActif(nombreSaisi(panLargeurEl?.value), nombreSaisi(panLongueurEl?.value));
    } else if (cible?.id === 'rp9-pan-pivoter') {
      pivoterPanActif(nombreSaisi(panRotationEl?.value));
    } else if (cible?.id === 'rp9-site-pivoter') {
      pivoterSiteActif(nombreSaisi((document.getElementById('rp9-site-rotation') as HTMLInputElement | null)?.value));
    }
  });

  // ACAL510 — « Pan existant » : case et année du pan ACTIF ; une année refusée se dit sous le champ.
  geometryPanelEl?.addEventListener('change', (e) => {
    const t = e.target as HTMLInputElement;
    const pan = ctx.areas.find((a) => a.id === ctx.activeAreaId);
    if (!pan || (t.id !== 'rp9-pan-existant' && t.id !== 'rp9-pan-annee')) return;
    if (t.id === 'rp9-pan-existant') {
      if (t.checked) pan.existant = true; else { delete pan.existant; delete pan.anneeMiseEnService; } // absent = pan neuf : octet pour octet
      syncBoutonDisposition(); // ACAL574
      return;
    }
    const v = anneeValide(t.value);
    direRefusGeometrie(v.ok ? null : v.motif, 'rp9-pan-annee-erreur');
    if (v.ok) pan.anneeMiseEnService = v.annee;
  });

  // ACAL520 — clic sur le cadenas d'un pan : bascule `verrouille` et redessine la liste.
  ctx.dom.areasListEl?.addEventListener('click', (e) => {
    const id = (e.target as HTMLElement).closest<HTMLElement>('[data-area-lock]')?.dataset.areaLock;
    const pan = id ? ctx.areas.find((a) => a.id === id) : undefined;
    if (!pan) return;
    if (pan.verrouille) delete pan.verrouille; else pan.verrouille = true; // absent = modifiable : octet pour octet
    renderAreasPanel();
  });

  // ACAL554 — « Appliquer ces réglages à… » : cases à cocher, confirmation en deux temps, UNE photo d'historique.
  function ouvrirReport(sourceId: string) {
    const source = ctx.areas.find((a) => a.id === sourceId);
    const hote = ctx.dom.areasWindowEl;
    if (!source || !hote) return;
    document.getElementById('rp9-pan-report')?.remove();
    const nom = (a: AreaRecord) => areaLabel(Math.max(0, ctx.areas.indexOf(a))); // ACAL1527 — « Zone 2 », jamais l'identifiant `area-copie-1`
    const box = document.createElement('div');
    box.id = 'rp9-pan-report';
    box.className = 'mt-2 space-y-1 border border-white/20 p-3 text-xs text-lune-soft';
    box.innerHTML = `<p>Appliquer le module, le type de toit, la pente et la face de ${esc(nom(source))} à :</p>`
      + ctx.areas.filter((a) => a.id !== sourceId).map((a) => `<label class="flex min-h-11 items-center gap-2"><input type="checkbox" value="${esc(a.id)}" />${esc(nom(a))}</label>`).join('')
      + '<p id="rp9-pan-report-note" role="status" class="text-alert-300"></p>'
      + '<button type="button" class="rp9-btn min-h-11" data-report="ok">Appliquer</button> <button type="button" class="rp9-btn min-h-11" data-report="non">Annuler</button>';
    const note = box.querySelector<HTMLElement>('#rp9-pan-report-note')!;
    const ok = box.querySelector<HTMLButtonElement>('[data-report="ok"]')!;
    let confirme = false;
    box.addEventListener('change', () => { confirme = false; ok.textContent = 'Appliquer'; note.textContent = ''; });
    box.querySelector('[data-report="non"]')!.addEventListener('click', () => box.remove());
    ok.addEventListener('click', () => {
      const ids = [...box.querySelectorAll<HTMLInputElement>('input:checked')].map((i) => i.value);
      const cibles = ctx.areas.filter((a) => ids.includes(a.id));
      const refus = refusModulePan(source) ?? (cibles.length ? null : 'Cochez au moins un pan.');
      if (refus || !deps.selectArea) { note.textContent = refus ?? 'Report indisponible ici.'; return; }
      const mains = pansReglesAMain(cibles);
      if (!confirme) {
        confirme = true;
        ok.textContent = 'Confirmer';
        note.textContent = `${mains.length ? `Déjà réglés à la main, ils seront écrasés : ${mains.map(nom).join(', ')}. ` : ''}${fmt(cibles.length)} pans seront re-pavés.`;
        return;
      }
      ctx.pushWorkshopHistory?.(); // CAL100 — annuler rend l'état d'avant pour tous les pans
      const aller = deps.selectArea;
      if (ctx.activeAreaId !== sourceId) aller(sourceId);
      snapshotActiveAreaGeometry();
      appliquerReglagesAuxPans(source, cibles);
      for (const id of [...cibles.map((c) => c.id), sourceId]) aller(id);
      deps.setStatus?.(`Réglages de ${nom(source)} appliqués à ${fmt(cibles.length)} pans, re-pavés.`);
      box.remove();
    });
    hote.appendChild(box);
  }
  function refusModulePan(source: AreaRecord): string | null {
    if (!source.moduleId) return null;
    const m = resoudreModuleDuPan(catalogueAtelier.choisissables, source.moduleId); // même règle que CALX109
    const c = estRefus(m) ? m : cotesDeModule(m);
    return estRefus(c) ? `${source.label || source.id} : ${c.message}` : null;
  }
  ctx.dom.areasListEl?.addEventListener('click', (e) => {
    const id = (e.target as HTMLElement).closest<HTMLElement>('[data-area-report]')?.dataset.areaReport;
    if (id) ouvrirReport(id);
  });

  // ————————————————————————————————————————————————————————————————————
  // CALX98 — bouton « Dupliquer ce pan » + son pas SAISI, créés ICI si l'hôte ne les
  // fournit pas. Le champ part VIDE et le bouton reste INACTIF tant qu'il l'est, avec le
  // motif affiché : aucun décalage n'est supposé.
  // ————————————————————————————————————————————————————————————————————
  function ensureDuplicatePanel(): HTMLElement | null {
    const existing = document.getElementById('rp9-pan-duplicate');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-pan-duplicate';
    el.className = 'rp9-pan-duplicate mt-2 flex flex-wrap items-center gap-2 text-xs';
    el.innerHTML =
      `<label class="flex min-w-0 flex-col gap-1" for="rp9-pan-dup-pas">Décalage de la copie (m)` +
      `<input type="text" id="rp9-pan-dup-pas" class="rp9-input w-20" inputmode="decimal" value="" /></label>` +
      `<button type="button" id="rp9-pan-dup" class="rp9-btn" disabled>Dupliquer ce pan</button>` +
      `<span id="rp9-pan-dup-motif" class="text-alert-300" role="status"></span>`;
    areasWindowEl.appendChild(el);
    return el;
  }
  const duplicatePanelEl = ensureDuplicatePanel();
  const dupPasEl = document.getElementById('rp9-pan-dup-pas') as HTMLInputElement | null;
  const dupBtnEl = document.getElementById('rp9-pan-dup') as HTMLButtonElement | null;
  const dupMotifEl = document.getElementById('rp9-pan-dup-motif');

  /** CALX98 — le bouton suit le pas saisi : inactif tant qu'il manque, motif affiché. */
  function syncDuplicateButton() {
    const motif = motifPasDuplication(nombreSaisi(dupPasEl?.value));
    if (dupBtnEl) dupBtnEl.disabled = motif != null;
    if (dupMotifEl) dupMotifEl.textContent = motif ?? '';
  }

  function dupliquerPanActif(pasM: number): boolean {
    const source = ctx.activeArea();
    if (!source) return false;
    // La zone active vit dans `ctx` : on fige sa géométrie avant de la recopier.
    snapshotActiveAreaGeometry();
    const verdict = dupliquerPan(source, idZoneCopie(ctx.areas), pasM);
    if (!verdict.ok) {
      if (dupMotifEl) dupMotifEl.textContent = verdict.motif;
      deps.setStatus?.(verdict.motif);
      return false;
    }
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    ctx.areas.push(verdict.zone);
    renderAreasPanel();
    deps.setStatus?.(
      `${nomDuPanActif()} dupliqué — la copie porte ses ${verdict.zone.obstacles.length} obstacle(s) et ses réglages. Ouvrez-la avec « Voir ».`,
    );
    return true;
  }

  dupPasEl?.addEventListener('input', syncDuplicateButton);
  dupPasEl?.addEventListener('change', syncDuplicateButton);
  duplicatePanelEl?.addEventListener('click', (e) => {
    if ((e.target as HTMLElement).closest<HTMLElement>('#rp9-pan-dup')) {
      dupliquerPanActif(nombreSaisi(dupPasEl?.value));
    }
  });
  syncDuplicateButton(); // état initial : champ vide ⇒ bouton inactif + motif affiché

  // ————————————————————————————————————————————————————————————————————
  // CALX109/CALX110 câblage — LE SÉLECTEUR DE MODULE DU PAN ACTIF
  //
  // LE CONSTAT. `moduleSelect.ts` savait déjà lire le catalogue de la société, résoudre le
  // module d'un pan et écrire le tout dans le document — mais RIEN ne permettait de choisir :
  // aucun sélecteur n'existait, donc aucun pan ne portait jamais de `moduleId` et l'atelier
  // ne pavait que son module par défaut. Ce bloc crée le contrôle LUI-MÊME quand la page
  // hôte ne le fournit pas (même patron qu'`ensureStatsTable` / `ensureGeometryPanel`,
  // d'origine `obstaclesUi.ts ensureTypePicker`) : aucune page n'a à être modifiée.
  //
  // CE QU'IL MONTRE, ET CE QU'IL REFUSE. La liste s'ouvre TOUJOURS sur le module par défaut
  // de l'atelier, NOMMÉ — c'est ce qui est posé tant que personne n'a choisi. Viennent
  // ensuite les modèles CHOISISSABLES, puis les modèles GRISÉS (`disabled`) avec le motif du
  // SERVEUR : une fiche produit incomplète reste VISIBLE, sinon on la cherche en vain. Un
  // refus nomme le pan et le modèle, s'affiche À CÔTÉ du sélecteur et dans le bandeau de
  // statut — jamais un « non enregistré » générique. Catalogue vide ⇒ le motif du serveur
  // est dit tel quel ; aucune cote n'est inventée, jamais.
  // ————————————————————————————————————————————————————————————————————

  /** CALX109 — le catalogue de la société, lu UNE fois : `ctx.opts` est figé au boot. */
  const catalogueAtelier: CatalogueModules = lireModulesDisponibles(ctx.opts?.modulesDisponibles);

  /** Le motif d'un modèle GRISÉ : celui du serveur d'abord, sinon celui que les cotes
   *  manquantes dictent (`cotesDeModule` NOMME déjà le champ). Jamais un motif inventé. */
  function motifGrise(g: ModuleDisponible): string {
    if (g.motif && g.motif.trim()) return g.motif.trim();
    const refus = cotesDeModule(g.module);
    return estRefus(refus) ? refus.message : 'fiche produit incomplète';
  }

  function ensureModulePicker(): HTMLElement | null {
    const existing = document.getElementById('rp9-pan-module');
    if (existing) return existing;
    const { areasWindowEl } = ctx.dom;
    if (!areasWindowEl || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-pan-module';
    el.className = 'rp9-pan-module mt-2 flex flex-wrap items-center gap-2 text-xs';
    const options = [
      `<option value="">${esc(MODULE_PAR_DEFAUT_ATELIER.libelle)}</option>`,
      ...catalogueAtelier.choisissables.map(
        (m) => `<option value="${esc(m.id)}">${esc(m.libelle)}</option>`,
      ),
      ...catalogueAtelier.grises.map(
        (g) => `<option value="${esc(g.module.id)}" disabled data-module-grise="1">${esc(g.module.libelle)} — ${esc(motifGrise(g))}</option>`,
      ),
    ].join('');
    el.innerHTML =
      `<label class="flex w-full min-w-0 flex-col gap-1" for="rp9-pan-module-select">Module du pan` +
      `<select id="rp9-pan-module-select" class="rp9-input w-full min-w-0">${options}</select></label>` +
      `<span id="rp9-pan-module-mention" class="text-lune-faint"></span>` +
      `<span id="rp9-pan-module-erreur" class="text-alert-300" role="alert" hidden></span>`;
    areasWindowEl.appendChild(el);
    return el;
  }
  const modulePickerEl = ensureModulePicker();
  const moduleSelectEl = document.getElementById('rp9-pan-module-select') as HTMLSelectElement | null;
  const moduleMentionEl = document.getElementById('rp9-pan-module-mention');
  const moduleErreurEl = document.getElementById('rp9-pan-module-erreur');

  /** Affiche (ou efface) un refus NOMMÉ, à côté du sélecteur ET dans le bandeau de statut. */
  function direRefusModule(motif: string | null, code?: string) {
    if (moduleErreurEl) {
      moduleErreurEl.textContent = motif ?? '';
      moduleErreurEl.hidden = !motif;
      // ACAL1980 — un blocage « module absent » est AUSSI posé au canal « À régler » : la coque (`BandeauxCoque`) lit ce
      // marqueur et le dit dans le panneau de l'étape, au ton « À régler » ; la pilule du bas de carte reste.
      if (motif && code) { moduleErreurEl.dataset.ton = 'a-regler'; moduleErreurEl.dataset.code = code; }
      else { delete moduleErreurEl.dataset.ton; delete moduleErreurEl.dataset.code; }
    }
    if (motif) deps.setStatus?.(motif);
  }

  /**
   * CALX109/CALX110 — le module RÉSOLU d'un pan, pour `computePanStats`.
   *
   * Un pan SANS choix rend `null` — et pas le module par défaut : c'est ce qui garantit que
   * tant que personne n'a choisi, le tableau par pan affiche exactement les chiffres
   * d'aujourd'hui (kWc du résultat de zone, empreinte de l'étude), octet pour octet. Un
   * `moduleId` devenu introuvable rend `null` aussi : on n'invente pas une cote à sa place
   * (le refus, lui, est dit par `syncModulePicker`).
   */
  function moduleDuPan(a: AreaRecord): ModuleDocument | null {
    if (!a.moduleId) return null;
    const module = resoudreModuleDuPan(catalogueAtelier.choisissables, a.moduleId);
    if (estRefus(module)) return null;
    return estRefus(cotesDeModule(module)) ? null : module;
  }

  /** CALX109 — le sélecteur suit le pan ACTIF ; la mention NOMME ce qui est posé. */
  function syncModulePicker(synthese?: SyntheseModules) {
    if (!modulePickerEl) return;
    const a = ctx.activeArea();
    modulePickerEl.hidden = !a;
    if (!a) return;
    if (moduleSelectEl && document.activeElement !== moduleSelectEl) {
      moduleSelectEl.value = a.moduleId ?? '';
      // Un `moduleId` que le catalogue ne porte plus ne peut pas être sélectionné : le
      // <select> retombe sur le défaut tout seul. On le DIT, plutôt que de laisser croire
      // que ce pan est revenu au module par défaut de son plein gré.
      if (a.moduleId && moduleSelectEl.value !== a.moduleId) {
        // T4-U4-007 — le module est NOMMÉ par son libellé (document, sinon catalogue), jamais par l'identifiant interne.
        const connu = [...(ctx.modulesDuDocument ?? []), ...catalogueAtelier.grises.map((g) => g.module)]
          .find((m) => (m as ModuleDocument | null)?.id === a.moduleId) as ModuleDocument | undefined;
        const nom = connu?.libelle ? `le module « ${connu.libelle} »` : 'le module de ce pan';
        // T4-U4-026 — `modulesDisponibles: null` = la LECTURE du catalogue a échoué (useAtelierBoot) : le module n'est
        // pas sorti du catalogue, il n'a pas pu être vérifié. Le geste est « Réessayer » de la barre d'enregistrement.
        direRefusModule(ctx.opts?.modulesDisponibles === null
          ? `${nomDuPanActif()} : le catalogue des modules n’a pas pu être lu — ${nom} n’est pas vérifié.`
            + ' Cliquez sur « Réessayer » pour le relire.'
          : `${nomDuPanActif()} : ${nom} ne figure plus dans le catalogue de la société —`
            + ' rechargez le catalogue, ou choisissez un module de la liste.',
        ctx.opts?.modulesDisponibles === null ? 'catalogue-illisible' : 'module-absent');
      } else if (moduleErreurEl?.dataset.ton === 'a-regler') direRefusModule(null); // le module est revenu : le motif part
    }
    // ACAL913/ACAL1415 — un module posé d'office reste « à confirmer » tant que le pan ne porte pas le drapeau
    // `moduleChoisi` (écrit au document : il survit à l'enregistrement, contrairement à un état de session).
    const depart = !(a as PanAuChoix).moduleChoisi ? moduleDeDepart(catalogueAtelier) : null;
    if (moduleMentionEl && depart && a.moduleId === depart.id) {
      moduleMentionEl.textContent = `${depart.libelle} — ${MENTION_MODULE_DE_DEPART}`;
    } else if (moduleMentionEl) {
      const aucunChoix = !ctx.areas.some((z) => z.moduleId);
      moduleMentionEl.textContent = aucunChoix
        ? `${MODULE_PAR_DEFAUT_ATELIER.libelle} — ${
          catalogueAtelier.choisissables.length
            ? 'aucun module du catalogue n’est posé sur ce site.'
            : catalogueAtelier.motifListeVide
              ?? 'aucun module de la société n’est choisissable aujourd’hui.'
        }`
        : synthese?.mention ?? '';
    }
  }

  /**
   * CALX109/CALX110 — pose un modèle sur le pan ACTIF (chaîne vide = retour au module par
   * défaut de l'atelier, NOMMÉ). Un modèle grisé, inconnu, ou dont la fiche n'a pas de cotes
   * est REFUSÉ en nommant le champ fautif : RIEN n'est écrit sur le pan, et le pavage ne
   * bouge pas. Un choix accepté re-pave immédiatement (`deps.recalc`) — c'est tout l'intérêt
   * de choisir un module : ses VRAIES cotes changent le nombre de rangées.
   */
  function choisirModuleDuPanActif(moduleId: string | null | undefined): boolean {
    const a = ctx.activeArea();
    if (!a) return false;
    const existant = motifDuPanExistantActif(); // ACAL574 — changer le module re-paverait le pan
    if (existant) { direRefusModule(existant); return false; }
    const id = typeof moduleId === 'string' ? moduleId.trim() : '';
    if (!id) {
      ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
      delete a.moduleId;
      delete (a as PanAuChoix).moduleChoisi; // ACAL1415 — plus de module désigné, plus de choix
      direRefusModule(null);
      deps.recalc?.();
      renderAreasPanel();
      deps.setStatus?.(`${nomDuPanActif()} : ${MODULE_PAR_DEFAUT_ATELIER.libelle}.`);
      return true;
    }
    const grise = catalogueAtelier.grises.find((g) => g.module.id === id);
    if (grise) {
      direRefusModule(`${nomDuPanActif()} : « ${grise.module.libelle} » — ${motifGrise(grise)}`);
      syncModulePicker();
      return false;
    }
    const module = resoudreModuleDuPan(catalogueAtelier.choisissables, id);
    if (estRefus(module)) {
      direRefusModule(`${nomDuPanActif()} : ${module.message}`);
      syncModulePicker();
      return false;
    }
    const cotes = cotesDeModule(module);
    if (estRefus(cotes)) {
      direRefusModule(`${nomDuPanActif()} : ${cotes.message}`);
      syncModulePicker();
      return false;
    }
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    a.moduleId = module.id;
    (a as PanAuChoix).moduleChoisi = true; // ACAL913/ACAL1415 — choisi : plus « de départ », écrit au document
    direRefusModule(null);
    deps.recalc?.(); // le pavage repart avec les VRAIES cotes de ce module
    renderAreasPanel();
    deps.setStatus?.(
      `${nomDuPanActif()} : module « ${module.libelle} » — le calepinage est repavé à ses cotes.`,
    );
    return true;
  }

  moduleSelectEl?.addEventListener('change', () => {
    choisirModuleDuPanActif(moduleSelectEl.value);
  });
  syncModulePicker(); // état initial : le module par défaut est NOMMÉ, jamais muet

  /** CAL59 — assigne le bâtiment d'une zone (chaîne vide = retour au bâtiment unique). */
  function setAreaBuilding(id: string, buildingId: string) {
    const a = ctx.areas.find((x) => x.id === id);
    if (!a) return;
    const trimmed = buildingId.trim();
    a.buildingId = trimmed ? trimmed : undefined;
    renderAreasPanel();
  }

  return {
    liveActiveResult,
    snapshotActiveAreaResult,
    snapshotActiveAreaGeometry,
    syncAddAreaButton,
    renderAreasPanel,
    setAreaBuilding,
    pivoterPanActif,
    pivoterSiteActif,
    redimensionnerPanActif,
    dupliquerPanActif,
    choisirModuleDuPanActif, // CALX109/CALX110 câblage
  };
}

// ————————————————————————————————————————————————————————————————————————
// CAL69 — ZONES INTERDITES / RÉSERVÉES / PRÉFÉRÉES TRACÉES DANS L'ATELIER
//
// L'atelier ne proposait que « + Ajouter une zone » au sens PAN DE TOIT : une
// servitude ou une bande coupe-feu tracée par le dessinateur ne changeait RIEN au
// compte publié. Ce bloc porte la zone d'EXCLUSION au sens CAL68, écrivant EXACTEMENT
// le contrat `exclusionZones` du document v2 (`contract_samples/zones.json`,
// `roof_layout_v2.schema.json` `$defs/exclusionZone`) : `id`, `label`, `nature`,
// `vertices` [[lng, lat], …], `setbackM`, `heightM`.
//
// LES DEUX GARANTIES DE CAL68, TENUES CÔTÉ ÉCRAN :
//  - INTERDITE et RESERVEE retirent leur surface du posable ⇒ le compte de modules
//    bouge IMMÉDIATEMENT (leurs anneaux rejoignent les obstructions du pavage) ;
//  - PREFEREE ne change JAMAIS un compte (bonus doux de départage côté moteur) ⇒
//    elle ne rejoint AUCUNE obstruction.
// ENVELOPPE existe dans le vocabulaire du moteur mais ne se trace pas ici : c'est le
// contour lui-même.
//
// GÉOMÉTRIE PURE : aucun Three, aucun DOM, aucune carte — testable seule.
// ————————————————————————————————————————————————————————————————————————

/** Natures traçables dans l'atelier (sous-ensemble de `core.calepinage.types.NatureZone` :
 *  ENVELOPPE est le contour, il ne se dessine pas comme une zone). */
export type ExclusionNature = 'INTERDITE' | 'RESERVEE' | 'PREFEREE';

/** CALX401 — les usages qu'une zone peut porter EN PLUS de sa nature. Un seul aujourd'hui. */
export type UsageZone = 'circulation';

/** CALX401 — l'usage « allée de circulation », tel que le contrat le nomme. */
export const USAGE_CIRCULATION: UsageZone = 'circulation';

export const EXCLUSION_NATURES: readonly { id: ExclusionNature; label: string; note: string }[] = [
  { id: 'INTERDITE', label: 'Interdite', note: 'retirée du posable — le compte baisse' },
  { id: 'RESERVEE', label: 'Réservée', note: 'retirée du posable, chiffrée à part' },
  { id: 'PREFEREE', label: 'Préférée', note: 'ne change jamais le compte' },
];

/** Code couleur DISTINCT de celui des obstacles (`#ff6b6b`) : une zone n'est pas un
 *  obstacle physique, on ne doit pas les confondre à l'œil. */
export const EXCLUSION_COLORS: Record<ExclusionNature, string> = {
  INTERDITE: '#8b5cf6',
  RESERVEE: '#38bdf8',
  PREFEREE: '#22c55e',
};

export function exclusionColor(nature: ExclusionNature): string {
  return EXCLUSION_COLORS[nature] ?? EXCLUSION_COLORS.INTERDITE;
}

/** Une zone d'exclusion du document d'atelier — MÊMES noms de clés que le contrat. */
export interface ExclusionZone {
  id: string;
  label?: string;
  nature: ExclusionNature;
  /** Contour [[lng, lat], …], même repère que `zones[].vertices` (les pans). */
  vertices: LngLat[];
  /** Retrait SAISI (m) autour de la zone. Jamais deviné : 0 tant que rien n'est saisi. */
  setbackM: number;
  /** Hauteur (m). `null`/absente = non renseignée — jamais un repli. */
  heightM?: number | null;
  /** CALX401/CALX403 — ce à quoi la zone SERT, quand ce n'est pas seulement sa nature.
   *  `circulation` = ALLÉE tracée sur le toit. Absent = zone d'exclusion ordinaire. */
  usage?: UsageZone;
  /** CALX401 — la POLYLIGNE tracée (≥ 2 points). Elle garde le GESTE ; c'est `vertices`
   *  qui fait foi pour la géométrie, le couloir y ayant été calculé depuis `axe` et
   *  `largeurM` au moment du tracé. */
  axe?: LngLat[];
  /** CALX401 — largeur SAISIE (m) du passage. Aucune largeur n'est livrée par le dépôt. */
  largeurM?: number;
  /** ACAL31 — provenance déclarative de la zone (contrat `exclusionZones[].source`), relue
   *  et réécrite telle quelle — jamais inventée. Absente = non renseignée. */
  source?: string;
}

/** Retrait PLANCHER/PLAFOND (m) — mêmes ordres de grandeur que les obstacles. */
export const ZONE_MAX_SETBACK_M = 10;
export const ZONE_MAX_HEIGHT_M = 60;

const ZONE_DEG2RAD = Math.PI / 180;
import { WGS84_RADIUS as ZONE_WGS84_RADIUS } from '../../lib/geo';
const ZONE_DEG2M = ZONE_DEG2RAD * ZONE_WGS84_RADIUS;

function clampNum(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Zone rectangulaire née d'un glissé (deux coins), retrait 0 et hauteur non renseignée :
 *  RIEN n'est inventé tant que l'utilisateur n'a pas saisi. */
export function exclusionZoneFromDrag(
  id: string,
  nature: ExclusionNature,
  a: LngLat,
  b: LngLat,
  gabarit?: GabaritZone | null,
): ExclusionZone {
  const zone: ExclusionZone = {
    id,
    nature,
    vertices: [a, [b[0], a[1]], b, [a[0], b[1]]],
    setbackM: 0,
  };
  // ACAL291 — posée depuis un gabarit réglementaire de la société : libellé, nature, retrait,
  // hauteur et SOURCE sont ceux du gabarit (aucun n'est complété ici) ; la géométrie reste le glissé.
  if (!gabarit) return zone;
  return {
    ...zone,
    nature: gabarit.nature,
    label: gabarit.libelle,
    setbackM: gabarit.retraitM,
    ...(gabarit.hauteurM != null ? { heightM: gabarit.hauteurM } : {}),
    source: gabarit.source,
  };
}

export function withZoneNature(z: ExclusionZone, nature: ExclusionNature): ExclusionZone {
  return { ...z, nature };
}

export function withZoneSetback(z: ExclusionZone, setbackM: number | null | undefined): ExclusionZone {
  if (setbackM == null || !Number.isFinite(setbackM) || setbackM <= 0) return { ...z, setbackM: 0 };
  return { ...z, setbackM: clampNum(setbackM, 0, ZONE_MAX_SETBACK_M) };
}

export function withZoneHeight(z: ExclusionZone, heightM: number | null | undefined): ExclusionZone {
  if (heightM == null || !Number.isFinite(heightM) || heightM <= 0) {
    const { heightM: _drop, ...rest } = z;
    return rest;
  }
  return { ...z, heightM: clampNum(heightM, 0, ZONE_MAX_HEIGHT_M) };
}

export function withZoneLabel(z: ExclusionZone, label: string | null | undefined): ExclusionZone {
  const v = (label ?? '').trim();
  if (!v) {
    const { label: _drop, ...rest } = z;
    return rest;
  }
  return { ...z, label: v };
}

/**
 * Anneau AFFICHÉ/OPPOSÉ AU PAVAGE : le contour saisi, DILATÉ du retrait saisi (le
 * retrait d'une zone dilate son emprise, exactement comme `sommets_decales` côté
 * moteur). Retrait 0 ⇒ le contour tel quel. Moins de 3 sommets ⇒ rien à dessiner.
 */
export function exclusionZoneRing(z: ExclusionZone): LngLat[] | null {
  if (!z.vertices || z.vertices.length < 3) return null;
  if (!(z.setbackM > 0)) return z.vertices.map((v) => [v[0], v[1]] as LngLat);
  let sumLng = 0;
  let sumLat = 0;
  for (const [lng, lat] of z.vertices) {
    sumLng += lng;
    sumLat += lat;
  }
  const cLng = sumLng / z.vertices.length;
  const cLat = sumLat / z.vertices.length;
  const cosLat = Math.max(1e-6, Math.cos(cLat * ZONE_DEG2RAD));
  return z.vertices.map(([lng, lat]) => {
    const dx = (lng - cLng) * ZONE_DEG2M * cosLat;
    const dy = (lat - cLat) * ZONE_DEG2M;
    const d = Math.hypot(dx, dy);
    if (d < 1e-9) return [lng, lat] as LngLat;
    const k = (d + z.setbackM) / d;
    return [cLng + (dx * k) / (ZONE_DEG2M * cosLat), cLat + (dy * k) / ZONE_DEG2M] as LngLat;
  });
}

/** Zones qui RETIRENT de la surface posable : INTERDITE et RESERVEE. PREFEREE jamais. */
export function blockingExclusionZones(list: readonly ExclusionZone[] | null | undefined): ExclusionZone[] {
  return (list ?? []).filter((z) => z.nature === 'INTERDITE' || z.nature === 'RESERVEE');
}

/** Anneaux d'obstruction apportés par les zones — à concaténer aux obstacles du pavage.
 *  Une PRÉFÉRÉE n'en produit AUCUN : c'est ce qui garantit que le compte ne bouge pas. */
export function exclusionObstructionRings(list: readonly ExclusionZone[] | null | undefined): LngLat[][] {
  const out: LngLat[][] = [];
  for (const z of blockingExclusionZones(list)) {
    const ring = exclusionZoneRing(z);
    if (ring) out.push(ring);
  }
  return out;
}

/** Sérialisation vers le document v2 (`exclusionZones`) : clés du contrat, rien de plus,
 *  et aucune zone invalide (< 3 sommets) n'est écrite. */
export function serializeExclusionZones(
  list: readonly ExclusionZone[] | null | undefined,
): Array<ZoneSerialisee> {
  const out: Array<ZoneSerialisee> = [];
  for (const z of list ?? []) {
    if (!z || !Array.isArray(z.vertices) || z.vertices.length < 3) continue;
    if (z.nature !== 'INTERDITE' && z.nature !== 'RESERVEE' && z.nature !== 'PREFEREE') continue;
    out.push({
      id: String(z.id),
      ...(z.label ? { label: z.label } : {}),
      nature: z.nature,
      vertices: z.vertices.map((v) => [v[0], v[1]] as LngLat),
      setbackM: Number.isFinite(z.setbackM) && z.setbackM > 0 ? z.setbackM : 0,
      heightM: Number.isFinite(z.heightM as number) && (z.heightM as number) > 0 ? (z.heightM as number) : null,
      // CALX401/CALX403 — l'allée voyage AVEC son geste et sa largeur SAISIE, ou pas du
      // tout : les trois clés sont indissociables (le contrat exige `axe` + `largeurM`
      // dès que `usage` vaut `circulation`), donc on n'en émet jamais une partie.
      ...champsAlleeCirculation(z),
      ...(typeof z.source === 'string' && z.source ? { source: z.source } : {}), // ACAL31
    });
  }
  return out;
}

/** Forme SÉRIALISÉE d'une zone d'exclusion — les clés du contrat, rien de plus. */
export interface ZoneSerialisee {
  id: string;
  label?: string;
  nature: ExclusionNature;
  vertices: LngLat[];
  setbackM: number;
  heightM: number | null;
  usage?: UsageZone;
  axe?: LngLat[];
  largeurM?: number;
  source?: string; // ACAL31
}

/** Relecture d'un document : tolérante aux formes bancales, ne fabrique jamais de zone. */
export function deserializeExclusionZones(json: unknown): ExclusionZone[] {
  if (!Array.isArray(json)) return [];
  const out: ExclusionZone[] = [];
  for (const raw of json) {
    const z = raw as Partial<ExclusionZone> | null;
    if (!z || typeof z.id !== 'string') continue;
    if (z.nature !== 'INTERDITE' && z.nature !== 'RESERVEE' && z.nature !== 'PREFEREE') continue;
    const verts = Array.isArray(z.vertices)
      ? z.vertices
          .filter((v): v is LngLat => Array.isArray(v) && v.length === 2 && Number.isFinite(v[0]) && Number.isFinite(v[1]))
          .map((v) => [v[0], v[1]] as LngLat)
      : [];
    if (verts.length < 3) continue;
    let zone: ExclusionZone = { id: z.id, nature: z.nature, vertices: verts, setbackM: 0 };
    zone = withZoneSetback(zone, typeof z.setbackM === 'number' ? z.setbackM : null);
    zone = withZoneHeight(zone, typeof z.heightM === 'number' ? z.heightM : null);
    zone = withZoneLabel(zone, typeof z.label === 'string' ? z.label : null);
    // CALX401/CALX403 — l'allée se relit telle qu'elle a été écrite (geste + largeur
    // SAISIE). Une allée amputée de son axe ou de sa largeur n'est plus une allée : elle
    // se relit alors comme la zone d'exclusion ordinaire qu'elle reste, jamais complétée.
    zone = { ...zone, ...champsAlleeCirculation(raw) };
    if (typeof z.source === 'string' && z.source) zone.source = z.source; // ACAL31 — relue telle quelle
    out.push(zone);
  }
  return out;
}

// ————————————————————————————————————————————————————————————————————————
// CALX403 — ALLÉE DE CIRCULATION TRACÉE DANS L'ATELIER
//
// L'atelier ne savait dessiner qu'un obstacle rectangulaire au glissé et des zones
// polygonales : aucun outil ne traçait un COULOIR par sa polyligne et sa largeur, et rien
// ne signalait un module posé en travers d'un passage. Le panneau d'allées existant
// (CAL70) ne règle que la largeur UNIFORME entre rangées — un retrait entre rangées et un
// passage de pompier ne sont pas la même pièce. Parité Aurora (« fire pathways » : les
// modules chevauchants passent en jaune, et un glissé conserve l'orientation et la largeur).
//
// ZÉRO LARGEUR INVENTÉE (D-CALX 7, CALX402) : le dépôt ne porte AUCUNE largeur de
// référence. Sans largeur saisie pour le pays du site, l'allée est OMISE et le motif NOMME
// le pays ET le réglage manquant — jamais une largeur supposée.
//
// GÉOMÉTRIE PURE : aucun Three, aucun DOM, aucune carte.
// ————————————————————————————————————————————————————————————————————————

/** Les clés d'allée d'une zone, à ÉMETTRE ou à RELIRE — les trois ensemble, ou aucune. */
function champsAlleeCirculation(
  brut: unknown,
): { usage?: UsageZone; axe?: LngLat[]; largeurM?: number } {
  const z = (brut ?? {}) as Partial<ExclusionZone>;
  if (z.usage !== USAGE_CIRCULATION) return {};
  const axe = Array.isArray(z.axe)
    ? z.axe
        .filter((p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]))
        .map((p) => [p[0], p[1]] as LngLat)
    : [];
  const largeur = z.largeurM;
  if (axe.length < 2) return {};
  if (typeof largeur !== 'number' || !Number.isFinite(largeur) || largeur <= 0) return {};
  return { usage: USAGE_CIRCULATION, axe, largeurM: largeur };
}

/**
 * CALX403 — la largeur d'allée de circulation SAISIE par la société pour un pays, lue dans
 * la section `degagements` des réglages (`allees_circulation`). C'est le JUMEAU côté écran
 * de `services/degagements.py::largeur_allee_circulation` (CALX402) : mêmes clés, même
 * règle, et surtout le même refus — pays non saisi ⇒ `largeurM: null` et un motif qui NOMME
 * le réglage manquant. AUCUN défaut n'est fabriqué ici.
 */
export function largeurAlleeDepuisReglages(
  sectionDegagements: unknown,
  pays: string | null | undefined,
): { largeurM: number | null; motif: string } {
  const code = String(pays ?? '').trim().toLowerCase();
  if (!code) return { largeurM: null, motif: motifAlleeSansLargeur(code) };
  const section = (sectionDegagements ?? {}) as Record<string, unknown>;
  const entrees = Array.isArray(section.allees_circulation) ? (section.allees_circulation as unknown[]) : [];
  for (const brut of entrees) {
    if (!brut || typeof brut !== 'object' || Array.isArray(brut)) continue;
    const e = brut as Record<string, unknown>;
    if (String(e.pays ?? '').trim().toLowerCase() !== code) continue;
    const largeur = e.largeur_m;
    if (typeof largeur !== 'number' || !Number.isFinite(largeur) || largeur <= 0) break;
    const source = String(e.source ?? '').trim();
    const reference = String(e.reference ?? '').trim();
    const citation = [source || 'source non renseignée', reference].filter(Boolean).join(', ');
    return {
      largeurM: largeur,
      motif: `Allée de circulation (${code}) : ${largeur} m (réglage de votre société — ${citation}).`,
    };
  }
  return { largeurM: null, motif: motifAlleeSansLargeur(code) };
}

/** ACAL962 — le refus d'une allée sans largeur, en mots simples (jamais la clé technique du réglage). */
function motifAlleeSansLargeur(code: string): string {
  return code
    ? `Allée non tracée : aucune largeur d’allée n’est réglée pour le pays « ${code} ». Réglez-la dans Réglages › Allées.`
    : 'Allée non tracée : le pays du site n’est pas réglé. Réglez-le dans Réglages › Site.';
}

/** Verdict d'un tracé d'allée — un refus NOMME toujours sa raison. */
export type VerdictAllee = { ok: true; zone: ExclusionZone } | { ok: false; motif: string };

/** CALX403 — la largeur saisie est-elle exploitable ? `null` = oui, sinon le motif. */
export function motifLargeurAllee(largeurM: number | null | undefined, pays?: string | null): string | null {
  if (largeurM == null || !Number.isFinite(largeurM) || largeurM <= 0) {
    return motifAlleeSansLargeur(String(pays ?? '').trim().toLowerCase());
  }
  return null;
}

/**
 * CALX403 — le COULOIR (contour fermé) d'une polyligne ÉLARGIE de sa largeur saisie : on
 * décale chaque point de la moitié de la largeur de part et d'autre, puis on referme
 * (côté gauche + côté droit parcouru à l'envers). Les extrémités ne sont PAS prolongées :
 * un couloir de 1 m de large sur 10 m de long fait 10 m², pas un mètre de plus.
 *
 * Aux coudes, le décalage suit la BISSECTRICE (longueur de l'onglet), pour que la largeur
 * MESURÉE en travers du passage reste celle qui a été saisie. Un virage en épingle verrait
 * cet onglet partir à l'infini : il est borné (convention de DESSIN, `ONGLET_MIN`), ce qui
 * ne change ni la largeur saisie ni le geste enregistré.
 */
export function couloirDepuisAxe(axe: readonly LngLat[], largeurM: number): LngLat[] | null {
  const pts = (axe ?? []).filter(
    (p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
  );
  if (pts.length < 2 || !Number.isFinite(largeurM) || largeurM <= 0) return null;
  const cosLat = Math.max(1e-6, Math.cos(pts[0][1] * ZONE_DEG2RAD));
  const versEnu = ([lng, lat]: LngLat): [number, number] => [
    (lng - pts[0][0]) * ZONE_DEG2M * cosLat,
    (lat - pts[0][1]) * ZONE_DEG2M,
  ];
  const versLngLat = ([x, y]: [number, number]): LngLat => [
    pts[0][0] + x / (ZONE_DEG2M * cosLat),
    pts[0][1] + y / ZONE_DEG2M,
  ];
  const enu = pts.map(versEnu);
  // Normale unitaire (à gauche) de chaque segment ; un segment de longueur nulle n'en a pas.
  const normales: Array<[number, number] | null> = [];
  for (let i = 0; i < enu.length - 1; i++) {
    const dx = enu[i + 1][0] - enu[i][0];
    const dy = enu[i + 1][1] - enu[i][1];
    const len = Math.hypot(dx, dy);
    normales.push(len < 1e-9 ? null : [-dy / len, dx / len]);
  }
  const valides = normales.filter((n): n is [number, number] => n != null);
  if (!valides.length) return null;
  const demi = largeurM / 2;
  const ONGLET_MIN = 0.4; // convention de dessin : borne de l'onglet en épingle
  const gauche: Array<[number, number]> = [];
  const droite: Array<[number, number]> = [];
  for (let i = 0; i < enu.length; i++) {
    const avant = i > 0 ? normales[i - 1] : null;
    const apres = i < normales.length ? normales[i] : null;
    let dep: [number, number];
    if (avant && apres) {
      const mx = avant[0] + apres[0];
      const my = avant[1] + apres[1];
      const m = Math.max(ONGLET_MIN, Math.hypot(mx, my));
      dep = [(mx * largeurM) / (m * m), (my * largeurM) / (m * m)];
    } else {
      const n = (apres ?? avant) as [number, number];
      dep = [n[0] * demi, n[1] * demi];
    }
    gauche.push([enu[i][0] + dep[0], enu[i][1] + dep[1]]);
    droite.push([enu[i][0] - dep[0], enu[i][1] - dep[1]]);
  }
  return [...gauche, ...droite.reverse()].map(versLngLat);
}

/**
 * CALX403 — construit l'allée de circulation depuis le geste tracé et la largeur SAISIE.
 * Elle est de nature INTERDITE : sa surface est retirée du posable comme n'importe quelle
 * zone interdite (`exclusionObstructionRings` la reprend sans rien changer). Refus NOMMÉ
 * quand l'axe est trop court ou la largeur non saisie — jamais une allée sans largeur.
 */
export function alleeCirculation(
  id: string,
  axe: readonly LngLat[],
  largeurM: number | null | undefined,
  pays?: string | null,
): VerdictAllee {
  const pts = (axe ?? []).filter(
    (p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
  );
  if (pts.length < 2) {
    return { ok: false, motif: 'Allée non tracée : il faut au moins deux points — un passage à un point ne mène nulle part.' };
  }
  const motif = motifLargeurAllee(largeurM, pays);
  if (motif) return { ok: false, motif };
  const vertices = couloirDepuisAxe(pts, largeurM as number);
  if (!vertices || vertices.length < 3) {
    return { ok: false, motif: 'Allée non tracée : les points saisis sont confondus, aucun couloir n’en sort.' };
  }
  return {
    ok: true,
    zone: {
      id,
      nature: 'INTERDITE',
      vertices,
      setbackM: 0,
      usage: USAGE_CIRCULATION,
      axe: pts.map((p) => [p[0], p[1]] as LngLat),
      largeurM: largeurM as number,
    },
  };
}

/** CALX403 — l'allée déplacée d'un delta lng/lat : l'axe ET le couloir suivent le même
 *  mouvement, et `largeurM` est recopiée TELLE QUELLE (le glissé ne re-dérive aucune cote,
 *  donc la largeur est conservée au millimètre). Une zone qui n'est pas une allée est
 *  renvoyée inchangée. */
export function deplacerAllee(z: ExclusionZone, dLng: number, dLat: number): ExclusionZone {
  if (z?.usage !== USAGE_CIRCULATION || !Array.isArray(z.axe)) return z;
  return {
    ...z,
    vertices: (z.vertices ?? []).map(([lng, lat]) => [lng + dLng, lat + dLat] as LngLat),
    axe: z.axe.map(([lng, lat]) => [lng + dLng, lat + dLat] as LngLat),
    largeurM: z.largeurM,
  };
}

/** CALX403 — l'aire (m²) réellement retirée par une allée : celle de son couloir. */
export function aireAlleeM2(z: ExclusionZone): number {
  const ring = exclusionZoneRing(z);
  return ring ? geodesicAreaM2(ring) : 0;
}

/** CALX403 — un module POSÉ, tel que l'atelier le connaît : son repère et son emprise au
 *  sol en mètres ENU autour de l'origine de la scène. */
export interface ModulePose {
  repere: string;
  empriseM: Array<[number, number]>;
}

/**
 * CALX403 — l'emprise au sol d'un module posé, en ENU, depuis ce que le pavage publie :
 * son centre (`cx`, `cy`), l'azimut du pavage, la largeur de rangée et la profondeur AU SOL
 * (`footprintPerPanelM2 / rowWidthM`). Mêmes vecteurs de base que le pavage
 * (`estimatorBrainV2` : `s = [sin az, cos az]` empile les rangées, `u = [-cos az, sin az]`
 * porte la rangée) : aucune cote n'est inventée, toutes sont lues sur le plan.
 */
export function empriseModuleENU(
  centre: { cx: number; cy: number },
  azimutDeg: number,
  largeurRangeeM: number,
  profondeurAuSolM: number,
): Array<[number, number]> {
  const az = azimutDeg * ZONE_DEG2RAD;
  const s: [number, number] = [Math.sin(az), Math.cos(az)];
  const u: [number, number] = [-s[1], s[0]];
  const du = largeurRangeeM / 2;
  const dv = profondeurAuSolM / 2;
  return [
    [-du, -dv],
    [du, -dv],
    [du, dv],
    [-du, dv],
  ].map(([a, b]) => [centre.cx + a * u[0] + b * s[0], centre.cy + a * u[1] + b * s[1]] as [number, number]);
}

/** Deux segments se croisent-ils ? (orientations opposées de part et d'autre). */
function segmentsSeCroisent(
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
  p4: [number, number],
): boolean {
  const d = (a: [number, number], b: [number, number], c: [number, number]) =>
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const d1 = d(p3, p4, p1);
  const d2 = d(p3, p4, p2);
  const d3 = d(p1, p2, p3);
  const d4 = d(p1, p2, p4);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}

/**
 * CALX403 — les REPÈRES des modules qui chevauchent l'allée. Un module est chevauchant si
 * un de ses coins est dans le couloir, si un sommet du couloir est dans son emprise, ou si
 * leurs bords se croisent (cas du passage étroit qui TRAVERSE une rangée : ni coin ni
 * sommet ne tombe dans l'autre, et pourtant ils se chevauchent).
 *
 * CETTE FONCTION NE SUPPRIME RIEN : elle COMPTE. Parité Aurora — un module posé en travers
 * d'un passage est signalé, jamais effacé dans le dos du dessinateur.
 */
export function modulesSurAllee(
  modules: readonly ModulePose[],
  allee: ExclusionZone,
  origine: LngLat,
): string[] {
  if (allee?.usage !== USAGE_CIRCULATION) return [];
  const ring = exclusionZoneRing(allee);
  if (!ring || ring.length < 3) return [];
  const cosLat = Math.max(1e-6, Math.cos(origine[1] * ZONE_DEG2RAD));
  const couloir = ring.map(
    ([lng, lat]) => [(lng - origine[0]) * ZONE_DEG2M * cosLat, (lat - origine[1]) * ZONE_DEG2M] as [number, number],
  );
  const touche = (emprise: Array<[number, number]>): boolean => {
    if (emprise.length < 3) return false;
    if (emprise.some((c) => pointInPolygon(c, couloir))) return true;
    if (couloir.some((c) => pointInPolygon(c, emprise))) return true;
    for (let i = 0; i < emprise.length; i++) {
      const a = emprise[i];
      const b = emprise[(i + 1) % emprise.length];
      for (let j = 0; j < couloir.length; j++) {
        if (segmentsSeCroisent(a, b, couloir[j], couloir[(j + 1) % couloir.length])) return true;
      }
    }
    return false;
  };
  return (modules ?? []).filter((m) => touche(m.empriseM ?? [])).map((m) => m.repere);
}

export { etiquettePanExistant } from './panStats'; // ACAL511 — définie à côté du tableau Site (ACAL1431), une seule étiquette

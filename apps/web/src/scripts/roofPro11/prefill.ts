/**
 * Pré-remplissage du diagnostic enrichi (handoff vers le formulaire de lead) +
 * l'aire géodésique du tracé. Extrait de roof-tool-pro11.ts (split modulaire
 * 2026-06-20) — comportement INCHANGÉ.
 *
 * GARDE-FOU PERMANENT : ce module ne poste AUCUN lead. Il n'écrit QUE dans les
 * champs du diagnostic existant (`lf-area`, `lf-orient`, `lf-kwc-est`, W110 :
 * `lf-name`/`lf-phone`/`lf-city` quand on les lui fournit + la ville géocodée
 * depuis `rp9-address`, et — pour le diagnostic « une page » de pro-11 — les
 * selects OBLIGATOIRES `billRange`/`roofType` pré-remplis depuis le simulateur)
 * et défile vers `#simulateur` ; toute la plomberie (seuil, consentement,
 * webhook, CAPI) reste celle du formulaire existant. Aucune requête réseau (ni
 * route lead, ni route de simulation) n'est émise ici.
 */
import { DEG2RAD, WGS84_RADIUS } from './constants';
import { $ } from './dom';
import { type Ctx } from './context';
import { type AreaRecord, type CardData, type LeadPayload, type ObstacleType, type ObstacleProvenance } from './types';
import { type LngLat } from '../../lib/roof';
import { BILL_RANGES } from '../../lib/billRange';
import { PANEL2_WATT } from '../../lib/estimatorBrainV2';
import { ROOF_TYPES } from '../../lib/lead';
import { type Measurement, type MeasureKind, isMeasureValid } from './mesureUi';
import { deduceEdgeTypes, fusionnerAretesSaisies, type SerializedEdge, type EdgeDeductionZone } from './edges';
import { type EnvironmentObject } from './environment';
import { serializeExclusionZones, deserializeExclusionZones, type ExclusionZone } from './zones';
import { resolveSetbacks, type PerimeterSetbacks } from '../../lib/roofPro2';
import { sortedHorizonPoints, horizonMaxHeightDeg, type HorizonProfile, type HorizonSource } from '../../lib/horizonEngine';
import { type CoucheElectrique, type DocumentElectrique } from './electrique3d';
import { numeroterDocument } from './numerotation'; // CALX111

import { emettreBatiments, type Batiment } from './batiment'; // CALX100

/** W110 — coordonnées client OPTIONNELLES à reporter dans le diagnostic (handoff, jamais
 *  un POST). Toutes optionnelles : un champ absent/vide n'écrase rien. */
export interface LeadContact {
  name?: string;
  phone?: string;
  city?: string;
}

export interface Prefill {
  geodesicArea: () => number;
  prefillLead: (d: CardData, contact?: LeadContact) => void;
}

// Tranche de facture mensuelle (MAD) ↔ id `BILL_RANGES`. Le simulateur saisit un
// montant LIBRE en MAD/mois ; on le range dans le bon bucket pour pré-remplir le
// select obligatoire `billRange`. Bornes alignées 1:1 sur les libellés de
// `lib/billRange.ts` (lt800 · 800-1000 · 1000-1500 · 1500-3000 · 3000-5000 ·
// 5000-10000 · gt10000). Renvoie '' si le montant n'est pas un nombre fini > 0.
export function billRangeIdForAmount(mad: number): string {
  if (!Number.isFinite(mad) || mad <= 0) return '';
  if (mad < 800) return 'lt800';
  if (mad < 1000) return '800-1000';
  if (mad < 1500) return '1000-1500';
  if (mad < 3000) return '1500-3000';
  if (mad < 5000) return '3000-5000';
  if (mad < 10000) return '5000-10000';
  return 'gt10000';
}

// Type de toit du builder (flat/pitched) ↔ option `ROOF_TYPES` du formulaire.
// Toit plat → 'toit_plat' ; toit en pente → 'villa' (le plus courant en pente).
// Les deux ids existent dans `ROOF_TYPES` (lib/lead.ts) ; repli 'autre' sinon.
export function roofTypeIdForBuilder(t: 'flat' | 'pitched'): string {
  const id = t === 'flat' ? 'toit_plat' : 'villa';
  return ROOF_TYPES.some((r) => r.id === id) ? id : 'autre';
}

export function createPrefill(ctx: Ctx): Prefill {
  function geodesicArea(): number {
    // surface tracée (m²) pour pré-remplir le champ « surface toit »
    const ring = ctx.vertices;
    if (ring.length < 3) return 0;
    let total = 0;
    for (let i = 0; i < ring.length; i++) {
      const [lng1, lat1] = ring[i];
      const [lng2, lat2] = ring[(i + 1) % ring.length];
      total += (lng2 - lng1) * DEG2RAD * (2 + Math.sin(lat1 * DEG2RAD) + Math.sin(lat2 * DEG2RAD));
    }
    return Math.abs((total * WGS84_RADIUS * WGS84_RADIUS) / 2);
  }

  /** W85 — Orientation `enrichment.ORIENTATIONS` déduite de la config GAGNANTE,
   *  pour que le diagnostic reçoive la VRAIE face (et non « sud » en dur). Toit
   *  plat : la famille sud ET la famille est-ouest se rapportent au sud (la liste
   *  d'orientations n'a pas d'« est-ouest »). Toit en pente : on mappe l'azimut de
   *  face réel (180→sud, 135→sud-est, 225→sud-ouest, 90→est, 270→ouest), au plus
   *  proche, avec repli « sud ». Lecture PURE de l'état `ctx` — n'écrit rien dans
   *  le formulaire, ne poste rien. */
  function leadOrientationId(): string {
    if (ctx.roofType === 'pitched') {
      const az = ((ctx.facingAzimuthDeg % 360) + 360) % 360;
      const targets: { az: number; id: string }[] = [
        { az: 180, id: 'sud' },
        { az: 135, id: 'sud-est' },
        { az: 225, id: 'sud-ouest' },
        { az: 90, id: 'est' },
        { az: 270, id: 'ouest' },
      ];
      let best = 'sud';
      let bestDiff = Infinity;
      for (const t of targets) {
        const diff = Math.abs(((az - t.az + 540) % 360) - 180);
        if (diff < bestDiff) {
          bestDiff = diff;
          best = t.id;
        }
      }
      return best;
    }
    // Toit plat : la famille sud ET la famille est-ouest se rapportent au sud.
    return 'sud';
  }

  function prefillLead(d: CardData, contact?: LeadContact) {
    // Pré-remplit le diagnostic enrichi — RÉUTILISE le même formulaire et toute sa
    // plomberie (seuil 1 000 MAD, consentement, webhook, CAPI) : on n'écrit que
    // dans ses champs, on ne poste AUCUN lead ici.
    const area = $<HTMLInputElement>('lf-area');
    const orient = $<HTMLSelectElement>('lf-orient');
    const kwc = $<HTMLInputElement>('lf-kwc-est');
    if (area) {
      // Correction « cos de la pente » : sur un toit incliné, le tracé satellite est la
      // projection HORIZONTALE — il paraît plus petit. La VRAIE surface de toiture =
      // projetée / cos(pente). Toit plat : inchangé (aucune correction). Garde-fou : si
      // cos(pente) ≤ 0 ou non fini (pente aberrante), on retombe sur la projetée.
      const projected = geodesicArea();
      let surface = projected;
      if (ctx.roofType === 'pitched') {
        const cosPitch = Math.cos(ctx.pitchDeg * DEG2RAD);
        if (Number.isFinite(cosPitch) && cosPitch > 0) surface = projected / cosPitch;
      }
      area.value = String(Math.round(surface));
    }
    if (orient) orient.value = leadOrientationId(); // W85 : face réelle de la config gagnante
    if (kwc) kwc.value = String(Math.round(d.kwc * 100) / 100);

    // W110 — flux en une page : reporte Nom / Téléphone / Ville quand fournis, et — à défaut
    // de ville saisie — la VILLE GÉOCODÉE depuis #rp9-address (handoff, jamais un POST). On
    // n'écrase un champ que si on a une vraie valeur (champ vide → on n'efface rien).
    const name = $<HTMLInputElement>('lf-name');
    const phone = $<HTMLInputElement>('lf-phone');
    const city = $<HTMLInputElement>('lf-city');
    const trimmedName = contact?.name?.trim();
    const trimmedPhone = contact?.phone?.trim();
    const trimmedCity = contact?.city?.trim();
    const geocodedAddress = ($<HTMLInputElement>('rp9-address')?.value ?? '').trim();
    if (name && trimmedName) name.value = trimmedName;
    if (phone && trimmedPhone) phone.value = trimmedPhone;
    const cityValue = trimmedCity || geocodedAddress;
    if (city && cityValue && !city.value.trim()) city.value = cityValue;

    // Diagnostic « une page » (pro-11) : le visiteur ne tape que Nom/Téléphone/Adresse.
    // On pré-remplit les selects OBLIGATOIRES (billRange, roofType) depuis le simulateur,
    // pour que la soumission passe sans saisie supplémentaire. On n'écrit que des valeurs
    // sûres (id connu) — sinon le visiteur complète lui-même.
    const billSelect = $<HTMLSelectElement>('lf-bill');
    const billInput = document.getElementById('rp9-bill') as HTMLInputElement | null;
    if (billSelect && billInput) {
      const mad = Number(String(billInput.value).replace(/\s/g, '').replace(',', '.'));
      const id = billRangeIdForAmount(mad);
      if (id && BILL_RANGES.some((r) => r.id === id)) billSelect.value = id;
    }
    const roofSelect = $<HTMLSelectElement>('lf-roof');
    if (roofSelect) roofSelect.value = roofTypeIdForBuilder(ctx.roofType);

    const details = (area?.closest('details') as HTMLDetailsElement | null) ?? null;
    if (details) details.open = true;
    document.getElementById('simulateur')?.scrollIntoView({ behavior: ctx.opts.reducedMotion ? 'auto' : 'smooth', block: 'start' });
  }

  return { geodesicArea, prefillLead };
}

// ═══════════ W113 — SÉRIALISATION / HYDRATATION DU LAYOUT (linchpin) ═══════════
// Le layout sérialisé est un JSON PUR et stable : la liste des zones (géométrie +
// dimensionnement par zone) + un repère léger (pin/outline) au niveau racine, pour
// que la capture client (pin seul) et l'étude Meriem (contour complet) parlent le
// MÊME format. Les champs DÉRIVÉS (résultat optimiseur, plan de rendu 3D, caches
// PVGIS) sont VOLONTAIREMENT exclus : ils sont recalculés au boot par l'optimiseur,
// jamais persistés. serializeLayout → deserializeLayout est une IDENTITÉ pour ces
// champs (garde de test).

/** WJ24 — géométrie PLEINE par pan (plane) d'une zone, pour que le devis/PDF ERP reflète
 *  le VRAI design multi-plan. Champ ADDITIF (optionnel) : n'existe que si la zone a un plan
 *  de rendu (renderPlan) ; jamais retiré ni renommé (le backend lit les champs existants). */
export interface SerializedZoneGeometry {
  /** Azimut de FACE du pan (°, 0=N, 90=E, 180=S, 270=O). */
  azimuthDeg: number;
  /** Inclinaison du pan (°). */
  tiltDeg: number;
  /** Famille de config (south / eastwest). */
  family: 'south' | 'eastwest';
  /** Pose affleurante (toit en pente) ? */
  flush: boolean;
  /** Puissance crête totale POSÉE (kWc) du plan. */
  kwc: number;
  /** Nombre de panneaux POSÉS. */
  count: number;
  /** Origine ENU (lng/lat) du repère des centres de panneaux. */
  origin: LngLat;
  /** Centres ENU (m) + face de CHAQUE panneau posé (repère `origin`). */
  panels: Array<{ cx: number; cy: number; face?: 'E' | 'W' }>;
  /**
   * PV30 — MODE de placement de ces panneaux. ADDITIF et OMIS par défaut : un pan calepiné
   * sur les emplacements validés sérialise exactement comme avant (octet pour octet), et
   * tout lecteur existant continue de ne lire que `panels`. `'free'` signale un PLACEMENT
   * LIBRE — les centres sont alors des positions choisies à la main, à recharger VERBATIM
   * (les re-snapper sur la lattice détruirait le gain de place qu'ils enregistrent).
   */
  mode?: 'free';
  /**
   * CAL248 — ACCÈS SOLAIRE PAR MODULE, persisté avec le document. `pointSolarAccess` /
   * `cellsSolarAccess` vivaient côté client et ne sortaient jamais de l'écran : aucune
   * tâche backend ne pouvait les consommer. Champ ADDITIF et OPTIONNEL — absent =
   * comportement d'aujourd'hui, JAMAIS une valeur par défaut (un module sans accès
   * solaire calculé n'est pas un module à 100 %). Forme figée par le schéma v2
   * (`roof_layout_v2.schema.json`, `$defs/solarAccess`).
   */
  solarAccess?: SerializedSolarAccess;
}

/**
 * CAL248 — accès solaire par module tel qu'il voyage DANS le document. Forme exactement
 * celle du contrat v2 (`$defs/solarAccess`) : `values` aligné sur `panels`, la méthode
 * nommée, les hypothèses en objet libre, et la DATE de calcul (sans elle on ne sait pas
 * si ces valeurs précèdent la dernière édition du toit).
 */
export interface SerializedSolarAccess {
  /** Un facteur (0–1) par module, MÊME ORDRE et MÊME LONGUEUR que `panels`. `null` =
   *  module non calculé — jamais 1, qui se lirait « aucun ombrage mesuré ». */
  values: Array<number | null>;
  method: string;
  assumptions: Record<string, unknown>;
  /** ISO 8601. */
  computedAt: string;
}

/**
 * CAL248 — normalise un accès solaire avant écriture. Il n'est écrit QUE s'il est
 * exploitable : autant de valeurs que de modules posés (sinon les valeurs seraient
 * décalées d'un module à l'autre au rechargement), méthode non vide, date lisible.
 * Toute valeur hors [0;1] ou non finie devient `null` — non calculée, jamais corrigée
 * en silence. Renvoie `null` si rien n'est écrivable.
 */
export function serializeSolarAccess(
  raw: SerializedSolarAccess | null | undefined,
  panelCount: number,
): SerializedSolarAccess | null {
  if (!raw || !Array.isArray(raw.values) || raw.values.length !== panelCount || panelCount <= 0) return null;
  if (typeof raw.method !== 'string' || !raw.method.trim()) return null;
  const values = raw.values.map((v) =>
    typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1 ? v : null,
  );
  if (values.every((v) => v === null)) return null; // rien de calculé : on n'écrit rien
  const computedAt =
    typeof raw.computedAt === 'string' && raw.computedAt ? raw.computedAt : new Date().toISOString();
  const assumptions =
    raw.assumptions && typeof raw.assumptions === 'object' && !Array.isArray(raw.assumptions)
      ? { ...raw.assumptions }
      : {};
  return { values, method: raw.method, assumptions, computedAt };
}

/** CAL248 — relit l'accès solaire d'une géométrie de zone sérialisée. Absent, mal formé
 *  ou décalé ⇒ `null` : un document sans accès solaire se relit SANS erreur, et aucune
 *  valeur n'est reconstituée. */
export function deserializeSolarAccess(geometry: unknown, panelCount: number): SerializedSolarAccess | null {
  const raw = (geometry as { solarAccess?: SerializedSolarAccess } | null | undefined)?.solarAccess;
  return serializeSolarAccess(raw, panelCount);
}

/** Une zone sérialisée (sous-ensemble plat et JSON-sûr d'AreaRecord). */
export interface SerializedZone {
  id: string;
  label: string;
  /** Contour lng/lat [[lng,lat],…]. */
  vertices: LngLat[];
  /** Obstacles (zones d'exclusion) — objets plats {id,centerLng,centerLat,lengthM,widthM}.
   *  PV61 — `type` (optionnel) porte le dégagement de l'obstacle ; absent = comportement
   *  historique (dégagement uniforme). Jamais émis pour un obstacle sans type. CAL66 —
   *  `heightM` (optionnel, SAISI) : absent = obstacle plan, aucune ombre. CAL72 —
   *  `provenance` (optionnel) : absent = comportement historique (aucun blocage). */
  obstacles: Array<{
    id: string;
    centerLng: number;
    centerLat: number;
    lengthM: number;
    widthM: number;
    type?: ObstacleType;
    heightM?: number;
    provenance?: ObstacleProvenance;
  }>;
  /** F2 — OPTIONNELS : `serializeLayout` les écrit toujours, mais une zone posée
   *  par le SERVEUR depuis le tracé du client les OMET délibérément (personne n'a
   *  mesuré ce toit, et un champ écrit ici descend jusqu'à l'annexe « paramètres du
   *  site » de la proposition client). Les DEUX lecteurs — `deserializeLayout` (ERP)
   *  et `buildViewerFullPlan` (visionneuse publique) — appliquent alors les MÊMES
   *  valeurs de zone vierge que `newAreaRecord()`. */
  roofType?: 'flat' | 'pitched';
  pitchDeg?: number;
  facingAzimuthDeg?: number;
  facingManual: boolean;
  neededPanels: number;
  neededAuto: boolean;
  /** WJ24 — géométrie pleine par pan (optionnel, additif). Présent seulement si un plan
   *  de rendu existe pour la zone. Le round-trip deserializeLayout l'ignore (dérivé,
   *  recalculé au boot) — il sert uniquement à l'export ERP (devis/PDF multi-plan). */
  geometry?: SerializedZoneGeometry;
  /** CAL59 — bâtiment auquel ce pan appartient. Optionnel et additif : absent = bâtiment
   *  unique, comportement historique. */
  buildingId?: string;
  /** CAL57 — type d'arête par segment de contour (déduit, corrigible à la main). Optionnel
   *  et additif : absent = aucune arête typée, comportement historique. */
  edges?: SerializedEdge[];
}

// ═══════════ PV13 — SÉRIALISATION v2 (additive, jamais destructive) ═══════════
// La v2 AJOUTE au JSON de quoi le lire SANS rejouer l'optimiseur : le résultat global
// (panneaux/kWc/kWh/économies), le scénario commercial, la puissance panneau, la
// batterie et l'origine (devis ou lead). TOUS les champs v1 restent présents, au même
// endroit, avec la même valeur — un lecteur v1 continue de fonctionner tel quel, et
// `deserializeLayout` IGNORE purement et simplement les ajouts (champs dérivés).

/** Scénario commercial associé au design. */
export type LayoutScenario = 'reseau' | 'avec_batterie' | 'hybride';

/** Batterie retenue (forme minimale, tout optionnel). `null` = aucune batterie. */
export interface SerializedBattery {
  /** Capacité utile (kWh). */
  kwh?: number;
  /** Nombre de modules. */
  count?: number;
  /** Modèle/référence, tel qu'affiché. */
  model?: string;
}

/** Résultat GLOBAL du design, cohérent avec les géométries de zone exportées. */
export interface SerializedResult {
  /** Somme des panneaux POSÉS des géométries exportées. */
  panels: number;
  /** Somme des kWc des géométries exportées. */
  kwc: number;
  /** Production annuelle (kWh) — somme des résultats de zone déjà calculés à l'écran. */
  annualKwh: number;
  /** Économies annuelles (MAD) telles qu'AFFICHÉES, ou null si l'appelant ne les fournit pas. */
  savings: number | null;
}

/** Métadonnées passées par la page (jamais devinées ici). */
export interface SerializeMeta {
  scenario?: LayoutScenario;
  /** Puissance unitaire du panneau (W). Défaut : le panneau du moteur (720 W). */
  panelWatt?: number;
  battery?: SerializedBattery | null;
  /** D'où vient ce design : un devis existant, ou un lead. */
  source?: 'devis' | 'lead';
  devisId?: string | number | null;
  /** Économies annuelles (MAD) affichées. Ni recalculées ni inventées ici. */
  savingsMad?: number | null;
  /**
   * CAL248 — accès solaire par module, PAR ZONE (clé = id de zone). Fourni par
   * l'appelant (l'atelier le tient via `shadingUi.solarAccess()`) : `prefill.ts` reste
   * pur et ne calcule aucun ombrage. Une zone absente de cette table sort simplement
   * SANS accès solaire — jamais avec des valeurs par défaut.
   */
  solarAccessByZone?: Record<string, SerializedSolarAccess | null | undefined>;
  /** CAL76 — les quatre retraits de rive RÉGLÉS dans l'atelier (PV63 + le joint CAL76),
   *  à écrire à la racine du document. Fourni par l'appelant (l'outil les tient dans
   *  `setbacks`, cf. roof-tool-pro11.ts) : `prefill.ts` reste pur et n'invente rien. */
  setbacksM?: PerimeterSetbacks;
  /** CAL93 — le profil d'horizon lointain RÉELLEMENT en vigueur (`ctx.horizonProfile`,
   *  tenu par `shadingUi.ts`). Fourni par l'appelant, comme `setbacksM` ci-dessus. */
  horizonProfile?: HorizonProfile;
  /**
   * CALX22x câblage — la couche électrique de l'atelier (CALX219-221/223,
   * `electrique3d.ts`), si l'appelant en tient une (`onApiReady`'s `electrique`).
   * Fournie par l'appelant, comme `setbacksM`/`horizonProfile` ci-dessus :
   * `prefill.ts` reste pur et ne recalcule ni ne recopie jamais la logique
   * d'écriture — elle reste ENTIÈREMENT déléguée à `couche.ecrireDansDocument`,
   * la seule source de vérité pour la forme de `electrical`. Absente ⇒ comportement
   * historique, aucune clé `electrical` dans le document sérialisé.
   */
  coucheElectrique?: Pick<CoucheElectrique, 'ecrireDansDocument'> | null;
}

// ═══════════ PV71 — MATRICE D'OMBRAGE 12 × 24 (sérialisation) ═══════════
// `ctx.shadeFactors` est une matrice 12 mois × 24 heures de facteurs de dérate (0–1,
// 1 = aucun ombrage), calculée par le tracé d'ombres (shadingUi → hourlyShadeFactors).
// Elle vit sur le ctx GLOBALEMENT (pas par zone) — le layout la porte donc à la RACINE.
// Sans elle, rouvrir un dossier perdait tout le travail d'ombrage voisin et la production
// remontait artificiellement.

/** Mois et heures de la matrice — la taille est FIXE, donc la charge utile est bornée. */
export const SHADING_MONTHS = 12;
export const SHADING_HOURS = 24;
/** Décimales conservées par facteur : 3 → ±0,1 % de dérate, ~6 caractères par valeur. */
const SHADING_DECIMALS = 3;

/**
 * PV71 — normalise une matrice d'ombrage pour la sérialisation : exactement 12 × 24
 * facteurs, chacun borné à [0, 1] et arrondi à 3 décimales (taille bornée, ~1,5 ko).
 * Toute matrice de mauvaise forme (mois manquant, heure en trop, valeur non finie) est
 * REFUSÉE en bloc → `null` : mieux vaut aucune ombre qu'une matrice à moitié fausse.
 */
export function serializeShading(factors: readonly (readonly number[])[] | null | undefined): number[][] | null {
  if (!Array.isArray(factors) || factors.length !== SHADING_MONTHS) return null;
  const out: number[][] = [];
  const round = 10 ** SHADING_DECIMALS;
  for (const row of factors) {
    if (!Array.isArray(row) || row.length !== SHADING_HOURS) return null;
    const clean: number[] = [];
    for (const v of row) {
      if (typeof v !== 'number' || !Number.isFinite(v)) return null;
      clean.push(Math.round(Math.max(0, Math.min(1, v)) * round) / round);
    }
    out.push(clean);
  }
  return out;
}

/**
 * PV71 — relit une matrice d'ombrage sérialisée. Mêmes garde-fous que l'écriture (forme
 * exacte, valeurs bornées) : un JSON douteux rend `null` et l'outil repart sans ombrage
 * plutôt qu'avec un dérate inventé. Renvoie une matrice NEUVE (aucun alias sur le JSON).
 */
export function deserializeShading(json: unknown): number[][] | null {
  const raw = (json as { shading12x24?: unknown } | null | undefined)?.shading12x24 ?? json;
  return serializeShading(raw as readonly (readonly number[])[] | null | undefined);
}

// ═══════════ CAL102 — MESURES (sérialisation) ═══════════
// Mêmes garanties que `shading12x24` : un tableau de MAUVAISE forme est REFUSÉ EN BLOC
// (mieux vaut aucune mesure au rechargement qu'une mesure à moitié fausse) — mais ici
// chaque ENTRÉE est validée INDIVIDUELLEMENT (`isMeasureValid`), les entrées valides d'un
// tableau par ailleurs correct sont donc conservées ; seule une entrée invalide (genre
// inconnu, points manquants) est ÉCARTÉE, jamais silencieusement corrigée.
const MEASURE_KINDS: readonly MeasureKind[] = ['distance', 'area', 'angle'];

/** Normalise la liste de mesures pour la sérialisation : chaque mesure doit porter un id
 *  non vide, un genre reconnu et des points géométriquement valides pour ce genre. */
export function serializeMeasurements(list: readonly Measurement[] | null | undefined): Measurement[] {
  if (!Array.isArray(list)) return [];
  const out: Measurement[] = [];
  for (const m of list) {
    if (!m || typeof m.id !== 'string' || !m.id) continue;
    if (!MEASURE_KINDS.includes(m.kind)) continue;
    if (!Array.isArray(m.points) || !isMeasureValid(m)) continue;
    const points = m.points.filter(
      (p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
    );
    if (points.length !== m.points.length || !isMeasureValid({ kind: m.kind, points })) continue;
    out.push({ id: m.id, kind: m.kind, points: points.map((p) => [p[0], p[1]] as LngLat), ...(m.label ? { label: m.label } : {}) });
  }
  return out;
}

/** Relit une liste de mesures sérialisée — mêmes garde-fous que l'écriture. Accepte soit
 *  le layout complet (lit `.measurements`), soit déjà le tableau brut. */
export function deserializeMeasurements(json: unknown): Measurement[] {
  const raw = (json as { measurements?: unknown } | null | undefined)?.measurements ?? json;
  return serializeMeasurements(raw as readonly Measurement[] | null | undefined);
}

// ═══════════ CAL67 — ENVIRONNEMENT (arbres/bâtiments voisins, sérialisation) ═══════════
// Même garantie que `measurements` : une entrée géométriquement invalide (id vide, genre
// inconnu) est ÉCARTÉE individuellement — jamais silencieusement corrigée ni inventée.
const ENV_KINDS = ['arbre', 'batiment'] as const;

/** Normalise la liste d'objets d'environnement pour la sérialisation. */
export function serializeEnvironment(list: readonly EnvironmentObject[] | null | undefined): EnvironmentObject[] {
  if (!Array.isArray(list)) return [];
  const out: EnvironmentObject[] = [];
  for (const o of list) {
    if (!o || typeof o.id !== 'string' || !o.id) continue;
    if (!(ENV_KINDS as readonly string[]).includes(o.kind)) continue;
    if (!Number.isFinite(o.centerLng) || !Number.isFinite(o.centerLat)) continue;
    const clean: EnvironmentObject = { id: o.id, kind: o.kind, centerLng: o.centerLng, centerLat: o.centerLat };
    if (o.label) clean.label = o.label;
    if (typeof o.heightM === 'number' && Number.isFinite(o.heightM) && o.heightM > 0) clean.heightM = o.heightM;
    if (typeof o.crownDiameterM === 'number' && Number.isFinite(o.crownDiameterM) && o.crownDiameterM > 0) clean.crownDiameterM = o.crownDiameterM;
    if (typeof o.evergreen === 'boolean') clean.evergreen = o.evergreen;
    if (Array.isArray(o.footprint) && o.footprint.length >= 3) clean.footprint = o.footprint.map((p) => [p[0], p[1]] as LngLat);
    if (typeof o.lengthM === 'number' && Number.isFinite(o.lengthM) && o.lengthM > 0) clean.lengthM = o.lengthM;
    if (typeof o.widthM === 'number' && Number.isFinite(o.widthM) && o.widthM > 0) clean.widthM = o.widthM;
    out.push(clean);
  }
  return out;
}

/** Relit une liste d'environnement sérialisée — mêmes garde-fous que l'écriture. Accepte
 *  soit le layout complet (lit `.environment`), soit déjà le tableau brut. */
export function deserializeEnvironment(json: unknown): EnvironmentObject[] {
  const raw = (json as { environment?: unknown } | null | undefined)?.environment ?? json;
  return serializeEnvironment(raw as readonly EnvironmentObject[] | null | undefined);
}

/** Layout complet sérialisé : version + zones + repère léger (pin/outline). */
export interface SerializedLayout {
  version: 1 | 2;
  /** Pin {lat,lng} (le centroïde du contour, ou le repère client posé), ou null. */
  pin: { lat: number; lng: number } | null;
  /** Contour de la zone active en [[lat,lng],…] (vide si pas de tracé fermé). */
  outline: Array<[number, number]>;
  /** Consommation annuelle (kWh) issue de la facture, si connue. */
  billKwh: number | null;
  zones: SerializedZone[];
  /** Id de la zone active au moment de la sérialisation. */
  activeAreaId: string;
  // — PV13, ajouts v2 (tous DÉRIVÉS ou fournis ; `deserializeLayout` les ignore) —
  /** Résultat global cohérent avec les géométries exportées. */
  result?: SerializedResult;
  /** Scénario commercial (défaut `reseau`). */
  scenario?: LayoutScenario;
  /** Puissance unitaire du panneau (W). */
  panelWatt?: number;
  /** Batterie retenue, ou null. */
  battery?: SerializedBattery | null;
  /** Origine du design (défaut `lead`). */
  source?: 'devis' | 'lead';
  /** Identifiant du devis d'origine, ou null. */
  devisId?: string | number | null;
  /** PV71 — matrice d'ombrage 12 mois × 24 heures (facteurs 0–1), ou null si aucune ombre
   *  n'a été tracée. Taille FIXE, donc charge utile bornée. */
  shading12x24?: number[][] | null;
  /** CAL102 — mesures posées (distance/surface/angle), annotations du calepinage. Omis ou
   *  vide = aucune mesure (comportement historique, byte pour byte). */
  measurements?: Measurement[];
  /** CAL67 — objets d'environnement (arbres/bâtiments voisins) posés HORS contour. Omis
   *  ou vide = aucun objet (comportement historique, byte pour byte). */
  environment?: EnvironmentObject[];
  /** CAL68/CAL69 — zones INTERDITE/RESERVEE/PREFEREE tracées dans l'atelier. Le nom du
   *  tableau est `exclusionZones` (CAL232 : `zones` est PRIS par les pans depuis la v1).
   *  Omis ou vide = aucune zone (comportement historique, byte pour byte). */
  exclusionZones?: ReturnType<typeof serializeExclusionZones>;
  /** CAL76 — les QUATRE retraits de rive (PV63 latéral/extrémité/acrotère + le joint
   *  ajouté par CAL76) tels que RÉGLÉS dans l'atelier au moment de l'export. Champ RACINE
   *  (un seul jeu de retraits pour tout le document, pas par zone). Omis ⇒ un lecteur
   *  reprend `uniformSetbacks()` (comportement historique, byte pour byte) — voir
   *  `deserializeSetbacksFromLayout`. Forme figée par `roof_layout_v2.schema.json`
   *  (`$defs/perimeterSetbacks`). */
  setbacksM?: PerimeterSetbacks;
  /** CAL93 — le profil d'horizon lointain (CAL92 PVGIS, ou saisi) RÉELLEMENT en vigueur au
   *  moment de l'export. Champ RACINE (une seule valeur pour tout le document). Omis ⇒
   *  aucun horizon lointain modélisé — comportement historique, byte pour byte. Forme
   *  figée par `roof_layout_v2.schema.json` (`$defs/horizonProfile`). */
  horizonProfile?: HorizonProfile;
  /** CALX119 — l'instant du soleil de SCÈNE (jour + heure) RÉELLEMENT affiché au moment de
   *  l'export (contrat CALX88, `roof_layout_v2.schema.json` `$defs/scene`). Aucun calcul
   *  n'en dépend (un point de vue, pas une donnée d'ingénierie). Omis seulement si
   *  `ctx.sunDay`/`ctx.sunHour` ne sont pas finis (ne devrait pas arriver) — sinon TOUJOURS
   *  écrit, pour que rouvrir le document restaure l'instant réellement vu (sinon chaque
   *  rechargement retombe au solstice d'hiver/midi, l'incident que CALX119 corrige). */
  scene?: ScenePoint;
  /**
   * CALX22x câblage — la couche électrique (organes + cheminements), écrite par
   * `couche.ecrireDansDocument` (voir `meta.coucheElectrique` ci-dessous) quand
   * l'appelant en tient une ET qu'elle porte au moins un organe ou un cheminement.
   * Omis sinon (aucune couche fournie, ou couche vide) — comportement historique,
   * byte pour byte. Forme figée par `electrique3d.ts` (`DocumentElectrique`) /
   * `roof_layout_v2.schema.json` (`electrical.equipements[]` / `electrical.cheminements[]`).
   */
  electrical?: DocumentElectrique;
  /**
   * CALX84/CALX100 — les BÂTIMENTS du site (hauteur SAISIE + sa provenance, étages,
   * hauteur d'étage, relevé d'acrotère), ceux que `zones[].buildingId` (CAL59) désigne.
   * Clé RACINE, écrite par `batiment.ts` (`emettreBatiments`). Omise tant qu'aucun
   * bâtiment n'apprend rien au document — comportement historique, byte pour byte.
   * Forme figée par `roof_layout_v2.schema.json` (`$defs/building`).
   */
  buildings?: Batiment[];
}

/** Centroïde {lat,lng} d'un contour lng/lat, ou null si < 1 sommet. */
function centroidOf(vertices: LngLat[]): { lat: number; lng: number } | null {
  if (vertices.length < 1) return null;
  let lng = 0;
  let lat = 0;
  for (const [x, y] of vertices) {
    lng += x;
    lat += y;
  }
  return { lng: lng / vertices.length, lat: lat / vertices.length };
}

/**
 * Sérialise l'état du builder en un JSON PUR (zones + repère léger). Lit `ctx`
 * (les zones vivent dans ctx.areas + l'état d'édition de la zone active) sans
 * écrire nulle part. `billKwh` est optionnel (passé par l'appelant — l'outil ne
 * connaît pas la conversion facture→kWh ici).
 */
export function serializeLayout(ctx: Ctx, billKwh: number | null = null, meta?: SerializeMeta): SerializedLayout {
  // On part des zones figées (ctx.areas) et on superpose l'état d'édition VIVANT de
  // la zone active (vertices/obstacles/roofType… vivent sur ctx, pas encore re-figés).
  const zones: SerializedZone[] = ctx.areas.map((a) => {
    const isActive = a.id === ctx.activeAreaId;
    const vertices = isActive ? ctx.vertices : a.vertices;
    const obstacles = isActive ? ctx.obstacles : a.obstacles;
    const zone: SerializedZone = {
      id: a.id,
      label: a.label,
      vertices: vertices.map(([lng, lat]) => [lng, lat] as LngLat),
      obstacles: obstacles.map((o) => ({
        id: o.id,
        centerLng: o.centerLng,
        centerLat: o.centerLat,
        lengthM: o.lengthM,
        widthM: o.widthM,
        ...(o.type ? { type: o.type } : {}), // PV61 — additif, jamais émis si absent
        ...(o.heightM != null ? { heightM: o.heightM } : {}), // CAL66 — additif
        ...(o.provenance ? { provenance: o.provenance } : {}), // CAL72 — additif
      })),
      roofType: isActive ? ctx.roofType : a.roofType,
      pitchDeg: isActive ? ctx.pitchDeg : a.pitchDeg,
      facingAzimuthDeg: isActive ? ctx.facingAzimuthDeg : a.facingAzimuthDeg,
      facingManual: isActive ? ctx.facingManual : a.facingManual ?? false,
      neededPanels: isActive ? ctx.neededPanels : a.neededPanels,
      neededAuto: isActive ? ctx.neededAuto : a.neededAuto,
      ...(a.buildingId ? { buildingId: a.buildingId } : {}), // CAL59 — additif
    };
    // WJ24 — géométrie pleine par pan (additif) : depuis le plan de rendu figé de la zone
    // (a.renderPlan) ou, pour la zone active, le plan gagnant vivant (ctx.layoutPlan). Les
    // panneaux POSÉS = les `count` premiers du pavage (l'occupation personnalisée reste un
    // sur-ensemble de la lattice ; on exporte le design du gagnant). Absent si pas de plan.
    const rp = a.renderPlan;
    const g = rp
      ? { pack: rp.pack, grid: rp.grid, tiltDeg: rp.tiltDeg, family: rp.family, flush: rp.flush, count: rp.count }
      : isActive && ctx.layoutPlan
        ? {
            pack: ctx.layoutPlan.pack,
            grid: ctx.layoutPlan.grid,
            tiltDeg: ctx.layoutPlan.tiltDeg,
            family: ctx.layoutPlan.family,
            flush: ctx.layoutPlan.flush,
            count: ctx.layoutOptimalCount,
          }
        : null;
    if (g && g.grid.panels.length) {
      // PV27 — les panneaux exportés sont les cellules RÉELLEMENT OCCUPÉES, pas les
      // `count` premières du pavage. L'ancien `slice(0, count)` était un mensonge dès que
      // la disposition avait été éditée à la main : retirer le panneau nº12 et en garder
      // un nº47 exportait quand même « les 46 premiers », donc l'édition manuelle était
      // silencieusement effacée à l'export (puis au ré-import). La liste occupée n'existe
      // que pour la zone ACTIVE (c'est la seule en cours d'édition) ; une zone figée garde
      // le comportement historique (les `count` premières du pavage).
      // PV30 — PLACEMENT LIBRE de la zone active : les panneaux ne sont plus des cellules
      // de la lattice mais des positions continues choisies à la main. Elles sont déjà des
      // centres ENU dans le repère `origin` — donc AUCUN nouveau format de coordonnées :
      // on remplace simplement la liste, et `mode: 'free'` dit au rechargement de ne pas
      // les re-snapper. Hors placement libre, tout ce bloc est ignoré et la sérialisation
      // reste identique au byte près.
      const freePosed = isActive && ctx.freeMode && ctx.freeState ? ctx.freeState.panels : null;
      const live =
        isActive && ctx.layoutState && ctx.layoutState.cells.length === g.grid.panels.length
          ? [...ctx.layoutState.occupied].filter((i) => i >= 0 && i < g.grid.panels.length).sort((a, b) => a - b)
          : null;
      const posedIdx =
        live ?? Array.from({ length: Math.max(0, Math.min(g.grid.panels.length, Math.round(g.count))) }, (_, i) => i);
      const panels = freePosed
        ? freePosed.map((p) => ({ cx: p.cx, cy: p.cy, ...(p.face ? { face: p.face } : {}) }))
        : posedIdx.map((i) => {
            const p = g.grid.panels[i];
            return { cx: p.cx, cy: p.cy, ...(p.face ? { face: p.face } : {}) };
          });
      const posed = panels.length;
      zone.geometry = {
        azimuthDeg: g.pack.azimuthDeg,
        tiltDeg: g.tiltDeg,
        family: g.family,
        flush: g.flush,
        kwc: g.grid.panels.length > 0 ? (g.grid.kwc * posed) / g.grid.panels.length : 0,
        count: posed,
        origin: [g.pack.origin[0], g.pack.origin[1]] as LngLat,
        panels,
        // PV30 — jamais émis hors placement libre (additif, rétro-compatible).
        ...(freePosed ? { mode: 'free' as const } : {}),
      };
      // CAL248 — l'accès solaire par module voyage AVEC la géométrie du pan : mêmes
      // modules, même ordre. Écrit seulement s'il est exploitable (autant de valeurs que
      // de modules posés) ; sinon omis, jamais complété.
      const access = serializeSolarAccess(meta?.solarAccessByZone?.[a.id], posed);
      if (access) zone.geometry.solarAccess = access;
    }
    return zone;
  });
  // CAL57 — déduit le type de chaque arête de CHAQUE zone depuis sa géométrie + ses
  // voisines (mêmes valeurs EFFECTIVES que ci-dessus : vertices/roofType/azimut déjà
  // résolus sur `zone`). Additif : jamais émis pour une zone < 3 sommets.
  const edgeZones: EdgeDeductionZone[] = zones.map((z) => ({
    vertices: z.vertices,
    roofType: z.roofType ?? 'flat',
    facingAzimuthDeg: z.facingAzimuthDeg ?? 180,
    // CALX94 — crochet laissé par CALX93 : la pente SAISIE du pan voyage jusqu'à la
    // déduction (sans elle, aucune noue ni arêtier n'apparaît dans le vrai document).
    // Absente/non finie ⇒ omise, et l'arête reste « inconnue » plutôt que supposée.
    ...(typeof z.pitchDeg === 'number' && Number.isFinite(z.pitchDeg) ? { pitchDeg: z.pitchDeg } : {}),
  }));
  zones.forEach((z, i) => {
    const others = edgeZones.filter((_, j) => j !== i);
    const edges = deduceEdgeTypes(edgeZones[i], others);
    if (edges.length) z.edges = edges;
  });
  // CALX94 — les SAISIES d'arête (type corrigé à la main `manuel: true`, retrait propre
  // `retraitM`) sont superposées à la déduction ci-dessus : une correction n'est jamais
  // ré-écrasée, et une arête non corrigée reste re-déduite. Une seule ligne d'appel vers
  // la fonction pure `fusionnerAretesSaisies` (edges.ts) — aucune logique dupliquée ici.
  zones.forEach((z, i) => {
    const fusion = fusionnerAretesSaisies(ctx.areas[i]?.edges, z.edges);
    if (fusion) z.edges = fusion;
  });
  const activeVerts = ctx.vertices.length >= 1 ? ctx.vertices : ctx.areas.find((a) => a.id === ctx.activeAreaId)?.vertices ?? [];
  const outline: Array<[number, number]> =
    activeVerts.length >= 3 ? activeVerts.map(([lng, lat]) => [lat, lng] as [number, number]) : [];
  // PV13 — RÉSULTAT GLOBAL, cohérent avec ce qui vient d'être exporté : panneaux et kWc
  // sont la SOMME des `zone.geometry` émises ci-dessus (si le JSON dit 42 panneaux, le
  // résultat dit 42) ; la production est la somme des résultats de zone DÉJÀ calculés à
  // l'écran (même source que le total « Plusieurs zones ») ; les économies ne sont JAMAIS
  // recalculées ni sommées ici (une somme zone à zone sur-compte le plafond facture) :
  // l'appelant fournit le chiffre affiché, sinon `null`.
  let panelsTotal = 0;
  let kwcTotal = 0;
  for (const z of zones) {
    if (!z.geometry) continue;
    panelsTotal += z.geometry.count;
    kwcTotal += z.geometry.kwc;
  }
  let annualKwhTotal = 0;
  for (const a of ctx.areas) if (a.result) annualKwhTotal += a.result.annualKwh;
  const savings = typeof meta?.savingsMad === 'number' && Number.isFinite(meta.savingsMad) ? meta.savingsMad : null;

  const layout: SerializedLayout = {
    version: 2,
    pin: centroidOf(activeVerts),
    outline,
    billKwh: Number.isFinite(billKwh as number) ? billKwh : null,
    zones,
    activeAreaId: ctx.activeAreaId,
    // — ajouts v2 (aucun champ v1 déplacé ni modifié) —
    result: { panels: panelsTotal, kwc: kwcTotal, annualKwh: annualKwhTotal, savings },
    scenario: meta?.scenario ?? 'reseau',
    panelWatt: typeof meta?.panelWatt === 'number' && Number.isFinite(meta.panelWatt) ? meta.panelWatt : PANEL2_WATT,
    battery: meta?.battery ?? null,
    source: meta?.source ?? 'lead',
    devisId: meta?.devisId ?? null,
    // PV71 — les ombres tracées voyagent avec le design (sinon la production remonte
    // artificiellement au ré-import).
    shading12x24: serializeShading(ctx.shadeFactors),
    // CAL102 — les mesures posées voyagent avec le design (sinon rouvrir le dossier les
    // perd, comme n'importe quelle autre annotation de l'atelier).
    ...(ctx.measurements && ctx.measurements.length ? { measurements: serializeMeasurements(ctx.measurements) } : {}),
    // CAL67 — les objets d'environnement (arbres/bâtiments voisins) voyagent avec le
    // design, comme les mesures et l'ombrage tracé ci-dessus.
    ...(ctx.environment && ctx.environment.length ? { environment: serializeEnvironment(ctx.environment) } : {}),
    // CAL69 — additif : rien n'est émis tant qu'aucune zone n'est tracée.
    ...(ctx.exclusionZones && ctx.exclusionZones.length
      ? { exclusionZones: serializeExclusionZones(ctx.exclusionZones) }
      : {}),
    // CAL76 — les quatre retraits de rive RÉGLÉS voyagent avec le document (jusqu'ici
    // perdus au rechargement : `setbacks` ne vivait qu'en mémoire dans l'outil).
    ...(meta?.setbacksM ? { setbacksM: { ...meta.setbacksM } } : {}),
    // CAL93 — le profil d'horizon lointain voyage avec le document, comme `setbacksM`.
    // Rien n'est écrit tant qu'aucun profil n'est renseigné (≥ 2 points exploitables).
    ...(meta?.horizonProfile && meta.horizonProfile.points.length >= 2
      ? { horizonProfile: serializeHorizonProfile(meta.horizonProfile) }
      : {}),
    // CALX119 — l'instant du soleil de scène RÉELLEMENT affiché voyage avec le document,
    // comme l'horizon et les retraits ci-dessus (sinon rouvrir le dossier ramène toujours
    // midi au solstice d'hiver, l'incident que cette tâche corrige).
    ...serializeScene(ctx.sunDay, ctx.sunHour),

    ...emettreBatiments(ctx.batiments), // CALX100 — hauteurs SAISIES + provenance (batiment.ts)
  };
  // CALX111 — numéros STABLES des modules : sème la mémoire depuis ce que le document porte
  // déjà, puis écrit `n`/`rangee`/`numerotation` (bascule « Numéroter » éteinte par défaut ⇒
  // document inchangé, octet pour octet). L'attribution elle-même est PURE (`numerotation.ts`).
  numeroterDocument(layout);
  // CALX22x câblage — la couche électrique s'écrit EN DERNIER, par son PROPRE crochet
  // d'export (`ecrireDansDocument`) : jamais une deuxième copie de sa logique ici — elle
  // gère seule la copie profonde et l'absence de la clé quand le document ne porte ni
  // organe ni cheminement. Sans couche fournie, `layout` repart inchangé (byte pour byte).
  return meta?.coucheElectrique ? meta.coucheElectrique.ecrireDansDocument(layout) : layout;
}

/**
 * CAL76 — relit les quatre retraits de rive d'un layout sérialisé. Mêmes garde-fous que
 * `deserializeShading`/`deserializeMeasurements` : un JSON douteux (clé manquante, valeur
 * non finie, négative) ne casse jamais l'ouverture — `resolveSetbacks` renvoie des valeurs
 * saines (repli sur `PERIMETER_SETBACK_M` pour les trois retraits historiques, 0 pour le
 * joint). Renvoie `null` quand le document ne porte aucun `setbacksM` (documents
 * antérieurs à CAL76) : l'appelant garde alors `uniformSetbacks()`, comportement
 * strictement inchangé.
 */
export function deserializeSetbacksFromLayout(json: unknown): PerimeterSetbacks | null {
  const raw = (json as { setbacksM?: Partial<PerimeterSetbacks> } | null | undefined)?.setbacksM;
  if (!raw || typeof raw !== 'object') return null;
  return resolveSetbacks(raw);
}

/** CAL93 — normalise un profil d'horizon avant écriture : points TRIÉS/assainis (aucun
 *  point non fini), `hauteurMaxDeg` RECALCULÉE (jamais recopiée telle quelle — c'est la
 *  seule définition, `horizonMaxHeightDeg`), source repliée sur `'saisie'` si absente. */
export function serializeHorizonProfile(profile: HorizonProfile): HorizonProfile {
  const points = sortedHorizonPoints(profile.points);
  return {
    source: profile.source === 'pvgis' ? 'pvgis' : 'saisie',
    points,
    hauteurMaxDeg: horizonMaxHeightDeg(points),
  };
}

/**
 * CAL93 — relit le profil d'horizon d'un layout sérialisé. Mêmes garde-fous que
 * `deserializeSetbacksFromLayout` : un JSON douteux (points manquants/non finis, source
 * inconnue) est assaini plutôt que de casser l'ouverture ; moins de 2 points exploitables
 * (ou clé absente — document antérieur à CAL93) ⇒ `null`, jamais un horizon inventé.
 */
export function deserializeHorizonProfileFromLayout(json: unknown): HorizonProfile | null {
  const raw = (json as { horizonProfile?: { source?: unknown; points?: unknown } } | null | undefined)?.horizonProfile;
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.points)) return null;
  const points = sortedHorizonPoints(
    (raw.points as Array<{ azimuthDeg?: unknown; heightDeg?: unknown }>)
      .filter((p) => typeof p?.azimuthDeg === 'number' && typeof p?.heightDeg === 'number')
      .map((p) => ({ azimuthDeg: p.azimuthDeg as number, heightDeg: p.heightDeg as number })),
  );
  if (points.length < 2) return null;
  const source: HorizonSource = raw.source === 'pvgis' ? 'pvgis' : 'saisie';
  return { source, points, hauteurMaxDeg: horizonMaxHeightDeg(points) };
}

/**
 * CALX119 — l'instant du soleil de SCÈNE (jour + heure AFFICHÉS), round-trip verbatim
 * (contrat CALX88, `scene{sunDay,sunHour}` de `roof_layout_v2.schema.json`). AUCUN calcul
 * n'en dépend (le contrat le dit) : ce n'est qu'un point de vue sauvegardé, jamais une
 * donnée d'ingénierie — donc jamais recalculé ici, seulement recopié.
 */
export interface ScenePoint {
  sunDay: number;
  sunHour: number;
}

/** Sérialise l'instant de scène courant. `sunDay`/`sunHour` non finis (ne devrait jamais
 *  arriver — `ctx` les garde toujours valides) ⇒ rien n'est émis, jamais une valeur
 *  inventée. */
export function serializeScene(sunDay: number, sunHour: number): { scene?: ScenePoint } {
  if (!Number.isFinite(sunDay) || !Number.isFinite(sunHour)) return {};
  return { scene: { sunDay, sunHour } };
}

/**
 * Relit l'instant de scène d'un layout sérialisé. Absent (document antérieur à
 * CALX88/CALX119) ou non exploitable ⇒ `null` : l'appelant garde alors le défaut
 * historique (solstice d'hiver, midi) — comportement d'aujourd'hui, jamais un jour deviné.
 */
export function deserializeSceneFromLayout(json: unknown): ScenePoint | null {
  const raw = (json as { scene?: { sunDay?: unknown; sunHour?: unknown } } | null | undefined)?.scene;
  const sunDay = raw?.sunDay;
  const sunHour = raw?.sunHour;
  if (typeof sunDay !== 'number' || !Number.isFinite(sunDay)) return null;
  if (typeof sunHour !== 'number' || !Number.isFinite(sunHour)) return null;
  return { sunDay, sunHour };
}

/**
 * Reconstruit la liste d'AreaRecord à partir d'un layout sérialisé. Les champs
 * dérivés (result/renderPlan) repartent à null — l'optimiseur les recalcule au
 * boot. C'est l'inverse de serializeLayout : round-trip = identité sur la géométrie
 * et le dimensionnement.
 */
export function deserializeLayout(json: SerializedLayout): AreaRecord[] {
  const zones = Array.isArray(json?.zones) ? json.zones : [];
  return zones.map((z) => ({
    id: z.id,
    label: z.label,
    vertices: (z.vertices ?? []).map(([lng, lat]) => [lng, lat] as LngLat),
    obstacles: (z.obstacles ?? []).map((o) => ({
      id: o.id,
      centerLng: o.centerLng,
      centerLat: o.centerLat,
      lengthM: o.lengthM,
      widthM: o.widthM,
      ...(o.type ? { type: o.type } : {}), // PV61 — le type survit au round-trip
      ...(o.heightM != null ? { heightM: o.heightM } : {}), // CAL66 — round-trip verbatim
      ...(o.provenance ? { provenance: o.provenance } : {}), // CAL72 — round-trip verbatim
    })),
    // F2 (fondateur 26/08/2026) — une zone posée par le SERVEUR depuis le tracé du
    // client n'écrit PAS ces trois champs : personne n'a mesuré ce toit, et un champ
    // écrit dans le layout descend jusqu'à l'annexe « paramètres du site » de la
    // proposition CLIENT (voir apps/ventes/services.zone_toit_depuis_contour). L'écran,
    // lui, a besoin d'une valeur pour calculer : il applique donc SES propres valeurs
    // de zone vierge — les MÊMES que `newAreaRecord()` dans roof-tool-pro11.ts — là où
    // elles sont visiblement modifiables. Un layout sérialisé par le builder porte
    // TOUJOURS les trois clés, donc ce repli ne change rien pour un dossier enregistré.
    roofType: z.roofType ?? 'flat',
    pitchDeg: z.pitchDeg ?? 22,
    facingAzimuthDeg: z.facingAzimuthDeg ?? 180,
    facingManual: z.facingManual,
    neededPanels: z.neededPanels,
    neededAuto: z.neededAuto,
    result: null,
    renderPlan: null,
    // CAL59 — round-trip verbatim (absent = bâtiment unique, comportement historique).
    ...(z.buildingId ? { buildingId: z.buildingId } : {}),
    // CAL57 — round-trip verbatim ; un document sans arêtes n'en gagne aucune ici (elles
    // sont recalculées à la sérialisation SUIVANTE, pas devinées à la lecture).
    ...(z.edges && z.edges.length ? { edges: z.edges } : {}),
  }));
}

// ═══════════ PV19 — HYDRATATION DEPUIS UN DEVIS ═══════════
// Un devis EXISTANT porte déjà un design (le layout sérialisé) et une CIBLE commerciale
// (le nombre de panneaux vendus). Repartir de la facture serait un contresens : le devis
// fait foi. `hydrateFromDevis` est le jumeau PUR de `hydrateFromLead` — aucun effet de
// bord, aucun fetch — et le boot lead reste INCHANGÉ quand `hydrate.devis` est absent.

/** Payload devis minimal consommé par l'hydratation (tout est optionnel). */
export interface DevisPayload {
  id?: string | number | null;
  /** Géométrie du devis : le layout sérialisé s'il existe, sinon un repère lead-like. */
  geometrie?: {
    roof_layout?: SerializedLayout | null;
    roof_point?: { lat: number; lng: number } | null;
    roof_outline?: Array<[number, number]> | null;
  } | null;
  /** Cible commerciale : ce qui a été VENDU (panneaux, puissance unitaire, scénario). */
  cible?: {
    panneaux?: number | null;
    panel_watt?: number | null;
    scenario?: LayoutScenario | null;
  } | null;
  /**
   * CAL37 — ce document porte-t-il une cible VENDUE ? `false` UNIQUEMENT pour un
   * document qui n'a aucun devis derrière lui (un calepinage autonome, contrat
   * `calepinage_design_context.json` : « LA CIBLE N'EST JAMAIS INVENTÉE », `cible`
   * vaut alors `null`). ABSENT ⇒ `true` ⇒ comportement devis/AO strictement
   * inchangé : là, une cible vide est une CIBLE VENDUE DE ZÉRO (L2, incident
   * DEV-202608-0016) et l'optimiseur ne pose RIEN. Sur un calepinage sans devis,
   * il n'y a rien de vendu du tout : l'optimiseur doit travailler librement,
   * exactement comme pour un lead sans facture.
   */
  cibleVendue?: boolean;
  fullName?: string;
  phone?: string;
  city?: string;
  [k: string]: unknown;
}

/** Ce que l'hydratation devis rend au boot (rien n'est appliqué ici). */
export interface DevisHydration {
  /** Contour lng/lat de la zone ACTIVE (vide si seul un pin est disponible). */
  vertices: LngLat[];
  /** Centre de vol lng/lat, ou null. */
  center: LngLat | null;
  contact: { name?: string; phone?: string; city?: string };
  /** Zones reconstruites depuis `roof_layout`, ou null si le devis n'en porte pas. */
  zones: AreaRecord[] | null;
  /** Id de zone active du layout, ou null. */
  activeAreaId: string | null;
  /** Nombre de panneaux VENDU : impose la cible de l'optimiseur (null si absent). */
  neededPanels: number | null;
  /** false dès qu'une cible est imposée : le devis pilote, pas la facture. */
  neededAuto: boolean;
  /** CAL37 — le document porte-t-il une cible VENDUE ? (voir `DevisPayload.cibleVendue`) */
  cibleVendue: boolean;
  /** Puissance unitaire vendue (W), ou null. */
  panelWatt: number | null;
  scenario: LayoutScenario | null;
  devisId: string | number | null;
}

/** Entier positif, ou null (une cible de 0/−3/NaN panneaux n'impose rien). */
function positiveInt(v: unknown): number | null {
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.round(n);
}

/**
 * PV19 — Reconstruit l'état de départ du builder à partir d'un DEVIS. Deux chemins :
 *  1. `geometrie.roof_layout` présent → les zones sont reconstruites par
 *     `deserializeLayout` (le design du devis, à l'identique) ;
 *  2. sinon → repli exactement lead-like (pin / contour), pour qu'un devis sans design
 *     ouvre quand même la bonne toiture.
 * Dans les DEUX cas, la CIBLE du devis (`cible.panneaux`) devient le besoin IMPOSÉ
 * (`neededAuto = false`) : c'est le nombre vendu qui pilote l'optimiseur, jamais la
 * facture. PURE : aucun effet de bord, l'appelant applique le résultat.
 */
export function hydrateFromDevis(devis: DevisPayload | null | undefined): DevisHydration {
  const empty: DevisHydration = {
    vertices: [],
    center: null,
    contact: {},
    zones: null,
    activeAreaId: null,
    neededPanels: null,
    neededAuto: true,
    panelWatt: null,
    scenario: null,
    devisId: null,
    cibleVendue: true,
  };
  if (!devis) return empty;

  const geo = devis.geometrie ?? null;
  const layout = geo?.roof_layout ?? null;
  let zones: AreaRecord[] | null = null;
  let activeAreaId: string | null = null;
  let vertices: LngLat[] = [];
  let center: LngLat | null = null;

  if (layout && Array.isArray(layout.zones) && layout.zones.length) {
    zones = deserializeLayout(layout);
    const wanted = typeof layout.activeAreaId === 'string' ? layout.activeAreaId : null;
    const active = zones.find((z) => z.id === wanted) ?? zones[0];
    activeAreaId = active?.id ?? null;
    vertices = active ? active.vertices.map(([lng, lat]) => [lng, lat] as LngLat) : [];
    const pin = layout.pin;
    if (pin && Number.isFinite(pin.lat) && Number.isFinite(pin.lng)) center = [pin.lng, pin.lat];
  }
  if (!vertices.length || !center) {
    // Repli lead-like : le devis n'a pas (encore) de design, ou pas de pin.
    const seed = hydrateFromLead({ roof_point: geo?.roof_point ?? null, roof_outline: geo?.roof_outline ?? null });
    if (!vertices.length) vertices = seed.vertices;
    if (!center) center = seed.center ?? (vertices.length ? centroidOf(vertices) && ([centroidOf(vertices)!.lng, centroidOf(vertices)!.lat] as LngLat) : null);
  }

  const contact: { name?: string; phone?: string; city?: string } = {};
  if (typeof devis.fullName === 'string' && devis.fullName.trim()) contact.name = devis.fullName.trim();
  if (typeof devis.phone === 'string' && devis.phone.trim()) contact.phone = devis.phone.trim();
  if (typeof devis.city === 'string' && devis.city.trim()) contact.city = devis.city.trim();

  const neededPanels = positiveInt(devis.cible?.panneaux);
  const panelWatt = positiveInt(devis.cible?.panel_watt);
  const scenario = devis.cible?.scenario ?? null;
  return {
    vertices,
    center,
    contact,
    zones,
    activeAreaId,
    neededPanels,
    // Une cible vendue IMPOSE le besoin ; sans cible, on laisse la facture décider.
    neededAuto: neededPanels == null,
    panelWatt,
    scenario,
    devisId: devis.id ?? null,
    // ABSENT ⇒ true : un appelant qui ne connaît pas ce drapeau (devis, AO) garde
    // EXACTEMENT le comportement d'avant.
    cibleVendue: devis.cibleVendue !== false,
  };
}

/**
 * W113 — Sème le contour/pin de la zone active depuis un payload lead. Renvoie le
 * contour lng/lat à appliquer (vide si seul un pin est disponible) + le centre de
 * vol. PURE (aucun effet de bord) : le boot consomme le résultat pour poser
 * vertices/centroid/flyTo. Les coordonnées lead sont en [lat,lng] (convention CRM)
 * et sont converties en [lng,lat] (convention MapLibre/builder).
 */
export function hydrateFromLead(lead: LeadPayload | null | undefined): {
  vertices: LngLat[];
  center: LngLat | null;
  contact: { name?: string; phone?: string; city?: string };
} {
  const empty = { vertices: [] as LngLat[], center: null as LngLat | null, contact: {} };
  if (!lead) return empty;
  // AP-F1 (fondateur 26/08/2026) — UN SEUL validateur de contour : avant ce correctif,
  // cette fonction ré-implémentait son propre filtre et n'acceptait QUE la forme
  // `[lat, lng]`, alors que `referenceContourRing` (plus bas dans ce fichier) accepte
  // déjà les DEUX formes RÉELLES de `Lead.roof_outline` (`[lat, lng]` du webhook ET
  // `{lat, lng}` de l'import/saisie manuelle), avec le MÊME bornage. La divergence
  // faisait qu'un contour `{lat, lng}` se dessinait comme calque passif de référence
  // (referenceContourRing l'acceptait) mais ne semait AUCUNE zone éditable — les
  // panneaux n'apparaissaient jamais tant que le commercial ne retraçait pas le toit
  // à la main. Sortie IDENTIQUE à avant pour la forme tuple (même conversion
  // [lat,lng] → [lng,lat], même règle ≥ 3 sommets valides, même bornage).
  const ring = referenceContourRing(lead.roof_outline);
  const vertices: LngLat[] = ring ?? [];
  let center: LngLat | null = null;
  const pt = lead.roof_point;
  if (pt && Number.isFinite(pt.lat) && Number.isFinite(pt.lng)) {
    center = [pt.lng, pt.lat];
  } else {
    center = centroidOf(vertices) ? ([centroidOf(vertices)!.lng, centroidOf(vertices)!.lat] as LngLat) : null;
  }
  const contact: { name?: string; phone?: string; city?: string } = {};
  if (typeof lead.fullName === 'string' && lead.fullName.trim()) contact.name = lead.fullName.trim();
  if (typeof lead.phone === 'string' && lead.phone.trim()) contact.phone = lead.phone.trim();
  if (typeof lead.city === 'string' && lead.city.trim()) contact.city = lead.city.trim();
  return { vertices, center, contact };
}

/** Un point du contour brut, TEL QUE rencontré en base : `[lat, lng]` (le
 *  webhook) ou `{lat, lng}` (import/saisie manuelle) — les DEUX formes que
 *  `Lead.roof_outline` porte réellement. */
export type RawContourPoint = [number, number] | { lat: number; lng: number };

/** Borne lat/lng STRICTE — MÊME predicat que `borne()` de traceToit.js (côté
 *  ERP, frontend/src/features/crm/workspace/traceToit.js) : dupliqué ici
 *  (les deux packages ne partagent aucun module — apps/web et frontend/ sont
 *  deux builds distincts) mais avec la MÊME formule, jamais une version plus
 *  permissive qui accepterait ce que l'ERP refuse. Toute divergence future
 *  entre les deux doit se lire comme un bug, pas une variation voulue. */
function coordonneeValide(lat: number, lng: number): boolean {
  return Number.isFinite(lat) && lat >= -90 && lat <= 90
    && Number.isFinite(lng) && lng >= -180 && lng <= 180;
}

/**
 * L-MAP (fondateur 26/08/2026 : « i want it visible on the map in the 3D
 * layouter ») — le contour ORIGINAL dessiné par le client, en `[lng, lat]` ×
 * n, prêt pour un calque GÉO-RÉFÉRENCÉ passif (`roof-tool-pro11.ts`, source
 * `rp9-ref-contour`). MÊME validation que `normaliserContour` (traceToit.js,
 * ERP) — les DEUX formes de points (`[lat, lng]` ET `{lat, lng}`) et le MÊME
 * bornage lat ∈ [-90, 90] / lng ∈ [-180, 180], jamais une version plus
 * permissive : un contour que l'écran hôte refuse (légende/bascule absentes)
 * ne doit JAMAIS dessiner un polygone orphelin, sans bascule pour le masquer,
 * sur la carte. Usage différent de `hydrateFromLead`/`vertices` ci-dessus
 * (qui SÈMENT la zone active éditable) : celui-ci reste une trace PERMANENTE
 * et NON ÉDITABLE, distincte du calepinage courant même après une édition.
 * `null` sans contour exploitable (< 3 sommets valides) — jamais un tableau
 * vide qui dessinerait un polygone dégénéré, jamais un contour deviné.
 */
export function referenceContourRing(brut: RawContourPoint[] | null | undefined): LngLat[] | null {
  if (!Array.isArray(brut)) return null;
  const ring: LngLat[] = [];
  for (const p of brut) {
    let lat: number;
    let lng: number;
    if (Array.isArray(p) && p.length >= 2) {
      lat = Number(p[0]);
      lng = Number(p[1]);
    } else if (p && typeof p === 'object') {
      lat = Number((p as { lat?: unknown }).lat);
      lng = Number((p as { lng?: unknown }).lng);
    } else {
      continue;
    }
    if (coordonneeValide(lat, lng)) ring.push([lng, lat]);
  }
  return ring.length >= 3 ? ring : null;
}

/** CAL69 — relit les zones d'exclusion d'un document d'atelier. Accepte soit le layout
 *  complet (lit `.exclusionZones`), soit déjà le tableau brut. JSON douteux ⇒ tableau
 *  vide, jamais une exception — même esprit que `deserializeMeasurements`. */
export function deserializeExclusionZonesFromLayout(json: unknown): ExclusionZone[] {
  const raw = (json as { exclusionZones?: unknown } | null | undefined)?.exclusionZones ?? json;
  return deserializeExclusionZones(raw);
}

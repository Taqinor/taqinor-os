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
import { type AreaRecord, type CardData, type LeadPayload, type ObstacleType } from './types';
import { type LngLat } from '../../lib/roof';
import { BILL_RANGES } from '../../lib/billRange';
import { PANEL2_WATT } from '../../lib/estimatorBrainV2';
import { ROOF_TYPES } from '../../lib/lead';

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
}

/** Une zone sérialisée (sous-ensemble plat et JSON-sûr d'AreaRecord). */
export interface SerializedZone {
  id: string;
  label: string;
  /** Contour lng/lat [[lng,lat],…]. */
  vertices: LngLat[];
  /** Obstacles (zones d'exclusion) — objets plats {id,centerLng,centerLat,lengthM,widthM}.
   *  PV61 — `type` (optionnel) porte le dégagement de l'obstacle ; absent = comportement
   *  historique (dégagement uniforme). Jamais émis pour un obstacle sans type. */
  obstacles: Array<{ id: string; centerLng: number; centerLat: number; lengthM: number; widthM: number; type?: ObstacleType }>;
  roofType: 'flat' | 'pitched';
  pitchDeg: number;
  facingAzimuthDeg: number;
  facingManual: boolean;
  neededPanels: number;
  neededAuto: boolean;
  /** WJ24 — géométrie pleine par pan (optionnel, additif). Présent seulement si un plan
   *  de rendu existe pour la zone. Le round-trip deserializeLayout l'ignore (dérivé,
   *  recalculé au boot) — il sert uniquement à l'export ERP (devis/PDF multi-plan). */
  geometry?: SerializedZoneGeometry;
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
      })),
      roofType: isActive ? ctx.roofType : a.roofType,
      pitchDeg: isActive ? ctx.pitchDeg : a.pitchDeg,
      facingAzimuthDeg: isActive ? ctx.facingAzimuthDeg : a.facingAzimuthDeg,
      facingManual: isActive ? ctx.facingManual : a.facingManual ?? false,
      neededPanels: isActive ? ctx.neededPanels : a.neededPanels,
      neededAuto: isActive ? ctx.neededAuto : a.neededAuto,
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
    }
    return zone;
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

  return {
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
  };
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
    })),
    roofType: z.roofType,
    pitchDeg: z.pitchDeg,
    facingAzimuthDeg: z.facingAzimuthDeg,
    facingManual: z.facingManual,
    neededPanels: z.neededPanels,
    neededAuto: z.neededAuto,
    result: null,
    renderPlan: null,
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
  let vertices: LngLat[] = [];
  let center: LngLat | null = null;
  if (Array.isArray(lead.roof_outline) && lead.roof_outline.length >= 3) {
    vertices = lead.roof_outline
      .filter((p) => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1]))
      .map(([lat, lng]) => [lng, lat] as LngLat);
  }
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

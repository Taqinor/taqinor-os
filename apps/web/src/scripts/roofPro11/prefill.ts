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
import { type AreaRecord, type CardData, type LeadPayload } from './types';
import { type LngLat } from '../../lib/roof';
import { BILL_RANGES } from '../../lib/billRange';
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

/** Une zone sérialisée (sous-ensemble plat et JSON-sûr d'AreaRecord). */
export interface SerializedZone {
  id: string;
  label: string;
  /** Contour lng/lat [[lng,lat],…]. */
  vertices: LngLat[];
  /** Obstacles (zones d'exclusion) — objets plats {id,centerLng,centerLat,lengthM,widthM}. */
  obstacles: Array<{ id: string; centerLng: number; centerLat: number; lengthM: number; widthM: number }>;
  roofType: 'flat' | 'pitched';
  pitchDeg: number;
  facingAzimuthDeg: number;
  facingManual: boolean;
  neededPanels: number;
  neededAuto: boolean;
}

/** Layout complet sérialisé : version + zones + repère léger (pin/outline). */
export interface SerializedLayout {
  version: 1;
  /** Pin {lat,lng} (le centroïde du contour, ou le repère client posé), ou null. */
  pin: { lat: number; lng: number } | null;
  /** Contour de la zone active en [[lat,lng],…] (vide si pas de tracé fermé). */
  outline: Array<[number, number]>;
  /** Consommation annuelle (kWh) issue de la facture, si connue. */
  billKwh: number | null;
  zones: SerializedZone[];
  /** Id de la zone active au moment de la sérialisation. */
  activeAreaId: string;
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
export function serializeLayout(ctx: Ctx, billKwh: number | null = null): SerializedLayout {
  // On part des zones figées (ctx.areas) et on superpose l'état d'édition VIVANT de
  // la zone active (vertices/obstacles/roofType… vivent sur ctx, pas encore re-figés).
  const zones: SerializedZone[] = ctx.areas.map((a) => {
    const isActive = a.id === ctx.activeAreaId;
    const vertices = isActive ? ctx.vertices : a.vertices;
    const obstacles = isActive ? ctx.obstacles : a.obstacles;
    return {
      id: a.id,
      label: a.label,
      vertices: vertices.map(([lng, lat]) => [lng, lat] as LngLat),
      obstacles: obstacles.map((o) => ({
        id: o.id,
        centerLng: o.centerLng,
        centerLat: o.centerLat,
        lengthM: o.lengthM,
        widthM: o.widthM,
      })),
      roofType: isActive ? ctx.roofType : a.roofType,
      pitchDeg: isActive ? ctx.pitchDeg : a.pitchDeg,
      facingAzimuthDeg: isActive ? ctx.facingAzimuthDeg : a.facingAzimuthDeg,
      facingManual: isActive ? ctx.facingManual : a.facingManual ?? false,
      neededPanels: isActive ? ctx.neededPanels : a.neededPanels,
      neededAuto: isActive ? ctx.neededAuto : a.neededAuto,
    };
  });
  const activeVerts = ctx.vertices.length >= 1 ? ctx.vertices : ctx.areas.find((a) => a.id === ctx.activeAreaId)?.vertices ?? [];
  const outline: Array<[number, number]> =
    activeVerts.length >= 3 ? activeVerts.map(([lng, lat]) => [lat, lng] as [number, number]) : [];
  return {
    version: 1,
    pin: centroidOf(activeVerts),
    outline,
    billKwh: Number.isFinite(billKwh as number) ? billKwh : null,
    zones,
    activeAreaId: ctx.activeAreaId,
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

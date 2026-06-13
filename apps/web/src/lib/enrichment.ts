/**
 * Champs d'enrichissement FACULTATIFS du diagnostic (preview privé).
 *
 * Ces champs sont purement additifs : ils ne participent JAMAIS à la
 * validation du lead, ni au seuil 1 000 MAD, ni à la bande ROI, ni au
 * message WhatsApp, ni à l'événement CAPI. Quand l'utilisateur n'y touche
 * pas, `cleanEnrichment` renvoie `{}` et le lead transmis est strictement
 * identique à celui du formulaire en production. Quand ils sont remplis, ils
 * « ride along » dans la même soumission et sont ajoutés tels quels à la
 * charge utile transmise au CRM (affichage CRM = tâche taqinor-os séparée).
 *
 * Module pur (aucun DOM) → testé unitairement.
 */

export const SUPPLY_TYPES = [
  { id: 'mono', label: 'Monophasé' },
  { id: 'tri', label: 'Triphasé' },
  { id: 'inconnu', label: 'Je ne sais pas' },
] as const;
export type SupplyTypeId = (typeof SUPPLY_TYPES)[number]['id'];

export const ORIENTATIONS = [
  { id: 'sud', label: 'Sud' },
  { id: 'sud-est', label: 'Sud-Est' },
  { id: 'sud-ouest', label: 'Sud-Ouest' },
  { id: 'est', label: 'Est' },
  { id: 'ouest', label: 'Ouest' },
  { id: 'nord', label: 'Nord' },
  { id: 'inconnu', label: 'Je ne sais pas' },
] as const;
export type OrientationId = (typeof ORIENTATIONS)[number]['id'];

export interface Enrichment {
  supplyType?: SupplyTypeId;
  roofAreaM2?: number;
  orientation?: OrientationId;
}

/** Surface de toiture plausible (m²) : > 0 et sous un plafond raisonnable. */
const ROOF_AREA_MAX = 100000;

/**
 * Normalise les champs facultatifs : ne retient que des valeurs canoniques
 * et plausibles. Toute entrée vide/absente/invalide est silencieusement
 * ignorée — jamais une erreur, jamais un blocage de la capture.
 */
export function cleanEnrichment(body: unknown): Enrichment {
  const b = (body ?? {}) as Record<string, unknown>;
  const out: Enrichment = {};

  const supply = typeof b.supplyType === 'string' ? b.supplyType.trim() : '';
  if (SUPPLY_TYPES.some((s) => s.id === supply)) out.supplyType = supply as SupplyTypeId;

  const orient = typeof b.orientation === 'string' ? b.orientation.trim() : '';
  if (ORIENTATIONS.some((o) => o.id === orient)) out.orientation = orient as OrientationId;

  const rawArea = b.roofArea;
  const area = typeof rawArea === 'number' ? rawArea : parseFloat(String(rawArea ?? '').replace(',', '.'));
  if (Number.isFinite(area) && area > 0 && area <= ROOF_AREA_MAX) out.roofAreaM2 = area;

  return out;
}

/** Vrai si au moins un champ facultatif a été rempli. */
export function hasEnrichment(e: Enrichment): boolean {
  return e.supplyType !== undefined || e.roofAreaM2 !== undefined || e.orientation !== undefined;
}

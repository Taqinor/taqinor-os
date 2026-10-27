/**
 * RWEB2 — durées de garantie onduleur / batterie du bloc « garanties » de
 * /proposition, selon la MARQUE réellement posée (décision fondateur
 * 27/10/2026 : une seule durée, celle qui vaut au Maroc).
 *
 * Deye → 5 ans, Huawei → 10 ans, batterie Dyness → 10 ans (`lib/warranty.ts`).
 * Marque non reconnue → `null` : la durée est OMISE plutôt que supposée.
 */
import {
  BATTERY_WARRANTY_YEARS,
  DEYE_INVERTER_WARRANTY_YEARS,
  HUAWEI_INVERTER_WARRANTY_YEARS,
} from '../warranty';

interface LigneMarque {
  designation?: string | null;
  marque?: string | null;
}

function texte(l: LigneMarque): string {
  return `${l.marque ?? ''} ${l.designation ?? ''}`.toLowerCase();
}

/** Garantie onduleur en années, ou null (aucune marque connue). Deux marques → la plus courte. */
export function garantieOnduleurAns(lignes: readonly LigneMarque[]): number | null {
  const t = lignes.map(texte);
  if (t.some((x) => x.includes('deye'))) return DEYE_INVERTER_WARRANTY_YEARS;
  if (t.some((x) => x.includes('huawei'))) return HUAWEI_INVERTER_WARRANTY_YEARS;
  return null;
}

/** Garantie batterie en années (Dyness), ou null (pas de batterie Dyness dans le devis). */
export function garantieBatterieAns(lignes: readonly LigneMarque[]): number | null {
  return lignes.some((l) => texte(l).includes('dyness')) ? BATTERY_WARRANTY_YEARS : null;
}

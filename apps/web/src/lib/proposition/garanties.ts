/**
 * RWEB2 — durées de garantie onduleur / batterie du bloc « garanties » de
 * /proposition, selon la MARQUE réellement posée (décision fondateur
 * 27/10/2026 : une seule durée, celle qui vaut au Maroc).
 *
 * Deye → 5 ans, Huawei → 10 ans, batterie Dyness → 7 ans (`lib/warranty.ts`).
 * Marque non reconnue → `null` : la durée est OMISE plutôt que supposée.
 */
import {
  PANEL_PERFORMANCE_WARRANTY_YEARS,
  PANEL_PRODUCT_WARRANTY_YEARS,
  BATTERY_WARRANTY_YEARS,
  DEYE_INVERTER_WARRANTY_YEARS,
  DYNESS_POWERBOX_PRO_WARRANTY_YEARS,
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
  // Lignes onduleur seulement : une « Batterie Deye » à côté d'un onduleur Huawei ne donne pas 5 ans.
  const t = lignes.map(texte).filter((x) => !x.includes('batter'));
  if (t.some((x) => x.includes('deye'))) return DEYE_INVERTER_WARRANTY_YEARS;
  if (t.some((x) => x.includes('huawei'))) return HUAWEI_INVERTER_WARRANTY_YEARS;
  return null;
}

/** Garantie batterie en années (Dyness DL5.0C 7, Powerbox Pro 10), ou null (pas de batterie Dyness). */
export function garantieBatterieAns(lignes: readonly LigneMarque[]): number | null {
  const t = lignes.map(texte).filter((x) => x.includes('dyness'));
  if (!t.length) return null;
  // Deux gammes dans le même devis → la plus courte (jamais promettre plus que la garantie réelle).
  return t.every((x) => x.includes('powerbox')) ? DYNESS_POWERBOX_PRO_WARRANTY_YEARS : BATTERY_WARRANTY_YEARS;
}

/**
 * RWEB19 — garanties PANNEAUX (produit 12 ans / performance 30 ans) comme le PDF
 * (`residential/theme.py` : repli constante réservé au panneau Canadian Solar par défaut).
 * Autre marque (JA Solar…) ou aucun panneau → null : les deux durées sont OMISES.
 */
export function garantiesPanneauxAns(lignes: readonly LigneMarque[]): { produit: number; performance: number } | null {
  // Graphies du catalogue (« Canadien Solar ») comprises, comme theme.py::_PANNEAU_DEFAUT_MARQUEURS ; Jinko : le PDF
  // n'a pas de repli constante (garantie_mois non saisi au catalogue) → omis ici aussi (même document).
  const ok = lignes.map(texte).some((x) => /canadian|canadien/.test(x) && /panneau|module|panel|\bwc\b|\d\s*w\b/.test(x));
  return ok ? { produit: PANEL_PRODUCT_WARRANTY_YEARS, performance: PANEL_PERFORMANCE_WARRANTY_YEARS } : null;
}

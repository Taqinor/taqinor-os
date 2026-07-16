/**
 * Tranches de facture mensuelle (MAD) — champ obligatoire du formulaire.
 * Filtre seuil : les factures sous 1 000 MAD n'atteignent JAMAIS le CRM
 * (`qualifies: false`) — l'état de remerciement s'affiche quand même.
 */
export const BILL_RANGES = [
  { id: 'lt800', label: 'Moins de 800 MAD', qualifies: false },
  { id: '800-1000', label: '800 – 1 000 MAD', qualifies: false },
  { id: '1000-1500', label: '1 000 – 1 500 MAD', qualifies: true },
  { id: '1500-3000', label: '1 500 – 3 000 MAD', qualifies: true },
  { id: '3000-5000', label: '3 000 – 5 000 MAD', qualifies: true },
  { id: '5000-10000', label: '5 000 – 10 000 MAD', qualifies: true },
  { id: 'gt10000', label: 'Plus de 10 000 MAD', qualifies: true },
] as const;

export type BillRangeId = (typeof BILL_RANGES)[number]['id'];

export function isBillRangeId(v: unknown): v is BillRangeId {
  return typeof v === 'string' && BILL_RANGES.some((r) => r.id === v);
}

export function qualifiesForCrm(id: BillRangeId): boolean {
  return BILL_RANGES.find((r) => r.id === id)?.qualifies ?? false;
}

export function billRangeLabel(id: BillRangeId): string {
  return BILL_RANGES.find((r) => r.id === id)?.label ?? '';
}

/**
 * Bornes numériques de chaque tranche (MAD/mois) — intervalles semi-ouverts
 * [min, max) pour que chaque montant tombe dans EXACTEMENT une tranche ; la
 * dernière est ouverte (∞) et attrape tout grand montant. Dérivées des ids/
 * libellés de BILL_RANGES ci-dessus — garder alignées si les tranches bougent.
 */
const BILL_RANGE_BOUNDS: Record<BillRangeId, { min: number; max: number }> = {
  lt800: { min: 0, max: 800 },
  '800-1000': { min: 800, max: 1000 },
  '1000-1500': { min: 1000, max: 1500 },
  '1500-3000': { min: 1500, max: 3000 },
  '3000-5000': { min: 3000, max: 5000 },
  '5000-10000': { min: 5000, max: 10000 },
  gt10000: { min: 10000, max: Infinity },
};

/**
 * Tranche correspondant à un montant EXACT de facture (MAD/mois) : la plus
 * petite tranche dont les bornes contiennent le montant (valeur du select du
 * formulaire). null pour une entrée non chiffrable (NaN/≤ 0) — jamais deviné.
 */
export function billRangeFromExact(mad: number): BillRangeId | null {
  if (!Number.isFinite(mad) || mad <= 0) return null;
  for (const r of BILL_RANGES) {
    const b = BILL_RANGE_BOUNDS[r.id];
    if (mad >= b.min && mad < b.max) return r.id;
  }
  return null; // inatteignable (dernière tranche ouverte) — défensif
}

/**
 * Bande préliminaire kWc + ROI — fallback local quand SIMULATOR_API_URL
 * n'est pas configurée. Jamais un devis : une fourchette indicative.
 * Hypothèses : barème régie ONEE (tranche effective ≈ 1,38–1,60 MAD/kWh selon la
 * consommation, base partagée avec l'estimateur), ~1 600 kWh/kWc/an au Maroc.
 */
export interface EstimateBand {
  kwcMin: number;
  kwcMax: number;
  kwcLabel: string;
  paybackLabel: string;
  source: 'local' | 'simulator';
}

const LOCAL_BANDS: Record<BillRangeId, Omit<EstimateBand, 'source'>> = {
  'lt800': { kwcMin: 2, kwcMax: 3, kwcLabel: '2 à 3 kWc', paybackLabel: '6 à 8 ans' },
  '800-1000': { kwcMin: 2, kwcMax: 4, kwcLabel: '2 à 4 kWc', paybackLabel: '5 à 7 ans' },
  '1000-1500': { kwcMin: 3, kwcMax: 5, kwcLabel: '3 à 5 kWc', paybackLabel: '5 à 7 ans' },
  '1500-3000': { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans' },
  '3000-5000': { kwcMin: 9, kwcMax: 15, kwcLabel: '9 à 15 kWc', paybackLabel: '4 à 6 ans' },
  '5000-10000': { kwcMin: 15, kwcMax: 30, kwcLabel: '15 à 30 kWc', paybackLabel: '3 à 5 ans' },
  'gt10000': { kwcMin: 30, kwcMax: 100, kwcLabel: '30 kWc et plus (étude dédiée)', paybackLabel: '3 à 5 ans' },
};

export function localEstimateBand(id: BillRangeId): EstimateBand {
  return { ...LOCAL_BANDS[id], source: 'local' };
}

/**
 * WJ1 — libellés d'amortissement indicatifs par TAILLE d'installation (kWc).
 * Dérivés des `paybackLabel` déjà committés des bandes de tranche ci-dessus (mêmes
 * fourchettes) : plus l'installation est grande, plus le retour est court. AUCUN
 * nombre nouveau inventé — c'est un re-mapping des constantes existantes, utilisé
 * par billEstimate.ts pour une estimation à partir de la facture SEULE (sans devis
 * chiffré, puisqu'on n'a aucun prix €/kWc fiable côté site).
 */
export interface PaybackHint {
  /** Taille maximale (kWc) couverte par ce libellé (inclus). */
  maxKwc: number;
  paybackLabel: string;
}
export const LOCAL_PAYBACK_BY_KWC: PaybackHint[] = [
  { maxKwc: 4, paybackLabel: '6 à 8 ans' },
  { maxKwc: 9, paybackLabel: '5 à 7 ans' },
  { maxKwc: 15, paybackLabel: '4 à 6 ans' },
  { maxKwc: Infinity, paybackLabel: '3 à 5 ans' },
];

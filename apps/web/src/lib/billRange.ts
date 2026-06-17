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

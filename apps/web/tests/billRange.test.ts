import { describe, expect, it } from 'vitest';
import { BILL_RANGES, isBillRangeId, localEstimateBand, qualifiesForCrm } from '../src/lib/billRange';
import { formatMAD } from '../src/lib/format';

describe('seuil CRM — les factures sous 1 000 MAD ne sont jamais qualifiées', () => {
  it('disqualifie lt800 et 800-1000', () => {
    expect(qualifiesForCrm('lt800')).toBe(false);
    expect(qualifiesForCrm('800-1000')).toBe(false);
  });

  it('qualifie toutes les tranches à partir de 1 000 MAD', () => {
    for (const id of ['1000-1500', '1500-3000', '3000-5000', '5000-10000', 'gt10000'] as const) {
      expect(qualifiesForCrm(id)).toBe(true);
    }
  });

  it('couvre les 7 tranches du brief (800, 1 000, 1 500, 3 000, 5 000, 10 000+)', () => {
    expect(BILL_RANGES).toHaveLength(7);
  });
});

describe('isBillRangeId', () => {
  it('accepte les ids connus et rejette le reste', () => {
    expect(isBillRangeId('1500-3000')).toBe(true);
    expect(isBillRangeId('9999')).toBe(false);
    expect(isBillRangeId(null)).toBe(false);
  });
});

describe('localEstimateBand', () => {
  it('retourne une bande locale pour chaque tranche', () => {
    for (const r of BILL_RANGES) {
      const band = localEstimateBand(r.id);
      expect(band.source).toBe('local');
      expect(band.kwcLabel.length).toBeGreaterThan(0);
      expect(band.paybackLabel.length).toBeGreaterThan(0);
      expect(band.kwcMax).toBeGreaterThanOrEqual(band.kwcMin);
    }
  });
});

describe('formatMAD', () => {
  it('formate avec séparateur de milliers espace et devise après', () => {
    expect(formatMAD(12500)).toBe('12 500 MAD');
    expect(formatMAD(800)).toBe('800 MAD');
    expect(formatMAD(1000000)).toBe('1 000 000 MAD');
    expect(formatMAD(-2500)).toBe('-2 500 MAD');
  });
});

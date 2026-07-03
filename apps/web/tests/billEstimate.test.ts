import { describe, expect, it } from 'vitest';
import {
  climateConfidenceFactor,
  distributeurHonestyNote,
  estimateFromBill,
  formatMad,
  formatMadRange,
} from '../src/lib/billEstimate';
import { climateDerateFactor, tariffForCity, TARIFF_BY_CITY } from '../src/lib/estimatorBrainV2';

describe('estimateFromBill — WJ69 repointed to estimatorBrainV2 (parity preserved)', () => {
  it('renvoie une estimation cohérente pour une facture typique', () => {
    const est = estimateFromBill(1200);
    expect(est).not.toBeNull();
    if (!est) return;
    expect(est.kwc).toBeGreaterThan(0);
    expect(est.productionKwhYr).toBeGreaterThan(0);
    expect(est.savingsLow).toBeGreaterThanOrEqual(0);
    expect(est.savingsHigh).toBeGreaterThanOrEqual(est.savingsLow);
    expect(est.latitudeUsed).toBe(33.5); // Casablanca par défaut
  });

  it('renvoie null pour une facture non chiffrable (jamais un chiffre fabriqué)', () => {
    expect(estimateFromBill(0)).toBeNull();
    expect(estimateFromBill(-100)).toBeNull();
    expect(estimateFromBill(NaN)).toBeNull();
  });

  it('affine la latitude quand un repère est posé', () => {
    const estAgadir = estimateFromBill(1200, { lat: 30.4 });
    expect(estAgadir?.latitudeUsed).toBe(30.4);
  });
});

// ——— WJ71 — bande de confiance climatique surfacée PAR DÉFAUT ———
describe('WJ71 — productionBand surfacé par défaut sur l\'estimation publique', () => {
  it('productionBand.high == productionKwhYr (le chiffre nu déjà affiché)', () => {
    const est = estimateFromBill(1200);
    expect(est).not.toBeNull();
    if (!est) return;
    // high est calculé AVANT arrondi (kwc * yld) — proche de productionKwhYr (arrondi).
    expect(est.productionBand.high).toBeCloseTo(est.productionKwhYr, 0);
  });

  it('productionBand.low <= point <= high (jamais un gain, jamais une inversion)', () => {
    const est = estimateFromBill(1500);
    expect(est).not.toBeNull();
    if (!est) return;
    expect(est.productionBand.low).toBeLessThanOrEqual(est.productionBand.point);
    expect(est.productionBand.point).toBeLessThanOrEqual(est.productionBand.high);
  });

  it('productionBand.low = high × climateDerateFactor() (le même dérate documenté WJ22)', () => {
    const est = estimateFromBill(1200);
    expect(est).not.toBeNull();
    if (!est) return;
    const derate = climateDerateFactor();
    expect(est.productionBand.low).toBeCloseTo(est.productionBand.high * derate, 6);
  });

  it('savingsLowBand <= savingsHigh (économies basses climatiques jamais au-dessus du haut existant)', () => {
    const est = estimateFromBill(1200);
    expect(est).not.toBeNull();
    if (!est) return;
    expect(est.savingsLowBand).toBeLessThanOrEqual(est.savingsHigh);
    expect(est.savingsHighBand).toBe(est.savingsHigh);
  });

  it('climateConfidenceFactor() est ≤ 1 (jamais un gain) et cohérent avec estimatorBrainV2', () => {
    const f = climateConfidenceFactor();
    expect(f).toBeGreaterThan(0);
    expect(f).toBeLessThanOrEqual(1);
    expect(f).toBe(climateDerateFactor());
  });
});

// ——— WJ70 — sélecteur distributeur honnête ———
describe('WJ70 — distributeurHonestyNote : honnêteté plutôt qu\'une fausse promesse', () => {
  it('Lydec/Redal sont encore égalées au barème ONEE (la raison d\'être de la note)', () => {
    expect(TARIFF_BY_CITY.Casablanca).toBe(tariffForCity()); // REGIE_TARIFF
    expect(tariffForCity('Casablanca')).toEqual(tariffForCity('Rabat'));
    expect(tariffForCity('Casablanca')).toEqual(tariffForCity(undefined));
  });

  it('renvoie un texte non vide en FR et en AR', () => {
    const fr = distributeurHonestyNote('fr');
    const ar = distributeurHonestyNote('ar');
    expect(fr.length).toBeGreaterThan(0);
    expect(ar.length).toBeGreaterThan(0);
    expect(fr).not.toBe(ar);
    // Mentionne ONEE/le caractère conservateur, jamais un chiffre inventé.
    expect(fr.toLowerCase()).toContain('onee');
  });

  it('FR est la langue par défaut', () => {
    expect(distributeurHonestyNote()).toBe(distributeurHonestyNote('fr'));
  });
});

describe('formatMad / formatMadRange — inchangés', () => {
  it('formate un nombre en MAD avec séparateur de milliers', () => {
    expect(formatMad(1200)).toContain('1');
    expect(formatMad(1200)).toContain('200');
  });

  it('formatMadRange affiche une fourchette ou un seul nombre si bornes égales', () => {
    expect(formatMadRange(0, 0)).toBe('—');
    expect(formatMadRange(500, 500)).toBe('500 MAD');
    expect(formatMadRange(300, 500)).toContain('–');
  });
});

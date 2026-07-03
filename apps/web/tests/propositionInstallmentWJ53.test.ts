// WJ53 — Toggle « payer comptant / paiement échelonné » : logique PURE.
// Discipline « zéro taux inventé » : la mensualité est une simple division du
// TTC par le nombre de mois choisi — jamais un taux d'intérêt fabriqué.
import { describe, expect, it } from 'vitest';
import { installmentSplit, INSTALLMENT_MONTH_OPTIONS } from '../src/lib/proposition';

describe('WJ53 — installmentSplit (simple division, aucun taux)', () => {
  it('divise le TTC par le nombre de mois choisi', () => {
    const s = installmentSplit(120000, 12);
    expect(s).not.toBeNull();
    expect(s!.cashTtc).toBe(120000);
    expect(s!.months).toBe(12);
    expect(s!.monthly).toBe(10000);
  });

  it('arrondit au MAD (pas de centimes)', () => {
    const s = installmentSplit(100000, 3);
    expect(s!.monthly).toBe(Math.round(100000 / 3));
  });

  it('couvre toutes les durées proposées par le toggle', () => {
    for (const months of INSTALLMENT_MONTH_OPTIONS) {
      const s = installmentSplit(84000, months);
      expect(s!.months).toBe(months);
      expect(s!.monthly).toBe(Math.round(84000 / months));
    }
  });

  it('mois invalide (hors liste) replie sur 12 mois — jamais un NaN', () => {
    // @ts-expect-error — simule une valeur hors du type littéral (défense en profondeur)
    const s = installmentSplit(120000, 5);
    expect(s!.months).toBe(12);
  });

  it('sans prix réel (zéro/négatif/NaN) → null, jamais un chiffre fabriqué', () => {
    expect(installmentSplit(0, 12)).toBeNull();
    expect(installmentSplit(-500, 12)).toBeNull();
    expect(installmentSplit(NaN, 12)).toBeNull();
  });

  it('défaut = 12 mois quand non précisé', () => {
    const s = installmentSplit(60000);
    expect(s!.months).toBe(12);
  });
});

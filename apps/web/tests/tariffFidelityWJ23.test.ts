// WJ23 — fidélité tarifaire par régie (ONEE/Lydec/Redal) + honnêteté 82-21. On vérifie :
// (1) barèmes éditables par régie ; (2) économie « autoconsommation d'abord » qui efface
// les tranches LES PLUS CHÈRES en premier (tarif marginal capté) ; (3) l'économie ne
// dépasse jamais le coût évitable ; (4) la ligne d'injection de surplus reste OFF/à zéro
// tant que le tarif ANRE n'est pas confirmé (aucun chiffre inventé). Module PUR.
import { describe, expect, it } from 'vitest';
import {
  tariffForUtility,
  makeEditableTariff,
  selfConsumptionFirstSavings,
  surplusInjectionLine,
  billMAD,
  ANRE_TARIFF_CONFIRMED,
  REGIE_TARIFF,
  type TariffGrid,
} from '../src/lib/estimatorBrainV2';

describe('WJ23 — barèmes par régie (éditables)', () => {
  it('ONEE/Lydec/Redal existent (défaut = barème ONEE conservateur)', () => {
    expect(tariffForUtility('ONEE')).toBe(REGIE_TARIFF);
    expect(tariffForUtility('Lydec')).toBeTruthy();
    expect(tariffForUtility('Redal')).toBeTruthy();
    expect(tariffForUtility('Inconnu')).toBe(REGIE_TARIFF); // repli conservateur
  });

  it('makeEditableTariff garantit la dernière tranche sélective ouverte', () => {
    const g = makeEditableTariff(
      [{ upToKwh: 100, rate: 0.9 }],
      [{ upToKwh: 200, rate: 1.1 }, { upToKwh: 500, rate: 1.4 }],
    );
    expect(g.selective[g.selective.length - 1].upToKwh).toBe(Infinity);
  });
});

describe('WJ23 — autoconsommation d’abord (haut de grille effacé en premier)', () => {
  it('efface le tarif marginal (le plus cher) : marginalRate ≈ tarif haut', () => {
    // Conso élevée → mode sélectif, tarif haut (>510 = 1,5958 MAD/kWh sur REGIE).
    const cons = 600;
    const r = selfConsumptionFirstSavings(cons, 100, REGIE_TARIFF);
    // Le marginal effacé doit être proche du haut de grille (bien > le tarif bas ~0,9).
    expect(r.marginalRate).toBeGreaterThan(1.3);
    expect(r.offsetKwh).toBe(100);
    expect(r.monthlyMad).toBeGreaterThan(0);
  });

  it('plus on autoconsomme, plus l’économie TOTALE monte (monotone, jamais négative)', () => {
    // NB : le barème marocain est SÉLECTIF au-dessus du seuil (tout le mois au tarif de
    // sa tranche), donc effacer de la conso peut faire BASCULER dans une tranche moins
    // chère — le tarif marginal MOYEN n'est pas strictement monotone. L'invariant honnête
    // est que l'économie TOTALE croît avec l'autoconsommation et reste ≥ 0.
    const cons = 600;
    const small = selfConsumptionFirstSavings(cons, 50, REGIE_TARIFF);
    const large = selfConsumptionFirstSavings(cons, 550, REGIE_TARIFF);
    expect(large.monthlyMad).toBeGreaterThanOrEqual(small.monthlyMad - 1e-9);
    expect(small.monthlyMad).toBeGreaterThanOrEqual(0);
    expect(large.monthlyMad).toBeGreaterThanOrEqual(0);
  });

  it('économie ≤ coût évitable (jamais au-dessus de la facture)', () => {
    const cons = 400;
    const avoidable = billMAD(cons, REGIE_TARIFF);
    // autoconsommation ABSURDE (plus que la conso) → bornée, économie ≤ facture.
    const r = selfConsumptionFirstSavings(cons, 99999, REGIE_TARIFF);
    expect(r.monthlyMad).toBeLessThanOrEqual(avoidable + 1e-6);
    expect(r.offsetKwh).toBeLessThanOrEqual(cons);
  });

  it('conso ou autoconso nulle → économie nulle', () => {
    expect(selfConsumptionFirstSavings(0, 100).monthlyMad).toBe(0);
    expect(selfConsumptionFirstSavings(300, 0).monthlyMad).toBe(0);
  });

  it('fonctionne avec une grille éditée par l’utilisateur', () => {
    const g: TariffGrid = makeEditableTariff(
      [{ upToKwh: 100, rate: 1.0 }],
      [{ upToKwh: 300, rate: 1.5 }, { upToKwh: 999999, rate: 2.0 }],
      150, 10,
    );
    const r = selfConsumptionFirstSavings(400, 50, g);
    expect(r.monthlyMad).toBeGreaterThan(0);
    expect(r.monthlyMad).toBeLessThanOrEqual(billMAD(400, g) + 1e-6);
  });
});

describe('WJ23 — ligne injection surplus (82-21) OFF tant que l’ANRE non confirmé', () => {
  it('par défaut : désactivée, valeur zéro, label « en attente du tarif ANRE »', () => {
    expect(ANRE_TARIFF_CONFIRMED).toBe(false);
    const line = surplusInjectionLine(3000);
    expect(line.enabled).toBe(false);
    expect(line.valueMad).toBe(0);
    expect(line.label).toContain('ANRE');
    expect(line.surplusKwh).toBe(3000);
  });

  it('reste à zéro même si un tarif est passé mais non confirmé', () => {
    const line = surplusInjectionLine(3000, false, 0.8);
    expect(line.enabled).toBe(false);
    expect(line.valueMad).toBe(0);
  });

  it('valorise le surplus UNIQUEMENT quand confirmé + tarif > 0', () => {
    const line = surplusInjectionLine(3000, true, 0.8);
    expect(line.enabled).toBe(true);
    expect(line.valueMad).toBeCloseTo(2400, 6);
  });

  it('confirmé mais tarif 0 → reste off (aucun chiffre inventé)', () => {
    const line = surplusInjectionLine(3000, true, 0);
    expect(line.enabled).toBe(false);
    expect(line.valueMad).toBe(0);
  });
});

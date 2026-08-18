// ORDRE FONDATEUR (18/08) — ÉCONOMIES RÉELLES, AU BARÈME.
//
// « For the estimator I want a real saving calculation because the client will
//   go down in the price per kWh because he will be below 500 kWh per month —
//   I want the new price per kWh to be used so the savings are real. »
//
// Le barème résidentiel marocain n'est pas un tarif moyen : il est progressif
// jusqu'au seuil, puis SÉLECTIF (toute la consommation est facturée au tarif de
// SA tranche). Un foyer à 700 kWh/mois paie donc 1,5958 MAD/kWh sur la TOTALITÉ
// de sa consommation ; une fois le solaire passé, son résiduel de 280 kWh/mois
// retombe dans la tranche ≤ 300 et se facture 1,1676 MAD/kWh — sur la totalité
// lui aussi. L'économie réelle = facture(avant) − facture(après), mois par mois
// (jamais annualisée avant d'être tarifée : le seuil des 500 kWh est MENSUEL).
//
// Ce fichier verrouille ce comportement de bout en bout, avec les chiffres
// dérivés à la main depuis REGIE_TARIFF (barème du cerveau, WJ23).
import { describe, expect, it } from 'vitest';
import {
  REGIE_TARIFF,
  annualSavingsMad,
  billMAD,
  billToAnnualKwh,
  selfConsumptionFirstSavings,
} from '../src/lib/estimatorBrainV2';

/** Tarif marginal du haut de grille (> 510 kWh/mois) — REGIE_TARIFF. */
const TARIF_HAUT = 1.5958;
/** Tarif de la tranche 211–310 kWh/mois. */
const TARIF_300 = 1.1676;

describe('Barème : le seuil des 500 kWh/mois existe vraiment', () => {
  it('la grille porte bien la marche 500 kWh et le haut de grille', () => {
    const bandes = REGIE_TARIFF.selective.map((b) => [b.upToKwh, b.rate]);
    expect(bandes).toContainEqual([500, 1.3817]);
    expect(bandes).toContainEqual([Infinity, TARIF_HAUT]);
  });

  it('le prix EFFECTIF du kWh chute quand on passe sous 500 kWh/mois', () => {
    // 700 kWh/mois : 700 × 1,5958 = 1 117,06 MAD → 1,5958 MAD/kWh effectif.
    // 280 kWh/mois : 280 × 1,1676 =   326,93 MAD → 1,1676 MAD/kWh effectif.
    expect(billMAD(700)).toBeCloseTo(1117.06, 2);
    expect(billMAD(700) / 700).toBeCloseTo(TARIF_HAUT, 4);
    expect(billMAD(280)).toBeCloseTo(326.93, 2);
    expect(billMAD(280) / 280).toBeCloseTo(TARIF_300, 4);
    // C'est la baisse de prix par kWh que le fondateur décrit.
    expect(billMAD(280) / 280).toBeLessThan(billMAD(700) / 700);
  });
});

describe('SCÉNARIO FONDATEUR — 700 kWh/mois, résiduel sous 500', () => {
  // Dérivation à la main (REGIE_TARIFF) :
  //   conso            700 kWh/mois → facture 700 × 1,5958   = 1 117,06 MAD
  //   autoconsommé     420 kWh/mois (60 % — l'ordre de grandeur solaire)
  //   résiduel         280 kWh/mois → facture 280 × 1,1676   =   326,93 MAD
  //   économie réelle  1 117,06 − 326,93                     =   790,13 MAD/mois
  //                                                    ×12   = 9 481,6 MAD/an
  const CONSO_MOIS = 700;
  const AUTO_MOIS = 420;

  it('économie = facture(avant) − facture(après), au barème', () => {
    const s = selfConsumptionFirstSavings(CONSO_MOIS, AUTO_MOIS);
    expect(s.monthlyMad).toBeCloseTo(790.13, 2);
    expect(s.monthlyMad).toBeCloseTo(billMAD(700) - billMAD(280), 9);
    expect(s.offsetKwh).toBe(AUTO_MOIS);
  });

  it('le passage sous le seuil vaut PLUS que les kWh évités au tarif marginal', () => {
    // 420 kWh × 1,5958 = 670,24 MAD si l'on valorisait « à l'ancien prix ».
    // L'économie réelle est de 790,13 MAD, soit 1,179× plus : en descendant
    // sous 510 kWh, le client ne fait pas qu'effacer 420 kWh — il RE-TARIFE
    // les 280 kWh qui restent (1,5958 → 1,1676). C'est la marche sélective du
    // barème marocain ; la sous-estimer serait mentir dans l'autre sens.
    const auMarginal = AUTO_MOIS * TARIF_HAUT;
    expect(auMarginal).toBeCloseTo(670.24, 2);
    const reel = selfConsumptionFirstSavings(CONSO_MOIS, AUTO_MOIS).monthlyMad;
    expect(reel).toBeGreaterThan(auMarginal);
    expect(reel / auMarginal).toBeCloseTo(1.179, 3);
  });

  it('l’économie ne dépasse JAMAIS la facture évitable (plafond structurel)', () => {
    // Même en autoconsommant tout, on ne peut pas économiser plus que la facture.
    const tout = selfConsumptionFirstSavings(CONSO_MOIS, CONSO_MOIS);
    expect(tout.monthlyMad).toBeCloseTo(billMAD(CONSO_MOIS), 9);
    const trop = selfConsumptionFirstSavings(CONSO_MOIS, CONSO_MOIS * 3);
    expect(trop.monthlyMad).toBeCloseTo(billMAD(CONSO_MOIS), 9);
    expect(trop.offsetKwh).toBe(CONSO_MOIS); // borné à la consommation
  });
});

describe('Chaîne annuelle — jamais annualiser avant de tarifer', () => {
  it('annualSavingsMad tarifie MOIS PAR MOIS (seuil 500 kWh mensuel)', () => {
    // 700 kWh/mois = 8 400 kWh/an ; production 5 040 kWh/an = 420 kWh/mois.
    // La borne haute (alignement temporel parfait) doit retrouver EXACTEMENT
    // les 790,13 MAD/mois × 12 = 9 481,56 MAD/an dérivés ci-dessus.
    const { low, high } = annualSavingsMad(5040, 8400);
    expect(high).toBeCloseTo(790.13 * 12, 1);
    expect(high).toBeCloseTo(9481.56, 1);
    // Borne basse : 75 % de l'autoconsommation réellement synchrone (315 kWh)
    // → résiduel 385 kWh/mois, encore sous 500 mais dans la tranche ≤ 500 :
    // 385 × 1,3817 = 531,9545 MAD → économie 1 117,06 − 531,9545 = 585,1055
    // MAD/mois, soit 7 021,27 MAD/an.
    expect(low).toBeCloseTo(585.1055 * 12, 1);
    expect(low).toBeCloseTo(7021.27, 1);
    expect(low).toBeLessThan(high);
  });

  it('un tarif moyen plat de 1,4 MAD/kWh se serait TROMPÉ sur ce client', () => {
    // L'ancien modèle valorisait la production à 1,4 MAD/kWh :
    // 5 040 kWh × 1,4 = 7 056 MAD/an, puis 60–90 % → 4 234 à 6 350 MAD/an.
    // Le calcul réel donne 9 482 MAD/an : le tarif moyen SOUS-estimait de ~33 %
    // ce client du haut de grille (il paie 1,5958, pas 1,4).
    const platHaut = 5040 * 1.4 * 0.9;
    const { high } = annualSavingsMad(5040, 8400);
    expect(platHaut).toBeCloseTo(6350.4, 1);
    expect(high).toBeGreaterThan(platHaut);
  });
});

describe('Facture → kWh : inverse EXACT du barème, jamais un diviseur plat', () => {
  it('billToAnnualKwh inverse billMAD au kWh près', () => {
    for (const kwhMois of [120, 300, 480, 700, 1200]) {
      const facture = billMAD(kwhMois);
      const retrouve = billToAnnualKwh(facture) / 12;
      expect(retrouve).toBeCloseTo(kwhMois, 3);
    }
  });

  it('un diviseur plat aurait fabriqué des kWh qui n’existent pas', () => {
    // Facture 1 117,06 MAD/mois : le vrai barème dit 700 kWh (tarif 1,5958).
    // Un diviseur « moyen » à 1,4 aurait annoncé 798 kWh — 14 % de trop, donc
    // un système surdimensionné et des économies surévaluées.
    const facture = billMAD(700);
    expect(billToAnnualKwh(facture) / 12).toBeCloseTo(700, 3);
    expect(facture / 1.4).toBeCloseTo(797.9, 1);
  });
});

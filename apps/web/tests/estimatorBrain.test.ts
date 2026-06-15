// Cerveau de l'estimateur piloté par la facture — src/lib/estimatorBrain.ts.
// Module PUR (aucun DOM, aucune carte) : géométrie d'espacement solaire,
// pavage portrait/paysage, sous-champs Est-Ouest, productible depuis la table
// PVGIS committée, et l'algorithme de recommandation (les 3 branches).
// Voir apps/web/ESTIMATOR_BRAIN_NOTES.md.
import { describe, expect, it } from 'vitest';
import {
  sunPositionWinterSolstice,
  rowPitchM,
  specificYield,
  billToAnnualKwh,
  packConfig,
  recommend,
  annualSavingsMad,
  productionKwh,
  billMAD,
  DESIGN_SOLAR_HOUR,
  PANEL2_WATT,
} from '../src/lib/estimatorBrain';
import { type LngLat } from '../src/lib/roof';

// Tracé carré de `side` mètres centré sur (lng0, lat0).
function squareRing(side: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

describe('sunPositionWinterSolstice — position solaire solstice d’hiver', () => {
  it('midi solaire à Casablanca : élévation ≈ 32,9°, azimut ≈ 0° (plein sud)', () => {
    const noon = sunPositionWinterSolstice(33.59, 12);
    expect(noon.elevationDeg).toBeCloseTo(32.9, 0);
    expect(Math.abs(noon.azimuthFromSouthDeg)).toBeLessThan(0.5);
  });

  it('à 10 h le soleil est plus bas et nettement à l’est du sud', () => {
    const morning = sunPositionWinterSolstice(33.59, 10);
    const noon = sunPositionWinterSolstice(33.59, 12);
    expect(morning.elevationDeg).toBeLessThan(noon.elevationDeg);
    expect(morning.elevationDeg).toBeCloseTo(26.2, 0);
    expect(Math.abs(morning.azimuthFromSouthDeg)).toBeGreaterThan(20);
  });

  it('le moment de design par défaut est 10 h', () => {
    expect(DESIGN_SOLAR_HOUR).toBe(10);
  });
});

describe('rowPitchM — pas inter-rangées par géométrie solaire', () => {
  it('Casablanca 29° portrait (L=2,384) au soleil de 10 h : pas ≈ 4,1 m (+ marge sécurité)', () => {
    // Ancre brief ≈ 4,1 m (géométrique) ; +0,05 m de marge construction → ~4,15 m.
    const p = rowPitchM(2.384, 29, 33.59);
    expect(p).toBeGreaterThan(4.0);
    expect(p).toBeLessThan(4.25);
  });

  it('Casablanca 29° portrait au midi solaire : pas ≈ 3,9 m (plus dense)', () => {
    const noon = rowPitchM(2.384, 29, 33.59, { solarHour: 12 });
    expect(noon).toBeCloseTo(3.9, 1);
    expect(noon).toBeLessThan(rowPitchM(2.384, 29, 33.59));
  });

  it('le pas DÉCROÎT quand l’inclinaison baisse (29° → 15° → 10°)', () => {
    const p29 = rowPitchM(2.384, 29, 33.59);
    const p15 = rowPitchM(2.384, 15, 33.59);
    const p10 = rowPitchM(2.384, 10, 33.59);
    expect(p15).toBeLessThan(p29);
    expect(p10).toBeLessThan(p15);
  });
});

describe('specificYield — productible depuis la table committée', () => {
  it('Casablanca sud (aspect 0) optimal ≈ 1 650 kWh/kWc/an (bande 1 650–1 900)', () => {
    const y = specificYield(33.59, 30, 0);
    expect(y).toBeGreaterThanOrEqual(1600);
    expect(y).toBeLessThanOrEqual(1900);
  });

  it('le sud (0°) rend plus que l’est (−90°) à inclinaison optimale', () => {
    expect(specificYield(33.59, 29, 0)).toBeGreaterThan(specificYield(33.59, 29, -90));
  });

  it('interpole entre deux villes pour une latitude intermédiaire', () => {
    const cas = specificYield(33.59, 30, 0);
    const rab = specificYield(34.02, 30, 0);
    const mid = specificYield((33.59 + 34.02) / 2, 30, 0);
    const lo = Math.min(cas, rab);
    const hi = Math.max(cas, rab);
    expect(mid).toBeGreaterThanOrEqual(lo - 1);
    expect(mid).toBeLessThanOrEqual(hi + 1);
  });
});

describe('billMAD — modèle ONEE BT domestique (progressif ≤150, sélectif au-delà)', () => {
  it('progressif sous 150 kWh : 100×0,90 + 50×1,07 = 143,5 MAD à 150 kWh', () => {
    expect(billMAD(100)).toBeCloseTo(90, 2);
    expect(billMAD(150)).toBeCloseTo(143.5, 2);
  });

  it('sélectif au-delà de 150 : TOUTE la conso au tarif de sa tranche', () => {
    // 250 kWh → tranche 201–300 (1,18) sur tout : 250×1,18 = 295.
    expect(billMAD(250)).toBeCloseTo(250 * 1.18, 2);
    // 600 kWh → tranche >500 (1,66) : 600×1,66 = 996.
    expect(billMAD(600)).toBeCloseTo(600 * 1.66, 2);
  });

  it('est MONOTONE non-décroissante (y compris aux bornes de tranche)', () => {
    let prev = -1;
    for (let k = 0; k <= 1200; k += 1) {
      const b = billMAD(k);
      expect(b, `billMAD(${k})=${b} < billMAD(${k - 1})=${prev}`).toBeGreaterThanOrEqual(prev - 1e-9);
      prev = b;
    }
  });

  it('un client à 501 kWh ne paie jamais moins qu’à 500 (garantie de bord)', () => {
    expect(billMAD(501)).toBeGreaterThanOrEqual(billMAD(500));
  });
});

describe('billToAnnualKwh — inversion numérique du modèle sélectif', () => {
  it('1 500 MAD/mois → ~10 000–11 000 kWh/an (PAS ~15 385 de l’ancien diviseur plat)', () => {
    const kwh = billToAnnualKwh(1500);
    expect(kwh).toBeGreaterThanOrEqual(10000);
    expect(kwh).toBeLessThanOrEqual(11000);
  });
  it('inverse billMAD pour des factures atteignables (la facturation sélective a des sauts)', () => {
    // 1 500 et 2 500 tombent dans la tranche haute (continue) → inversion exacte.
    expect(billMAD(billToAnnualKwh(1500) / 12)).toBeCloseTo(1500, 0);
    expect(billMAD(billToAnnualKwh(2500) / 12)).toBeCloseTo(2500, 0);
  });
  it('croît avec la facture', () => {
    expect(billToAnnualKwh(3000)).toBeGreaterThan(billToAnnualKwh(1000));
  });
});

describe('packConfig — pavage portrait ET paysage, sud et Est-Ouest', () => {
  it('calcule portrait ET paysage et garde le meilleur compte', () => {
    const ring = squareRing(30);
    const r = packConfig(ring, 33.59, { family: 'south', tiltDeg: 29 });
    expect(r.portrait.count).toBeGreaterThan(0);
    expect(r.landscape.count).toBeGreaterThan(0);
    expect(r.best.count).toBe(Math.max(r.portrait.count, r.landscape.count));
    expect(r.best.kwc).toBeCloseTo((r.best.count * PANEL2_WATT) / 1000, 6);
  });

  it('15° pose plus de panneaux que 29° (pas plus serré)', () => {
    const ring = squareRing(30);
    const t29 = packConfig(ring, 33.59, { family: 'south', tiltDeg: 29 });
    const t15 = packConfig(ring, 33.59, { family: 'south', tiltDeg: 15 });
    expect(t15.best.count).toBeGreaterThan(t29.best.count);
  });

  it('l’Est-Ouest @10° loge PLUS de kWc que le sud optimal sur le même toit', () => {
    const ring = squareRing(30);
    const south = packConfig(ring, 33.59, { family: 'south', tiltDeg: 29 });
    const ew = packConfig(ring, 33.59, { family: 'eastwest', tiltDeg: 10 });
    expect(ew.best.kwc).toBeGreaterThan(south.best.kwc);
  });

  it('un tracé minuscule ou invalide → zéro panneau', () => {
    expect(packConfig(squareRing(2), 33.59, { family: 'south', tiltDeg: 29 }).best.count).toBe(0);
    expect(
      packConfig([[0, 0], [1, 1]] as LngLat[], 33.59, { family: 'south', tiltDeg: 29 }).best.count,
    ).toBe(0);
  });

  it('une obstruction retire des panneaux', () => {
    const ring = squareRing(30);
    const center: LngLat = [-7.62, 33.59];
    const d = 5 / 111320;
    const dLng = 5 / (111320 * Math.cos((33.59 * Math.PI) / 180));
    const obstruction: LngLat[] = [
      [center[0] - dLng, center[1] - d],
      [center[0] + dLng, center[1] - d],
      [center[0] + dLng, center[1] + d],
      [center[0] - dLng, center[1] + d],
    ];
    const without = packConfig(ring, 33.59, { family: 'south', tiltDeg: 15 });
    const withObs = packConfig(ring, 33.59, { family: 'south', tiltDeg: 15, obstructions: [obstruction] });
    expect(withObs.best.count).toBeLessThan(without.best.count);
  });
});

describe('recommend — l’algorithme (les 3 branches)', () => {
  it('BRANCHE « couvre à 29° » : grand toit + petite facture → sud optimal, dimensionné au besoin', () => {
    const ring = squareRing(40); // grand toit
    const rec = recommend(ring, 33.59, 1000); // facture modeste
    expect(rec.recommended.family).toBe('south');
    expect(rec.recommended.tiltDeg).toBeGreaterThanOrEqual(25); // proche de l’optimal
    // dimensionné au besoin : couvre la cible mais NE remplit PAS tout le toit
    expect(rec.recommended.annualKwh).toBeGreaterThanOrEqual(rec.targetAnnualKwh);
    expect(rec.recommended.count).toBeLessThan(rec.recommended.roofMaxCount);
    expect(rec.comparison.length).toBeGreaterThanOrEqual(4);
  });

  it('BRANCHE « densifie » : sud optimal ne couvre pas mais une config plus dense oui', () => {
    // side 11 : sud-opt ≈ 19 020 kWh < cible 2 800 MAD (≈ 20 240) < sud-15 ≈ 24 130.
    const ring = squareRing(11);
    const rec = recommend(ring, 33.59, 2800);
    expect(rec.recommended.id).not.toBe('south-opt'); // a dû densifier
    expect(rec.recommended.annualKwh).toBeGreaterThanOrEqual(rec.targetAnnualKwh);
    expect(rec.recommended.tiltDeg).toBeLessThanOrEqual(29);
    expect(rec.roofLimited).toBe(false);
    expect(rec.comparison.length).toBeGreaterThanOrEqual(4);
  });

  it('BRANCHE « plafond toit » : toit minuscule + facture énorme → E-O max + message honnête', () => {
    const ring = squareRing(10);
    const rec = recommend(ring, 33.59, 9000);
    expect(rec.recommended.annualKwh).toBeLessThan(rec.targetAnnualKwh);
    expect(rec.roofLimited).toBe(true);
    expect(rec.recommended.family).toBe('eastwest');
    expect(rec.recommended.pctOfTarget).toBeLessThan(100);
  });

  it('expose « max par panneau (≈29°) » vs « max sur ce toit (X°) »', () => {
    const ring = squareRing(20);
    const rec = recommend(ring, 33.59, 5000);
    expect(rec.maxPerPanelTiltDeg).toBeGreaterThanOrEqual(25);
    expect(rec.maxPerPanelTiltDeg).toBeLessThanOrEqual(35);
    // sur un toit limité, l’angle « max énergie totale » est ≤ l’optimal par panneau
    expect(rec.maxRoofEnergyTiltDeg).toBeLessThanOrEqual(rec.maxPerPanelTiltDeg);
    expect(rec.maxRoofEnergyTiltDeg).toBeGreaterThan(0);
  });

  it('chaque config du comparatif porte compte · kWc · kWh · % cible · économies', () => {
    const ring = squareRing(25);
    const rec = recommend(ring, 33.59, 2500);
    for (const c of rec.comparison) {
      expect(c.count).toBeGreaterThanOrEqual(0);
      expect(c.kwc).toBeGreaterThanOrEqual(0);
      expect(c.annualKwh).toBeGreaterThanOrEqual(0);
      expect(c.pctOfTarget).toBeGreaterThanOrEqual(0);
      expect(c.savingsLow).toBeGreaterThanOrEqual(0);
      expect(c.savingsHigh).toBeGreaterThanOrEqual(c.savingsLow);
      expect(typeof c.label).toBe('string');
    }
  });
});

// ——— FIXES DE CORRECTNESS : bornes physiques dures ———

const FAMILIES = ['south', 'eastwest'] as const;
const TILTS = [10, 15, 29] as const;

describe('FIX 1a — Σ empreintes au sol ≤ surface utile (panneaux jamais superposés)', () => {
  for (const side of [16, 24, 40]) {
    for (const family of FAMILIES) {
      for (const tiltDeg of TILTS) {
        it(`${family} ${tiltDeg}° sur ${side} m : Σ empreintes ≤ surface utile`, () => {
          const pack = packConfig(squareRing(side), 33.59, { family, tiltDeg });
          for (const grid of [pack.portrait, pack.landscape]) {
            const sumFootprints = grid.count * grid.footprintPerPanelM2;
            expect(sumFootprints).toBeLessThanOrEqual(pack.usableAreaM2 + 1e-6);
          }
        });
      }
    }
  }

  it('une obstruction réduit la surface utile et le compte tient encore la borne', () => {
    const ring = squareRing(30);
    const d = 4 / 111320;
    const dLng = 4 / (111320 * Math.cos((33.59 * Math.PI) / 180));
    const c: LngLat = [-7.62, 33.59];
    const obs: LngLat[] = [
      [c[0] - dLng, c[1] - d],
      [c[0] + dLng, c[1] - d],
      [c[0] + dLng, c[1] + d],
      [c[0] - dLng, c[1] + d],
    ];
    const pack = packConfig(ring, 33.59, { family: 'eastwest', tiltDeg: 10, obstructions: [obs] });
    expect(pack.usableAreaM2).toBeLessThan(pack.areaM2);
    expect(pack.best.count * pack.best.footprintPerPanelM2).toBeLessThanOrEqual(pack.usableAreaM2 + 1e-6);
  });
});

describe('FIX 2 — Est-Ouest ≥ Sud à inclinaison ÉGALE (les chevrons récupèrent l’ombre)', () => {
  // Vérité physique : à inclinaison égale, l'E-O dos à dos récupère l'intervalle
  // d'ombre que le Sud gaspille → compte E-O ≥ compte Sud (sur toit à aspect neutre).
  // Et Σ empreintes ≤ surface utile reste vrai pour chaque config.
  for (const side of [16, 24, 40, 48]) {
    for (const tiltDeg of [10, 15] as const) {
      it(`carré ${side} m @${tiltDeg}° : E-O ≥ Sud, et bornes empreinte respectées`, () => {
        const ring = squareRing(side);
        const south = packConfig(ring, 33.59, { family: 'south', tiltDeg });
        const ew = packConfig(ring, 33.59, { family: 'eastwest', tiltDeg });
        expect(ew.best.count).toBeGreaterThanOrEqual(south.best.count);
        for (const pack of [south, ew]) {
          for (const grid of [pack.portrait, pack.landscape]) {
            expect(grid.count * grid.footprintPerPanelM2).toBeLessThanOrEqual(pack.usableAreaM2 + 1e-6);
          }
        }
      });
    }
  }

  it('converge (égalité possible) mais ne descend jamais sous le Sud à 10°', () => {
    const ring = squareRing(30);
    const s = packConfig(ring, 33.59, { family: 'south', tiltDeg: 10 });
    const e = packConfig(ring, 33.59, { family: 'eastwest', tiltDeg: 10 });
    expect(e.best.count).toBeGreaterThanOrEqual(s.best.count);
  });
});

describe('FIX 1c — UNE seule règle d’espacement solaire ; E-O n’a pas de densité codée en dur', () => {
  it('le pas E-O dépend de la latitude (donc du soleil), il n’est pas constant', () => {
    const ring = squareRing(40);
    const ewLow = packConfig(ring, 20, { family: 'eastwest', tiltDeg: 15 });
    const ewHigh = packConfig(ring, 50, { family: 'eastwest', tiltDeg: 15 });
    // latitude plus haute → ombres plus longues → pas plus grand → moins de panneaux
    expect(ewHigh.best.rowPitchM).toBeGreaterThan(ewLow.best.rowPitchM);
    expect(ewHigh.best.count).toBeLessThanOrEqual(ewLow.best.count);
  });
});

describe('FIX 1d — pas de perte de la rangée/colonne de rive (bug flottant sin 180°)', () => {
  it('un petit toit pave bien sa rive : Sud 12×10 @10° loge ≥ 20 panneaux (pas 14)', () => {
    // Régression : sin(180°)≈1e−16 plaçait les cellules de rive à 0,5−ε et les
    // rejetait → toute la 1re rangée + 1re colonne perdues. Corrigé par EDGE_EPS.
    const rect = (w: number, h: number, lng0 = -7.62, lat0 = 33.59): LngLat[] => {
      const dLat = h / 111320;
      const dLng = w / (111320 * Math.cos((lat0 * Math.PI) / 180));
      return [
        [lng0 - dLng / 2, lat0 - dLat / 2],
        [lng0 + dLng / 2, lat0 - dLat / 2],
        [lng0 + dLng / 2, lat0 + dLat / 2],
        [lng0 - dLng / 2, lat0 + dLat / 2],
      ];
    };
    const south = packConfig(rect(12, 10), 33.59, { family: 'south', tiltDeg: 10 });
    expect(south.best.count).toBeGreaterThanOrEqual(20);
  });

  it('compte cohérent en tournant le toit de 90° (la rive n’est plus perdue)', () => {
    const rect = (w: number, h: number, lng0 = -7.62, lat0 = 33.59): LngLat[] => {
      const dLat = h / 111320;
      const dLng = w / (111320 * Math.cos((lat0 * Math.PI) / 180));
      return [
        [lng0 - dLng / 2, lat0 - dLat / 2],
        [lng0 + dLng / 2, lat0 - dLat / 2],
        [lng0 + dLng / 2, lat0 + dLat / 2],
        [lng0 - dLng / 2, lat0 + dLat / 2],
      ];
    };
    // Le bug donnait 12×10→14 mais 10×12→10 (incohérent). Désormais les deux
    // pavent leur rive ; l'écart restant est de la vraie géométrie (aspect).
    const a = packConfig(rect(12, 10), 33.59, { family: 'south', tiltDeg: 10 }).best.count;
    const b = packConfig(rect(10, 12), 33.59, { family: 'south', tiltDeg: 10 }).best.count;
    expect(Math.min(a, b)).toBeGreaterThanOrEqual(16);
  });
});

describe('FIX 1/2 — économies = réduction de la facture énergie, jamais > billMAD(conso)', () => {
  it('un système surdimensionné (prod ≫ conso) plafonne au coût énergie évitable', () => {
    const consumption = 8000; // kWh/an
    const energyBill = billMAD(consumption / 12) * 12; // coût énergie annuel
    const s = annualSavingsMad(20000, consumption); // prod = 2,5× conso
    expect(s.high).toBeLessThanOrEqual(energyBill + 1e-6);
    expect(s.high).toBeGreaterThan(0);
    expect(s.low).toBeLessThanOrEqual(s.high);
  });

  it('autoconsommation partielle = vraie réduction de facture (efface le kWh cher d’abord)', () => {
    // conso 8000/an (≈667/mois), prod 3000/an (≈250/mois) toute autoconsommée.
    const s = annualSavingsMad(3000, 8000);
    const expected = (billMAD(8000 / 12) - billMAD(8000 / 12 - 3000 / 12)) * 12;
    expect(s.high).toBeCloseTo(expected, 0);
    expect(s.high).toBeGreaterThan(0);
  });

  it('chaque config affichée : économies ≤ coût énergie de la consommation', () => {
    for (const side of [12, 20, 30]) {
      const rec = recommend(squareRing(side), 33.59, 1500);
      const cap = billMAD(rec.targetAnnualKwh / 12) * 12 + 1e-6;
      for (const c of [...rec.comparison, rec.recommended]) {
        expect(c.savingsHigh, `${c.label}`).toBeLessThanOrEqual(cap);
      }
    }
  });
});

describe('FIX 3 — un seul modèle ONEE sélectif (plus de tarif moyen/marginal plat)', () => {
  it('la conso vient de l’inversion du modèle sélectif ; facture énergie exposée', () => {
    const bill = 1500;
    const rec = recommend(squareRing(40), 33.59, bill);
    expect(rec.targetAnnualKwh).toBeGreaterThanOrEqual(10000);
    expect(rec.targetAnnualKwh).toBeLessThanOrEqual(11000);
    // facture énergie modélisée ≈ facture saisie × 12, tarif effectif cohérent.
    expect(rec.annualBillMad).toBeCloseTo(bill * 12, -2);
    expect(rec.effectiveRateMadPerKwh).toBeGreaterThan(1.5); // grosse facture → tranche haute
    expect(rec.effectiveRateMadPerKwh).toBeLessThanOrEqual(1.67); // ≈ 1,66 (tranche >500)
  });
});

describe('FIX — productionKwh Est-Ouest = moitié Est + moitié Ouest (inchangé)', () => {
  it('somme les deux sous-champs', () => {
    const kwc = 10;
    const ew = productionKwh(33.59, 'eastwest', 10, kwc);
    const south = productionKwh(33.59, 'south', 29, kwc);
    expect(ew).toBeGreaterThan(0);
    expect(south).toBeGreaterThan(ew); // sud optimal rend plus par kWc
  });
});

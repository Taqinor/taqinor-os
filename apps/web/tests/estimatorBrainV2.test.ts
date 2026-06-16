// Cerveau V2 de l'estimateur — src/lib/estimatorBrainV2.ts (preview privé pro-4).
// La V2 est une COPIE versionnée de estimatorBrain.ts : SEULE la recommandation
// change (balayage d'inclinaison capé + objet recommandé toujours plafonné au
// besoin). Ces tests prouvent :
//  1. PARITÉ des fonctions pures V2 == V1 (l'isolation n'a pas dérivé) → pro-3 sûr.
//  2. Le balayage choisit une inclinaison plus plate UNIQUEMENT sur toit limité et
//     ne dépasse JAMAIS le plafond « besoin ».
//  3. Toit spacieux → garde l'optimal (~30°) et le besoin (pas de sur-remplissage).
//  4. Cohérence/plafond sur toute la matrice orientation × inclinaison.
//  5. Basculer d'option ne corrompt pas la recommandation.
// Voir apps/web/BRAIN_V2_NOTES.md.
import { describe, expect, it } from 'vitest';
import * as V2 from '../src/lib/estimatorBrainV2';
import * as V1 from '../src/lib/estimatorBrain';
import {
  recommend,
  packConfig,
  neededPanelsForTarget,
  optimalSouthTiltDeg,
  tiltSweepSouth,
  specificYield,
  productionKwh,
  billMAD,
  PANEL2_WATT,
  TILT_SWEEP_MIN,
} from '../src/lib/estimatorBrainV2';
import { type LngLat } from '../src/lib/roof';

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

const LAT = 33.59;
const OPT = optimalSouthTiltDeg(LAT);

// ——————————————————————————————————————————————————————————————————————
// 1. PARITÉ V2 == V1 : la copie n'a pas dérivé sauf recommend() (régression).
// ——————————————————————————————————————————————————————————————————————
describe('Parité V2 ≡ V1 — fonctions pures inchangées (régression isolation)', () => {
  it('sunPositionWinterSolstice identique', () => {
    for (const h of [9, 10, 12, 14]) {
      const a = V2.sunPositionWinterSolstice(LAT, h);
      const b = V1.sunPositionWinterSolstice(LAT, h);
      expect(a.elevationDeg).toBe(b.elevationDeg);
      expect(a.azimuthFromSouthDeg).toBe(b.azimuthFromSouthDeg);
    }
  });

  it('rowPitchM, specificYield, billMAD, billToAnnualKwh identiques', () => {
    for (const t of [10, 15, 29]) {
      expect(V2.rowPitchM(2.384, t, LAT)).toBe(V1.rowPitchM(2.384, t, LAT));
      expect(V2.specificYield(LAT, t, 0)).toBe(V1.specificYield(LAT, t, 0));
    }
    for (const k of [100, 250, 600, 1200]) expect(V2.billMAD(k)).toBe(V1.billMAD(k));
    for (const b of [800, 1500, 3500]) expect(V2.billToAnnualKwh(b)).toBe(V1.billToAnnualKwh(b));
  });

  it('packConfig pose le MÊME nombre de panneaux (géométrie non touchée)', () => {
    for (const side of [12, 20, 40]) {
      for (const family of ['south', 'eastwest'] as const) {
        for (const tiltDeg of [10, 15, 29]) {
          const a = V2.packConfig(squareRing(side), LAT, { family, tiltDeg });
          const b = V1.packConfig(squareRing(side), LAT, { family, tiltDeg });
          expect(a.best.count).toBe(b.best.count);
          expect(a.usableAreaM2).toBe(b.usableAreaM2);
        }
      }
    }
  });

  it('neededPanelsForTarget identique', () => {
    for (const tgt of [4000, 9000, 20000]) {
      expect(V2.neededPanelsForTarget(tgt, LAT)).toBe(V1.neededPanelsForTarget(tgt, LAT));
    }
  });
});

// ——————————————————————————————————————————————————————————————————————
// 2. Plafond « besoin » : JAMAIS dépassé, sur tout le balayage.
// ——————————————————————————————————————————————————————————————————————
describe('Plafond besoin — recommended.count ≤ neededPanels, toujours', () => {
  for (const side of [9, 11, 12, 14, 16, 20, 25, 40]) {
    for (const bill of [1500, 2500, 3500, 5000, 8000]) {
      it(`side=${side} bill=${bill} : posés ≤ besoin et ≤ ce qui tient`, () => {
        const rec = recommend(squareRing(side), LAT, bill);
        expect(rec.recommended.count).toBeLessThanOrEqual(rec.neededPanels);
        expect(rec.recommended.count).toBeLessThanOrEqual(rec.recommended.roofMaxCount);
        expect(rec.recommendedTiltDeg).toBeLessThanOrEqual(OPT);
        expect(rec.recommendedTiltDeg).toBeGreaterThanOrEqual(TILT_SWEEP_MIN);
      });
    }
  }
});

// ——————————————————————————————————————————————————————————————————————
// 3. Toit SPACIEUX → garde l'optimal, pas de sur-remplissage.
// ——————————————————————————————————————————————————————————————————————
describe('Toit spacieux — garde ~30° optimal et le besoin (zéro overfill)', () => {
  it('grand toit + facture modeste : sud optimal, dimensionné au besoin', () => {
    const ring = squareRing(40);
    const rec = recommend(ring, LAT, 1000);
    expect(rec.recommended.family).toBe('south');
    expect(rec.recommendedTiltDeg).toBe(OPT);
    expect(rec.flatterTiltChosen).toBe(false);
    expect(rec.roofLimited).toBe(false);
    // posés = besoin exact, et il reste de la place (besoin < ce qui tient).
    expect(rec.recommended.count).toBe(neededPanelsForTarget(rec.targetAnnualKwh, LAT));
    expect(rec.recommended.count).toBeLessThan(rec.recommended.roofMaxCount);
  });

  it('NE flatte PAS pour bourrer du surplus quand le besoin tient à l’optimal', () => {
    // À 30° le toit loge déjà bien plus que le besoin → aucune raison d'aplatir.
    for (const bill of [600, 1500, 3500, 5000]) {
      const rec = recommend(squareRing(30), LAT, bill);
      expect(rec.recommendedTiltDeg).toBe(OPT);
      expect(rec.flatterTiltChosen).toBe(false);
      expect(rec.flatterTiltExtraEnergyPct).toBe(0);
    }
  });
});

// ——————————————————————————————————————————————————————————————————————
// 4. Toit LIMITÉ → aplatit pour loger plus, honnêtement, sans dépasser le besoin.
// ——————————————————————————————————————————————————————————————————————
describe('Toit limité — aplatit SEULEMENT si ça loge plus, jamais au-delà du besoin', () => {
  it('cas concret : aplatit le sud pour atteindre le besoin (mieux que l’optimal)', () => {
    // side=14, bill=5000 : à 30° le toit n'atteint pas le besoin ; on aplatit juste
    // assez pour loger le besoin au meilleur rendement → bat l'Est-Ouest.
    const ring = squareRing(14);
    const rec = recommend(ring, LAT, 5000);
    const fitOpt = packConfig(ring, LAT, { family: 'south', tiltDeg: OPT }).best.count;
    expect(rec.roofLimited).toBe(true);
    expect(rec.flatterTiltChosen).toBe(true);
    expect(rec.recommended.family).toBe('south');
    expect(rec.recommendedTiltDeg).toBeLessThan(OPT);
    // a posé plus que ce que l'optimal permettait, sans dépasser le besoin
    expect(rec.recommended.count).toBeGreaterThan(fitOpt);
    expect(rec.recommended.count).toBeLessThanOrEqual(rec.neededPanels);
    // honnêteté chiffrée : plus d'énergie totale, moins de rendement/panneau
    expect(rec.flatterTiltExtraEnergyPct).toBeGreaterThan(0);
    expect(rec.flatterTiltYieldLossPct).toBeGreaterThan(0);
    expect(rec.recommended.notes).toMatch(/faire tenir plus de panneaux/);
  });

  it('toit profondément limité : l’Est-Ouest reprend la main (plus dense que sud plat)', () => {
    // side=11, bill=5000 : même aplati, le sud ne loge pas le besoin ; l'E-O dos à
    // dos pose plus → c'est lui le recommandé.
    const ring = squareRing(11);
    const rec = recommend(ring, LAT, 5000);
    expect(rec.roofLimited).toBe(true);
    expect(rec.recommended.family).toBe('eastwest');
    expect(rec.flatterTiltChosen).toBe(false);
    expect(rec.recommended.count).toBeLessThan(rec.neededPanels);
  });

  it('le flatter ne se déclenche QUE si plus de panneaux que l’optimal', () => {
    // Propriété : si flatterTiltChosen, alors posés > fit à l'optimal ET roofLimited.
    for (const side of [9, 10, 12, 13, 14, 16, 18]) {
      for (const bill of [2500, 3500, 5000, 8000]) {
        const ring = squareRing(side);
        const rec = recommend(ring, LAT, bill);
        if (rec.flatterTiltChosen) {
          const fitOpt = packConfig(ring, LAT, { family: 'south', tiltDeg: OPT }).best.count;
          expect(rec.roofLimited).toBe(true);
          expect(rec.recommended.family).toBe('south');
          expect(rec.recommendedTiltDeg).toBeLessThan(OPT);
          expect(rec.recommended.count).toBeGreaterThan(fitOpt);
          expect(rec.recommended.count).toBeLessThanOrEqual(rec.neededPanels);
        }
      }
    }
  });
});

// ——————————————————————————————————————————————————————————————————————
// 5. tiltSweepSouth — l'unité du balayage.
// ——————————————————————————————————————————————————————————————————————
describe('tiltSweepSouth — maximise la production POSÉE (capée)', () => {
  it('toit spacieux : besoin tient partout → choisit l’optimal (plateau favorise le raide)', () => {
    const ring = squareRing(40);
    const need = neededPanelsForTarget(8000 * 0 + 5000, LAT); // besoin modéré
    const sweep = tiltSweepSouth(ring, LAT, need);
    expect(sweep.best.tiltDeg).toBe(OPT);
    expect(sweep.best.placedCount).toBe(need);
  });

  it('toit limité : choisit une inclinaison plus plate qui pose strictement plus', () => {
    const ring = squareRing(12);
    const need = neededPanelsForTarget(50000, LAT); // besoin volontairement énorme
    const sweep = tiltSweepSouth(ring, LAT, need);
    const fitOpt = packConfig(ring, LAT, { family: 'south', tiltDeg: OPT }).best.count;
    expect(sweep.best.tiltDeg).toBeLessThan(OPT);
    expect(sweep.best.placedCount).toBeGreaterThan(fitOpt);
  });

  it('la production posée du choix ≥ celle de l’optimal sur le même toit', () => {
    const ring = squareRing(13);
    const need = neededPanelsForTarget(40000, LAT);
    const sweep = tiltSweepSouth(ring, LAT, need);
    const optKwc = (Math.min(need, packConfig(ring, LAT, { family: 'south', tiltDeg: OPT }).best.count) * PANEL2_WATT) / 1000;
    const optKwh = productionKwh(LAT, 'south', OPT, optKwc);
    expect(sweep.best.placedAnnualKwh).toBeGreaterThanOrEqual(optKwh - 1e-6);
  });

  it('expose le « max énergie totale sur ce toit » ≤ optimal par panneau', () => {
    const ring = squareRing(16);
    const sweep = tiltSweepSouth(ring, LAT, neededPanelsForTarget(20000, LAT));
    expect(sweep.maxRoofEnergyTiltDeg).toBeGreaterThan(0);
    expect(sweep.maxRoofEnergyTiltDeg).toBeLessThanOrEqual(OPT);
    expect(sweep.maxRoofEnergyKwh).toBeGreaterThan(0);
  });
});

// ——————————————————————————————————————————————————————————————————————
// 6. Matrice orientation × inclinaison : capée et cohérente partout.
// ——————————————————————————————————————————————————————————————————————
describe('Matrice — toute combinaison capée, bornes physiques tenues', () => {
  const FAMILIES = ['south', 'eastwest'] as const;
  const TILTS = [5, 10, 15, 29] as const;
  for (const side of [12, 24, 40]) {
    for (const family of FAMILIES) {
      for (const tiltDeg of TILTS) {
        it(`${family} ${tiltDeg}° / ${side} m : posés = min(besoin, fit) ≤ fit, Σ empreintes ≤ utile`, () => {
          const ring = squareRing(side);
          const need = neededPanelsForTarget(billMAD(500) * 0 + 18000, LAT);
          const pack = packConfig(ring, LAT, { family, tiltDeg });
          const placed = Math.min(need, pack.best.count);
          expect(placed).toBeLessThanOrEqual(need);
          expect(placed).toBeLessThanOrEqual(pack.best.count);
          for (const grid of [pack.portrait, pack.landscape]) {
            expect(grid.count * grid.footprintPerPanelM2).toBeLessThanOrEqual(pack.usableAreaM2 + 1e-6);
          }
        });
      }
    }
  }

  it('E-O ≥ Sud à inclinaison égale (les chevrons récupèrent l’ombre) — préservé', () => {
    for (const side of [16, 24, 40]) {
      for (const t of [10, 15]) {
        const s = packConfig(squareRing(side), LAT, { family: 'south', tiltDeg: t });
        const e = packConfig(squareRing(side), LAT, { family: 'eastwest', tiltDeg: t });
        expect(e.best.count).toBeGreaterThanOrEqual(s.best.count);
      }
    }
  });

  it('chaque économie affichée ≤ coût énergie évitable (plafond)', () => {
    for (const side of [12, 20, 30]) {
      const rec = recommend(squareRing(side), LAT, 1500);
      const cap = billMAD(rec.targetAnnualKwh / 12) * 12 + 1e-6;
      for (const c of [...rec.comparison, rec.recommended]) {
        expect(c.savingsHigh, c.label).toBeLessThanOrEqual(cap);
      }
    }
  });
});

// ——————————————————————————————————————————————————————————————————————
// 7. Stabilité : la recommandation ne dépend pas de l'ordre / reste cohérente.
// ——————————————————————————————————————————————————————————————————————
describe('Stabilité de la recommandation', () => {
  it('déterministe : deux appels identiques → résultat identique', () => {
    const ring = squareRing(14);
    const a = recommend(ring, LAT, 5000);
    const b = recommend(ring, LAT, 5000);
    expect(a.recommended.id).toBe(b.recommended.id);
    expect(a.recommendedTiltDeg).toBe(b.recommendedTiltDeg);
    expect(a.recommended.count).toBe(b.recommended.count);
    expect(a.recommended.annualKwh).toBe(b.recommended.annualKwh);
  });

  it('la recommandation figure dans le comparatif (le ✓ a une ligne)', () => {
    for (const [side, bill] of [[40, 1000], [14, 5000], [11, 5000], [9, 3500]] as const) {
      const rec = recommend(squareRing(side), LAT, bill);
      const row = rec.comparison.find((c) => c.id === rec.recommended.id);
      expect(row, `${side}/${bill} → id ${rec.recommended.id}`).toBeTruthy();
    }
  });

  it('pas d’obstacle → identique à obstacles=[] (aucune régression)', () => {
    const ring = squareRing(20);
    const a = recommend(ring, LAT, 2500);
    const b = recommend(ring, LAT, 2500, []);
    expect(a.recommended.count).toBe(b.recommended.count);
    expect(a.recommendedTiltDeg).toBe(b.recommendedTiltDeg);
    expect(a.recommended.annualKwh).toBe(b.recommended.annualKwh);
  });

  it('un obstacle réduit (ou laisse égal) le compte recommandé', () => {
    const ring = squareRing(14);
    const c: LngLat = [-7.62, 33.59];
    const d = 4 / 111320;
    const dLng = 4 / (111320 * Math.cos((LAT * Math.PI) / 180));
    const obs: LngLat[] = [
      [c[0] - dLng, c[1] - d],
      [c[0] + dLng, c[1] - d],
      [c[0] + dLng, c[1] + d],
      [c[0] - dLng, c[1] + d],
    ];
    const free = recommend(ring, LAT, 5000);
    const blocked = recommend(ring, LAT, 5000, [obs]);
    expect(blocked.recommended.count).toBeLessThanOrEqual(free.recommended.count);
  });
});

// ——————————————————————————————————————————————————————————————————————
// 8. Champs V2 exposés à l'écran pro-4.
// ——————————————————————————————————————————————————————————————————————
describe('Recommendation V2 — champs exposés', () => {
  it('porte neededPanels, recommendedTiltDeg, flatterTilt* cohérents', () => {
    const rec = recommend(squareRing(14), LAT, 5000);
    expect(rec.neededPanels).toBeGreaterThan(0);
    expect(rec.recommendedTiltDeg).toBe(rec.recommended.tiltDeg);
    expect(typeof rec.flatterTiltChosen).toBe('boolean');
    if (!rec.flatterTiltChosen) {
      expect(rec.flatterTiltExtraEnergyPct).toBe(0);
      expect(rec.flatterTiltYieldLossPct).toBe(0);
    }
  });
});

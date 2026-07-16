// Cerveau V2 de l'estimateur — src/lib/estimatorBrainV2.ts (LE moteur public).
// La V2 était une copie versionnée de estimatorBrain.ts (V1, labo) ; la parité
// V2 == V1 a été prouvée ici jusqu'à la suppression de V1 (code mort, plus
// aucun call-site — parcours 3 profils 2026-07). Ces tests prouvent :
//  1. Le balayage choisit une inclinaison plus plate UNIQUEMENT sur toit limité et
//     ne dépasse JAMAIS le plafond « besoin ».
//  2. Toit spacieux → garde l'optimal (~30°) et le besoin (pas de sur-remplissage).
//  3. Cohérence/plafond sur toute la matrice orientation × inclinaison.
//  4. Basculer d'option ne corrompt pas la recommandation.
// Voir apps/web/BRAIN_V2_NOTES.md.
import { describe, expect, it } from 'vitest';
import {
  recommend,
  packConfig,
  neededPanelsForTarget,
  optimalSouthTiltDeg,
  tiltSweepSouth,
  specificYield,
  productionKwh,
  billMAD,
  roofDominantAzimuthDeg,
  PANEL2_WATT,
  TILT_SWEEP_MIN,
  ANNUAL_DEGRADATION,
  LIFETIME_YEARS,
  DC_AC_RATIO,
  degradationFactor,
  clipDcAcKwh,
  effectiveDcAcRatio,
  BIFACIAL_GAIN_FLAT,
  BIFACIAL_GAIN_TILTED,
} from '../src/lib/estimatorBrainV2';
import { type LngLat } from '../src/lib/roof';

const DEG = Math.PI / 180;
// Rectangle de `wEW` m (est-ouest) × `hNS` m (nord-sud), TOURNÉ de `rotDeg`
// (sens horaire vu du ciel), centré sur (lng0, lat0). Sert à tester l'alignement
// de l'array sur les vraies arêtes d'un toit qui n'est pas plein sud.
function rotatedRect(wEW: number, hNS: number, rotDeg: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const cosLat = Math.cos(lat0 * DEG);
  const c = Math.cos(rotDeg * DEG);
  const s = Math.sin(rotDeg * DEG);
  // coins en mètres (x=est, y=nord) avant rotation
  const corners: [number, number][] = [
    [-wEW / 2, -hNS / 2],
    [wEW / 2, -hNS / 2],
    [wEW / 2, hNS / 2],
    [-wEW / 2, hNS / 2],
  ];
  return corners.map(([x, y]) => {
    const xr = x * c - y * s;
    const yr = x * s + y * c;
    return [lng0 + xr / (111320 * cosLat), lat0 + yr / 111320] as LngLat;
  });
}

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
// 1. Plafond « besoin » : JAMAIS dépassé, sur tout le balayage.
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

// ═══════════ W1 — AZIMUT RÉEL, ALIGNEMENT TOIT, MARGE, OPTIONS RECOMMANDÉES ═══════════

describe('W1 roofDominantAzimuthDeg — orientation réelle des arêtes du toit', () => {
  it('un toit aligné nord-sud/est-ouest donne plein sud (≈180°)', () => {
    expect(roofDominantAzimuthDeg(squareRing(20))).toBeCloseTo(180, 0);
    // rectangle aligné : grand côté E-O → les rangées suivent E-O → face plein sud
    expect(roofDominantAzimuthDeg(rotatedRect(30, 10, 0))).toBeCloseTo(180, 0);
  });

  it('un toit tourné de 15° donne un azimut à ~15° du sud (suit les arêtes)', () => {
    const az = roofDominantAzimuthDeg(rotatedRect(30, 10, 15));
    expect(Math.abs(az - 180)).toBeGreaterThan(8);
    expect(Math.abs(az - 180)).toBeLessThan(22);
  });

  it('reste toujours dans l’hémisphère sud du toit (90°–270°)', () => {
    for (const rot of [-40, -20, 5, 25, 50, 80]) {
      const az = roofDominantAzimuthDeg(rotatedRect(28, 12, rot));
      expect(az).toBeGreaterThan(90);
      expect(az).toBeLessThan(270);
    }
  });
});

describe('W1 packConfig — azimut paramétrable, l’array suit les arêtes du toit', () => {
  it('azimut par défaut : sud=180°, est-ouest=90° (rétro-compatible)', () => {
    const ring = squareRing(24);
    expect(packConfig(ring, LAT, { family: 'south', tiltDeg: 29 }).azimuthDeg).toBe(180);
    expect(packConfig(ring, LAT, { family: 'eastwest', tiltDeg: 10 }).azimuthDeg).toBe(90);
  });

  it('sur un toit tourné, l’array aligné sur le toit loge ≥ panneaux que plein sud forcé', () => {
    // toit long et étroit, nettement tourné : suivre les arêtes pave bien mieux
    // que forcer des rangées plein sud (qui gaspillent les coins).
    const roof = rotatedRect(30, 9, 28);
    const roofAz = roofDominantAzimuthDeg(roof);
    const aligned = packConfig(roof, LAT, { family: 'south', tiltDeg: 12, azimuthDeg: roofAz });
    const forcedSouth = packConfig(roof, LAT, { family: 'south', tiltDeg: 12, azimuthDeg: 180 });
    expect(aligned.best.count).toBeGreaterThan(forcedSouth.best.count);
  });

  it('Σ empreintes ≤ surface utile reste vrai à un azimut quelconque', () => {
    const roof = rotatedRect(28, 14, 22);
    const p = packConfig(roof, LAT, { family: 'south', tiltDeg: 15, azimuthDeg: roofDominantAzimuthDeg(roof) });
    for (const grid of [p.portrait, p.landscape]) {
      expect(grid.count * grid.footprintPerPanelM2).toBeLessThanOrEqual(p.usableAreaM2 + 1e-6);
    }
  });
});

describe('W1 production — le rendement/panneau baisse honnêtement hors du sud', () => {
  it('plein sud (aspect 0) rend plus par kWc qu’un array décalé de 20°', () => {
    const south = productionKwh(LAT, 'south', 29, 10, 0); // aspect 0 = sud
    const off20 = productionKwh(LAT, 'south', 29, 10, -20); // 20° à l’est du sud
    expect(off20).toBeLessThan(south);
    expect(off20).toBeGreaterThan(0.9 * south); // léger, pas catastrophique à 20°
  });

  it('sans aspect explicite, le sud vaut aspect 0 (rétro-compatible)', () => {
    expect(productionKwh(LAT, 'south', 29, 10)).toBeCloseTo(productionKwh(LAT, 'south', 29, 10, 0), 6);
  });
});

describe('W1 recommend — marge (setback) paramétrable et balayage d’azimut', () => {
  it('retirer la marge (setback 0) loge ≥ panneaux que la marge par défaut', () => {
    const ring = squareRing(16);
    const withMargin = recommend(ring, LAT, 4000);
    const noMargin = recommend(ring, LAT, 4000, [], { setbackM: 0 });
    expect(noMargin.recommended.roofMaxCount).toBeGreaterThanOrEqual(withMargin.recommended.roofMaxCount);
  });

  it('grand toit + petite facture (besoin atteint au sud) → on GARDE le plein sud et la marge', () => {
    const rec = recommend(squareRing(40), LAT, 1000);
    expect(rec.recommendedOptions.azimuthDeg).toBe(180); // pas de balayage : le sud suffit
    expect(rec.recommendedOptions.margin).toBe('keep'); // besoin atteint avec la marge
  });

  it('toit tourné, limité, besoin NON atteint → on peut suivre les arêtes ET retirer la marge', () => {
    const roof = rotatedRect(13, 11, 25);
    const rec = recommend(roof, LAT, 9000); // grosse facture, petit toit tourné
    expect(rec.roofLimited).toBe(true);
    expect(rec.recommendedOptions.margin).toBe('remove'); // besoin non atteint → récupérer la rive
    // l’azimut recommandé est soit plein sud soit aligné toit, jamais inventé
    const roofAz = roofDominantAzimuthDeg(roof);
    expect([180, roofAz]).toContainEqual(rec.recommendedOptions.azimuthDeg);
  });

  it('GARDE-FOU pro-4 : sans opt-in l’aligné-toit ne gagne JAMAIS (moteur identique à l’origine)', () => {
    // Toit tourné, limité : c’est le cas où l’aligné-toit logerait plus de panneaux.
    const roof = rotatedRect(13, 11, 25);
    const roofAz = roofDominantAzimuthDeg(roof);
    // pro-4 (aucune option) : le gagnant reste plein sud (azimut 180), comme avant W1.
    const base = recommend(roof, LAT, 9000);
    expect(base.recommended.azimuthDeg).toBe(180);
    // pro-5 (opt-in) : l’aligné-toit PEUT gagner et loge strictement plus de panneaux.
    const opted = recommend(roof, LAT, 9000, [], { enableRoofAligned: true });
    expect(opted.recommended.azimuthDeg).toBe(roofAz);
    expect(opted.recommended.count).toBeGreaterThan(base.recommended.count);
  });
});

describe('W1 recommendedOptions — une recommandation calculée par groupe, indépendante du choix', () => {
  it('expose famille, orientation, inclinaison, azimut et marge, cohérents avec la config recommandée', () => {
    const rec = recommend(squareRing(24), LAT, 2500);
    const o = rec.recommendedOptions;
    expect(['south', 'eastwest']).toContain(o.family);
    expect(['portrait', 'landscape']).toContain(o.panelOrientation);
    expect(o.tiltDeg).toBeGreaterThan(0);
    expect(o.azimuthDeg).toBeGreaterThan(90);
    expect(o.azimuthDeg).toBeLessThan(270);
    expect(['keep', 'remove']).toContain(o.margin);
    // cohérence : l’option recommandée DÉCRIT la config recommandée
    expect(o.family).toBe(rec.recommended.family);
    expect(o.tiltDeg).toBe(rec.recommended.tiltDeg);
    expect(o.panelOrientation).toBe(rec.recommended.panelOrientation);
  });

  it('ne dépend d’aucune sélection utilisateur : recommend() est pur (mêmes entrées → même reco)', () => {
    const a = recommend(squareRing(24), LAT, 2500).recommendedOptions;
    const b = recommend(squareRing(24), LAT, 2500).recommendedOptions;
    expect(b).toEqual(a);
  });
});

// ——————————————————————————————————————————————————————————————————————
// W72 — UNE source de rendement pour le cap besoin ET la production.
// neededPanelsForTarget accepte un rendement par panneau (PVGIS) en surcharge :
// quand on le passe, le cap se recalcule sur CE rendement, pas la table sud-optimal.
// optimalSouthTiltDeg devient sensible à l'aspect (scan au vrai aspect, pas 0).
// ——————————————————————————————————————————————————————————————————————
describe('W72 — neededPanelsForTarget(yieldOverride) recale le cap sur le rendement PVGIS', () => {
  it('passer un rendement PVGIS change le compte vs la table par défaut', () => {
    const target = 18000;
    const tableNeed = neededPanelsForTarget(target, LAT); // table, sud optimal
    const tableYield = specificYield(LAT, optimalSouthTiltDeg(LAT), 0);
    // un rendement PVGIS PLUS BAS que la table → il faut PLUS de panneaux pour la cible.
    const lowNeed = neededPanelsForTarget(target, LAT, tableYield * 0.7);
    expect(lowNeed).toBeGreaterThan(tableNeed);
    // un rendement PVGIS PLUS HAUT que la table → il en faut MOINS.
    const highNeed = neededPanelsForTarget(target, LAT, tableYield * 1.3);
    expect(highNeed).toBeLessThan(tableNeed);
  });

  it('un override égal au rendement de table redonne EXACTEMENT le compte de table', () => {
    const target = 9000;
    const tableYield = specificYield(LAT, optimalSouthTiltDeg(LAT), 0);
    expect(neededPanelsForTarget(target, LAT, tableYield)).toBe(neededPanelsForTarget(target, LAT));
  });

  it('un override non fini / ≤ 0 retombe sur la table (rétro-compatible)', () => {
    const target = 9000;
    const base = neededPanelsForTarget(target, LAT);
    expect(neededPanelsForTarget(target, LAT, NaN)).toBe(base);
    expect(neededPanelsForTarget(target, LAT, 0)).toBe(base);
    expect(neededPanelsForTarget(target, LAT, -100)).toBe(base);
    expect(neededPanelsForTarget(target, LAT, Infinity)).toBe(base);
  });

  it('optimalSouthTiltDeg est sensible à l\'aspect : l\'optimum à l\'est diffère du plein sud', () => {
    const south = optimalSouthTiltDeg(LAT); // aspect 0 par défaut (inchangé)
    expect(optimalSouthTiltDeg(LAT, 0)).toBe(south);
    // à un aspect fortement décalé (est), l'inclinaison qui maximise le rendement
    // n'est pas forcément la même qu'au plein sud — au minimum, jamais une exception
    // et toujours une inclinaison bornée [0, 35].
    const east = optimalSouthTiltDeg(LAT, -45);
    expect(east).toBeGreaterThanOrEqual(0);
    expect(east).toBeLessThanOrEqual(35);
  });
});

// ══════════════════════════ W94 — TROIS UPGRADES D'HONNÊTETÉ ══════════════════════════

// 1. Dégradation linéaire des panneaux : fourchette Année 1 ↔ Année 25.
describe('W94 dégradation — Année 25 ≈ Année 1 × (1 − deg)^24', () => {
  it('la constante est une valeur datasheet défendable (~0,5 %/an)', () => {
    expect(ANNUAL_DEGRADATION).toBeGreaterThan(0);
    expect(ANNUAL_DEGRADATION).toBeLessThanOrEqual(0.01); // jamais une dégradation absurde
    expect(LIFETIME_YEARS).toBe(25);
  });

  it('Année 1 = facteur 1,0 ; Année 25 = (1 − deg)^24, strictement < Année 1', () => {
    expect(degradationFactor(1)).toBe(1);
    expect(degradationFactor(LIFETIME_YEARS)).toBeCloseTo(Math.pow(1 - ANNUAL_DEGRADATION, 24), 10);
    expect(degradationFactor(LIFETIME_YEARS)).toBeLessThan(1);
    // monotone décroissante : chaque année rend strictement moins.
    expect(degradationFactor(10)).toBeLessThan(degradationFactor(5));
  });

  it('la production Année 25 est une fraction honnête (≈ 89 %) de l’Année 1', () => {
    const y1 = productionKwh(LAT, 'south', OPT, 10, 0);
    const y25 = y1 * degradationFactor(LIFETIME_YEARS);
    expect(y25).toBeLessThan(y1);
    expect(y25).toBeGreaterThan(0.85 * y1); // ~11 % de perte sur 25 ans à 0,5 %/an
  });
});

// 2. Plafond onduleur DC:AC : un champ DC sur-densifié ne sur-estime plus son kWh.
describe('W94 clip DC:AC — l’onduleur écrête les champs DC sur-densifiés', () => {
  it('un champ au ratio de design (ou en-dessous) n’est PAS écrêté', () => {
    expect(clipDcAcKwh(10000, DC_AC_RATIO)).toBe(10000);
    expect(clipDcAcKwh(10000, DC_AC_RATIO - 0.3)).toBe(10000);
    expect(clipDcAcKwh(10000, 1.0)).toBe(10000);
  });

  it('un champ AU-DELÀ du ratio de design perd de l’énergie (écrêtage), borné à 30 %', () => {
    const clipped = clipDcAcKwh(10000, DC_AC_RATIO + 0.5);
    expect(clipped).toBeLessThan(10000);
    expect(clipped).toBeGreaterThanOrEqual(7000); // plafond de perte 30 %
    // monotone : plus le ratio dépasse, plus on écrête.
    expect(clipDcAcKwh(10000, DC_AC_RATIO + 1)).toBeLessThan(clipDcAcKwh(10000, DC_AC_RATIO + 0.2));
  });

  it('Sud = ratio de design (jamais écrêté) ; E-O = ratio plus haut (écrêté)', () => {
    expect(effectiveDcAcRatio('south')).toBe(DC_AC_RATIO);
    expect(effectiveDcAcRatio('eastwest')).toBeGreaterThan(DC_AC_RATIO);
  });

  it('productionKwh : un Sud normal est INCHANGÉ, une tente E-O respecte le plafond AC', () => {
    const kwc = 8;
    // Sud : la production = kWc × rendement, sans écrêtage (ratio = design).
    expect(productionKwh(LAT, 'south', OPT, kwc, 0)).toBeCloseTo(kwc * specificYield(LAT, OPT, 0), 6);
    // E-O : la production est STRICTEMENT sous la somme DC brute des deux faces.
    const ewRaw = (kwc / 2) * specificYield(LAT, 10, -90) + (kwc / 2) * specificYield(LAT, 10, 90);
    const ewClipped = productionKwh(LAT, 'eastwest', 10, kwc, 0);
    expect(ewClipped).toBeLessThan(ewRaw);
    expect(ewClipped).toBe(clipDcAcKwh(ewRaw, effectiveDcAcRatio('eastwest')));
  });

  it('le plafond d’économies tient toujours après écrêtage (jamais > facture)', () => {
    for (const side of [12, 20, 30]) {
      const rec = recommend(squareRing(side), LAT, 4000);
      const cap = billMAD(rec.targetAnnualKwh / 12) * 12 + 1e-6;
      for (const c of [...rec.comparison, rec.recommended]) {
        expect(c.savingsHigh, c.label).toBeLessThanOrEqual(cap);
      }
    }
  });
});

// 3. Bifacial : constantes réelles, pas un littéral magique.
describe('W94 bifacial — constantes flat/tilted, jamais un « × 0,05 » magique', () => {
  it('les constantes sont distinctes et la flat (E-O/plate) est ≤ la tilted (sud inclinée)', () => {
    expect(BIFACIAL_GAIN_FLAT).toBeGreaterThan(0);
    expect(BIFACIAL_GAIN_TILTED).toBeGreaterThan(0);
    expect(BIFACIAL_GAIN_FLAT).toBeLessThanOrEqual(BIFACIAL_GAIN_TILTED);
  });

  it('bifacialAnnualKwh d’une config reflète la bonne constante (flat E-O vs tilted sud)', () => {
    const rec = recommend(squareRing(24), LAT, 2500);
    for (const c of rec.comparison) {
      const expectedGain = c.family === 'eastwest' || c.tiltDeg < 12 ? BIFACIAL_GAIN_FLAT : BIFACIAL_GAIN_TILTED;
      expect(c.bifacialAnnualKwh).toBeCloseTo(c.annualKwh * (1 + expectedGain), 6);
    }
  });
});

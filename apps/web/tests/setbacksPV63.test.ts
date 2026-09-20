// PV63 — RETRAITS DE RIVE CONFIGURABLES. Un seul chiffre (PERIMETER_SETBACK_M) + un
// bouton binaire devient trois retraits saisis : latéral (côtés des rangées), extrémité
// (bout de rangée) et acrotère (distance minimale à toute rive). Règle de saisie : on
// n'arrondit ni ne rejette jamais une frappe — on AVERTIT.
import { describe, expect, it } from 'vitest';
import { packConfig } from '../src/lib/estimatorBrainV2';
import { packFlushPlane } from '../src/lib/estimatorBrainV3';
import { solveLive } from '../src/lib/estimatorBrainV7';
import {
  PERIMETER_SETBACK_M,
  SETBACK_UNUSUAL_M,
  resolveSetbacks,
  readSetbackInput,
  uniformSetbacks,
  lateralTotalM,
  extremityTotalM,
} from '../src/lib/roofPro2';
import { type LngLat } from '../src/lib/roof';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LNG0 = -7.62;
const LAT0 = 33.59;
const at = (x: number, y: number): LngLat => [LNG0 + x / (DEG2M * Math.cos(LAT0 * DEG2RAD)), LAT0 + y / DEG2M];
const rect = (w: number, h: number): LngLat[] => [at(-w / 2, -h / 2), at(w / 2, -h / 2), at(w / 2, h / 2), at(-w / 2, h / 2)];
const RING = rect(20, 14);
const countWith = (setbacksM?: Parameters<typeof packConfig>[2]['setbacksM']) =>
  packConfig(RING, LAT0, { family: 'south', tiltDeg: 13, setbacksM }).best.count;

describe('PV63 — résolution des trois retraits', () => {
  it('objet absent → les trois valent le retrait de design (comportement historique), joint à 0', () => {
    expect(resolveSetbacks(undefined)).toEqual(uniformSetbacks(PERIMETER_SETBACK_M));
    expect(uniformSetbacks()).toEqual({
      lateralM: PERIMETER_SETBACK_M,
      extremityM: PERIMETER_SETBACK_M,
      parapetM: PERIMETER_SETBACK_M,
      jointM: 0,
    });
  });

  it('champ absent/non fini → repli ; négatif → 0 (pleine rive) ; valeur saisie NON arrondie', () => {
    expect(resolveSetbacks({ lateralM: -1, extremityM: Number.NaN, parapetM: 0.37 })).toEqual({
      lateralM: 0,
      extremityM: PERIMETER_SETBACK_M,
      parapetM: 0.37, // ni arrondi ni « snappé »
      jointM: 0,
    });
    expect(resolveSetbacks({}, 0.8)).toEqual(uniformSetbacks(0.8));
  });
});

// ═══════════ CAL76 — 4ᵉ rive « joint » (extrémité+joint), totaux affichés ═══════════
describe('CAL76 — le joint, 4ᵉ rive, s’ajoute au retrait d’extrémité', () => {
  it('jointM absent d’un document/objet existant → 0, comportement inchangé', () => {
    const s = resolveSetbacks({ lateralM: 0.5, extremityM: 0.5, parapetM: 0.5 });
    expect(s.jointM).toBe(0);
    expect(extremityTotalM(s)).toBe(0.5);
    expect(lateralTotalM(s)).toBe(1.0); // lateralM + parapetM
  });

  it('jointM saisi négatif → 0 (même règle que les trois autres retraits)', () => {
    expect(resolveSetbacks({ jointM: -1 }).jointM).toBe(0);
  });

  it('lateralTotalM/extremityTotalM sont les sommes brutes, jamais recalculées à la main', () => {
    const s = { lateralM: 0.4, extremityM: 0.6, parapetM: 0.3, jointM: 0.2 };
    expect(lateralTotalM(s)).toBeCloseTo(0.7, 10);
    expect(extremityTotalM(s)).toBeCloseTo(0.8, 10);
  });

  it('à joint=0 (défaut), le calepinage est identique au comportement d’avant CAL76 (toit plat)', () => {
    const withoutJoint = packConfig(RING, LAT0, {
      family: 'south',
      tiltDeg: 13,
      setbacksM: uniformSetbacks(PERIMETER_SETBACK_M),
    }).best;
    const withJointZero = packConfig(RING, LAT0, {
      family: 'south',
      tiltDeg: 13,
      setbacksM: { ...uniformSetbacks(PERIMETER_SETBACK_M), jointM: 0 },
    }).best;
    expect(withJointZero.count).toBe(withoutJoint.count);
    expect(withJointZero.panels).toEqual(withoutJoint.panels);
  });

  it('un joint POSITIF réduit (ou laisse égal) le nombre de panneaux — même sens que le retrait d’extrémité', () => {
    const base = countWith();
    const withJoint = countWith({ lateralM: 0.5, extremityM: 0.5, parapetM: 0.5, jointM: 1.5 });
    expect(withJoint).toBeLessThanOrEqual(base);
  });
});

describe('PV63 — lecture d’un champ de saisie (avertir, jamais rejeter ni arrondir)', () => {
  it('une décimale saisie est gardée TELLE QUELLE (point ou virgule française)', () => {
    expect(readSetbackInput('0.37', 0.5)).toEqual({ valueM: 0.37, warning: null });
    expect(readSetbackInput('1,25', 0.5)).toEqual({ valueM: 1.25, warning: null });
    expect(readSetbackInput(' 0,05 ', 0.5)).toEqual({ valueM: 0.05, warning: null });
    expect(readSetbackInput('0', 0.5)).toEqual({ valueM: 0, warning: null });
  });

  it('champ vide ou illisible → le retrait précédent est CONSERVÉ, avec avertissement', () => {
    const empty = readSetbackInput('', 0.5);
    expect(empty.valueM).toBe(0.5);
    expect(empty.warning).toBeTruthy();
    const junk = readSetbackInput('abc', 0.42);
    expect(junk.valueM).toBe(0.42);
    expect(junk.warning).toBeTruthy();
  });

  it('valeur négative → 0 m avec avertissement (jamais un rejet de la frappe)', () => {
    const neg = readSetbackInput('-2', 0.5);
    expect(neg.valueM).toBe(0);
    expect(neg.warning).toBeTruthy();
  });

  it('valeur inhabituelle mais valide → APPLIQUÉE telle quelle, seulement avertie', () => {
    const big = readSetbackInput(String(SETBACK_UNUSUAL_M + 1.5), 0.5);
    expect(big.valueM).toBe(SETBACK_UNUSUAL_M + 1.5);
    expect(big.warning).toBeTruthy();
  });
});

describe('PV63 — effet des trois retraits sur le calepinage (toit plat)', () => {
  it('trois retraits ÉGAUX au retrait de design = calepinage identique au retrait unique', () => {
    const base = packConfig(RING, LAT0, { family: 'south', tiltDeg: 13 }).best;
    const three = packConfig(RING, LAT0, {
      family: 'south',
      tiltDeg: 13,
      setbacksM: uniformSetbacks(PERIMETER_SETBACK_M),
    }).best;
    expect(three.count).toBe(base.count);
    expect(three.panels).toEqual(base.panels);
  });

  it('chaque retrait agit dans SA direction : plus grand ⇒ moins de panneaux', () => {
    const base = countWith();
    const lateral = countWith({ lateralM: 2, extremityM: 0.5, parapetM: 0.5 });
    const extremity = countWith({ lateralM: 0.5, extremityM: 2, parapetM: 0.5 });
    const parapet = countWith({ lateralM: 0.5, extremityM: 0.5, parapetM: 2 });
    expect(base).toBeGreaterThan(0);
    expect(lateral).toBeLessThan(base);
    expect(extremity).toBeLessThan(base);
    // L'acrotère contraint TOUTES les rives : il mord au moins autant que chacun des deux.
    expect(parapet).toBeLessThanOrEqual(Math.min(lateral, extremity));
  });

  it('retraits à zéro (pleine rive) ⇒ plus de panneaux que la marge de design', () => {
    expect(countWith(uniformSetbacks(0))).toBeGreaterThan(countWith());
  });

  it('un seul champ fourni : les autres gardent le retrait de design', () => {
    expect(countWith({ lateralM: 2 })).toBe(countWith({ lateralM: 2, extremityM: PERIMETER_SETBACK_M, parapetM: PERIMETER_SETBACK_M }));
  });

  it('toit en PENTE : les retraits passent par le pan ou par les options', () => {
    const plane = { ring: RING, pitchDeg: 25, facingAzimuthDeg: 180 };
    const base = packFlushPlane(plane).best.count;
    expect(packFlushPlane({ ...plane, setbacksM: { lateralM: 2 } }).best.count).toBeLessThan(base);
    expect(packFlushPlane(plane, { setbacksM: uniformSetbacks(0) }).best.count).toBeGreaterThan(base);
  });
});

describe('PV63 — le solveur vivant honore les retraits saisis', () => {
  it('des retraits plus larges logent moins de panneaux', () => {
    const base = solveLive(RING, LAT0, 3000, [], {});
    const wide = solveLive(RING, LAT0, 3000, [], {}, { setbacksM: uniformSetbacks(1.5) });
    expect(wide.winner.fitCount).toBeLessThan(base.winner.fitCount);
  });

  it('« pleine rive » (marge retirée) IGNORE les retraits saisis : zéro partout', () => {
    const withInputs = solveLive(RING, LAT0, 3000, [], { margin: 'remove' }, { setbacksM: uniformSetbacks(1.5) });
    const without = solveLive(RING, LAT0, 3000, [], { margin: 'remove' }, {});
    expect(withInputs.winner.fitCount).toBe(without.winner.fitCount);
  });
});

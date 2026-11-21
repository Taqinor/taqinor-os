// ACAL583 — pavage en châssis N × M : la cellule devient le châssis entier, développé en panneaux.
import { describe, expect, it } from 'vitest';
import { packConfig, type PackOptions } from '../src/lib/estimatorBrainV2';
import { chassisApplicable, dimensionsChassis } from '../src/lib/estimatorBrainV2Blocs';
import type { LngLat } from '../src/lib/roof';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LNG0 = -7.62;
const LAT0 = 33.59;
const MODULE = { longM: 2.278, courtM: 1.134, epaisM: null, watt: 600 };

function rect(wEW: number, hNS: number): LngLat[] {
  const dLng = wEW / 2 / (DEG2M * Math.cos(LAT0 * DEG2RAD));
  const dLat = hNS / 2 / DEG2M;
  return [
    [LNG0 - dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 + dLat],
    [LNG0 - dLng, LAT0 + dLat],
  ];
}

const base: PackOptions = { family: 'south', tiltDeg: 15, module: MODULE };
const CHASSIS = { rangs: 2, modulesParRang: 10, jeuEntreRangsM: 0.03 };

describe('ACAL583 — packConfig : option chassis', () => {
  it('rectangle 30 × 12 m, 2 × 10 : des blocs entiers (compte multiple de 20), nombre publié', () => {
    const r = packConfig(rect(30, 12), LAT0, { ...base, chassis: CHASSIS });
    for (const g of [r.portrait, r.landscape]) {
      expect(g.count % 20).toBe(0);
      expect(g.chassis).toEqual({ nombre: g.count / 20, rangs: 2, modulesParRang: 10 });
    }
    expect(r.best.count).toBeGreaterThan(0);
  });

  it('aucun chevauchement entre panneaux (le pas inter-châssis tient compte des 2 rangs)', () => {
    const g = packConfig(rect(30, 12), LAT0, { ...base, chassis: CHASSIS }).portrait;
    const largeur = MODULE.courtM; // portrait : le petit côté court le long de la rangée
    const profondeur = MODULE.longM * Math.cos(15 * DEG2RAD);
    const eps = 1e-6;
    for (let i = 0; i < g.panels.length; i++) {
      for (let j = i + 1; j < g.panels.length; j++) {
        const dx = Math.abs(g.panels[i].cx - g.panels[j].cx);
        const dy = Math.abs(g.panels[i].cy - g.panels[j].cy);
        expect(dx < largeur - eps && dy < profondeur - eps, `panneaux ${i} et ${j} se chevauchent`).toBe(false);
      }
    }
  });

  it('sans option, ou à 1 × 1 : JSON identique', () => {
    const sans = JSON.stringify(packConfig(rect(30, 12), LAT0, base));
    const un = JSON.stringify(packConfig(rect(30, 12), LAT0, { ...base, chassis: { rangs: 1, modulesParRang: 1, jeuEntreRangsM: 0 } }));
    const invalide = JSON.stringify(packConfig(rect(30, 12), LAT0, { ...base, chassis: { rangs: 0, modulesParRang: 10, jeuEntreRangsM: 0.03 } }));
    expect(un).toBe(sans);
    expect(invalide).toBe(sans);
  });

  it('Est-Ouest : l’option est ignorée et chassisMotif dit pourquoi', () => {
    const ew: PackOptions = { ...base, family: 'eastwest' };
    const avec = packConfig(rect(30, 12), LAT0, { ...ew, chassis: CHASSIS });
    const sans = packConfig(rect(30, 12), LAT0, ew);
    expect(avec.chassisMotif).toBe('châssis 2 × 10 : poses au sud seulement');
    expect(avec.best.count).toBe(sans.best.count);
    expect(avec.best.chassis).toBeUndefined();
  });

  it('contour de moins de 3 sommets : pavage vide (résultat identique à celui d’avant l’extraction de panVide)', () => {
    const r = packConfig([[LNG0, LAT0], [LNG0 + 0.0001, LAT0]], LAT0, base);
    expect(r.ringENU).toEqual([]);
    expect(r.origin).toEqual([LNG0, LAT0]);
    expect(r.best).toBe(r.portrait);
    expect(r.portrait).toMatchObject({ panelOrientation: 'portrait', count: 0, kwc: 0, panels: [], slopeLenM: MODULE.longM, rowWidthM: MODULE.courtM });
    expect(r.landscape).toMatchObject({ panelOrientation: 'landscape', count: 0, slopeLenM: MODULE.courtM, rowWidthM: MODULE.longM });
    expect(r.portrait.footprintPerPanelM2).toBeCloseTo(MODULE.longM * Math.cos(15 * DEG2RAD) * MODULE.courtM, 10);
    expect(packConfig([], LAT0, base).origin).toEqual([0, 0]);
  });

  it('dimensions : longueur de pente = 2 × côté + jeu ÷ cos, largeur = 10 × module + 9 × jeu latéral', () => {
    const d = dimensionsChassis(CHASSIS, 2.278, 1.134, 0.02, 15);
    expect(d.slopeLenM).toBeCloseTo(2 * 2.278 + 0.03 / Math.cos(15 * DEG2RAD), 10);
    expect(d.rowWidthM).toBeCloseTo(10 * 1.134 + 9 * 0.02, 10);
    expect(chassisApplicable(CHASSIS)).toBe(CHASSIS);
    expect(chassisApplicable({ ...CHASSIS, jeuEntreRangsM: -1 })).toBeNull();
  });
});

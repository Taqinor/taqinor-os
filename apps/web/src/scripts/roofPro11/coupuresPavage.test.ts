// ACAL576 — coupures automatiques du pavage (contrat ACAL586) : bandes INTERDITES générées depuis
// `zones[].coupuresPavage`, évitées par un `packConfig` inchangé.
import { describe, expect, it } from 'vitest';
import { packConfig } from '../../lib/estimatorBrainV2';
import { PANEL_SIDE_GAP_M } from '../../lib/roofPro2';
import { rectRing } from './harnaisAtelier';
import {
  anneauxDeCoupures, colonnesParCoupure, emettreCoupures, lireCoupures, noteCoupure, validerCoupures, type CoupuresPavage,
} from './coupuresPavage';

const LAT = 33.5;
const OPTS = { family: 'south' as const, tiltDeg: 0, azimuthDeg: 180, setbackM: 0 };
const COUPURE: CoupuresPavage = { tousLesNModules: 8, largeurCoupureM: 0.5, source: 'allée de maintenance' };

/** Un rectangle large de 20 colonnes exactement (au pas du pavage), profond de 3 rangées. */
function scene() {
  const vide = packConfig(rectRing(10, 10), LAT, OPTS);
  const grid = vide.landscape;
  const pas = grid.rowWidthM + PANEL_SIDE_GAP_M;
  const ring = rectRing(20 * pas - PANEL_SIDE_GAP_M + 0.05, 3 * grid.rowPitchM + 0.2);
  return { ring, pas };
}
/** Modules posés par rangée (rangée = même v arrondie), triés. */
function parRangee(panels: { cx: number; cy: number }[]): number[][] {
  const rangs = new Map<number, number[]>();
  for (const p of panels) {
    const k = Math.round(p.cy * 100);
    rangs.set(k, [...(rangs.get(k) ?? []), p.cx]); // azimut 180 : u = +x (geomAxes)
  }
  return [...rangs.values()].map((r) => r.sort((a, b) => a - b));
}

describe('ACAL576 — coupuresPavage', () => {
  it('20 colonnes, N = 8, 0,50 m ⇒ bandes aux colonnes 9 et 18, rangées de 8 + 8 + 2', () => {
    const { ring, pas } = scene();
    const sans = packConfig(ring, LAT, OPTS).landscape;
    const anneaux = anneauxDeCoupures(ring, COUPURE, { azimuthDeg: 180, pasColonneM: pas, retraitLateralM: 0 });
    expect(anneaux).toHaveLength(2);
    const avec = packConfig(ring, LAT, { ...OPTS, obstructions: anneaux, obstructionClearancesM: anneaux.map(() => 0) }).landscape;
    const rangeesSans = parRangee(sans.panels);
    expect(rangeesSans[0]).toHaveLength(20);
    for (const r of parRangee(avec.panels)) {
      expect(r).toHaveLength(18); // 8 + 8 + 2
      const sauts = r.slice(1).map((u, i) => Math.round((u - r[i]) / pas));
      expect(sauts.filter((d) => d === 2).length).toBe(2); // une colonne manque deux fois
      expect(sauts.indexOf(2)).toBe(7); // après 8 modules (colonne 9 retirée)
      expect(sauts.lastIndexOf(2)).toBe(15); // après 16 modules (colonne 18 retirée)
    }
    expect(avec.count).toBe(sans.count - 2 * rangeesSans.length);
  });

  it('largeur > pas ⇒ n = 2 colonnes ; la note dit la coupure réelle', () => {
    const { pas } = scene();
    expect(colonnesParCoupure(0.5, pas)).toBe(1);
    expect(colonnesParCoupure(pas + 0.01, pas)).toBe(2);
    expect(noteCoupure(COUPURE, pas)).toBe('Coupure réelle : 1 colonne retirée (largeur lue au pas du pavage) pour 0,50 m demandés');
  });

  it('sans clé ⇒ aucun anneau ; valeur ≤ 0 refusée en nommant le champ ; champ vidé ⇒ aucune coupure', () => {
    const { ring, pas } = scene();
    expect(anneauxDeCoupures(ring, null, { azimuthDeg: 180, pasColonneM: pas, retraitLateralM: 0 })).toEqual([]);
    expect(lireCoupures({ tousLesNModules: 8, largeurCoupureM: 0, source: 'x' })).toBeNull();
    expect(lireCoupures({ tousLesNModules: 8, largeurCoupureM: 0.5, source: ' ' })).toBeNull();
    expect(emettreCoupures(undefined)).toEqual({});
    expect(emettreCoupures(COUPURE)).toEqual({ coupuresPavage: COUPURE });
    const r = validerCoupures('8', '0', 'allée');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.motif).toContain('Largeur de la coupure (m)');
    expect(validerCoupures('8', '', 'allée')).toEqual({ ok: true, coupures: null });
    expect(validerCoupures('8', '0,5', 'allée de maintenance')).toEqual({ ok: true, coupures: COUPURE });
  });

  it('ordre des dégagements = ordre des anneaux (un 0 par bande, ajoutés après les autres obstructions)', () => {
    const { ring, pas } = scene();
    const anneaux = anneauxDeCoupures(ring, COUPURE, { azimuthDeg: 180, pasColonneM: pas, retraitLateralM: 0 });
    const autres: [number, number][][] = [];
    const tous = [...autres, ...anneaux];
    const degagements = [...autres.map(() => 0.3), ...anneaux.map(() => 0)];
    expect(degagements).toHaveLength(tous.length);
    expect(degagements.slice(-anneaux.length)).toEqual([0, 0]);
  });
});

// PV64 — TROIS VARIANTES LISIBLES du balayage V6 déjà calculé (densité max plein sud /
// Est-Ouest / aligné toit). Couche d'AFFICHAGE + SÉLECTION uniquement : `pickVariantCards`
// est pure, ne pave rien, ne résout rien, et ne fait que refléter des lignes existantes.
import { describe, expect, it } from 'vitest';
import { fineGridMatrixV6, type MatrixEvalV6, type MatrixV6Result } from '../src/lib/estimatorBrainV6';
import { pickVariantCards } from '../src/scripts/roofPro11/optimizer';
import { type LngLat } from '../src/lib/roof';

const DEG = Math.PI / 180;
/** Rectangle `wEW` × `hNS` m TOURNÉ de `rotDeg` (ouvre l'axe « aligné toit »). */
function rotatedRect(wEW: number, hNS: number, rotDeg: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const cosLat = Math.cos(lat0 * DEG);
  const c = Math.cos(rotDeg * DEG);
  const s = Math.sin(rotDeg * DEG);
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

const MATRIX = fineGridMatrixV6(rotatedRect(22, 15, 20), 33.59, 2500, []);

describe('PV64 — extraction des trois variantes', () => {
  it('un toit TOURNÉ donne les trois cartes, avec des identifiants distincts', () => {
    const cards = pickVariantCards(MATRIX);
    expect(cards.length).toBe(3);
    expect(new Set(cards.map((c) => c.id)).size).toBe(3);
    expect(cards.map((c) => c.id).sort()).toEqual(['aligned', 'eastwest', 'south-max']);
    for (const c of cards) {
      expect(c.title.length).toBeGreaterThan(0);
      expect(c.reason.length).toBeGreaterThan(0);
    }
  });

  it('chaque carte REFLÈTE sa ligne de balayage (aucun chiffre recalculé)', () => {
    for (const c of pickVariantCards(MATRIX)) {
      expect(c.count).toBe(c.row.placedCount);
      expect(c.kwc).toBe(c.row.kwc);
      expect(c.annualKwh).toBe(c.row.annualKwh);
      expect(MATRIX.rows).toContain(c.row); // la MÊME ligne, pas une copie
    }
  });

  it('« densité maximale plein sud » = la config SUD qui loge le plus de panneaux', () => {
    const card = pickVariantCards(MATRIX).find((c) => c.id === 'south-max')!;
    expect(card.row.family).toBe('south');
    const maxFit = Math.max(...MATRIX.rows.filter((r) => r.family === 'south').map((r) => r.fitCount));
    expect(card.row.fitCount).toBe(maxFit);
  });

  it('« Est-Ouest » = la meilleure tente E-O ; « aligné toit » suit les arêtes', () => {
    const cards = pickVariantCards(MATRIX);
    const ew = cards.find((c) => c.id === 'eastwest')!;
    expect(ew.row.family).toBe('eastwest');
    const bestEw = Math.max(...MATRIX.rows.filter((r) => r.family === 'eastwest').map((r) => r.annualKwh));
    expect(ew.row.annualKwh).toBeCloseTo(bestEw, 6);
    const aligned = cards.find((c) => c.id === 'aligned')!;
    expect(aligned.row.azimuthAxis).toBe('aligned');
  });

  it('un toit DÉJÀ plein sud n’invente pas de carte « aligné toit »', () => {
    const cards = pickVariantCards(fineGridMatrixV6(rotatedRect(22, 15, 0), 33.59, 2500, []));
    expect(cards.length).toBeLessThanOrEqual(3);
    expect(cards.some((c) => c.id === 'aligned')).toBe(false);
    expect(cards.some((c) => c.id === 'south-max')).toBe(true);
  });

  it('deux catégories qui pointent la MÊME config ne donnent qu’une carte', () => {
    const row = {
      family: 'south',
      tiltDeg: 15,
      azimuthDeg: 165,
      aspect: -15,
      orientation: 'portrait',
      margin: 'keep',
      azimuthAxis: 'aligned',
      fitCount: 20,
      placedCount: 18,
      kwc: 12.96,
      annualKwh: 20000,
      pctOfTarget: 100,
      savingsLow: 1,
      savingsHigh: 2,
      perPanelYield: 1600,
      yieldSource: 'estimate',
      orientationLabel: 'aligné toit',
      layoutLabel: 'portrait',
      label: 'x',
    } as unknown as MatrixEvalV6;
    const cards = pickVariantCards({ rows: [row] } as unknown as MatrixV6Result);
    expect(cards.length).toBe(1);
    expect(cards[0].row).toBe(row);
  });

  it('balayage absent/vide → aucune carte (jamais une carte de remplissage)', () => {
    expect(pickVariantCards(null)).toEqual([]);
    expect(pickVariantCards(undefined)).toEqual([]);
    expect(pickVariantCards({ rows: [] } as unknown as MatrixV6Result)).toEqual([]);
  });

  it('purement lecture : le balayage n’est pas modifié', () => {
    const before = MATRIX.rows.length;
    const snapshot = MATRIX.rows[0];
    pickVariantCards(MATRIX);
    expect(MATRIX.rows.length).toBe(before);
    expect(MATRIX.rows[0]).toBe(snapshot);
  });
});

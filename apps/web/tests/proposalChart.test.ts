// P2 — Graphe production-vs-consommation de la proposition client.
// Constructeur PUR de SVG : on teste le nettoyage défensif des tableaux Q6, le
// choix du mode (comparaison / production seule / rien), le compte de barres,
// l'échelle COMMUNE des deux séries, et le format kWh. Aucun DOM, aucun réseau.
import { describe, expect, it } from 'vitest';
import {
  fmtKwh,
  resolveSeries,
  barGroups,
  renderProposalChart,
  MONTH_LABELS_FR,
  DEFAULT_CHART_BOX,
} from '../src/lib/proposalChart';

const PROD = [800, 900, 1100, 1300, 1500, 1600, 1700, 1650, 1400, 1100, 850, 750];
const CONS = [1200, 1100, 1000, 900, 850, 1300, 1600, 1550, 1000, 950, 1050, 1250];

describe('fmtKwh', () => {
  it('entier groupé par milliers + unité', () => {
    expect(fmtKwh(1240)).toBe('1 240 kWh');
    expect(fmtKwh(999)).toBe('999 kWh');
    expect(fmtKwh(1234567)).toBe('1 234 567 kWh');
  });
  it('valeurs non finies / négatives → 0 kWh', () => {
    expect(fmtKwh(NaN)).toBe('0 kWh');
    expect(fmtKwh(-50)).toBe('0 kWh');
    expect(fmtKwh(Infinity)).toBe('0 kWh');
  });
});

describe('resolveSeries — nettoyage défensif + choix de mode', () => {
  it('production + consommation → comparaison', () => {
    const s = resolveSeries(PROD, CONS);
    expect(s.mode).toBe('comparison');
    expect(s.production).toHaveLength(12);
    expect(s.consumption).toHaveLength(12);
  });

  it('production seule → mode production', () => {
    const s = resolveSeries(PROD, []);
    expect(s.mode).toBe('production');
    expect(s.consumption).toBeNull();
  });

  it('production absente → mode none (jamais de conso « solo »)', () => {
    expect(resolveSeries([], CONS).mode).toBe('none');
    expect(resolveSeries(undefined, CONS).mode).toBe('none');
    expect(resolveSeries(null, null).mode).toBe('none');
  });

  it('taille ≠ 12 → série rejetée', () => {
    expect(resolveSeries([1, 2, 3], undefined).mode).toBe('none');
    expect(resolveSeries(PROD, [1, 2, 3]).mode).toBe('production'); // conso invalide ignorée
  });

  it('tableau tout-zéro → traité comme vide', () => {
    const zeros = new Array(12).fill(0);
    expect(resolveSeries(zeros, CONS).mode).toBe('none');
    expect(resolveSeries(PROD, zeros).mode).toBe('production');
  });

  it('valeurs non finies / négatives écrasées à 0', () => {
    const dirty = [NaN, -5, 1000, ...new Array(9).fill(100)];
    const s = resolveSeries(dirty, undefined);
    expect(s.production?.[0]).toBe(0);
    expect(s.production?.[1]).toBe(0);
    expect(s.production?.[2]).toBe(1000);
  });
});

describe('barGroups — géométrie déterministe', () => {
  it('1 barre par mois en mode production seule (12 barres)', () => {
    const { prod, cons } = barGroups(PROD, null);
    expect(prod).toHaveLength(12);
    expect(cons).toHaveLength(0);
  });

  it('2 barres par mois en mode comparaison (12 + 12)', () => {
    const { prod, cons } = barGroups(PROD, CONS);
    expect(prod).toHaveLength(12);
    expect(cons).toHaveLength(12);
  });

  it('échelle COMMUNE : le pic global = pleine hauteur de tracé', () => {
    const box = DEFAULT_CHART_BOX;
    const plotH = box.height - box.padTop - box.padBottom;
    const { prod, cons } = barGroups(PROD, CONS);
    // Le maximum des deux séries est dans CONS (1600). Sa barre = pleine hauteur.
    const maxConsH = Math.max(...cons.map((r) => r.height));
    const maxProdH = Math.max(...prod.map((r) => r.height));
    expect(Math.max(maxConsH, maxProdH)).toBeCloseTo(plotH, 5);
    // La production max (1700) > conso max (1600) → c'est la prod qui touche le plafond.
    expect(maxProdH).toBeCloseTo(plotH, 5);
    expect(maxConsH).toBeLessThan(plotH);
  });

  it('barres prod et cons ne se chevauchent pas (cons à droite de prod) dans un mois', () => {
    const { prod, cons } = barGroups(PROD, CONS);
    for (let m = 0; m < 12; m++) {
      expect(cons[m].x).toBeGreaterThanOrEqual(prod[m].x + prod[m].width - 1e-6);
    }
  });

  it('valeurs nulles → hauteur 0, jamais de NaN', () => {
    const zeros = new Array(12).fill(0);
    const { prod } = barGroups(zeros, null);
    for (const r of prod) {
      expect(r.height).toBe(0);
      expect(Number.isNaN(r.x)).toBe(false);
      expect(Number.isNaN(r.y)).toBe(false);
    }
  });

  it('toutes les barres restent dans la boîte', () => {
    const box = DEFAULT_CHART_BOX;
    const { prod, cons } = barGroups(PROD, CONS);
    for (const r of [...prod, ...cons]) {
      expect(r.x).toBeGreaterThanOrEqual(box.padLeft - 1e-6);
      expect(r.x + r.width).toBeLessThanOrEqual(box.width - box.padRight + 1e-6);
      expect(r.y).toBeGreaterThanOrEqual(box.padTop - 1e-6);
    }
  });
});

describe('renderProposalChart — SVG', () => {
  it('comparaison : 24 barres (12 prod + 12 cons) + 12 étiquettes de mois', () => {
    const svg = renderProposalChart(PROD, CONS);
    const rects = svg.match(/<rect /g) ?? [];
    expect(rects).toHaveLength(24);
    for (const lbl of MONTH_LABELS_FR) expect(svg).toContain(`>${lbl}<`);
    expect(svg).toContain('role="img"');
    expect(svg).toContain('viewBox="0 0 360 150"');
  });

  it('production seule : 12 barres laiton, aucune barre azur', () => {
    const svg = renderProposalChart(PROD, []);
    expect((svg.match(/<rect /g) ?? [])).toHaveLength(12);
    expect(svg).toContain('--color-brass-400');
    expect(svg).not.toContain('--color-azur-300');
  });

  it('comparaison utilise laiton (prod) ET azur (conso)', () => {
    const svg = renderProposalChart(PROD, CONS);
    expect(svg).toContain('--color-brass-400');
    expect(svg).toContain('--color-azur-300');
  });

  it('rien à dessiner → chaîne vide (le bloc se masque)', () => {
    expect(renderProposalChart([], [])).toBe('');
    expect(renderProposalChart(undefined, CONS)).toBe('');
    expect(renderProposalChart(null, null)).toBe('');
  });

  it('un mois à 0 ne produit pas de barre pour ce mois', () => {
    const oneZero = [0, ...PROD.slice(1)];
    const svg = renderProposalChart(oneZero, null);
    // 11 barres (le mois 0 à 0 est omis), pas 12.
    expect((svg.match(/<rect /g) ?? [])).toHaveLength(11);
  });

  it('les <title> portent le mois + la valeur formatée (chiffres backend seulement)', () => {
    const svg = renderProposalChart(PROD, CONS);
    expect(svg).toContain('janv. · production 800 kWh');
    expect(svg).toContain('janv. · consommation 1 200 kWh');
  });
});

// @vitest-environment jsdom
//
// PV75 — fenêtre « Production estimée » : ligne compacte P50/P90/PR + mini cascade
// des pertes, affichées SEULEMENT quand la page hôte injecte `ctx.opts.bankable`
// (l'outil n'appelle JAMAIS Django lui-même — discipline « le navigateur ne parle
// qu'à la page hôte »). Deux garanties couvertes ici :
//   1. Absent → rendu STRICTEMENT INCHANGÉ (golden) : aucun élément dynamique créé,
//      le chiffre de tête et le graphe existants restent produits normalement.
//   2. Présent → la ligne + la cascade apparaissent, avec les bons chiffres/libellés
//      FR, et un second rendu ne les duplique pas (idempotent).
import { describe, expect, it } from 'vitest';
import { createProdWindow, type ProdWindowDom } from '../src/scripts/roofPro11/prodWindow';
import { createGraphs } from '../src/scripts/roofPro11/graphs';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { BankableProduction } from '../src/scripts/roofPro11/types';
import { DEFAULT_GRAPH_BOX } from '../src/lib/productionWindow';
import type { ScaledProduction } from '../src/lib/productionEngine';

const IDS = [
  'prod-window', 'prod-scope-wrap', 'prod-month-picker', 'prod-month-label',
  'prod-day-picker', 'prod-day-label', 'prod-day-reset', 'prod-headline',
  'prod-sub', 'prod-source', 'prod-savings',
];

function setupDom() {
  document.body.innerHTML = '';
  for (const id of IDS) {
    const e = document.createElement('div');
    e.id = id;
    document.body.appendChild(e);
  }
  // Le graphe vit dans un <svg> entouré du wrapper réel `.rp9-prod-graph-wrap` —
  // c'est APRÈS ce wrapper que la mini cascade des pertes s'insère (PV75).
  const wrap = document.createElement('div');
  wrap.className = 'rp9-prod-graph-wrap';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.id = 'prod-graph';
  wrap.appendChild(svg);
  document.body.appendChild(wrap);
}

function makeDom(): ProdWindowDom {
  return {
    prodWindowEl: document.getElementById('prod-window'),
    prodScopeWrap: document.getElementById('prod-scope-wrap'),
    prodMonthPickerEl: document.getElementById('prod-month-picker'),
    prodMonthLabelEl: document.getElementById('prod-month-label'),
    prodDayPickerEl: document.getElementById('prod-day-picker'),
    prodDayLabelEl: document.getElementById('prod-day-label'),
    prodDayResetEl: document.getElementById('prod-day-reset'),
    prodHeadlineEl: document.getElementById('prod-headline'),
    prodSubEl: document.getElementById('prod-sub'),
    prodGraphEl: document.getElementById('prod-graph'),
    prodSourceEl: document.getElementById('prod-source'),
    prodSavingsEl: document.getElementById('prod-savings'),
  };
}

function makeProd(): ScaledProduction {
  const monthlyKwh = [500, 550, 600, 650, 700, 720, 740, 700, 650, 600, 550, 520];
  const annualKwh = monthlyKwh.reduce((a, b) => a + b, 0);
  return {
    source: 'pvgis',
    placedKwc: 10,
    annualKwh,
    monthlyKwh,
    typicalDayByMonth: Array.from({ length: 12 }, () => new Array(24).fill(0.1)),
    dailyKwhByMonth: monthlyKwh.map((v) => v / 30),
  };
}

function makeCtx(bankable: BankableProduction | null): Ctx {
  return {
    opts: { reducedMotion: true, maptilerKey: 'k', bankable },
    svgBox: DEFAULT_GRAPH_BOX,
    prodScope: 'year',
    prodMonth: 0,
    prodDay: null,
    prodToken: 0,
    prodPerKwc: null,
    prodSpecificDate: null,
    prodSource: 'pvgis',
    prodScaled: makeProd(),
    prodPanels: 20,
    prodTarget: 8000,
    prodPlaneKey: '',
    layoutMode: false,
    layoutState: null,
  } as unknown as Ctx;
}

function makeProdWindow(ctx: Ctx) {
  const graphs = createGraphs(ctx);
  return createProdWindow(ctx, makeDom(), {
    graphs,
    renderConsumption: () => {},
    renderLayoutPanel: () => {},
    snapshotActiveAreaResult: () => {},
    renderAreasPanel: () => {},
  });
}

describe('prodWindow — PV75 bankable (P50/P90 + cascade des pertes)', () => {
  it('absent : rendu strictement inchangé (aucun élément dynamique créé)', () => {
    setupDom();
    const ctx = makeCtx(null);
    const pw = makeProdWindow(ctx);

    pw.renderProdWindow();

    expect(document.querySelector('[data-prod-bankable]')).toBeNull();
    expect(document.querySelector('[data-prod-loss-cascade]')).toBeNull();
    // Le chiffre de tête + le graphe existants restent produits normalement.
    expect(document.getElementById('prod-headline')?.textContent).toContain('kWh/an');
    expect(document.getElementById('prod-graph')?.innerHTML).not.toBe('');
  });

  it('présent : ligne P50/P90/PR + cascade des pertes rendues, idempotent au second rendu', () => {
    setupDom();
    const bankable: BankableProduction = {
      p50_kwh: 71800, p90_kwh: 58300, performance_ratio: 0.812,
      loss_breakdown: { temperature: 8.0, soiling: 3.0, shading: 4.2 },
    };
    const ctx = makeCtx(bankable);
    const pw = makeProdWindow(ctx);

    pw.renderProdWindow();

    const line = document.querySelector('[data-prod-bankable]');
    expect(line).not.toBeNull();
    // Séparateur de milliers « fr-FR » = espace insécable fine → tolérant sur le
    // caractère exact (même patron que productionWindow.test.ts::fmtKwh).
    expect(line?.textContent).toMatch(/71.800/);
    expect(line?.textContent).toContain('(P50)');
    expect(line?.textContent).toContain('P90');
    expect(line?.textContent).toMatch(/58.300/);
    expect(line?.textContent).toContain('PR 81 %');

    const cascade = document.querySelector('[data-prod-loss-cascade]');
    expect(cascade).not.toBeNull();
    expect(cascade?.innerHTML).toContain('Température');
    expect(cascade?.innerHTML).toContain('Salissure');
    expect(cascade?.innerHTML).toContain('Ombrage');
    // Le graphe de scope (année/mois/jour) n'est pas touché par la cascade.
    expect(document.getElementById('prod-graph')?.innerHTML).not.toContain('Température');

    // Idempotent : un second rendu ne duplique PAS les éléments dynamiques.
    pw.renderProdWindow();
    expect(document.querySelectorAll('[data-prod-bankable]').length).toBe(1);
    expect(document.querySelectorAll('[data-prod-loss-cascade]').length).toBe(1);
  });

  it('présent mais loss_breakdown vide : la ligne P50/P90 apparaît, aucune cascade', () => {
    setupDom();
    const bankable: BankableProduction = {
      p50_kwh: 40000, p90_kwh: 32000, performance_ratio: 0.8, loss_breakdown: {},
    };
    const ctx = makeCtx(bankable);
    const pw = makeProdWindow(ctx);

    pw.renderProdWindow();

    expect(document.querySelector('[data-prod-bankable]')).not.toBeNull();
    const cascade = document.querySelector('[data-prod-loss-cascade]');
    // L'élément conteneur existe (créé lazily dès que `bankable` est fourni) mais
    // reste vide : `renderLossCascade` renvoie '' pour un breakdown sans poste.
    expect(cascade?.innerHTML ?? '').toBe('');
  });
});

describe('graphs — PV75 renderLossCascade (pure, FR)', () => {
  function makeGraphs() {
    const ctx = { svgBox: DEFAULT_GRAPH_BOX } as unknown as Ctx;
    return createGraphs(ctx);
  }

  it('poste inconnu : affiche la clé brute plutôt que d’échouer', () => {
    const graphs = makeGraphs();
    const svg = graphs.renderLossCascade({ postal_inconnu: 5.5 });
    expect(svg).toContain('postal_inconnu');
    expect(svg).toContain('5.5');
  });

  it('postes nuls/négatifs filtrés, breakdown vide → chaîne vide', () => {
    const graphs = makeGraphs();
    expect(graphs.renderLossCascade({ temperature: 0, soiling: -1 })).toBe('');
    expect(graphs.renderLossCascade({})).toBe('');
  });

  it('échappe les libellés (sécurité SVG)', () => {
    const graphs = makeGraphs();
    const svg = graphs.renderLossCascade({ '<script>': 2 });
    expect(svg).not.toContain('<script>2');
    expect(svg).toContain('&lt;script&gt;');
  });
});

// ERR-ACAL311-PANNEAU-ABSENT-ERP — l'atelier ERP n'a NI `#rp9-prod-window` NI la route
// `/api/roof-production` : la production du plan vient de l'option injectée
// `productionAtelier`, sans quoi « Affiner ma consommation » reste masqué (prodScaled null).
describe('prodWindow — page hôte sans fenêtre de production (option productionAtelier)', () => {
  function makeCtxSansFenetre(productionAtelier?: unknown): Ctx {
    return {
      opts: { reducedMotion: true, maptilerKey: 'k', ...(productionAtelier ? { productionAtelier } : {}) },
      closed: true,
      vertices: [[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51]],
      centroid: [-7.595, 33.505],
      roofType: 'flat',
      liveResult: { target: 6000, winner: { placedCount: 10, tiltDeg: 10, aspect: 0 } },
      pitchedLiveResult: null,
      prodScaled: null,
      prodPerKwc: null,
      prodPanels: 0,
      prodTarget: 0,
      prodSource: 'pvgis',
      layoutMode: false,
      layoutState: null,
    } as unknown as Ctx;
  }

  function sync(ctx: Ctx) {
    let rendus = 0;
    const dom = { ...makeDom(), prodWindowEl: null };
    const pw = createProdWindow(ctx, dom, {
      graphs: createGraphs(ctx),
      renderConsumption: () => { rendus += 1; },
      renderLayoutPanel: () => {},
      snapshotActiveAreaResult: () => {},
      renderAreasPanel: () => {},
    });
    pw.syncProductionWindow();
    return rendus;
  }

  it('option fournie : plan de production posé (10 panneaux) et fenêtre de conso re-rendue, sans requête', async () => {
    document.body.innerHTML = '';
    const { fallbackPerKwc, PANEL_KWC } = await import('../src/lib/productionEngine');
    const appels: unknown[] = [];
    const ctx = makeCtxSansFenetre((cfg: unknown) => { appels.push(cfg); return fallbackPerKwc(); });
    const fetchAvant = globalThis.fetch;
    let requetes = 0;
    globalThis.fetch = (() => { requetes += 1; return Promise.reject(new Error('aucune requête')); }) as typeof fetch;
    try {
      expect(sync(ctx)).toBe(1);
    } finally {
      globalThis.fetch = fetchAvant;
    }
    expect(requetes).toBe(0);
    expect(appels).toHaveLength(1);
    expect(appels[0]).toMatchObject({ panels: 10, tiltDeg: 10, aspect: 0, target: 6000 });
    expect(ctx.prodPanels).toBe(10);
    expect(ctx.prodTarget).toBe(6000);
    expect(ctx.prodSource).toBe('estimate');
    expect(ctx.prodScaled?.annualKwh).toBeCloseTo(fallbackPerKwc().annualKwh * 10 * PANEL_KWC, 6);
  });

  it('option absente (pages publiques) : aucun plan posé, aucun rendu de conso — comportement inchangé', () => {
    document.body.innerHTML = '';
    const ctx = makeCtxSansFenetre();
    expect(sync(ctx)).toBe(0);
    expect(ctx.prodScaled).toBeNull();
    expect(ctx.prodPanels).toBe(0);
  });

  it('aucun panneau posé : plan retiré (prodScaled null) et la conso est re-rendue (masquée)', () => {
    document.body.innerHTML = '';
    const ctx = makeCtxSansFenetre(() => { throw new Error('jamais appelée sans panneau'); });
    (ctx as unknown as { liveResult: unknown }).liveResult = { target: 6000, winner: { placedCount: 0, tiltDeg: 10, aspect: 0 } };
    expect(sync(ctx)).toBe(1);
    expect(ctx.prodScaled).toBeNull();
    expect(ctx.prodPanels).toBe(0);
  });
});

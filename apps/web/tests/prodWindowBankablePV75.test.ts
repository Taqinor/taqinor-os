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

  let rendusLayout = 0;
  function sync(ctx: Ctx) {
    let rendus = 0;
    rendusLayout = 0;
    const dom = { ...makeDom(), prodWindowEl: null };
    const pw = createProdWindow(ctx, dom, {
      graphs: createGraphs(ctx),
      renderConsumption: () => { rendus += 1; },
      renderLayoutPanel: () => { rendusLayout += 1; },
      snapshotActiveAreaResult: () => {},
      renderAreasPanel: () => {},
    });
    pw.syncProductionWindow();
    return rendus;
  }

  // ACAL958 — sans #rp9-prod-window, la fenêtre « Déplacer les panneaux » doit quand même être rendue.
  it('ACAL958 — renderLayoutPanel est appelé une fois quand prodWindowEl est nul', () => {
    document.body.innerHTML = '';
    sync(makeCtxSansFenetre());
    expect(rendusLayout).toBe(1);
  });

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

// Demande croisée (lane editeur-1) — la fenêtre de production multipliait le nombre posé par 720 W (PANEL_KWC) même quand
// le module DÉSIGNÉ du pan en a une autre puissance : 5 × 710 W lisait 3,60 kWc là où le bandeau (ACAL1520) lit 3,55.
describe('prodWindow — kWc du module désigné du pan, comme le bandeau', () => {
  const m710 = { id: 'produit-7', produitId: 7, libelle: 'Module 710 W', longueurMm: 2384, largeurMm: 1303, epaisseurMm: 33, poidsKg: 38, pmaxWc: 710, source: 'fiche' };
  const catalogue = { calepinage: 1, modules: [{ module: m710, selectionnable: true, champs_manquants: [], motif: null }], champs_requis: [], motif_liste_vide: null };
  const ctxAvec = (moduleId: string | null, extra: Record<string, unknown>): Ctx => {
    const pan = { id: 'z1', moduleId };
    return {
      opts: { reducedMotion: true, maptilerKey: 'k', modulesDisponibles: catalogue }, activeArea: () => pan, closed: true,
      vertices: [[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51]], centroid: [-7.595, 33.505], roofType: 'flat',
      liveResult: { target: 6000, winner: { placedCount: 5, tiltDeg: 10, aspect: 0 } }, pitchedLiveResult: null, prodScaled: null, prodPerKwc: null,
      prodPanels: 0, prodTarget: 0, prodSource: 'pvgis', layoutMode: false, layoutState: null, svgBox: DEFAULT_GRAPH_BOX, prodScope: 'year', prodMonth: 0,
      prodDay: null, prodToken: 0, prodSpecificDate: null, prodPlaneKey: '', ...extra,
    } as unknown as Ctx;
  };
  const deps = (ctx: Ctx) => ({ graphs: createGraphs(ctx), renderConsumption: () => {}, renderLayoutPanel: () => {}, snapshotActiveAreaResult: () => {}, renderAreasPanel: () => {} });

  it('atelier ERP (production injectée) : 5 × 710 W ⇒ 3,55 kWc et la production à 3,55 kWc ; sans module : 3,60', async () => {
    document.body.innerHTML = '';
    const { fallbackPerKwc } = await import('../src/lib/productionEngine');
    for (const [moduleId, kwc] of [['produit-7', 3.55], [null, 3.6]] as const) {
      const ctx = ctxAvec(moduleId, { opts: { reducedMotion: true, maptilerKey: 'k', modulesDisponibles: catalogue, productionAtelier: () => fallbackPerKwc() } });
      createProdWindow(ctx, { ...makeDom(), prodWindowEl: null }, deps(ctx)).syncProductionWindow();
      expect(ctx.prodScaled?.placedKwc).toBeCloseTo(kwc, 9);
      expect(ctx.prodScaled?.annualKwh).toBeCloseTo(fallbackPerKwc().annualKwh * kwc, 6);
    }
  });

  it('fenêtre de production (rescale sans requête) : 5 × 710 W ⇒ 3,55 kWc', async () => {
    setupDom();
    const { fallbackPerKwc } = await import('../src/lib/productionEngine');
    const cfg = { lat: 33.5, lon: -7.6, tiltDeg: 10, aspect: 0, mountingplace: 'free' as const, panels: 5, target: 6000 };
    const ctx = ctxAvec('produit-7', { prodPerKwc: fallbackPerKwc(), prodPlaneKey: '33.5000,-7.6000,10,0,free' });
    createProdWindow(ctx, makeDom(), deps(ctx)).updateProductionWindow(cfg);
    expect(ctx.prodScaled?.placedKwc).toBeCloseTo(3.55, 9);
  });
});

// Lot 10 (production-un-chiffre) — la fenêtre « Production estimée » et la carte de la pose
// (`optimizer.ts::renderConfig`) disent la MÊME production : le dérate ombrage × horizon de
// `facteurDerateAnnuel` s'applique aux deux, jamais à la carte seule.
describe('prodWindow — même dérate ombrage × horizon que la carte de la pose', () => {
  const chiffre = (id: string): number =>
    Number((document.getElementById(id)?.textContent ?? '').replace(/[^\d]/g, ''));

  it('ombrage 0,8 × horizon 0,9 : têtes de l’année et du mois réduites de 28 %', async () => {
    const { facteurDerateAnnuel } = await import('../src/scripts/roofPro11/optimizer');
    setupDom();
    const ctx = Object.assign(makeCtx(null), { shadeAnnualFactor: 0.8, horizonAnnualFactor: 0.9 });
    const brut = makeProd().annualKwh;
    expect(facteurDerateAnnuel(ctx)).toBeCloseTo(0.72, 12);
    const pw = makeProdWindow(ctx);

    pw.renderProdWindow();
    expect(chiffre('prod-headline')).toBe(Math.round(brut * facteurDerateAnnuel(ctx)));
    // La production rangée du contexte (lue par la conso) n'est pas touchée.
    expect(ctx.prodScaled?.annualKwh).toBe(brut);

    ctx.prodScope = 'month';
    pw.renderProdWindow();
    expect(chiffre('prod-headline')).toBe(Math.round(makeProd().monthlyKwh[0] * 0.72));
  });

  it('sans ombrage ni horizon (facteurs 1) : rendu inchangé', () => {
    setupDom();
    const ctx = Object.assign(makeCtx(null), { shadeAnnualFactor: 1, horizonAnnualFactor: 1 });
    makeProdWindow(ctx).renderProdWindow();
    expect(chiffre('prod-headline')).toBe(makeProd().annualKwh);
  });
});

// Tests sortis de optimizer.test.ts (fichier gelé, C20) : cible posée d'elle-même (ACAL1331) et carte de densité (ACAL1919).
import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { type Ctx } from './context';
import { createOptimizer } from './optimizer';
import { hydrateFromDevis, serializeLayout, type DevisPayload } from './prefill';
import { rectRing } from './harnaisAtelier';
import { createLayoutState } from '../../lib/layoutVariability';
import { heriterDuPanDecoupe } from './tailleAuto';

// ACAL1331 + ACAL1448 (D-ACAL-76 « dimensionner », 23/11/2026) — un calepinage VIERGE de l'atelier ERP se pose, dès que son
// toit est fermé, à la taille de la cible servie (celle du devis lié, sinon celle tirée de la facture du lead), et l'écran
// le DIT ; le commercial ajuste ; une pose tenue n'est jamais re-posée (ACAL1900) ; le site public ne change pas.
describe('ACAL1331 — la taille de la cible posée d’elle-même sur un calepinage vierge, et dite', () => {
  // les mots que l'ERP pose dans le payload (contexteAtelier.js : LIBELLES_SOURCE_CIBLE et sa forme « d'après »)
  const motsDeLaCarte: Record<string, { libelleOrigineCible: string; libelleApresOrigineCible: string }> = {
    factures: { libelleOrigineCible: 'Factures du lead', libelleApresOrigineCible: 'les factures du lead' },
    devis: { libelleOrigineCible: 'Devis lié', libelleApresOrigineCible: 'le devis lié' },
    lead: { libelleOrigineCible: 'Taille souhaitée sur la fiche du lead', libelleApresOrigineCible: 'la taille souhaitée sur la fiche du lead' },
  };
  const payload = (origineCible: string | null, roofLayout: unknown = null) => ({
    id: null, geometrie: { roof_layout: roofLayout, roof_point: null, roof_outline: null },
    cible: { panneaux: 8, panel_watt: 710, scenario: null }, cibleVendue: origineCible === 'devis', origineCible,
    ...(motsDeLaCarte[origineCible ?? ''] ?? {}),
  });
  /** Boot d'un plat `l × p` m depuis le payload de l'atelier (`hydrateFromDevis`, cible imposée au pan unique comme
   *  `imposeTarget`), puis `close()` : le premier rendu de l'optimiseur. */
  const fermer = (l: number, p: number, opts: Record<string, unknown>) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><p id="rp9-need-note"></p><dd id="rp9-reco-kwc"></dd><tbody id="rp9-compare"></tbody></body>').window.document;
    const h = hydrateFromDevis((opts.hydrate as { devis?: DevisPayload } | undefined)?.devis ?? null);
    const vertices = rectRing(l, p);
    const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
    const pan = { id: 'z1', label: 'Zone 1', vertices, obstacles: [], roofType: 'flat' };
    const ctx = {
      closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts, dom: {},
      centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
      v4YieldCache: new Map(), overhangM: 0, documentRelu: h.documentRelu, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
      neededAuto: h.neededAuto, neededPanels: h.neededPanels ?? 0, devisMode: true, cibleVendue: h.cibleVendue, panneauxDevis: h.neededPanels,
      layoutPlan: null, layoutState: null, layoutOptimalCount: 0, useRecommended: true, freeMode: false, freeState: null,
    } as unknown as Ctx;
    let dessinee = -1;
    const renderScene = vi.fn((pack: unknown, grid: { panels: unknown[] }, tiltDeg: number, family: string, maxCount: number, flush: boolean, occ?: Set<number>) => {
      dessinee = maxCount;
      if (!occ) Object.assign(ctx, { layoutPlan: { pack, grid, tiltDeg, family, flush }, layoutOptimalCount: Math.min(grid.panels.length, Math.round(maxCount)), layoutState: null });
    });
    const deps = { renderScene, paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
      syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0, obstructionRings: () => [], obstructionClearances: () => [], setStatus: vi.fn() };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    opt.liveResolveFlat(); // close() : le toit vient d'être fermé
    const note = () => document.getElementById('rp9-need-note')!.textContent ?? '';
    const kwc = () => (document.getElementById('rp9-reco-kwc')!.textContent ?? '').replace(/\s*kWc$/, '');
    return { ctx, opt, dessinee: () => dessinee, note, kwc, fin: () => { g.document = avant; } };
  };
  const ERP = (origine: string | null, roofLayout: unknown = null) => ({ chiffrage: null, rendementPvgis: null, hydrate: { devis: payload(origine, roofLayout) } });

  it('cible 8 tirée de la facture, toit qui en tient plus : 8 posés et DITS ; « + » ⇒ 9 et la phrase ne prétend plus la facture', () => {
    const a = fermer(12, 8, ERP('factures'));
    try {
      expect(a.dessinee()).toBe(8);
      expect(a.note()).toBe(`Posé d’après les factures du lead : 8 panneaux · ${a.kwc()} kWc — ajustez si besoin.`);
      a.ctx.neededPanels = 9; // « + »
      a.opt.liveResolveFlat();
      expect(a.dessinee()).toBe(9);
      expect(a.note()).not.toContain('d’après');
      expect(serializeLayout(a.ctx, null).zones[0].geometry!.count).toBe(9);
    } finally { a.fin(); }
  });

  it('pose tenue (le commercial a déplacé ou enregistré) : le recalcul de fond ne re-pose rien', async () => {
    const a = fermer(12, 8, ERP('factures'));
    try {
      const cellules = a.ctx.layoutPlan!.grid.panels;
      a.ctx.layoutState = createLayoutState(cellules, 7); // un panneau retiré à la main : 7
      await a.opt.computeMatrixPvgis();
      a.opt.liveResolveFlat(false);
      expect(serializeLayout(a.ctx, null).zones[0].geometry!.count).toBe(7);
    } finally { a.fin(); }
  });

  it('toit trop petit pour la cible : ce qui tient est posé, et l’écart est dit', () => {
    const a = fermer(5, 4, ERP('factures'));
    try {
      const n = a.dessinee();
      expect(n).toBeGreaterThan(0);
      expect(n).toBeLessThan(8);
      expect(a.note()).toMatch(new RegExp(`^Posé d’après les factures du lead : ${n} panneaux · ${a.kwc()} kWc sur 8 — seuls ${n} tiennent .+ ; ajustez si besoin\\.$`));
    } finally { a.fin(); }
  });

  it('devis lié : « Posé d’après le devis lié » ; taille souhaitée du lead : dite telle', () => {
    for (const [origine, mot] of [['devis', 'le devis lié'], ['lead', 'la taille souhaitée sur la fiche du lead']]) {
      const a = fermer(12, 8, ERP(origine));
      try {
        expect(a.dessinee()).toBe(8);
        expect(a.note().startsWith(`Posé d’après ${mot} : 8 panneaux`)).toBe(true);
      } finally { a.fin(); }
    }
  });

  it('T4-X8-012 (une cible) — la note nomme la MÊME source que la carte (même table) ; un payload sans ces mots garde le repli d’avant ; site public octet pour octet', () => {
    // la tête de la note dit la source de la carte « Cible — panneaux » (« Factures du lead ») après « d’après » : « les factures du lead »
    const a = fermer(5, 4, ERP('factures'));
    try { expect(a.note().startsWith('Posé d’après les factures du lead : ')).toBe(true); } finally { a.fin(); }
    // payload sans les mots de la table (jamais produit par l'ERP d'aujourd'hui) : le repli, texte d'avant
    const sansMots = fermer(12, 8, { chiffrage: null, rendementPvgis: null, hydrate: { devis: { ...payload('factures'), libelleOrigineCible: undefined, libelleApresOrigineCible: undefined } } });
    try { expect(sansMots.note()).toBe(`Posé d’après la facture : 8 panneaux · ${sansMots.kwc()} kWc — ajustez si besoin.`); } finally { sansMots.fin(); }
    // site public : le texte est le même avec ou sans les mots de l'ERP dans le payload (aucune note « d'après », aucun « cible »)
    const sans = fermer(12, 8, { rendementPvgis: null, hydrate: { devis: { ...payload('factures'), libelleOrigineCible: undefined, libelleApresOrigineCible: undefined } } });
    const avec = fermer(12, 8, { rendementPvgis: null, hydrate: { devis: payload('factures') } });
    try {
      expect(avec.note()).toBe(sans.note());
      expect(avec.note()).not.toMatch(/d’après|cible/);
    } finally { sans.fin(); avec.fin(); }
  });

  it('jumeaux inchangés : pose déjà enregistrée, aucune origine servie, site public', () => {
    const posee = { schema_version: 2, zones: [{ id: 'z1', vertices: rectRing(12, 8), geometry: { count: 8, panels: [{ cx: 0, cy: 0 }] } }] };
    for (const opts of [ERP('factures', posee), ERP(null), { rendementPvgis: null, hydrate: { devis: payload('factures') } }]) {
      const a = fermer(12, 8, opts);
      try { expect(a.note()).not.toContain('d’après'); } finally { a.fin(); }
    }
  });

  it('ACAL1448 — « 2 pans » sur un toit posé : le premier pan (le mieux exposé) garde la taille, tous gardent le module', () => {
    const pans = [{ id: 'area-2', neededPanels: 0, neededAuto: true }, { id: 'area-3', neededPanels: 0, neededAuto: true, existant: false }];
    heriterDuPanDecoupe({ moduleId: 'produit-710' }, { neededPanels: 5, neededAuto: false }, pans as never, true);
    expect(pans).toEqual([
      { id: 'area-2', neededPanels: 5, neededAuto: false, moduleId: 'produit-710' },
      { id: 'area-3', neededPanels: 0, neededAuto: true, existant: false, moduleId: 'produit-710' },
    ]);
    const publics = [{ id: 'area-2', neededPanels: 0, neededAuto: true }];
    heriterDuPanDecoupe({ moduleId: 'produit-710' }, { neededPanels: 5, neededAuto: false }, publics as never, false); // site public : rien
    expect(publics).toEqual([{ id: 'area-2', neededPanels: 0, neededAuto: true }]);
  });
});

// ACAL1919 — la carte « Densité maximale (plein sud) » ne cite pas un second nombre sans le nommer.
describe('ACAL1919 — un seul nombre de panneaux par carte de recommandation', () => {
  const grandToit = rectRing(10, 7);
  it('cible posée à 5 : l’en-tête dit 5, la raison nomme ce qui tient ET les 5 posés', async () => {
    const { fineGridMatrixV6 } = await import('../../lib/estimatorBrainV6');
    const { pickVariantCards } = await import('./optimizer');
    const res = fineGridMatrixV6(grandToit, 33.59, 5000, [], { neededPanelsPose: 5 });
    const carte = pickVariantCards(res).find((c) => c.id === 'south-max');
    expect(carte).toBeDefined();
    expect(carte!.count).toBe(5);
    const nombres = carte!.reason.match(/\d+(?=\s+(panneaux|tiennent|posés))/g) ?? [];
    expect(carte!.row.fitCount).toBeGreaterThan(5);
    expect(carte!.reason).toContain(`${carte!.row.fitCount} tiennent au total`);
    expect(carte!.reason).toContain('5 posés pour votre cible');
    expect(nombres.length).toBe(2);
  });

  it('quand tout ce qui tient est posé, la phrase ne dit qu’un nombre', async () => {
    const { phraseDensiteMax } = await import('./phrasesRecommandation');
    const p = phraseDensiteMax({ fitCount: 8, placedCount: 8, tiltDeg: 15, layoutLabel: 'paysage' });
    expect(p).toBe('La plus dense en plein sud : 8 panneaux tiennent à 15°, paysage.');
  });
});

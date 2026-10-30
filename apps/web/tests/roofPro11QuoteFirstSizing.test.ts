// @vitest-environment jsdom
// ORDRE FONDATEUR (2026-08-18) — « la logique du calepinage 3D ne part JAMAIS du prix,
// toujours du nombre de panneaux du DEVIS, et n'utilise QUE les composants du devis ». Ce
// test couvre le correctif de `consumption.ts` (`applyConsumptionToSizing`) : une CIBLE déjà
// FIGÉE en amont (devis vendu / verrou manuel — `ctx.neededAuto === false` sans que ce
// module l'ait posé lui-même) ne doit JAMAIS être écrasée par un besoin recalculé depuis la
// facture ou les appareils du panneau « Affiner ma consommation ». Le tunnel public SANS
// devis (mode auto) reste, lui, RÉVERSIBLE (W83) : ajouter/retirer un appareil doit toujours
// faire grandir/rétrécir le besoin.
import { describe, expect, it, vi } from 'vitest';
import { createConsumption, type ConsumptionDom, type ConsumptionDeps } from '../src/scripts/roofPro11/consumption';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { emptyCurve } from '../src/lib/applianceConsumption';
// ACAL311 — la consommation PROPOSÉE par le serveur (voir le bloc en fin de fichier).
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach } from 'vitest';
vi.mock('../src/scripts/roofPro11/hydratation', async (importOriginal) => {
  const reel = await importOriginal<typeof import('../src/scripts/roofPro11/hydratation')>();
  // Espion qui DÉLÈGUE à la vraie fonction : aucune application simulée.
  return { ...reel, appliquerHydratationAuCtx: vi.fn(reel.appliquerHydratationAuCtx) };
});
import { type PropositionConsommation } from '../src/scripts/roofPro11/consumption';
import { appliquerHydratationAuCtx } from '../src/scripts/roofPro11/hydratation';
import { lireCouchesDocument, deserializeConsumptionFromLayout } from '../src/scripts/roofPro11/prefill';
import { ctxAtelierNeuf, enregistrerAtelier } from '../src/scripts/roofPro11/harnaisDocument';
import { racineDepot } from '../src/scripts/roofPro11/harnaisAtelier';

/** DOM minimal : consumption.ts garde chaque accès DOM derrière `if (el)` / `?.`, donc
 *  `null` partout est un état légitime (panneau jamais ouvert dans ces tests). */
function emptyDom(): ConsumptionDom {
  return {
    consWindowEl: null,
    consToggleEl: null,
    consPanelEl: null,
    consTotalEl: null,
    consSelfEl: null,
    consSavingsEl: null,
    consBattEl: null,
    consGraphEl: null,
    consInputsEl: null,
    consRecalEl: null,
    consResetEl: null,
    consPaybackEl: null,
    consSeasonalToggleEl: null,
    consSeasonalControlsEl: null,
    consSummerFactorEl: null,
    consWinterFactorEl: null,
    consMonthlyChartEl: null,
    applKindEl: null,
    applAddEl: null,
    applAcEl: null,
    acBtuEl: null,
    acEerEl: null,
    acHoursEl: null,
    acWattsEl: null,
    applEvEl: null,
    evKwEl: null,
    evHoursEl: null,
    evKmEl: null,
    applNoteEl: null,
    applListEl: null,
  };
}

/** Plafond « panneaux nécessaires » identique à celui de l'optimiseur (1..400, arrondi) —
 *  dupliqué ici pour ne dépendre que de la surface publique de `consumption.ts`. */
const clampNeeded = (n: number): number => Math.max(1, Math.min(400, Math.round(n)));

function makeCtx(overrides: Partial<Ctx> = {}): Ctx {
  return {
    centroidLat: 33.57,
    neededPanels: 0,
    neededAuto: true,
    consMode: false,
    consCurve: emptyCurve(),
    consHandEdited: false,
    consAppliances: [],
    consDailyTarget: 0,
    consApplCounter: 0,
    consSeasonal: false,
    consSummerFactor: 1,
    consWinterFactor: 1,
    prodMonth: 0,
    prodPanels: 0,
    prodScaled: null,
    prodSpecificDate: null,
    ...overrides,
  } as unknown as Ctx;
}

function makeDeps(monthlyBillMad: number, renderActive = vi.fn()): ConsumptionDeps {
  return {
    renderActive,
    clampNeeded,
    monthlyBill: () => monthlyBillMad,
    fmt1: (n: number) => n.toFixed(1),
  };
}

describe('Ordre fondateur — le calepinage part du devis, jamais de la facture', () => {
  it('une cible VENDUE (devis, neededAuto=false) survit à un besoin conso/facture plus grand', () => {
    // Devis vendu : 8 panneaux imposés (PV19 hydrateFromDevis aurait déjà posé ceci).
    const ctx = makeCtx({ neededPanels: 8, neededAuto: false });
    const renderActive = vi.fn();
    // Facture/appareils qui, seuls, dimensionneraient largement AU-DESSUS de 8 panneaux.
    const deps = makeDeps(3000, renderActive);
    const cons = createConsumption(ctx, emptyDom(), deps);

    cons.applyConsumptionToSizing(15000); // conso annuelle énorme → consNeeded ≫ 8

    expect(ctx.neededPanels).toBe(8); // la cible du devis n'a PAS bougé
    expect(ctx.neededAuto).toBe(false); // toujours figée par le devis
    expect(renderActive).not.toHaveBeenCalled(); // aucun re-rendu déclenché par la conso
  });

  it('un verrou manuel (neededAuto=false posé par l\'utilisateur) est protégé de la même façon', () => {
    const ctx = makeCtx({ neededPanels: 12, neededAuto: false });
    const renderActive = vi.fn();
    const cons = createConsumption(ctx, emptyDom(), makeDeps(5000, renderActive));

    cons.applyConsumptionToSizing(20000);

    expect(ctx.neededPanels).toBe(12);
    expect(renderActive).not.toHaveBeenCalled();
  });

  it('sans devis (tunnel public, neededAuto=true) le dimensionnement reste RÉVERSIBLE (W83)', () => {
    const ctx = makeCtx({ neededPanels: 0, neededAuto: true });
    const renderActive = vi.fn();
    const deps = makeDeps(600, renderActive);
    const cons = createConsumption(ctx, emptyDom(), deps);

    // Un appareil « en plus » fait grandir le besoin.
    // PERTES 20 % (18/08) : le besoin est `max(besoin facture, besoin conso)`.
    // Avec le productible ramené à la base 20 % (≈ 1 488 au lieu de 1 600
    // kWh/kWc/an), il faut ~7 % de panneaux EN PLUS pour la même énergie : le
    // socle dicté par la facture (600 MAD/mois ≈ 5 200 kWh/an) rejoignait
    // l'ancien couple 6 000/3 000 kWh, qui retombait alors sur le même nombre
    // de panneaux des deux côtés — le test ne testait plus rien. On écarte donc
    // les deux consommations BIEN au-dessus de ce socle : l'intention (retirer
    // un appareil RÉTRÉCIT le système) redevient la seule chose mesurée.
    cons.applyConsumptionToSizing(12000);
    const withAppliance = ctx.neededPanels;
    expect(withAppliance).toBeGreaterThan(0);
    expect(ctx.neededAuto).toBe(false); // NOUS avons posé le latch (consOwnsLock)
    expect(renderActive).toHaveBeenCalledTimes(1);

    // Le retirer fait RÉTRÉCIR le besoin — la réversibilité W83 doit survivre au correctif.
    cons.applyConsumptionToSizing(7000);
    expect(ctx.neededPanels).toBeLessThan(withAppliance);
    expect(renderActive).toHaveBeenCalledTimes(2);
  });

  it('après un devis, une facture plus GRANDE ne fait pas non plus déborder la cible', () => {
    const ctx = makeCtx({ neededPanels: 5, neededAuto: false });
    const renderActive = vi.fn();
    const cons = createConsumption(ctx, emptyDom(), makeDeps(9000, renderActive));

    // annualConsKwh omis → passe par annualSummary() (courbe vide ici, donc 0) : la garde
    // doit de toute façon couper AVANT tout calcul dès que neededAuto est false et pas nôtre.
    cons.applyConsumptionToSizing();

    expect(ctx.neededPanels).toBe(5);
    expect(renderActive).not.toHaveBeenCalled();
  });
});

/* ============================================================================
   ACAL311 — « Affiner ma consommation » : les kWh viennent du SERVEUR (barème société).
   ----------------------------------------------------------------------------
   La facture, « Reprendre du lead », le CSV et le Ramadan appellent l'option injectée
   `proposerConsommation(corps)` (patron de `rendementPvgis`). La réponse — l'`exemple` du
   contrat `calepinage_consommation_proposee.json`, lu dans le dépôt — est posée dans le ctx
   par `appliquerHydratationAuCtx` (la MÊME fonction qu'à l'hydratation, jamais une seconde
   écriture) et le sérialiseur câblé réémet `consumption` tel quel (source.bareme='societe',
   saisi_le relu). Sans serveur (`null`) : « estimation (barème indicatif) », aucun bareme.
   ========================================================================== */
type Contrat = Record<string, unknown>;
const CONTRAT = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples',
  'calepinage_consommation_proposee.json',
), 'utf8')) as Contrat;
const reponse = (cle: string) => JSON.parse(JSON.stringify(CONTRAT[cle])) as PropositionConsommation;

function monter(proposer: unknown) {
  document.body.innerHTML = `<input id="bill" /><span id="kwh"></span><div id="panel"></div>`;
  const billEl = document.getElementById('bill') as HTMLInputElement;
  const dom = new Proxy({
    consPanelEl: document.getElementById('panel'), billEl, billKwhEl: document.getElementById('kwh'),
  } as Partial<ConsumptionDom>, { get: (t, k) => (t as Record<string | symbol, unknown>)[k] ?? null }) as ConsumptionDom;
  const ctx = { ...ctxAtelierNeuf(), opts: { proposerConsommation: proposer } } as unknown as Ctx;
  const conso = createConsumption(ctx, dom, {
    renderActive: () => undefined, clampNeeded: (n) => n,
    monthlyBill: () => Number(billEl.value) || 0, fmt1: (n) => String(n),
  });
  conso.wire();
  return { ctx, conso, billEl, panel: dom.consPanelEl as HTMLElement };
}

const attendre = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => { vi.mocked(appliquerHydratationAuCtx).mockClear(); });
afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ''; });

describe('ACAL311 — la consommation proposée par le serveur', () => {
  it('la facture appelle proposerConsommation et applique consumption au ctx par appliquerHydratationAuCtx', async () => {
    vi.useFakeTimers();
    const servie = reponse('exemple_factures');
    const proposer = vi.fn(async () => servie);
    const { ctx, conso, billEl, panel } = monter(proposer);
    (panel.querySelector('[data-cons-classe]') as HTMLSelectElement).value = 'residentiel';
    billEl.value = '850';
    billEl.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(700);

    expect(proposer).toHaveBeenCalledWith({ source: 'factures', factures: { hiver_mad: 850, classe: 'residentiel' } });
    // UNE écriture du ctx : celle de l'hydratation, avec la provenance servie.
    expect(appliquerHydratationAuCtx).toHaveBeenCalledTimes(1);
    const [cible, h] = vi.mocked(appliquerHydratationAuCtx).mock.calls[0];
    expect(cible).toBe(ctx);
    expect(h.consSource).toEqual((servie.consumption as { source: unknown }).source);
    expect(ctx.consCurve).toEqual((servie.consumption as { courbe24: number[] }).courbe24);
    // Les kWh affichés et sérialisés sont ceux du serveur, jamais billToAnnualKwh.
    expect(conso.kwhServi()).toBe(servie.kwh_annuel);
    expect(panel.querySelector('[data-cons-bareme]')?.getAttribute('data-bareme')).toBe('societe');

    // Le document enregistré porte la consumption servie telle quelle…
    const doc1 = enregistrerAtelier(ctx);
    const servi = servie.consumption as Record<string, unknown>;
    expect(doc1.consumption?.source).toEqual(servi.source);
    expect(doc1.consumption?.courbe24).toEqual(servi.courbe24);
    expect(doc1.consumption?.saisons).toEqual(servi.saisons);
    expect(doc1.consumption?.methode).toBe(servi.methode);
    // … et rouvrir puis enregistrer sans geste la réémet octet pour octet (critère A).
    const ctx2 = { ...ctxAtelierNeuf() } as unknown as Ctx;
    const relu = JSON.parse(JSON.stringify(doc1));
    appliquerHydratationAuCtx(ctx2, { ...deserializeConsumptionFromLayout(relu), ...lireCouchesDocument(relu) });
    expect(JSON.stringify(enregistrerAtelier(ctx2).consumption)).toBe(JSON.stringify(doc1.consumption));
  });

  it('« Reprendre du lead », le CSV et le Ramadan postent les corps du contrat', async () => {
    const proposer = vi.fn(async (corps: { source: string; ramadan?: unknown }) =>
      reponse(corps.ramadan ? 'exemple_ramadan' : corps.source === 'csv' ? 'exemple_csv_15_min' : 'exemple'));
    const { ctx, panel } = monter(proposer);
    (panel.querySelector('[data-cons-action="lead"]') as HTMLButtonElement).click();
    await attendre();
    expect(proposer).toHaveBeenLastCalledWith(CONTRAT.corps_lead);
    expect(ctx.consSource?.bareme).toBe('societe');

    const jour = panel.querySelector('[data-cons-ramadan-jour]') as HTMLInputElement;
    jour.value = '2027-02-20';
    const ramadan = panel.querySelector('[data-cons-ramadan]') as HTMLInputElement;
    ramadan.checked = true;
    ramadan.dispatchEvent(new Event('change'));
    await attendre();
    expect(proposer).toHaveBeenLastCalledWith({ source: 'lead', ramadan: { actif: true, jour: '2027-02-20' } });
    expect(ctx.consHandEdited).toBe(true); // methode « courbe » servie

    ramadan.checked = false;
    const csv = panel.querySelector('[data-cons-csv]') as HTMLInputElement;
    const contenu = 'horodatage;kwh\n2026-01-01T00:00:00+01:00;0.12\n';
    Object.defineProperty(csv, 'files', { value: [new File([contenu], 'releve.csv')] });
    csv.dispatchEvent(new Event('change'));
    await attendre(); await attendre();
    expect(proposer).toHaveBeenLastCalledWith({ source: 'csv', csv: { contenu } });
    expect(enregistrerAtelier(ctx).consumption?.source.origine).toBe('csv');
  });

  it('un refus est affiché SOUS le champ qu’il nomme (refus décodé par la page hôte)', async () => {
    const motif = (CONTRAT.refus_400_csv as Record<string, string>)['csv.colonne'];
    const proposer = vi.fn(async () => { throw { message: motif, champs: CONTRAT.refus_400_csv }; });
    const { ctx, panel } = monter(proposer);
    const csv = panel.querySelector('[data-cons-csv]') as HTMLInputElement;
    Object.defineProperty(csv, 'files', { value: [new File(['x'], 'r.csv')] });
    csv.dispatchEvent(new Event('change'));
    await attendre(); await attendre();
    const sous = panel.querySelector('[data-refus-champ="csv"]') as HTMLElement;
    expect(sous.hidden).toBe(false);
    expect(sous.textContent).toBe(motif);
    expect(appliquerHydratationAuCtx).not.toHaveBeenCalled();
    expect(ctx.consSource ?? null).toBeNull();
  });

  it('sans option, repli estimation sans source.bareme', async () => {
    vi.useFakeTimers();
    const { ctx, conso, billEl, panel } = monter(null);
    expect(panel.querySelector('[data-cons-proposer]')).toBeNull(); // aucune commande serveur
    expect(panel.querySelector('[data-cons-bareme]')?.textContent).toBe('estimation (barème indicatif)');
    billEl.value = '850';
    billEl.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(700);
    expect(appliquerHydratationAuCtx).not.toHaveBeenCalled();
    expect(conso.kwhServi()).toBeNull();
    ctx.consDailyTarget = 10; // une facture saisie : le bloc est émis, signé par l'atelier
    const source = enregistrerAtelier(ctx).consumption?.source as Record<string, unknown>;
    expect(source.origine).toBe('atelier');
    expect('bareme' in source).toBe(false);
  });

  it('pages publiques (option absente) : le panneau ne change pas', () => {
    const { panel } = monter(undefined);
    expect(panel.innerHTML).toBe('');
  });
});

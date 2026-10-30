// @vitest-environment jsdom
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
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./hydratation', async (importOriginal) => {
  const reel = await importOriginal<typeof import('./hydratation')>();
  // Espion qui DÉLÈGUE à la vraie fonction : aucune application simulée.
  return { ...reel, appliquerHydratationAuCtx: vi.fn(reel.appliquerHydratationAuCtx) };
});

import { createConsumption, type ConsumptionDom, type PropositionConsommation } from './consumption';
import { appliquerHydratationAuCtx } from './hydratation';
import { lireCouchesDocument, deserializeConsumptionFromLayout } from './prefill';
import { ctxAtelierNeuf, enregistrerAtelier } from './harnaisDocument';
import { racineDepot } from './harnaisAtelier';
import { type Ctx } from './context';

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

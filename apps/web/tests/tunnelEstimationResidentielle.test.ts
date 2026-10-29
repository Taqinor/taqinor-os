// @vitest-environment jsdom
// RWEB17-M6 — section « estimation résidentielle et document » du tunnel mon-toit
// (lib/tunnel/estimationResidentielle.ts). Entrées = celles des goldens
// tunnelExecution (montant exact 1800 MAD ; tranche 1500-3000 → 2250).
import { describe, expect, it } from 'vitest';
import { creerContexte, type ConfigLocale } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type EtatPage, type LocaleTunnel } from '../src/lib/tunnel/etat';
import {
  installerEstimationResidentielle, installerEstimationResidentielleSuivi, TEXTES_RESIDENTIEL, fmtNumLocale,
  type ConfigEstimationResidentielle, type ContexteEstimationResidentielle,
} from '../src/lib/tunnel/estimationResidentielle';

const HTML = `
<div id="mt-doc"></div><button id="mt-print-estimate" hidden></button><div id="mt-nearest-install"></div>
<a id="mt-nearest-install-link"></a><span id="mt-nearest-install-text"></span>
<div id="mt-cost-of-waiting"></div><span id="mt-cost-of-waiting-value"></span>
<div id="mt-teaser" hidden></div><div id="mt-teaser-hook-roof" hidden></div><div id="mt-teaser-hook-pump" hidden></div>
<div id="mt-teaser-hook-etude" hidden></div><div id="mt-teaser-hook-rappel" hidden></div>
<p id="mt-estimate-announce"></p><div id="mt-estimate-body" hidden></div><p id="mt-estimate-note" hidden></p>
<p id="mt-estimate-unavailable" hidden></p><p id="mt-estimate-toolarge" hidden></p><p id="mt-estimate-agricole" hidden></p>
<input id="mt-facture-hiver"><p id="mt-facture-hiver-err" hidden></p><input id="mt-city"><input id="rp9-address">
<span id="mt-est-kwc"></span><span id="mt-est-prod"></span><span id="mt-est-savings"></span><span id="mt-est-payback"></span>
<div id="mt-climate-band" hidden></div><span id="mt-climate-band-value"></span>
<div id="mt-doc-chart-wrap" hidden><div id="mt-doc-chart"></div></div>
<div id="mt-doc-hypo-wrap" hidden></div><p id="mt-doc-hypotheses"></p>
<span id="mt-doc-date"></span><span id="mt-doc-subtitle"></span><span id="mt-doc-city"></span>
<div id="mt-doc-city-line" hidden></div><p id="mt-doc-meta" hidden></p>`;

function monter(locale: LocaleTunnel, gate: boolean, bill: number | null, etatPartiel: Partial<EtatPage> = {}, langue = 'fr') {
  document.body.innerHTML = HTML;
  const config: ConfigLocale & ConfigEstimationResidentielle = {
    locale, langueBasculable: locale !== 'en', formatNombre: fmtNumLocale(locale),
    estimationGatee: gate, dateSuitLangue: locale === 'ar',
  };
  const etat = Object.assign(creerEtat(null, locale), { mode: 'residentiel' }, etatPartiel);
  const ctx = creerContexte(creerDom(document), etat, config) as ContexteEstimationResidentielle;
  const appels: string[] = [];
  ctx.crochets.installer('resolveMonthlyBill', () => bill);
  ctx.crochets.installer('isProMode', (m: string) => m === 'commercial' || m === 'industriel');
  ctx.crochets.installer('modeLabel', (m: string) => ({ residentiel: 'Résidentiel' } as Record<string, string>)[m]);
  ctx.crochets.installer('modeDocSubtitle', (m: string) => (m === 'residentiel' ? 'SOUS-TITRE' : undefined));
  ctx.crochets.installer('langueActive', () => langue);
  ctx.crochets.installer('tryRoofSnapshot', () => appels.push('snap'));
  ctx.crochets.installer('updatePanels3dVisibility', () => appels.push('3d'));
  ctx.crochets.installer('hasReachedConsentStep', () => true);
  ctx.crochets.installer('sendFunnelBeacon', (a: string, b: string) => appels.push(`beacon:${a}:${b}`));
  ctx.crochets.installer('computeProEstimate', () => { appels.push('pro'); return true; });
  ctx.crochets.installer('computeAgricoleEstimate', () => null);
  ctx.crochets.installer('renderAgricoleEstimate', () => appels.push('agri'));
  installerEstimationResidentielle(ctx);
  return { ctx, etat, appels };
}
const txt = (id: string) => document.getElementById(id)!.textContent;
const hid = (id: string) => (document.getElementById(id) as HTMLElement).hidden;
const LOCALES: LocaleTunnel[] = ['fr', 'en', 'ar'];

describe('estimation résidentielle — montant exact et tranche × 3 locales', () => {
  for (const loc of LOCALES) {
    it(`montant exact 1800, non gaté (${loc}) : textes #mt-est-*, annonce, 12 barres`, () => {
      // La langue affichée est celle de la page (EN : 'en' ; FR et AR : langue de départ).
      const { ctx, etat } = monter(loc, false, 1800, {}, loc);
      expect(ctx.crochets.appeler('computeEstimate')).toBe(true);
      // Le corps garde la forme source (corps.ts la localise à l'envoi, fbf756f7e).
      expect(etat.estimateShown).toEqual({ kwc: 9.5, prodKwh: 14590, ecoMadMonthLow: 1500, ecoMadMonthHigh: 1800, paybackLabel: '4 à 6 ans' });
      const T = TEXTES_RESIDENTIEL[loc];
      expect(etat.lastKwcLabel).toBe('9,5 kWc');
      expect(etat.lastSavingsLabel.endsWith(T.parMois)).toBe(true);
      expect(txt('mt-est-kwc')).toBe('9,5');
      // RWEB17-M21 / WEBERR-TUNNEL-PAYBACK-ECRAN-FR — le libellé AFFICHÉ suit la langue de l'écran.
      const retour = { fr: '4 à 6 ans', en: '4 – 6 years', ar: '4 – 6 سنة' }[loc];
      expect(txt('mt-est-payback')).toBe(retour);
      expect(txt('mt-est-savings')).toBe(etat.lastSavingsLabel.slice(0, -T.parMois.length));
      expect(txt('mt-estimate-announce')).toBe(T.annonceOk('9,5', txt('mt-est-savings')!, retour));
      expect(document.querySelectorAll('#mt-doc-chart rect')).toHaveLength(12);
      expect(document.getElementById('mt-doc-chart')!.textContent).toContain('kWh');
      expect(hid('mt-doc-chart-wrap')).toBe(false);
      expect(hid('mt-print-estimate')).toBe(false);
      expect(txt('mt-doc-subtitle')).toBe('SOUS-TITRE');
      expect(txt('mt-doc-meta')).toBe(T.projet('Résidentiel'));
    });

    it(`tranche 2250, gaté (${loc}) : golden, annonce gatée, aucun chiffre à l'écran`, () => {
      const { ctx, etat, appels } = monter(loc, true, 2250);
      expect(ctx.crochets.appeler('computeEstimate')).toBe(true);
      expect(etat.estimateShown).toEqual({ kwc: 12, prodKwh: 18430, ecoMadMonthLow: 1800, ecoMadMonthHigh: 2200, paybackLabel: '4 à 6 ans' });
      expect(txt('mt-estimate-announce')).toBe(TEXTES_RESIDENTIEL[loc].annonceGatee);
      expect(hid('mt-teaser')).toBe(false);
      expect(hid('mt-doc')).toBe(true);
      expect(hid('mt-teaser-hook-roof')).toBe(false);
      expect(txt('mt-est-kwc')).toBe('');
      expect(appels).toEqual(expect.arrayContaining(['beacon:estimation:viewed', 'beacon:contact:reached', '3d']));
      expect(etat.docRendered).toBe(true);
    });

    it(`facture absente (${loc}) : indisponible`, () => {
      const { ctx, etat } = monter(loc, true, null, { lastKwc: 4 });
      expect(ctx.crochets.appeler('computeEstimate')).toBe(false);
      expect(txt('mt-estimate-announce')).toBe(TEXTES_RESIDENTIEL[loc].indispoFacture);
      expect(hid('mt-estimate-unavailable')).toBe(false);
      expect(etat.lastKwc).toBeNull();
      expect(etat.estimateShown).toBeNull();
    });

    it(`montant exact au-delà du plafond (${loc}) : erreur inline + accroche « étude »`, () => {
      const { ctx } = monter(loc, true, 1800);
      (document.getElementById('mt-facture-hiver') as HTMLInputElement).value = '99999999';
      expect(ctx.crochets.appeler('computeEstimate')).toBe(false);
      expect(txt('mt-facture-hiver-err')).toBe(TEXTES_RESIDENTIEL[loc].verifierMontantChamp);
      expect(hid('mt-estimate-toolarge')).toBe(false);
      expect(hid('mt-teaser-hook-etude')).toBe(false);
      expect(hid('mt-teaser-hook-roof')).toBe(true);
      expect(txt('mt-estimate-announce')).toBe(TEXTES_RESIDENTIEL[loc].indispoMontant);
    });
  }
});

describe('estimation résidentielle — branches et document', () => {
  it('mode pro délègue à computeProEstimate ; agricole sans hydraulique → rappel', () => {
    const pro = monter('fr', true, 1800, { mode: 'industriel' });
    expect(pro.ctx.crochets.appeler('computeEstimate')).toBe(true);
    expect(pro.appels).toContain('pro');
    const agri = monter('en', true, 1800, { mode: 'agricole' });
    expect(agri.ctx.crochets.appeler('computeEstimate')).toBe(true);
    expect(txt('mt-estimate-announce')).toBe(TEXTES_RESIDENTIEL.en.pompageRappel);
    expect(hid('mt-teaser-hook-rappel')).toBe(false);
    expect(hid('mt-teaser-hook-pump')).toBe(true);
  });

  it('date du document : AR suit la langue affichée, FR reste fr-FR', () => {
    const ar = monter('ar', false, 1800, {}, 'ar');
    ar.ctx.crochets.appeler('fillDocChrome');
    const attAr = new Date().toLocaleDateString('ar-MA-u-nu-latn', { day: 'numeric', month: 'long', year: 'numeric' });
    expect(txt('mt-doc-date')).toBe(attAr);
    const fr = monter('fr', false, 1800, {}, 'ar');
    fr.ctx.crochets.appeler('fillDocChrome');
    expect(txt('mt-doc-date')).toBe(new Date().toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }));
  });

  it('bandeau du document : ville et repère GPS', () => {
    const { ctx } = monter('fr', false, 1800, { capturePin: { lat: 1, lng: 2 } });
    (document.getElementById('mt-city') as HTMLInputElement).value = ' Rabat ';
    ctx.crochets.appeler('fillDocChrome');
    expect(txt('mt-doc-meta')).toBe(`Rabat · ${TEXTES_RESIDENTIEL.fr.projet('Résidentiel')} · ${TEXTES_RESIDENTIEL.fr.toitRepere}`);
    expect(hid('mt-doc-city-line')).toBe(false);
  });

  it('graphique : masqué sans production', () => {
    const { ctx } = monter('fr', false, 1800);
    ctx.crochets.appeler('renderMonthlyChart', 0);
    expect(hid('mt-doc-chart-wrap')).toBe(true);
  });

  it('RWEB17-M21 — page FR basculée en عربي : le retour affiché et annoncé passe en forme arabe', () => {
    const { ctx } = monter('fr', false, 1800, {}, 'ar');
    expect(ctx.crochets.appeler('computeEstimate')).toBe(true);
    expect(txt('mt-est-payback')).toBe('4 – 6 سنة');
    expect(txt('mt-estimate-announce')).toContain('4 – 6 سنة');
  });

  it('RWEB17-M16 — suivi : docEngaged au focus du formulaire et à l’impression ; facture → tranche puis recalcul', () => {
    const { ctx, etat, appels } = monter('fr', true, 1800);
    // Le gabarit commun n'a ni formulaire ni <select> de tranche : on les ajoute puis on rebranche
    // le suivi (l'installateur est idempotent sur l'état, seuls des écouteurs s'ajoutent).
    document.body.insertAdjacentHTML('beforeend', '<form id="mt-form"><input id="mt-name"></form><select id="mt-bill"><option value="x">x</option></select>');
    ctx.crochets.installer('syncBillRangeFromExact', () => appels.push('tranche'));
    installerEstimationResidentielleSuivi(ctx);
    expect(etat.docEngaged).toBe(false);
    document.getElementById('mt-name')!.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    expect(etat.docEngaged).toBe(true);
    etat.docEngaged = false;
    document.getElementById('mt-print-estimate')!.click();
    expect(etat.docEngaged).toBe(true);
    appels.length = 0;
    document.getElementById('mt-facture-hiver')!.dispatchEvent(new Event('input'));
    expect(appels[0]).toBe('tranche');
    expect(appels).toContain('beacon:contact:reached');
    appels.length = 0;
    document.getElementById('mt-bill')!.dispatchEvent(new Event('change'));
    expect(appels).toContain('beacon:contact:reached');
  });

  it('carte KPI : valeur inconnue → carte masquée', () => {
    document.body.insertAdjacentHTML('beforeend', '<div id="c1"></div><span id="v1"></span>');
    const { ctx } = monter('fr', false, 1800);
    document.body.insertAdjacentHTML('beforeend', '<div id="c1"></div><span id="v1"></span>');
    ctx.crochets.appeler('setCard', 'c1', 'v1', null);
    expect(hid('c1')).toBe(true);
    ctx.crochets.appeler('setCard', 'c1', 'v1', '7');
    expect(hid('c1')).toBe(false);
    expect(txt('v1')).toBe('7');
  });
});

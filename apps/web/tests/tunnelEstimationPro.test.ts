// @vitest-environment jsdom
// RWEB17-M5 — section « estimation pro et agricole » du tunnel mon-toit
// (lib/tunnel/estimationPro.ts). Entrées = celles des goldens tunnelExecution
// (industriel 42000 MAD, commercial 9000 kWh, agricole HMT 85 / 30 m³/h).
import { describe, expect, it } from 'vitest';
import { creerContexte, type ConfigLocale } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type EtatPage, type LocaleTunnel } from '../src/lib/tunnel/etat';
import {
  installerEstimationPro, TEXTES_ESTIMATION_PRO, type ConfigEstimationPro, type ContexteEstimationPro,
} from '../src/lib/tunnel/estimationPro';

const HTML = `
<p id="mt-estimate-unavailable"></p><p id="mt-estimate-toolarge"></p><p id="mt-estimate-toolarge-pro" hidden></p>
<p id="mt-estimate-pro-missing" hidden></p><button id="mt-print-estimate" hidden></button>
<input id="mt-pro-bill"><input id="mt-cc-bill"><input id="mt-surface-m2">
<input id="mt-water-need"><input id="mt-hmt"><input id="mt-profondeur"><input id="mt-heures-pompage">
<input id="mt-fuel-spend"><input id="mt-surface-ha"><input id="mt-culture">
<div id="mt-doc-kpis-pro" hidden></div><div id="mt-doc-kpis-agri" hidden></div>
<p id="mt-pro-capped" hidden></p><p id="mt-doc-hypotheses" hidden></p><div id="mt-doc-hypo-wrap" hidden></div>
<p id="mt-estimate-note"></p><div id="mt-doc-flow" hidden></div>
<span id="mt-flow-heures"></span><span id="mt-flow-pompe"></span><span id="mt-flow-eau"></span>
<p id="mt-agri-water-note" hidden></p><span id="mt-agri-water-value"></span>`;

interface Env { ctx: ContexteEstimationPro; annonces: string[]; cartes: Record<string, string | null>; appels: string[]; etat: EtatPage }

function monter(locale: LocaleTunnel, gate: boolean, etatPartiel: Partial<EtatPage>): Env {
  document.body.innerHTML = HTML;
  const loc = locale === 'en' ? 'en-GB' : 'fr-FR';
  const fmt = (n: number) => (Math.round(n * 10) / 10).toLocaleString(loc);
  const config: ConfigLocale & ConfigEstimationPro = {
    locale, langueBasculable: locale !== 'en', formatNombre: fmt, estimationGatee: gate, annonceGatee: 'GATE',
  };
  const etat = Object.assign(creerEtat(null, locale), etatPartiel);
  const ctx = creerContexte(creerDom(document), etat, config) as ContexteEstimationPro;
  const annonces: string[] = [];
  const cartes: Record<string, string | null> = {};
  const appels: string[] = [];
  ctx.crochets.installer('announceEstimate', (m: string) => annonces.push(m));
  ctx.crochets.installer('setCard', (_c: string, v: string, t: string | null) => { cartes[v] = t; });
  ctx.crochets.installer('fillDocChrome', () => appels.push('doc'));
  ctx.crochets.installer('updatePanels3dVisibility', () => appels.push('3d'));
  ctx.crochets.installer('renderMonthlyChart', () => appels.push('chart'));
  ctx.crochets.installer('showEstimateTeaser', (m: string, v: string) => appels.push(`teaser:${m}:${v}`));
  ctx.crochets.installer('hasReachedConsentStep', () => true);
  ctx.crochets.installer('sendFunnelBeacon', (a: string, b: string) => appels.push(`beacon:${a}:${b}`));
  installerEstimationPro(ctx);
  return { ctx, annonces, cartes, appels, etat };
}
const saisir = (id: string, v: string) => { (document.getElementById(id) as HTMLInputElement).value = v; };
const LOCALES: LocaleTunnel[] = ['fr', 'en', 'ar'];

describe('estimation pro — industriel, commercial', () => {
  for (const loc of LOCALES) {
    it(`industriel gaté (${loc}) : annonce gatée, aucun chiffre vers le CRM`, () => {
      const e = monter(loc, true, { mode: 'industriel', tension: 'mt', activity: 'continuous', equipes: '3x8', surfaceType: 'terrasse' });
      saisir('mt-pro-bill', '42000'); saisir('mt-surface-m2', '900');
      expect(e.ctx.crochets.appeler('computeProEstimate')).toBe(true);
      expect(e.annonces).toEqual(['GATE']);
      expect(e.etat.estimateShown).toBeNull();
      expect(e.etat.lastKwcLabel).toBe('');
      expect(e.etat.lastKwc).toBeGreaterThan(0);
      expect(e.etat.lastProTarifMadKwh).toBeGreaterThan(0);
      expect(e.appels).toContain('beacon:estimation:viewed');
      expect(e.appels).toContain('beacon:contact:reached');
      expect(e.cartes).toEqual({});
    });

    it(`industriel non gaté (${loc}) : cartes, hypothèses et annonce de la locale`, () => {
      const e = monter(loc, false, { mode: 'industriel', tension: 'mt', activity: 'continuous', equipes: '3x8', surfaceType: 'terrasse' });
      saisir('mt-pro-bill', '42000'); saisir('mt-surface-m2', '900');
      expect(e.ctx.crochets.appeler('computeProEstimate')).toBe(true);
      expect(Object.keys(e.cartes)).toEqual(['mt-pro-kwc', 'mt-pro-prod', 'mt-pro-autoconso', 'mt-pro-couverture', 'mt-pro-eco', 'mt-pro-retour']);
      const T = TEXTES_ESTIMATION_PRO[loc];
      const retour = e.cartes['mt-pro-retour']!;
      expect(retour).toMatch(loc === 'fr' ? /ans$/ : loc === 'en' ? /years$/ : /سنة$/);
      const hyp = document.getElementById('mt-doc-hypotheses')!;
      expect(hyp.hidden).toBe(false);
      expect(hyp.textContent!.startsWith(T.hypothesesPro('').split(':')[0])).toBe(true);
      expect(e.annonces).toHaveLength(1);
      expect(e.annonces[0]).toBe(T.annonceOk('', e.cartes['mt-pro-eco']));
      expect(e.appels).toContain('chart');
      expect((document.getElementById('mt-print-estimate') as HTMLElement).hidden).toBe(false);
    });
  }

  it('commercial en kWh lit #mt-cc-bill', () => {
    const e = monter('fr', true, { mode: 'commercial', ccUnit: 'kwh' });
    expect(e.ctx.crochets.appeler('proBillId')).toBe('mt-cc-bill');
    saisir('mt-cc-bill', '9000');
    expect(e.ctx.crochets.appeler('computeProEstimate')).toBe(true);
    expect(e.annonces).toEqual(['GATE']);
  });

  for (const loc of LOCALES) {
    it(`facture absente (${loc}) : indisponible, état remis à zéro`, () => {
      const e = monter(loc, true, { mode: 'industriel', lastKwc: 3, lastKwcLabel: 'x' });
      expect(e.ctx.crochets.appeler('computeProEstimate')).toBe(false);
      expect(e.annonces).toEqual([TEXTES_ESTIMATION_PRO[loc].indispoConso]);
      expect(e.etat.lastKwc).toBeNull();
      expect(document.getElementById('mt-estimate-pro-missing')!.hidden).toBe(false);
    });

    it(`au-delà du plafond (${loc}) : message « étude dédiée » + accroche en parcours gaté`, () => {
      const e = monter(loc, true, { mode: 'industriel', proUnit: 'mad' });
      saisir('mt-pro-bill', '2000000');
      expect(e.ctx.crochets.appeler('computeProEstimate')).toBe(true);
      expect(e.annonces).toEqual([TEXTES_ESTIMATION_PRO[loc].etudeDedie]);
      expect(e.appels).toContain('teaser:industriel:etude');
      expect(document.getElementById('mt-estimate-toolarge-pro')!.hidden).toBe(false);
    });
  }
});

describe('estimation agricole', () => {
  const ETAT = { mode: 'agricole', waterSource: 'forage', waterUnit: 'm3h' } as Partial<EtatPage>;
  const entrees = () => {
    saisir('mt-profondeur', '60'); saisir('mt-hmt', '85'); saisir('mt-water-need', '30');
    saisir('mt-heures-pompage', '9'); saisir('mt-fuel-spend', '2500');
  };

  for (const loc of LOCALES) {
    it(`gaté (${loc}) : estimateShown = golden agricole, annonce gatée`, () => {
      const e = monter(loc, true, ETAT);
      entrees();
      const ag = e.ctx.crochets.appeler('computeAgricoleEstimate');
      expect(ag).not.toBeNull();
      e.ctx.crochets.appeler('renderAgricoleEstimate', ag);
      expect(e.etat.estimateShown).toEqual({ pompeCv: 30, champKwc: 31.24, nbPanneaux: 44, m3Jour: 270, bassinM3: 270 });
      expect(e.etat.lastKwc).toBeNull();
      expect(e.annonces).toEqual(['GATE']);
      expect(e.etat.lastKwcLabel).toBe(TEXTES_ESTIMATION_PRO[loc].champPv(e.etat.lastKwcLabel.split(' kWc')[0]));
    });

    it(`non gaté (${loc}) : cartes, flux et annonce de la locale`, () => {
      const e = monter(loc, false, ETAT);
      entrees();
      e.ctx.crochets.appeler('renderAgricoleEstimate', e.ctx.crochets.appeler('computeAgricoleEstimate'));
      const T = TEXTES_ESTIMATION_PRO[loc];
      expect(e.cartes['mt-agri-pompe']).toContain(T.uniteCv);
      expect(e.cartes['mt-agri-champ']).toContain(T.panneaux(44).trim().slice(2));
      expect(e.cartes['mt-agri-fuel']).toBe(T.carburant(loc === 'en' ? '2,500' : (2500).toLocaleString('fr-FR')));
      expect(document.getElementById('mt-flow-eau')!.textContent).toBe(T.fluxEau((270).toLocaleString(loc === 'en' ? 'en-GB' : 'fr-FR')));
      expect(document.getElementById('mt-doc-flow')!.hidden).toBe(false);
      expect(e.annonces[0]).toBe(T.annonceAgri(e.cartes['mt-agri-pompe'], e.cartes['mt-agri-champ']));
      expect(e.etat.estimateShown).toMatchObject({ pompeCv: 30, m3Jour: 270 });
    });
  }

  it('entrées insuffisantes → null', () => {
    const e = monter('fr', true, ETAT);
    expect(e.ctx.crochets.appeler('computeAgricoleEstimate')).toBeNull();
  });
});

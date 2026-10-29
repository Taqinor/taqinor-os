// @vitest-environment jsdom
// RWEB17-M2 — section « parcours » du tunnel mon-toit, hors page.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { creerContexte } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type LocaleTunnel } from '../src/lib/tunnel/etat';
import { installerParcours, TABLES_PARCOURS } from '../src/lib/tunnel/parcours';

const MODES = ['', 'residentiel', 'industriel', 'commercial', 'agricole'] as const;
const LOCALES: LocaleTunnel[] = ['fr', 'en', 'ar'];

function monter() {
  document.body.innerHTML = `
    <section>
      <ol><li class="mt-step"><div class="mt-step-bar"></div><span class="mt-step-label">a</span></li>
          <li class="mt-step"><div class="mt-step-bar"></div><span class="mt-step-label">b</span></li></ol>
      <div id="mt-panel-0"></div><div id="mt-panel-1" hidden></div><div id="mt-reveal" hidden></div>
      <h2 id="mt-h2-0"></h2><h2 id="mt-h2-1"></h2>
      <button class="mt-mode" data-mode="residentiel"></button>
      <button class="mt-mode" data-mode="industriel"></button>
      <button class="mt-mode" data-mode="commercial"></button>
      <button class="mt-mode" data-mode="agricole"></button>
      <p id="mt-mode-err" hidden></p>
      <div id="mt-sub-residentiel"></div><div id="mt-sub-professionnel"></div>
      <div id="mt-sub-commercial"></div><div id="mt-sub-agricole"></div>
      <div id="mt-step0-intro"></div><div id="mt-step0-intro-agri"></div><div id="mt-roof-mode-group"></div>
      <div id="mt-raison-sociale-wrap"></div>
      <input id="mt-city"><span id="mt-city-hint" hidden></span>
      <input type="radio" id="mt-contact-phone"><input type="radio" id="mt-contact-whatsapp"><div id="mt-callback-sla"></div>
      <button id="mt-next-0"></button><button id="mt-back-1"></button>
      <span data-i18n data-ar="مرحبا">Bonjour</span>
    </section>`;
}

function installer(locale: LocaleTunnel, mode: string, extra: Record<string, (...a: any[]) => any> = {}) {
  const ctx = creerContexte(creerDom(document), creerEtat({ mode }, locale), {
    locale, langueBasculable: locale !== 'en', formatNombre: (n) => String(n),
  });
  const appels: string[] = [];
  const faux: Record<string, (...a: any[]) => any> = {
    saveWizardState: () => appels.push('save'), markDataEntered: () => appels.push('mark'),
    hasReachedConsentStep: () => false, sendFunnelBeacon: () => {}, ensureMapBooted: () => appels.push('map'),
    validateStep0: () => true, validateStep1: () => true, computeEstimate: () => true, showWhatsappOffer: () => {},
    ...extra,
  };
  for (const [n, f] of Object.entries(faux)) ctx.crochets.installer(n, f);
  const p = installerParcours(ctx, { mode });
  return { ctx, p, appels };
}

beforeEach(() => {
  monter();
  history.replaceState(null, '', '/');
  window.scrollTo = vi.fn() as never;
  Element.prototype.scrollIntoView = vi.fn();
});

describe.each(LOCALES)('parcours — %s', (locale) => {
  it.each(MODES)('mode « %s » : panneaux visibles, libellés, cartes', (mode) => {
    const { ctx, p } = installer(locale, mode);
    p.brancherModes();
    const eff = mode || 'residentiel';
    const vis = (id: string) => !(document.getElementById(id) as HTMLElement).hidden;
    expect(vis('mt-sub-residentiel')).toBe(eff === 'residentiel');
    expect(vis('mt-sub-professionnel')).toBe(eff === 'industriel');
    expect(vis('mt-sub-commercial')).toBe(eff === 'commercial');
    expect(vis('mt-sub-agricole')).toBe(eff === 'agricole');
    expect(vis('mt-step0-intro-agri')).toBe(eff === 'agricole');
    expect(vis('mt-raison-sociale-wrap')).toBe(eff === 'industriel' || eff === 'commercial');
    const labels = TABLES_PARCOURS[locale].stepLabelsByMode[eff];
    const lus = [...document.querySelectorAll('.mt-step-label')].map((e) => e.textContent);
    expect(lus).toEqual([labels[0], labels[1]]);
    expect(document.getElementById('mt-h2-0')!.textContent).toBe(labels[0]);
    const pressed = [...document.querySelectorAll<HTMLElement>('.mt-mode')].filter((b) => b.getAttribute('aria-pressed') === 'true');
    expect(pressed.map((b) => b.dataset.mode)).toEqual(mode ? [mode] : []);
    expect(ctx.etat.mode).toBe(mode);
  });

  it('goStep pousse history.state ; popstate revient en arrière', () => {
    const { ctx, p } = installer(locale, 'residentiel');
    p.brancherEtapes();
    expect(history.state).toEqual({ mtStep: 0, mtRevealed: false });
    p.goStep(1);
    expect(history.state).toEqual({ mtStep: 1, mtRevealed: false });
    expect((document.getElementById('mt-panel-1') as HTMLElement).hidden).toBe(false);
    expect((document.getElementById('mt-panel-0') as HTMLElement).hidden).toBe(true);
    window.dispatchEvent(new PopStateEvent('popstate', { state: { mtStep: 0, mtRevealed: false } }));
    expect(ctx.etat.step).toBe(0);
    expect((document.getElementById('mt-panel-0') as HTMLElement).hidden).toBe(false);
    // entrée héritée mtStep 2 : étape bornée à 1 et révélation ouverte
    window.dispatchEvent(new PopStateEvent('popstate', { state: { mtStep: 2 } }));
    expect(ctx.etat.step).toBe(1);
    expect(ctx.etat.revealed).toBe(true);
    expect((document.getElementById('mt-reveal') as HTMLElement).hidden).toBe(false);
  });

  it('langue affichée : FR/AR basculables (défaut propre à la locale), EN sans bascule', () => {
    const { ctx, p } = installer(locale, '');
    if (locale === 'en') {
      expect(p.langueActive()).toBe('en');
      expect(document.querySelector('[data-i18n]')!.children).toHaveLength(0);
      return;
    }
    expect(p.langueActive()).toBe(locale === 'ar' ? 'ar' : 'fr');
    expect(document.documentElement.dir).toBe(locale === 'ar' ? 'rtl' : '');
    p.applyLang('ar');
    expect(ctx.etat.currentLang).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    p.applyLang('fr');
    expect(p.langueActive()).toBe('fr');
    expect(document.documentElement.dir).toBe('ltr');
  });
});

describe('parcours — divers', () => {
  it('?mode= valide présélectionne ; professionnel migre vers industriel', () => {
    history.replaceState(null, '', '/?mode=agricole');
    expect(installer('fr', '').ctx.etat.mode).toBe('agricole');
    history.replaceState(null, '', '/?mode=nimporte');
    expect(installer('fr', '').ctx.etat.mode).toBe('');
    history.replaceState(null, '', '/');
    expect(installer('fr', 'professionnel').ctx.etat.mode).toBe('industriel');
  });

  it('SLA de rappel : visible seulement si « m\'appeler » est coché', () => {
    const { p } = installer('fr', '');
    p.brancherRappel();
    const sla = document.getElementById('mt-callback-sla') as HTMLElement;
    expect(sla.hidden).toBe(true);
    const radio = document.getElementById('mt-contact-phone') as HTMLInputElement;
    radio.checked = true;
    radio.dispatchEvent(new Event('change'));
    expect(sla.hidden).toBe(false);
  });

  it('un crochet manquant lève une erreur claire', () => {
    const { p } = installer('fr', '', {});
    const ctx2 = creerContexte(creerDom(document), creerEtat(null, 'fr'), { locale: 'fr', langueBasculable: true, formatNombre: String });
    const p2 = installerParcours(ctx2, null);
    expect(() => p2.renderStep()).toThrow('Crochet non installé : ensureMapBooted');
    expect(p).toBeTruthy();
  });
});

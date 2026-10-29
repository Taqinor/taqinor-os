// @vitest-environment jsdom
// RWEB17-M8 — section « envoi et sortie » (lib/tunnel/envoi.ts) sur un fragment
// HTML minimal, dans les trois locales : envoi OK (ligne « Ma référence » du message
// WhatsApp, D-RWEB17-WA-REF), 500, hors ligne, délai dépassé, modale de sortie.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { creerContexte, type ContexteTunnel } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type LocaleTunnel } from '../src/lib/tunnel/etat';
import { installerEnvoi } from '../src/lib/tunnel/envoi';

const LOCALES: LocaleTunnel[] = ['fr', 'en', 'ar'];
const HTML = `
<main id="page"><form id="mt-form">
  <input id="mt-name" value="Karim"><input id="mt-city" value="Casablanca"><input id="mt-contact-phone" type="checkbox">
  <p id="mt-error" hidden></p><input id="mt-bill">
  <button id="mt-submit"><span id="mt-submit-label">Envoyer</span><span id="mt-submit-pending" hidden>...</span></button>
  <div id="mt-success" hidden><span id="mt-client-ref"></span><a id="mt-success-wa" href="#"></a></div>
  <div id="mt-belowthreshold" hidden><a id="mt-belowthreshold-wa" href="#"></a></div>
</form></main>
<div id="mt-exit" hidden><button id="mt-exit-close">x</button><input id="mt-exit-phone"><a id="mt-exit-wa" href="#">wa</a><p id="mt-exit-err" hidden></p></div>
<button id="mt-next-0">n</button><button id="mt-lang-fr">f</button>`;

const MSG = {
  fr: { serveur: 'Un problème technique de notre côté — réessayez.', horsLigne: 'Pas de connexion — vos réponses sont conservées, on réessaie dès le retour du réseau.', surligne: 'Vérifiez les champs surlignés ci-dessus.', sortie: "Indiquez un numéro pour qu'on vous réponde." },
  en: { serveur: 'A technical problem on our side — please try again.', horsLigne: "No connection — your answers are kept, we'll retry as soon as the network is back.", surligne: 'Please check the highlighted fields above.', sortie: 'Please enter a number so we can reply to you.' },
  ar: { serveur: 'مشكلة تقنية من جانبنا — يرجى إعادة المحاولة.', horsLigne: 'لا يوجد اتصال — إجاباتكم محفوظة، سنعيد المحاولة فور عودة الشبكة.', surligne: 'يرجى مراجعة الحقول المُبرزة أعلاه.', sortie: 'يرجى إدخال رقم للرد عليكم.' },
};

const attendre = async () => { for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 0)); };

function monter(locale: LocaleTunnel, errors: Record<string, string> = {}) {
  document.body.innerHTML = HTML;
  const etat = creerEtat(null, locale);
  etat.mode = 'residentiel';
  etat.lastKwcLabel = '9,5 kWc';
  const ctx: ContexteTunnel = creerContexte(creerDom(document), etat, { locale, langueBasculable: locale !== 'en', formatNombre: String });
  const appels: string[] = [];
  const stub = (nom: string, fn: (...a: any[]) => any) => ctx.crochets.installer(nom, fn);
  stub('langueActive', () => locale);
  stub('corpsDuLead', () => ({ body: { fullName: 'Karim' }, errors }));
  stub('showInlineErrors', (e: object) => appels.push(`inline:${Object.keys(e).length}`));
  stub('traduireErreur', (m: string) => m);
  stub('getOrCreateClientRef', () => etat.clientRef || 'TQ-ABCD1');
  stub('getOrCreateDedupTokens', () => ({ idempotencyKey: 'idem-12345678', eventId: 'evt-12345678' }));
  stub('clearWizardState', () => appels.push('clear'));
  stub('syncOfflineBanner', () => appels.push('offline'));
  stub('sendFunnelBeacon', (s: string, a: string) => appels.push(`beacon:${s}:${a}`));
  stub('hasReachedConsentStep', () => true);
  stub('resolveMonthlyBill', () => null);
  stub('syncBillRangeFromExact', () => appels.push('sync'));
  stub('computeEstimate', () => appels.push('compute'));
  installerEnvoi(ctx, document);
  return { ctx, etat, appels };
}

async function envoyer() {
  document.getElementById('mt-form')!.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
  await attendre();
}
const texte = (id: string) => document.getElementById(id)!.textContent;

beforeEach(() => {
  window.matchMedia = (() => ({ matches: true })) as unknown as typeof window.matchMedia;
  if (!AbortSignal.timeout) (AbortSignal as unknown as { timeout: () => AbortSignal }).timeout = () => new AbortController().signal;
  Element.prototype.scrollIntoView = function () {};
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
});
// Les écouteurs posés sur `document` par un test ne doivent pas survivre au suivant.
const ecouteursDocument: Array<[string, EventListenerOrEventListenerObject]> = [];
const ajouterOrigine = document.addEventListener.bind(document);
document.addEventListener = ((type: string, fn: EventListenerOrEventListenerObject, opts?: unknown) => {
  ecouteursDocument.push([type, fn]);
  ajouterOrigine(type, fn, opts as boolean);
}) as typeof document.addEventListener;
afterEach(() => {
  vi.unstubAllGlobals();
  for (const [type, fn] of ecouteursDocument.splice(0)) document.removeEventListener(type, fn);
});

describe.each(LOCALES)('RWEB17-M8 — envoi et sortie · %s', (locale) => {
  it('envoi OK : succès affiché, lien WhatsApp avec « Ma référence », champs désactivés, instantané effacé', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ok: true, qualified: true }), { status: 200 })));
    const { etat, appels } = monter(locale);
    await envoyer();
    expect(document.getElementById('mt-success')!.hidden).toBe(false);
    expect(texte('mt-client-ref')).toBe('TQ-ABCD1');
    const href = decodeURIComponent((document.getElementById('mt-success-wa') as HTMLAnchorElement).href);
    expect(href).toContain('Ma référence : TQ-ABCD1.'); // D-RWEB17-WA-REF : les trois locales
    expect(href).toContain('installation estimée 9,5 kWc');
    expect(etat.submitted).toBe(true);
    expect((document.getElementById('mt-name') as HTMLInputElement).disabled).toBe(true);
    expect(appels).toContain('clear');
  });

  it('sous le seuil : message de seuil + lien WhatsApp, pas de succès', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ok: true, qualified: false }), { status: 200 })));
    monter(locale);
    await envoyer();
    expect(document.getElementById('mt-success')!.hidden).toBe(true);
    expect(document.getElementById('mt-belowthreshold')!.hidden).toBe(false);
    expect(decodeURIComponent((document.getElementById('mt-belowthreshold-wa') as HTMLAnchorElement).href)).toContain('Ma référence : TQ-ABCD1.');
  });

  it('erreur 500 : message serveur de la langue, CTA rétabli', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 500 })));
    const { etat } = monter(locale);
    await envoyer();
    expect(texte('mt-error')).toBe(MSG[locale].serveur);
    expect(document.getElementById('mt-error')!.hidden).toBe(false);
    expect((document.getElementById('mt-submit') as HTMLButtonElement).disabled).toBe(false);
    expect(etat.submitted).toBe(false);
  });

  it('hors ligne : message dédié ; en ligne avec réseau coupé / délai dépassé : message serveur', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('réseau'); }));
    const { appels } = monter(locale);
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: false });
    await envoyer();
    expect(texte('mt-error')).toBe(MSG[locale].horsLigne);
    expect(appels).toContain('offline');
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true });
    vi.stubGlobal('fetch', vi.fn(async () => { throw new DOMException('délai', 'TimeoutError'); }));
    await envoyer();
    expect(texte('mt-error')).toBe(MSG[locale].serveur);
  });

  it('erreurs de champ : message surligné, pas de requête', async () => {
    const f = vi.fn();
    vi.stubGlobal('fetch', f);
    const { appels } = monter(locale, { fullName: 'x' });
    await envoyer();
    expect(f).not.toHaveBeenCalled();
    expect(texte('mt-error')).toBe(MSG[locale].surligne);
    expect(appels).toContain('inline:1');
  });

  it('modale de sortie : une seule fois, jamais après envoi, Échap rend le focus, piège de focus', () => {
    const { etat, appels } = monter(locale);
    etat.step = 1;
    etat.lastKwc = 9.5;
    etat.revealed = true;
    const modale = document.getElementById('mt-exit') as HTMLElement;
    ctxMaybe(() => document.dispatchEvent(new window.Event('visibilitychange')), false);
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
    document.dispatchEvent(new window.Event('visibilitychange'));
    expect(modale.hidden).toBe(false);
    expect(etat.exitShown).toBe(true);
    expect(appels).toContain('beacon:contact:abandoned');
    expect(document.getElementById('page')!.hasAttribute('inert')).toBe(true);
    // Tab sur le dernier élément boucle sur le premier
    const dernier = document.getElementById('mt-exit-wa')!;
    dernier.focus();
    const tab = new window.KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    modale.dispatchEvent(tab);
    modale.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(modale.hidden).toBe(true);
    expect(document.getElementById('page')!.hasAttribute('inert')).toBe(false);
    // une seule fois : un second déclenchement ne rouvre pas
    document.dispatchEvent(new window.Event('visibilitychange'));
    expect(modale.hidden).toBe(true);
  });

  it('lien WhatsApp de sortie : numéro trop court bloqué avec le message de la langue', () => {
    monter(locale);
    const lien = document.getElementById('mt-exit-wa') as HTMLAnchorElement;
    const clic = new window.MouseEvent('click', { bubbles: true, cancelable: true });
    lien.dispatchEvent(clic);
    expect(clic.defaultPrevented).toBe(true);
    expect(texte('mt-exit-err')).toBe(MSG[locale].sortie);
    const saisie = document.getElementById('mt-exit-phone') as HTMLInputElement;
    saisie.value = '0612345678';
    saisie.dispatchEvent(new window.Event('input', { bubbles: true }));
    expect(decodeURIComponent(lien.href)).toContain('Mon numéro : 0612345678.');
  });

  it('init finale : tranche resynchronisée, estimation recalculée si déjà révélée', () => {
    const { appels } = monter(locale);
    expect(appels).toEqual(['sync']);
    document.body.innerHTML = HTML;
    const e = creerEtat({ step: 1, revealed: true }, locale);
    const ctx = creerContexte(creerDom(document), e, { locale, langueBasculable: locale !== 'en', formatNombre: String });
    const vus: string[] = [];
    for (const nom of ['langueActive', 'corpsDuLead', 'showInlineErrors', 'traduireErreur', 'getOrCreateClientRef', 'getOrCreateDedupTokens', 'clearWizardState', 'syncOfflineBanner', 'sendFunnelBeacon', 'hasReachedConsentStep', 'resolveMonthlyBill']) ctx.crochets.installer(nom, () => null);
    ctx.crochets.installer('syncBillRangeFromExact', () => vus.push('sync'));
    ctx.crochets.installer('computeEstimate', () => vus.push('compute'));
    installerEnvoi(ctx, document);
    expect(vus).toEqual(['sync', 'compute']);
  });
});

/** Aucun déclenchement tant que la page est visible. */
function ctxMaybe(fn: () => void, attenduOuvert: boolean) {
  fn();
  expect((document.getElementById('mt-exit') as HTMLElement).hidden).toBe(!attenduOuvert);
}

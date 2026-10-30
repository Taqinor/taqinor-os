// @vitest-environment jsdom
// RWEB17-M1 — section « persistance » du tunnel mon-toit, hors page.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { creerContexte } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat } from '../src/lib/tunnel/etat';
import {
  installerPersistance, loadWizardState, readTrackingParams, WIZARD_STORAGE_KEY,
} from '../src/lib/tunnel/persistance';

const CONFIG = { locale: 'fr' as const, langueBasculable: true, formatNombre: (n: number) => String(n) };

function monter() {
  document.body.innerHTML = `
    <div id="mt-offline-banner" hidden></div>
    <input id="mt-name"><input id="mt-city"><input id="mt-heures-pompage">
    <input type="checkbox" id="mt-consent">`;
}

function ctxDepuis(saved = loadWizardState()) {
  const ctx = creerContexte(creerDom(document), creerEtat(saved, 'fr'), CONFIG);
  for (const nom of ['syncCityRequirement', 'syncCallbackSla', 'syncEquipDetails']) ctx.crochets.installer(nom, () => {});
  return { ctx, p: installerPersistance(ctx, saved) };
}

beforeEach(() => {
  sessionStorage.clear();
  monter();
});

describe('persistance — aller-retour', () => {
  it('sauvegarde → rechargement → réhydratation identique', () => {
    const a = ctxDepuis();
    (document.getElementById('mt-name') as HTMLInputElement).value = 'Amal';
    (document.getElementById('mt-city') as HTMLInputElement).value = 'Rabat';
    (document.getElementById('mt-consent') as HTMLInputElement).checked = true;
    a.ctx.etat.mode = 'residentiel';
    a.ctx.etat.capturePin = { lat: 33.5, lng: -7.6 };
    a.p.saveWizardState();
    expect(sessionStorage.getItem(WIZARD_STORAGE_KEY)).toContain('Amal');

    monter(); // « rechargement » : DOM vierge, instantané relu
    const saved = loadWizardState();
    const b = ctxDepuis(saved);
    b.p.rehydrater();
    expect((document.getElementById('mt-name') as HTMLInputElement).value).toBe('Amal');
    expect((document.getElementById('mt-city') as HTMLInputElement).value).toBe('Rabat');
    expect((document.getElementById('mt-consent') as HTMLInputElement).checked).toBe(true);
    expect(b.ctx.etat.mode).toBe('residentiel');
    expect(b.ctx.etat.capturePin).toEqual({ lat: 33.5, lng: -7.6 });
    expect(b.ctx.etat.cityTouched).toBe(true);
    expect(b.ctx.etat.hasEnteredData).toBe(true);
    expect(b.ctx.etat.dedupIdempotencyKey).toBe(a.ctx.etat.dedupIdempotencyKey);
    expect(b.ctx.etat.restoring).toBe(false);
  });

  it('restoring empêche toute ré-écriture pendant la réhydratation', () => {
    const a = ctxDepuis();
    (document.getElementById('mt-name') as HTMLInputElement).value = 'Amal';
    a.p.saveWizardState();
    const avant = sessionStorage.getItem(WIZARD_STORAGE_KEY);
    const b = ctxDepuis();
    b.ctx.crochets.installer('syncCallbackSla', () => {
      b.p.saveWizardState(); // appelé pendant la réhydratation
      expect(b.ctx.etat.restoring).toBe(true);
    });
    (document.getElementById('mt-name') as HTMLInputElement).value = 'Autre';
    const spy = vi.spyOn(Storage.prototype, 'setItem');
    b.p.rehydrater();
    expect(spy.mock.calls.filter(([k]) => k === WIZARD_STORAGE_KEY)).toHaveLength(0);
    expect(sessionStorage.getItem(WIZARD_STORAGE_KEY)).toBe(avant);
    spy.mockRestore();
  });
});

describe('persistance — balise de funnel', () => {
  it("n'est émise qu'une fois par étape (et jamais avant la révélation WB30 côté appelant)", () => {
    const beacon = vi.fn(() => true);
    Object.defineProperty(navigator, 'sendBeacon', { value: beacon, configurable: true });
    const { ctx, p } = ctxDepuis();
    p.sendFunnelBeacon('toit', 'reached');
    p.sendFunnelBeacon('toit', 'reached');
    p.sendFunnelBeacon('facture', 'reached');
    p.sendFunnelBeacon('toit', 'abandoned');
    p.sendFunnelBeacon('toit', 'abandoned');
    expect(beacon).toHaveBeenCalledTimes(4); // reached dédoublonné, abandoned jamais
    expect(p.hasReachedConsentStep()).toBe(false);
    ctx.etat.step = 1;
    ctx.etat.revealed = true;
    expect(p.hasReachedConsentStep()).toBe(true);
  });
});

describe('persistance — clés de suivi et jetons', () => {
  it("lit les clés de suivi depuis le sessionStorage ('tq_' + clé), seulement les présentes", () => {
    sessionStorage.setItem('tq_fbclid', 'abc');
    sessionStorage.setItem('tq_utm_source', 'meta');
    expect(readTrackingParams()).toEqual({ fbclid: 'abc', utm_source: 'meta' });
    expect(readTrackingParams()).not.toHaveProperty('gclid');
  });

  it('la référence client et les jetons sont stables après le premier appel', () => {
    const { p } = ctxDepuis();
    expect(p.getOrCreateClientRef()).toBe(p.getOrCreateClientRef());
    expect(p.getOrCreateDedupTokens()).toEqual(p.getOrCreateDedupTokens());
  });

  it('crochet absent : erreur claire ; crochets de la section installés', () => {
    const { ctx } = ctxDepuis();
    expect(ctx.crochets.a('saveWizardState')).toBe(true);
    // RWEB17-M11 — l'envoi (M8) appelle `syncOfflineBanner` : la persistance l'inscrit.
    expect(ctx.crochets.a('syncOfflineBanner')).toBe(true);
    const bandeau = document.getElementById('mt-offline-banner')!;
    bandeau.hidden = !navigator.onLine;
    ctx.crochets.appeler('syncOfflineBanner');
    expect(bandeau.hidden).toBe(navigator.onLine);
    expect(() => ctx.crochets.appeler('inconnu')).toThrow('Crochet non installé : inconnu');
  });
});

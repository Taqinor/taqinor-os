// @vitest-environment jsdom
// RWEB17-M4 — section « carte et toiture » du tunnel mon-toit (lib/tunnel/carte.ts).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { creerContexte, type ConfigLocale } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type LocaleTunnel } from '../src/lib/tunnel/etat';
import { installerCarte, TEXTES_CARTE, type ConfigCarte, type ContexteCarte } from '../src/lib/tunnel/carte';

const HTML = `
<input id="mt-city"><input id="rp9-address">
<div id="mt-fallback" hidden></div><div id="mt-stage"></div><div id="mt-roof-mode-group"></div>
<div id="rp9-map" class="mt-skeleton-shimmer"></div><p id="rp9-status"></p>
<button class="mt-roof-mode" data-value="point">p</button><button class="mt-roof-mode" data-value="draw">d</button>
<button id="rp9-finish" hidden></button>
<div id="mt-pin-confirm" hidden></div><span id="mt-pin-confirm-address" hidden></span>
<button id="mt-pin-confirm-yes"></button><button id="mt-pin-confirm-adjust"></button>
<div id="mt-panels3d" hidden><div id="mt-panels3d-stage"></div><div id="mt-panels3d-overlay"></div>
<button id="mt-panels3d-start"></button><p id="mt-panels3d-hint" hidden></p></div>
<figure id="mt-doc-roof" hidden><img id="mt-doc-roof-img"><span id="mt-doc-roof-attr"></span></figure>
<button id="mt-print-estimate"></button>`;

function monter(locale: LocaleTunnel, extra: Partial<ConfigCarte> = {}, langue = 'fr') {
  document.body.innerHTML = HTML;
  const bootCaptureOnly = vi.fn();
  const chargeurs = {
    captureBoot: vi.fn(async () => ({ bootCaptureOnly })),
    viewerOnly: vi.fn(async () => ({ createRoofViewer: vi.fn() })),
  };
  const config: ConfigLocale & ConfigCarte = {
    locale, langueBasculable: locale !== 'en', formatNombre: String,
    doc: document, reducedMotion: true, estimationGatee: true, apercu3dPublic: true,
    statutsSuiventLangue: locale === 'ar', optionsBootLocale: {}, chargeurs, ...extra,
  };
  const ctx = creerContexte(creerDom(document), creerEtat(null, locale), config) as ContexteCarte;
  const appels: string[] = [];
  ctx.crochets.installer('syncCityRequirement', () => appels.push('city'));
  ctx.crochets.installer('markDataEntered', () => appels.push('mark'));
  ctx.crochets.installer('saveWizardState', () => appels.push('save'));
  ctx.crochets.installer('langueActive', () => langue);
  installerCarte(ctx);
  return { ctx, appels, bootCaptureOnly, chargeurs };
}
const attendre = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('carte — repli et démarrage', () => {
  it('/api/roof-config indisponible → repli adresse', async () => {
    (fetch as any).mockRejectedValue(new Error('hors ligne'));
    const { ctx } = monter('fr');
    ctx.crochets.appeler('ensureMapBooted');
    await attendre();
    expect(document.getElementById('mt-fallback')!.hidden).toBe(false);
    expect(document.getElementById('mt-stage')!.hidden).toBe(true);
    expect(document.getElementById('mt-roof-mode-group')!.hidden).toBe(true);
    expect(document.getElementById('rp9-map')!.classList.contains('mt-skeleton-shimmer')).toBe(false);
  });

  it('délai dépassé (AbortSignal.timeout) → repli', async () => {
    (fetch as any).mockRejectedValue(new DOMException('timeout', 'TimeoutError'));
    const { ctx } = monter('en');
    ctx.crochets.appeler('ensureMapBooted');
    await attendre();
    expect(document.getElementById('mt-fallback')!.hidden).toBe(false);
  });

  it('config sans clé → repli', async () => {
    (fetch as any).mockResolvedValue({ json: async () => ({ available: false }) });
    const { ctx, chargeurs } = monter('fr');
    ctx.crochets.appeler('ensureMapBooted');
    await attendre();
    expect(document.getElementById('mt-fallback')!.hidden).toBe(false);
    expect(chargeurs.captureBoot).not.toHaveBeenCalled();
  });

  it('un seul démarrage de la carte, options de locale transmises', async () => {
    (fetch as any).mockResolvedValue({ json: async () => ({ available: true, maptilerKey: 'k', mapboxToken: 't' }) });
    const { ctx, bootCaptureOnly, chargeurs } = monter('ar', { optionsBootLocale: { dir: 'rtl' } });
    ctx.crochets.appeler('ensureMapBooted');
    ctx.crochets.appeler('ensureMapBooted');
    await attendre(); await attendre();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(chargeurs.captureBoot).toHaveBeenCalledTimes(1);
    expect(bootCaptureOnly).toHaveBeenCalledTimes(1);
    expect(bootCaptureOnly.mock.calls[0][0]).toMatchObject({ maptilerKey: 'k', mapboxToken: 't', dir: 'rtl' });
  });

  it('onCaptureChange met à jour l’état, la ville et la confirmation du repère', async () => {
    (fetch as any).mockResolvedValue({ json: async () => ({ available: true, maptilerKey: 'k' }) });
    const { ctx, bootCaptureOnly, appels } = monter('fr');
    ctx.crochets.appeler('ensureMapBooted');
    await attendre(); await attendre();
    const opts = bootCaptureOnly.mock.calls[0][0];
    expect(opts.roofInputMode()).toBe('point');
    opts.onCaptureChange({ pin: { lat: 33.5, lng: -7.6 }, outline: [], pans: [], layout: null, address: ' Casablanca ' });
    expect(ctx.etat.capturePin).toEqual({ lat: 33.5, lng: -7.6 });
    expect((document.getElementById('mt-city') as HTMLInputElement).value).toBe('Casablanca');
    expect(appels).toContain('city');
    expect(document.getElementById('mt-pin-confirm')!.hidden).toBe(false);
    expect(document.getElementById('mt-pin-confirm-address')!.textContent).toBe('Casablanca');
  });
});

describe('carte — repère et statuts', () => {
  it('repère confirmé : confirmation masquée et statut par locale', () => {
    for (const loc of ['fr', 'en', 'ar'] as const) {
      const { ctx } = monter(loc, {}, 'ar');
      ctx.etat.capturePin = { lat: 1, lng: 2 };
      document.getElementById('mt-pin-confirm-yes')!.click();
      expect(ctx.etat.confirmedPinKey).toBe('1.000000,2.000000');
      expect(document.getElementById('mt-pin-confirm')!.hidden).toBe(true);
      const attendu = loc === 'en' ? TEXTES_CARTE.en : loc === 'ar' ? TEXTES_CARTE.ar : TEXTES_CARTE.fr;
      expect(document.getElementById('rp9-status')!.textContent).toBe(attendu.confirme);
    }
  });

  it('FR garde ses statuts français même si la langue affichée est arabe ; AR les suit', () => {
    const fr = monter('fr', {}, 'ar');
    document.querySelectorAll<HTMLButtonElement>('.mt-roof-mode')[1].click();
    expect(document.getElementById('rp9-status')!.textContent).toBe(TEXTES_CARTE.fr.tracer);
    expect(fr.ctx.etat.roofInputMode).toBe('draw');
    expect(fr.appels).toEqual(['mark', 'save']);
    const ar = monter('ar', {}, 'ar');
    document.querySelectorAll<HTMLButtonElement>('.mt-roof-mode')[1].click();
    expect(document.getElementById('rp9-status')!.textContent).toBe(TEXTES_CARTE.ar.tracer);
    expect(ar.ctx.etat.roofInputMode).toBe('draw');
    expect(document.getElementById('rp9-finish')!.hidden).toBe(false);
  });

  it('ajuster : repère à reconfirmer', () => {
    const { ctx } = monter('en');
    (document.getElementById('rp9-map') as any).scrollIntoView = vi.fn();
    ctx.etat.confirmedPinKey = 'x';
    document.getElementById('mt-pin-confirm-adjust')!.click();
    expect(ctx.etat.confirmedPinKey).toBe('');
    expect(document.getElementById('rp9-status')!.textContent).toBe(TEXTES_CARTE.en.ajuster);
  });
});

describe('carte — aperçu 3D et instantané du toit', () => {
  it('le bloc 3D suit contour ≥ 3 sommets + kWc', () => {
    const { ctx } = monter('fr');
    const bloc = document.getElementById('mt-panels3d')!;
    ctx.crochets.appeler('updatePanels3dVisibility');
    expect(bloc.hidden).toBe(true);
    ctx.etat.captureOutline = [[0, 0], [0, 1], [1, 1]];
    ctx.etat.lastKwc = 5;
    ctx.crochets.appeler('updatePanels3dVisibility');
    expect(bloc.hidden).toBe(false);
  });

  it('parcours gaté sans aperçu public : bloc 3D masqué', () => {
    const { ctx } = monter('fr', { apercu3dPublic: false });
    ctx.etat.captureOutline = [[0, 0], [0, 1], [1, 1]];
    ctx.etat.lastKwc = 5;
    ctx.crochets.appeler('updatePanels3dVisibility');
    expect(document.getElementById('mt-panels3d')!.hidden).toBe(true);
  });

  it('aperçu 3D indisponible : libellé de la locale', async () => {
    for (const [loc, langue, texte] of [['fr', 'fr', TEXTES_CARTE.fr], ['fr', 'ar', TEXTES_CARTE.ar], ['en', 'fr', TEXTES_CARTE.en]] as const) {
      const { ctx, chargeurs } = monter(loc, {}, langue);
      chargeurs.viewerOnly.mockResolvedValue({ createRoofViewer: vi.fn(() => null) } as any);
      ctx.etat.captureOutline = [[33.5, -7.6], [33.5, -7.5], [33.6, -7.5], [33.6, -7.6]];
      ctx.etat.lastKwc = 5;
      document.getElementById('mt-panels3d-start')!.click();
      await vi.waitFor(() => expect(document.getElementById('mt-panels3d-start')!.textContent).not.toBe(''), { timeout: 5000 });
      expect(document.getElementById('mt-panels3d-start')!.textContent).toBe(texte.apercu3dIndisponible);
      expect(ctx.etat.panels3dStarted).toBe(false);
    }
  });

  it('instantané : masqué sans contour, rempli avec contour (un seul chargement)', async () => {
    const { ctx, chargeurs } = monter('fr');
    const spec = { image: { src: 'data:image/png;base64,AA==' }, attribution: '© fournisseur' };
    const build = vi.fn(async () => spec);
    chargeurs.viewerOnly.mockResolvedValue({ buildPublicRoofImageSpec: build, createRoofViewer: vi.fn() } as any);
    const fig = document.getElementById('mt-doc-roof')!;
    fig.hidden = false;
    await ctx.crochets.appeler('tryRoofSnapshot');
    expect(fig.hidden).toBe(true);
    ctx.etat.captureOutline = [[0, 0], [0, 1], [1, 1]];
    await ctx.crochets.appeler('tryRoofSnapshot');
    await ctx.crochets.appeler('tryRoofSnapshot');
    expect(build).toHaveBeenCalledTimes(1);
    expect(fig.hidden).toBe(false);
    expect(document.getElementById('mt-doc-roof-attr')!.textContent).toBe('© fournisseur');
    expect((document.getElementById('mt-doc-roof-img') as HTMLImageElement).src).toContain('data:image/png');
  });

  it('imprimer appelle window.print', () => {
    monter('fr');
    const print = vi.fn();
    (window as any).print = print;
    document.getElementById('mt-print-estimate')!.click();
    expect(print).toHaveBeenCalledTimes(1);
  });
});

// @vitest-environment jsdom
// RWEB17-M4 — section « carte et toiture » du tunnel mon-toit (lib/tunnel/carte.ts).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { creerContexte, type ConfigLocale } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type LocaleTunnel } from '../src/lib/tunnel/etat';
import { installerCarte, surveillerWorkersCarte, TEXTES_CARTE, type ConfigCarte, type ContexteCarte } from '../src/lib/tunnel/carte';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import {
  lireFichiersMaplibre, NOM_PARTAGE, NOM_WORKER, preparerFichiersWorker, reecrireChunk,
} from '../scripts/maplibre-worker.mjs';

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
  // Le repère confirmé emmène à la facture : `profil.choisi` simule le profil coché.
  const profil = { choisi: true };
  ctx.crochets.installer('validateStep0', () => profil.choisi);
  ctx.crochets.installer('goStep', (n: number) => appels.push(`etape:${n}`));
  installerCarte(ctx);
  return { ctx, appels, bootCaptureOnly, chargeurs, profil };
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
      const { ctx, appels } = monter(loc, {}, 'ar');
      ctx.etat.capturePin = { lat: 1, lng: 2 };
      document.getElementById('mt-pin-confirm-yes')!.click();
      expect(ctx.etat.confirmedPinKey).toBe('1.000000,2.000000');
      expect(document.getElementById('mt-pin-confirm')!.hidden).toBe(true);
      const attendu = loc === 'en' ? TEXTES_CARTE.en : loc === 'ar' ? TEXTES_CARTE.ar : TEXTES_CARTE.fr;
      expect(document.getElementById('rp9-status')!.textContent).toBe(attendu.confirme);
      // Cul-de-sac du 03/11 : « Oui, c'est mon toit » ne menait nulle part.
      expect(appels).toContain('etape:1');
    }
  });

  it('repère confirmé sans profil choisi : on reste sur l’écran (validateStep0 montre l’erreur)', () => {
    const { ctx, appels, profil } = monter('fr');
    profil.choisi = false;
    ctx.etat.capturePin = { lat: 1, lng: 2 };
    document.getElementById('mt-pin-confirm-yes')!.click();
    expect(appels).not.toContain('etape:1');
  });

  it('aucun statut ne renvoie « ci-dessous » : rien ne suit la carte sur cet écran', () => {
    for (const t of Object.values(TEXTES_CARTE)) {
      expect(t.confirme).not.toMatch(/ci-dessous|below|أدناه/);
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

describe('WAUD1 — worker MapLibre publié', () => {
  it('le paquet installé référence toujours worker + partagé (contrat du plugin)', async () => {
    const f = await lireFichiersMaplibre();
    expect(f.nomWorker).toMatch(/^maplibre-gl-worker\.[0-9a-f]{10}\.mjs$/);
    expect(f.nomPartage).toMatch(/^maplibre-gl-shared\.[0-9a-f]{10}\.mjs$/);
    expect(f.worker).toContain(`./${f.nomPartage}`);
    expect(f.worker).not.toContain(`./${NOM_PARTAGE}`);
    expect(f.worker).not.toContain('sourceMappingURL');
  });

  it('le chunk est réécrit ; un chunk sans la référence reste intact', () => {
    const f = preparerFichiersWorker(`import{a}from"./${NOM_PARTAGE}";a()`, 'export const a=()=>1');
    const code = reecrireChunk(`new URL("./${NOM_WORKER}")`, f);
    expect(code).toContain(f.nomWorker);
    expect(code).not.toContain(NOM_WORKER);
    expect(reecrireChunk('rien', f)).toBeNull();
  });

  it('un worker qui change de contrat fait échouer le build', () => {
    expect(() => preparerFichiersWorker('rien', 'x')).toThrow(/montée de MapLibre/);
  });

  it('build présent : le worker référencé par le chunk MapLibre existe bel et bien', () => {
    const astro = `${process.cwd()}/dist/client/_astro/`;
    if (!existsSync(astro)) return;
    const fichiers = readdirSync(astro);
    const chunk = fichiers.find((n) => /^maplibre-gl\..*\.js$/.test(n));
    expect(chunk).toBeTruthy();
    const code = readFileSync(astro + chunk, 'utf-8');
    const nom = code.match(/maplibre-gl-worker\.[0-9a-f]{10}\.mjs/)?.[0];
    expect(nom).toBeTruthy();
    expect(fichiers).toContain(nom);
    const partage = readFileSync(astro + nom, 'utf-8').match(/maplibre-gl-shared\.[0-9a-f]{10}\.mjs/)?.[0];
    expect(fichiers).toContain(partage);
  });
});

describe('WAUD1 — repli visible si la carte échoue', () => {
  class FauxWorker extends EventTarget { constructor(public url: string | URL, public options?: WorkerOptions) { super(); } }

  it('une erreur de chargement du worker appelle le repli, une seule fois', () => {
    const fenetre = { Worker: FauxWorker } as any;
    const repli = vi.fn();
    const retirer = surveillerWorkersCarte(fenetre, repli);
    const a = new fenetre.Worker('/a.mjs', { type: 'module' });
    const b = new fenetre.Worker('/b.mjs');
    expect(a.url).toBe('/a.mjs');
    a.dispatchEvent(new Event('error'));
    b.dispatchEvent(new Event('error'));
    expect(repli).toHaveBeenCalledTimes(1);
    retirer();
    expect(fenetre.Worker).toBe(FauxWorker);
  });

  it('sans Worker (navigateur ancien, jsdom) : aucune exception', () => {
    expect(() => surveillerWorkersCarte({} as any, vi.fn())()).not.toThrow();
    expect(() => surveillerWorkersCarte(null, vi.fn())()).not.toThrow();
  });

  it('panne carte en session (onMapError) → repli adresse', async () => {
    (fetch as any).mockResolvedValue({ json: async () => ({ available: true, maptilerKey: 'k' }) });
    const { ctx, bootCaptureOnly } = monter('fr');
    ctx.crochets.appeler('ensureMapBooted');
    await attendre(); await attendre();
    bootCaptureOnly.mock.calls[0][0].onMapError();
    expect(document.getElementById('mt-fallback')!.hidden).toBe(false);
  });
});

describe('WAUD78 — façade : aucune requête carte avant un geste', () => {
  const cfg = { json: async () => ({ available: true, maptilerKey: 'k' }) };
  function montage(pin = false) {
    (fetch as any).mockResolvedValue(cfg);
    document.body.innerHTML = '';
    const bootCaptureOnly = vi.fn();
    const chargeurs = { captureBoot: vi.fn(async () => ({ bootCaptureOnly })), viewerOnly: vi.fn(async () => ({ createRoofViewer: vi.fn() })) };
    document.body.innerHTML = `${HTML}<form id="rp9-search"></form><button id="mt-map-facade"></button>`;
    const config: ConfigLocale & ConfigCarte = {
      locale: 'fr', langueBasculable: true, formatNombre: String, doc: document, reducedMotion: true,
      estimationGatee: true, apercu3dPublic: true, statutsSuiventLangue: false, optionsBootLocale: {}, chargeurs,
    };
    const ctx = creerContexte(creerDom(document), creerEtat(null, 'fr'), config) as ContexteCarte;
    if (pin) ctx.etat.capturePin = { lat: 33.5, lng: -7.6 };
    for (const n of ['syncCityRequirement', 'markDataEntered', 'saveWizardState']) ctx.crochets.installer(n, () => {});
    ctx.crochets.installer('langueActive', () => 'fr');
    installerCarte(ctx);
    return { ctx, chargeurs, bootCaptureOnly };
  }

  it('étape 0 sans repère : config seulement, aucun import de carte, squelette arrêté', async () => {
    const { ctx, chargeurs } = montage();
    ctx.crochets.appeler('ensureMapBooted');
    await attendre(); await attendre();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(chargeurs.captureBoot).not.toHaveBeenCalled();
    expect(document.getElementById('rp9-map')!.classList.contains('mt-skeleton-shimmer')).toBe(false);
  });

  it('étape 0 : carte indisponible → repli immédiat, sans attendre de geste', async () => {
    const { ctx } = montage();
    (fetch as any).mockResolvedValue({ json: async () => ({ available: false }) });
    ctx.crochets.appeler('ensureMapBooted');
    await attendre(); await attendre();
    expect(document.getElementById('mt-fallback')!.hidden).toBe(false);
  });

  it('clic sur la façade : la carte démarre et la façade disparaît', async () => {
    const { ctx, bootCaptureOnly } = montage();
    ctx.crochets.appeler('ensureMapBooted');
    await attendre(); await attendre();
    document.getElementById('mt-map-facade')!.click();
    await attendre(); await attendre();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(bootCaptureOnly).toHaveBeenCalledTimes(1);
    expect(document.getElementById('mt-map-facade')).toBeNull();
  });

  it('un repère déjà posé (reprise) démarre la carte sans geste', async () => {
    const { ctx, bootCaptureOnly } = montage(true);
    ctx.crochets.appeler('ensureMapBooted');
    await attendre(); await attendre();
    expect(bootCaptureOnly).toHaveBeenCalledTimes(1);
  });

  it('focus sur l’adresse ou choix du geste : la carte démarre', async () => {
    const a = montage();
    document.getElementById('rp9-address')!.dispatchEvent(new Event('focus'));
    await attendre(); await attendre();
    expect(a.bootCaptureOnly).toHaveBeenCalledTimes(1);
    const b = montage();
    document.querySelectorAll<HTMLButtonElement>('.mt-roof-mode')[0].click();
    await attendre(); await attendre();
    expect(b.bootCaptureOnly).toHaveBeenCalledTimes(1);
  });

  it('adresse validée avant le chargement : pas de rechargement, recherchée au démarrage', async () => {
    const { bootCaptureOnly } = montage();
    (document.getElementById('rp9-address') as HTMLInputElement).value = ' Maârif ';
    const e = new Event('submit', { cancelable: true });
    document.getElementById('rp9-search')!.dispatchEvent(e);
    expect(e.defaultPrevented).toBe(true);
    await attendre(); await attendre();
    expect(bootCaptureOnly.mock.calls[0][0].initialQuery).toBe('Maârif');
  });
});

describe('WAUD34 — adresse cherchée sans repère', () => {
  it('pré-remplit une ville vide, jamais une ville saisie', () => {
    const { ctx } = monter('fr');
    const adresse = document.getElementById('rp9-address') as HTMLInputElement;
    const ville = document.getElementById('mt-city') as HTMLInputElement;
    adresse.value = ' Maârif ';
    adresse.dispatchEvent(new Event('change'));
    expect(ville.value).toBe('Maârif');
    ville.value = '';
    ctx.etat.cityTouched = true;
    adresse.dispatchEvent(new Event('change'));
    expect(ville.value).toBe('');
  });
});

describe('WAUD43 — étape toit : outils de dessinateur masqués au grand public', () => {
  const lire = (rel: string) => readFileSync(`${process.cwd()}/${rel}`, 'utf-8');

  it('le tunnel pose le contexte public ; le CSS masque les puces pro', () => {
    monter('fr');
    expect(document.getElementById('mt-stage')!.dataset.contexte).toBe('public');
    const css = lire('src/styles/mon-toit-page.css');
    for (const c of ['rp9-trace-chips', 'rp9-fond-calage', 'rp9-geocode-country']) {
      expect(css).toContain(`[data-contexte='public'] .${c}`);
    }
  });

  it('« Continuer » arrive avant la carte, sous les profils, dans les 3 langues', () => {
    for (const p of ['devis/mon-toit', 'en/devis/mon-toit', 'ar/devis/mon-toit']) {
      const page = lire(`src/pages/${p}.astro`);
      // Garde ACAL345 : le bouton vit dans un composant partagé, placé ici sous les profils.
      // L'id est un paramètre du composant (défaut : le bouton du haut) depuis sa reprise sous la carte.
      expect(lire('src/components/blocs/DevisMonToitContinuer.astro')).toContain("id = 'mt-next-0'");
      const suivant = page.indexOf('<DevisMonToitContinuer>');
      expect(suivant).toBeGreaterThan(page.indexOf('id="mt-mode-grid"'));
      expect(suivant).toBeLessThan(page.indexOf('id="mt-stage"'));
    }
  });

  it('« Continuer » est repris SOUS la carte, dans les 3 langues (cul-de-sac du 03/11)', () => {
    // Après « Localiser » ou le repère, le bouton du haut est hors écran : sans cette
    // reprise, le visiteur ne voyait plus aucun bouton (constat fondateur du 11/11).
    for (const p of ['devis/mon-toit', 'en/devis/mon-toit', 'ar/devis/mon-toit']) {
      const page = lire(`src/pages/${p}.astro`);
      // FR/AR : la reprise suit la confirmation du repère dans leur bloc partagé ; EN la pose elle-même.
      const partage = lire('src/components/blocs/DevisMonToitPinConfirm.astro');
      expect(partage.indexOf('<DevisMonToitContinuerBas')).toBeGreaterThan(partage.indexOf('id="mt-pin-confirm-adjust"'));
      const bas = page.indexOf(p.startsWith('en/') ? '<DevisMonToitContinuerBas' : '<DevisMonToitPinConfirm />');
      expect(lire('src/components/blocs/DevisMonToitContinuerBas.astro')).toContain('id="mt-next-0-bas"');
      expect(bas).toBeGreaterThan(page.indexOf('id="rp9-map"'));
      expect(bas).toBeGreaterThan(page.indexOf('id="rp9-status"'));
      expect(bas).toBeLessThan(page.indexOf('id="mt-panel-1"'));
    }
  });
});

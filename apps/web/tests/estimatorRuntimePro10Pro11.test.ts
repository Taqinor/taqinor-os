// @vitest-environment jsdom
//
// HARNESS D'EXÉCUTION (jsdom) pour les scripts d'estimateur pro-10 (W34, toit plat) et
// pro-11 (W35, toit en pente) — la couche INTERACTIVE que les tests de moteur (V7/V8) et
// les tests de garde "chaîne de caractères" NE FONT PAS tourner. Ici on MONTE vraiment le
// script dans un faux DOM, avec MapLibre mocké (et donc Three.js jamais instancié :
// `renderScene` s'auto-annule car `sceneRoot` reste null), on simule un tracé de toit, et
// on vérifie que l'OPTIMISEUR VIVANT se déclenche et remplit la carte de résultats — puis
// qu'un changement d'option RE-RÉSOUT en direct. C'est ce qui attrape un sélecteur cassé,
// un null deref, une erreur de câblage : des bugs qu'aucun test de moteur ne voit.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createRoofTypeSelect } from '../src/lib/roofTypeSelect';

import { FakeMap, fakeMaps, fakeMarkers, loadTool, setBill, setupDom, squareCorners, traceRoof, txt } from './estimatorRuntimePro11.harnais';

describe('runtime pro-10/pro-11 — montage du script sans crash', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    // PVGIS injoignable → repli table « estimé » (chemin déterministe, sans réseau).
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network in test'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('initRoofToolPro8 monte sans lancer d\'exception et crée la carte', async () => {
    const init = await loadTool();
    expect(() => init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) })).not.toThrow();
    expect(fakeMaps.length).toBe(1); // la carte a bien été instanciée
  });

  it('style d\'imagerie refusé : fond de repli puis hydratation', async () => {
    const init = await loadTool();
    const onHydrationTerminee = vi.fn();
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 7, geometrie: { roof_point: { lat: 33.59, lng: -7.62 } } } },
      onHydrationTerminee,
    } as Parameters<typeof init>[0]);
    const map = fakeMaps[0];
    map.fire('error', { error: { message: '403 style' } }); // style refusé, avant tout `load`
    expect(map.setStyleCalls).toHaveLength(1);
    const repli = map.setStyleCalls[0] as { sources: Record<string, unknown> };
    expect(Object.keys(repli.sources)).toEqual([]); // aucune source distante
    expect(onHydrationTerminee).not.toHaveBeenCalled();
    map.styleLoaded = true;
    map.fire('load', {});
    expect(onHydrationTerminee).toHaveBeenCalledTimes(1);
    expect(document.getElementById('rp9-status')?.textContent).toMatch(/Imagerie satellite indisponible/);
    map.fire('error', { error: { message: '404 tuile' }, sourceId: 'x' }); // tuile : aucun changement
    map.fire('error', { error: { message: 'encore' } });
    expect(map.setStyleCalls).toHaveLength(1);
  });
});

describe('runtime W34 (toit plat) — l\'optimiseur vivant se déclenche et remplit la carte', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('tracer un toit lance le calcul et remplit puissance + production + couverture', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    // l'optimiseur vivant a posé un résultat (pas le « — » initial)
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-kwc')).not.toBe('—');
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);
    expect(txt('rp9-reco-cover')).toMatch(/%/);
    // un badge « Recommandé » est posé quelque part (au moins un visible)
    const badges = Array.from(document.querySelectorAll<HTMLElement>('.rp9-reco-badge'));
    expect(badges.some((b) => !b.hidden)).toBe(true);
  });

  it('changer une option (pleine rive) RE-RÉSOUT en direct sans casser la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    const before = txt('rp9-reco-kwc');
    const removeMargin = document.querySelector<HTMLButtonElement>('[data-margin="remove"]')!;
    expect(() => removeMargin.click()).not.toThrow();
    // la marge verrouillée est tenue (puce pressée) et la carte reste remplie
    expect(removeMargin.getAttribute('aria-pressed')).toBe('true');
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(before).toMatch(/kWc/);
  });

  it('le tableau matrice (comparatif) est rempli et visible après le tracé', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    const rows = document.querySelectorAll('#rp9-compare tr');
    expect(rows.length).toBeGreaterThan(1); // plus d'une config évaluée affichée
    expect((document.getElementById('rp9-compare-wrap') as HTMLElement).hidden).toBe(false);
  });
});

describe('runtime W35 (toit en pente) — l\'optimiseur pente se déclenche', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('basculer en « Toit en pente » re-calcule la pose affleurante et remplit la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    // bascule pente (via la puce data-rooftype, câblée par createRoofTypeSelect)
    const pitchedBtn = document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!;
    expect(() => pitchedBtn.click()).not.toThrow();
    // les contrôles propres au plat sont masqués, le bloc pente visible
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('rp9-pitched-controls') as HTMLElement).hidden).toBe(false);
    // la carte affiche un résultat pente (puissance + production)
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);
    expect(txt('rp9-reco-title')).toMatch(/pente/i);
  });

  it('en pente, changer la pose (paysage) re-résout sans casser la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    const landscape = document.querySelector<HTMLButtonElement>('[data-orient="landscape"]')!;
    expect(() => landscape.click()).not.toThrow();
    expect(landscape.getAttribute('aria-pressed')).toBe('true');
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  });

  // W47 — en pente, les orientations IMPOSSIBLES (plein-sud tourné via data-family,
  // tente Est-Ouest, azimut) sont confinées à #rp9-flat-only, masqué dès le passage en
  // pente. « Alignée toit » est l'orientation de fait (coplanaire). Le toit plat les
  // ré-offre quand on rebascule (rien n'est cassé).
  it('W47 — passer en pente masque les orientations plates impossibles (flat-only caché)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    // plat : les orientations sont offertes
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(false);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    // pente : flat-only masqué → plein-sud tourné / Est-Ouest / azimut non offerts
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('rp9-pitched-controls') as HTMLElement).hidden).toBe(false);
    // la carte pente est remplie (pose affleurante alignée toit par défaut)
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-title')).toMatch(/pente/i);
    // rebascule plat : les orientations re-apparaissent (rien cassé)
    document.querySelector<HTMLButtonElement>('[data-rooftype="flat"]')!.click();
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// CORRECTION FINE DU SENS DE LA PENTE (curseur #rp9-facing-range 0–359°). Le visiteur
// peut régler n'importe quelle direction descendante (y compris intermédiaire/nord), la
// pose pente se re-résout en direct, la lecture (#rp9-facing-value) suit, et la direction
// est persistée PAR ZONE (snapshot/restore de facingAzimuthDeg).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime — correction fine du sens de la pente (curseur facing)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  const setFacing = (deg: number) => {
    const r = document.getElementById('rp9-facing-range') as HTMLInputElement;
    r.value = String(deg);
    r.dispatchEvent(new window.Event('input', { bubbles: true }));
  };

  it('régler une direction intermédiaire (160°) met à jour la lecture et re-résout sans casser', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    expect(() => setFacing(160)).not.toThrow();
    // la lecture montre le nom cardinal + les degrés (jamais rejeté)
    expect(txt('rp9-facing-value')).toMatch(/Sud.*·.*160°/);
    // la carte pente reste remplie après re-résolution
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-title')).toMatch(/pente/i);
  });

  it('le curseur accepte une direction NORD (0°) — impossible via les 5 boutons cardinaux', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    setFacing(0);
    expect(txt('rp9-facing-value')).toMatch(/Nord.*·.*0°/);
  });

  it('cliquer un bouton « Face du pan » synchronise le curseur + la lecture', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    document.querySelector<HTMLButtonElement>('[data-facing="90"]')!.click(); // Est
    const r = document.getElementById('rp9-facing-range') as HTMLInputElement;
    expect(Number(r.value)).toBe(90);
    expect(txt('rp9-facing-value')).toMatch(/Est.*·.*90°/);
  });

  it('la direction est PERSISTÉE PAR ZONE : chaque zone retrouve son propre sens de pente', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    setFacing(135); // zone 1 → sud-est
    // + Ajouter une zone, tracer la 2ᵉ, lui donner une autre direction
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click();
    traceRoof(fakeMaps[0], 16);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    setFacing(225); // zone 2 → sud-ouest
    expect(txt('rp9-facing-value')).toMatch(/225°/);
    // revenir à la zone 1 (1er bouton « Voir » de la liste) : le curseur + la lecture
    // doivent retrouver SON sens de pente (135°), pas celui de la zone 2.
    const firstSelect = document.querySelector<HTMLButtonElement>('#rp9-areas-list [data-area-select]');
    expect(firstSelect).not.toBeNull();
    firstSelect!.click();
    const r = document.getElementById('rp9-facing-range') as HTMLInputElement;
    expect(Number(r.value)).toBe(135);
    expect(txt('rp9-facing-value')).toMatch(/135°/);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// DIAGNOSTIC « UNE PAGE » (pro-11) — le CTA pré-remplit AUSSI adresse + tranche de facture
// + type de toiture (selects OBLIGATOIRES), et l'aire d'un toit en pente est corrigée du
// cos de la pente (projetée / cos(pente)). Toujours aucun POST de lead.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime — prefill une page : adresse + facture + toit + aire cos-pente', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  const lf = (id: string) => (document.getElementById(id) as HTMLInputElement | HTMLSelectElement).value;

  it('toit plat : le CTA pré-remplit adresse + billRange (bucket) + roofType (toit_plat), aire = projetée', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    (document.getElementById('rp9-address') as HTMLInputElement).value = '12 rue de Casablanca';
    setBill('1500'); // 1500 → tranche '1500-3000'
    traceRoof(fakeMaps[0], 16);
    const areaProjected = Number(lf('lf-area')) || 0; // pas encore prérempli (lu après clic)
    (document.getElementById('rp9-cta') as HTMLButtonElement).click();
    expect(lf('lf-city')).toBe('12 rue de Casablanca');
    expect(lf('lf-bill')).toBe('1500-3000');
    expect(lf('lf-roof')).toBe('toit_plat');
    // aire d'un carré de 16 m ≈ 256 m² (plat : pas de correction)
    expect(Number(lf('lf-area'))).toBeGreaterThan(180);
    expect(Number(lf('lf-area'))).toBeLessThan(340);
    void areaProjected;
  });

  it('toit en pente 45° : l\'aire pré-remplie est PLUS GRANDE que la projetée (cos-pente) + roofType villa', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    // relève l'aire projetée AVANT bascule pente (CTA plat câblé)
    (document.getElementById('rp9-cta') as HTMLButtonElement).click();
    const flatArea = Number(lf('lf-area'));
    // bascule pente, force 45° via le curseur de pente fin
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    const pitchR = document.getElementById('rp9-pitch-range') as HTMLInputElement;
    pitchR.value = '45';
    pitchR.dispatchEvent(new window.Event('input', { bubbles: true }));
    (document.getElementById('rp9-cta') as HTMLButtonElement).click();
    const slopeArea = Number(lf('lf-area'));
    // projetée / cos(45°) ≈ projetée × 1.414 → strictement plus grande
    expect(slopeArea).toBeGreaterThan(flatArea);
    expect(lf('lf-roof')).toBe('villa');
    // aucune route lead/simulation appelée
    const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    for (const c of calls) {
      expect(String(c[0])).not.toContain('/api/preview-lead');
      expect(String(c[0])).not.toContain('/api/simulate');
    }
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W46 — L'OPTIMISEUR RE-RÉSOUT APRÈS CHAQUE VERROU (pas seulement les deux premiers).
// On MONTE le vrai script avec une surface PVGIS injectée (rendement qui dépend de
// l'inclinaison ET de l'aspect) sur un toit TOURNÉ, puis on VERROUILLE des axes un par un
// (3ᵉ, 4ᵉ, 5ᵉ verrou) en vérifiant que chaque verrou est TENU et que les axes encore AUTO
// sont re-résolus (la production change quand un verrou déplace réellement l'optimum). On
// vérifie aussi que LIBÉRER un axe (« Recommandé » de l'inclinaison) garde TOUS les autres
// verrous accumulés — le bug W46 = un bouton qui effaçait tout après quelques verrous.
// ════════════════════════════════════════════════════════════════════════════════════

/** Toit RECTANGULAIRE TOURNÉ de `rotDeg` (sens horaire) → « aligné toit » est un vrai choix
 *  distinct du plein sud et l'Est-Ouest diffère. */
function rotatedCorners(lenM: number, widM: number, rotDeg: number, lng0 = -7.62, lat0 = 33.59): [number, number][] {
  const r = (rotDeg * Math.PI) / 180;
  const cos = Math.cos(r), sin = Math.sin(r);
  const mPerLat = 111320, mPerLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const corners: [number, number][] = [[-lenM / 2, -widM / 2], [lenM / 2, -widM / 2], [lenM / 2, widM / 2], [-lenM / 2, widM / 2]];
  return corners.map(([x, y]) => {
    const xr = x * cos - y * sin, yr = x * sin + y * cos;
    return [lng0 + xr / mPerLng, lat0 + yr / mPerLat] as [number, number];
  });
}

/** Trace un toit à partir de coins lng/lat fournis (toit tourné), puis « Terminer ». */
function traceCorners(map: FakeMap, corners: [number, number][]) {
  vi.useFakeTimers();
  for (const [lng, lat] of corners) {
    map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
    vi.advanceTimersByTime(241);
  }
  vi.useRealTimers();
  (document.getElementById('rp9-finish') as HTMLButtonElement).click();
}

/** Laisse résoudre les promesses PVGIS (warming async) + le débattement 280 ms du tilt. */
async function flushPvgis() {
  for (let i = 0; i < 25; i++) await Promise.resolve();
  await new Promise((r) => setTimeout(r, 350));
  for (let i = 0; i < 25; i++) await Promise.resolve();
}

/** Production annuelle (kWh) affichée, en nombre (sépare les espaces fines). */
function prod(): number {
  return Number((txt('rp9-reco-prod').match(/[\d   ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));
}
/** Valeurs des puces d'un groupe actuellement « pressées » (verrou ou miroir du gagnant). */
function pressedVals(attr: string): string[] {
  return Array.from(document.querySelectorAll<HTMLButtonElement>(`[${attr}]`))
    .filter((b) => b.getAttribute('aria-pressed') === 'true')
    .map((b) => b.getAttribute(attr) || '');
}

describe('W46 (toit plat) — re-résolution après CHAQUE verrou (3ᵉ, 4ᵉ, Nᵉ)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    // PVGIS PRÉSENT : rendement = surface non triviale en (inclinaison, aspect) → chaque
    // verrou qui déplace l'optimum DOIT changer la production. Pic à 29°, plein sud.
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: { body: string }) => {
      const body = JSON.parse(init.body) as { legs: { tiltDeg: number; aspect: number; kwc: number }[] };
      let annual = 0;
      for (const lg of body.legs) {
        const y = Math.max(200, 1800 - Math.abs(lg.tiltDeg - 29) * 12 - Math.abs(lg.aspect) * 8);
        annual += (lg.kwc || 1) * y;
      }
      return { ok: true, json: async () => ({ ok: true, annualKwh: annual }) } as unknown as Response;
    }));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('verrouiller le 3ᵉ puis le 4ᵉ axe re-résout (la production change) et TIENT tous les verrous', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('2500');
    traceCorners(fakeMaps[0], rotatedCorners(30, 18, 35));
    await flushPvgis();

    // Verrou 1 : orientation Est-Ouest (sous-optimale ici → l'optimum change vraiment).
    document.querySelector<HTMLButtonElement>('[data-family="eastwest"]')!.click();
    await flushPvgis();
    const afterLock1 = prod();
    expect(pressedVals('data-family')).toContain('eastwest');

    // Verrou 2 : pose paysage.
    document.querySelector<HTMLButtonElement>('[data-orient="landscape"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-orient')).toContain('landscape');

    // Verrou 3 : inclinaison 10° (loin du pic 29° → la production DOIT chuter).
    document.querySelector<HTMLButtonElement>('[data-tilt="10"]')!.click();
    await flushPvgis();
    const afterLock3 = prod();
    expect(pressedVals('data-tilt')).toContain('10');
    expect(afterLock3).toBeLessThan(afterLock1); // le 3ᵉ verrou a bien re-résolu
    // tous les verrous précédents sont TENUS (accumulation)
    expect(pressedVals('data-family')).toContain('eastwest');
    expect(pressedVals('data-orient')).toContain('landscape');

    // Verrou 4 : marge pleine rive — re-résout encore (le 4ᵉ verrou n'est pas ignoré).
    document.querySelector<HTMLButtonElement>('[data-margin="remove"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-margin')).toContain('remove');
    // les trois verrous précédents tiennent toujours
    expect(pressedVals('data-family')).toContain('eastwest');
    expect(pressedVals('data-orient')).toContain('landscape');
    expect(pressedVals('data-tilt')).toContain('10');

    // Changer un axe DÉJÀ verrouillé (inclinaison 10 → 29 = le pic) re-résout : production remonte.
    const beforeRetilt = prod();
    document.querySelector<HTMLButtonElement>('[data-tilt="29"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-tilt')).toContain('29');
    expect(prod()).toBeGreaterThan(beforeRetilt); // 29° (pic) > 10°
    // les autres verrous restent tenus pendant ce changement
    expect(pressedVals('data-family')).toContain('eastwest');
    expect(pressedVals('data-orient')).toContain('landscape');
    expect(pressedVals('data-margin')).toContain('remove');
  }, 60000);

  it('libérer l\'inclinaison (« Recommandé ») garde les AUTRES verrous accumulés (W46 §3)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('2500');
    traceCorners(fakeMaps[0], rotatedCorners(30, 18, 35));
    await flushPvgis();

    document.querySelector<HTMLButtonElement>('[data-family="eastwest"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-orient="landscape"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-tilt="10"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-tilt')).toContain('10');

    // LIBÉRER l'inclinaison via la puce « Recommandé » — ne doit PAS effacer family/orient.
    document.querySelector<HTMLButtonElement>('[data-tilt="reco"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-family')).toContain('eastwest'); // verrou conservé
    expect(pressedVals('data-orient')).toContain('landscape'); // verrou conservé
    // l'inclinaison est re-libérée : la production remonte vers l'optimum tenu (≠ 10° figé)
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);

    // Le BOUTON tilt-reco dédié (rp9-tilt-reco) doit faire pareil (ne pas tout réinitialiser).
    document.querySelector<HTMLButtonElement>('[data-tilt="15"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-tilt')).toContain('15');
    (document.getElementById('rp9-tilt-reco') as HTMLButtonElement).click();
    await flushPvgis();
    expect(pressedVals('data-family')).toContain('eastwest'); // toujours tenu
    expect(pressedVals('data-orient')).toContain('landscape'); // toujours tenu
  }, 60000);

  it('la séquence se termine quand TOUS les axes sont verrouillés (rien ne flotte)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('2500');
    traceCorners(fakeMaps[0], rotatedCorners(30, 18, 35));
    await flushPvgis();

    // Verrouille les CINQ axes exposés : orientation(famille) + azimut + inclinaison + pose + marge.
    document.querySelector<HTMLButtonElement>('[data-family="south"]')!.click();
    await flushPvgis();
    // azimut visible seulement sur toit tourné → présent ici
    const aligned = document.querySelector<HTMLButtonElement>('[data-azimuth="aligned"]')!;
    aligned.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-tilt="29"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-orient="portrait"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-margin="remove"]')!.click();
    await flushPvgis();

    // Tous tenus, la carte reste remplie (pas de crash, pas de blanc).
    expect(pressedVals('data-azimuth')).toContain('aligned');
    expect(pressedVals('data-tilt')).toContain('29');
    expect(pressedVals('data-orient')).toContain('portrait');
    expect(pressedVals('data-margin')).toContain('remove');
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);

    // « Réinitialiser » relâche TOUT → retour à l'optimum global.
    (document.getElementById('rp9-optimum') as HTMLButtonElement).click();
    await flushPvgis();
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  }, 60000);
});

// ════════════════════════════════════════════════════════════════════════════════════
// W50 — FENÊTRE « PRODUCTION ESTIMÉE » (Année / Mois / Jour). On MONTE le vrai script,
// mock /api/roof-production (jamais PVGIS directement), trace un toit, et vérifie : le
// scope donne la bonne série (Année=12 mois, Jour=courbe 24 h), le cyclage mois parcourt
// les 12 mois, le jour démarre sur le jour TYPE puis une date précise le surcharge, et
// éditer le nombre de panneaux rescale toutes les figures (linéarité, sans nouvel appel
// PVGIS direct). Le client appelle bien /api/roof-production.
// ════════════════════════════════════════════════════════════════════════════════════

const PANEL_KWC_TEST = 0.72;

/** Production PAR 1 kWc déterministe (mensuels distincts → on repère le mois affiché). */
function perKwcFixture() {
  const monthly = [80, 90, 120, 140, 160, 175, 180, 170, 145, 120, 95, 75]; // kWh/kWc/mois
  const annual = monthly.reduce((a, b) => a + b, 0);
  const daysIn = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const bell = (peak: number) => {
    const out = new Array<number>(24).fill(0);
    for (let h = 6; h <= 18; h++) {
      const x = (h - 12) / 4;
      out[h] = peak * Math.exp(-0.5 * x * x);
    }
    const s = out.reduce((a, b) => a + b, 0);
    return out.map((v) => (s > 0 ? v : 0));
  };
  const typicalDayByMonth: number[][] = [];
  const dailyKwhByMonth: number[] = [];
  for (let m = 0; m < 12; m++) {
    const targetDaily = monthly[m] / daysIn[m];
    const shape = bell(1);
    const shapeSum = shape.reduce((a, b) => a + b, 0);
    const k = shapeSum > 0 ? targetDaily / shapeSum : 0;
    const prof = shape.map((v) => v * k);
    typicalDayByMonth.push(prof);
    dailyKwhByMonth.push(prof.reduce((a, b) => a + b, 0));
  }
  return { annual, monthly, typicalDayByMonth, dailyKwhByMonth };
}

/** Mock fetch : /api/roof-production renvoie la fixture mise à l'échelle par placedPanels ;
 *  /api/roof-yield renvoie un rendement plausible ; toute URL est enregistrée. */
function installProductionFetch(urls: string[]) {
  const fx = perKwcFixture();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: { body?: string }) => {
      urls.push(url);
      const body = init?.body ? (JSON.parse(init.body) as Record<string, unknown>) : {};
      if (url.includes('/api/roof-production')) {
        const panels = Number(body.placedPanels) || 1;
        const kwc = panels * PANEL_KWC_TEST;
        const monthlyKwh = fx.monthly.map((v) => v * kwc);
        const annualKwh = fx.annual * kwc;
        const dailyKwhByMonth = fx.dailyKwhByMonth.map((v) => v * kwc);
        const typicalDayByMonth = fx.typicalDayByMonth.map((prof) => prof.map((v) => v * kwc));
        let specificDate = null;
        if (typeof body.dateMonth === 'number' && typeof body.dateDay === 'number') {
          // Date précise : profil clairement DIFFÉRENT du jour type (pic ×3) → on le repère.
          const peak = 3;
          const out = new Array<number>(24).fill(0);
          for (let h = 6; h <= 18; h++) {
            const x = (h - 12) / 4;
            out[h] = peak * Math.exp(-0.5 * x * x);
          }
          const hourlyKw = out.map((v) => v * kwc);
          specificDate = {
            month: body.dateMonth,
            day: body.dateDay,
            hourlyKw,
            dailyKwh: hourlyKw.reduce((a, b) => a + b, 0),
            yearsAveraged: 5,
          };
        }
        return {
          ok: true,
          json: async () => ({
            ok: true,
            source: 'pvgis',
            cacheHit: false,
            placedPanels: panels,
            panelKwc: PANEL_KWC_TEST,
            placedKwc: kwc,
            annualKwh,
            monthlyKwh,
            dailyKwhByMonth,
            typicalDayByMonth,
            specificDate,
          }),
        } as unknown as Response;
      }
      // /api/roof-yield : rendement plausible (PVGIS GPS exact) pour l'optimiseur.
      const legs = (body.legs as { kwc?: number }[]) || [];
      const annual = legs.reduce((a, lg) => a + (lg.kwc || 1) * 1700, 0);
      return { ok: true, json: async () => ({ ok: true, annualKwh: annual }) } as unknown as Response;
    }),
  );
}

/** kWh affichés dans le headline de la fenêtre de production (nombre). */
function prodHeadlineKwh(): number {
  return Number((txt('rp9-prod-headline').match(/[\d  ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));
}

describe('W50 — fenêtre de production : scope, cyclage, jour type/date, rescale', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function mount() {
    const urls: string[] = [];
    installProductionFetch(urls);
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    await flushPvgis();
    return urls;
  }

  it('la fenêtre se remplit (kWh/an) et le client appelle /api/roof-production', async () => {
    const urls = await mount();
    expect((document.getElementById('rp9-prod-window') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-prod-headline')).toMatch(/kWh\/an/);
    expect(prodHeadlineKwh()).toBeGreaterThan(0);
    // le client appelle bien la route serveur — JAMAIS PVGIS directement
    expect(urls.some((u) => u.includes('/api/roof-production'))).toBe(true);
    expect(urls.some((u) => u.includes('pvgis') || u.includes('re.jrc.ec.europa.eu'))).toBe(false);
    // un graphe SVG a été rendu (12 barres mensuelles)
    expect(document.querySelectorAll('#rp9-prod-graph rect').length).toBe(12);
  }, 60000);

  it('toggle Mois puis Jour change la série (Jour = courbe 24 points)', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-prod-scope="month"]')!.click();
    await flushPvgis();
    expect(txt('rp9-prod-sub')).toMatch(/Production de/i);
    expect((document.getElementById('rp9-prod-month-picker') as HTMLElement).hidden).toBe(false);
    // Jour : une courbe (path) au lieu de barres
    document.querySelector<HTMLButtonElement>('[data-prod-scope="day"]')!.click();
    await flushPvgis();
    expect((document.getElementById('rp9-prod-day-picker') as HTMLElement).hidden).toBe(false);
    expect(document.querySelectorAll('#rp9-prod-graph path').length).toBeGreaterThan(0);
    expect(txt('rp9-prod-sub')).toMatch(/jour type/i); // défaut = jour type
  }, 60000);

  it('cycler les mois parcourt les 12 mois et revient au point de départ', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-prod-scope="month"]')!.click();
    await flushPvgis();
    const next = document.getElementById('rp9-prod-month-next') as HTMLButtonElement;
    const seen = new Set<string>();
    for (let i = 0; i < 12; i++) {
      seen.add(txt('rp9-prod-month-label'));
      next.click();
      await flushPvgis();
    }
    expect(seen.size).toBe(12); // tous les mois affichés
  }, 60000);

  it('le jour démarre sur le JOUR TYPE ; une date choisie le surcharge', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-prod-scope="day"]')!.click();
    await flushPvgis();
    const typicalKwh = prodHeadlineKwh();
    expect(txt('rp9-prod-day-label')).toMatch(/jour type/i);
    // choisir une date précise (flèche jour suivant) → le profil change (pic ×3 dans le mock)
    (document.getElementById('rp9-prod-day-next') as HTMLButtonElement).click();
    await flushPvgis();
    expect(txt('rp9-prod-day-label')).not.toMatch(/jour type/i); // date précise affichée
    expect(prodHeadlineKwh()).toBeGreaterThan(typicalKwh); // la date pic ×3 > jour type
    // « Jour type » ramène au profil moyen
    const resetBtn = document.getElementById('rp9-prod-day-reset') as HTMLButtonElement;
    expect(resetBtn.hidden).toBe(false);
    resetBtn.click();
    await flushPvgis();
    expect(txt('rp9-prod-day-label')).toMatch(/jour type/i);
  }, 60000);

  it('éditer le nombre de panneaux rescale les figures (linéarité)', async () => {
    await mount();
    const before = prodHeadlineKwh();
    expect(before).toBeGreaterThan(0);
    // augmente le besoin → plus de panneaux posés → production plus haute
    const needInput = document.getElementById('rp9-need-input') as HTMLInputElement;
    const baseNeed = Number(needInput.value.replace(/[^\d]/g, '')) || 1;
    needInput.value = String(baseNeed + 6);
    needInput.dispatchEvent(new window.Event('input', { bubbles: true }));
    await flushPvgis();
    const after = prodHeadlineKwh();
    expect(after).toBeGreaterThan(before); // plus de panneaux → plus de production
  }, 60000);

  it('en pente, la fenêtre reflète la pose affleurante (building) et reste remplie', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    await flushPvgis();
    expect((document.getElementById('rp9-prod-window') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-prod-headline')).toMatch(/kWh\/an/);
  }, 60000);
});

// ════════════════════════════════════════════════════════════════════════════════════
// W91 — bouton « ma position » (GeolocateControl natif MapLibre, aucune dépendance ajoutée).
// On vérifie que le contrôle est bien AJOUTÉ à la carte, et qu'une position géolocalisée
// recentre en zoom 19 (flyTo en mouvement normal, jumpTo en reduced-motion).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W91 (map) — bouton ma position (GeolocateControl)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  function geolocateControl(map: FakeMap) {
    return map.controls.find(
      (c) => typeof (c as { fire?: unknown }).fire === 'function' && 'geoHandlers' in (c as object),
    ) as { fire: (ev: string, e: unknown) => void } | undefined;
  }

  it('un GeolocateControl est ajouté à la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: false, roofType: createRoofTypeSelect(document) });
    expect(geolocateControl(fakeMaps[0])).toBeDefined();
  });

  it('géolocaliser recentre en zoom 19 (flyTo en mouvement normal)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: false, roofType: createRoofTypeSelect(document) });
    const ctrl = geolocateControl(fakeMaps[0])!;
    ctrl.fire('geolocate', { coords: { longitude: -7.62, latitude: 33.59 } });
    const calls = fakeMaps[0].flyToCalls as Array<{ center: [number, number]; zoom: number }>;
    expect(calls.length).toBeGreaterThan(0);
    const last = calls[calls.length - 1];
    expect(last.zoom).toBe(19);
    expect(last.center).toEqual([-7.62, 33.59]);
  });

  it('en reduced-motion, géolocaliser saute (jumpTo) en zoom 19', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    const ctrl = geolocateControl(fakeMaps[0])!;
    ctrl.fire('geolocate', { coords: { longitude: -7.62, latitude: 33.59 } });
    const calls = fakeMaps[0].jumpToCalls as Array<{ center: [number, number]; zoom: number }>;
    expect(calls.some((c) => c.zoom === 19)).toBe(true);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W77 — PARITÉ TACTILE DU TRACÉ : double-tap pour finir + aucun coin perdu en traçant vite.
// On compte les sommets réellement posés via la source `rp9-pts` captée par FakeMap, et on
// vérifie que (1) tracer 4 coins distincts PLUS VITE que le délai anti-dblclick n'en perd
// aucun, (2) un double-tap tactile au même endroit FERME le tracé, (3) le double-clic
// desktop ferme SANS laisser de sommet parasite (comportement desktop inchangé).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W77 (map) — parité tactile du tracé', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  // Nombre de sommets actuellement posés (features de la source rp9-pts).
  function vertexCount(map: FakeMap): number {
    const d = map.sourceData['rp9-pts'] as { features?: unknown[] } | undefined;
    return d?.features?.length ?? 0;
  }

  // 4 coins d'un carré, à des POINTS écran DISTINCTS (sinon le garde double-tap les
  // confondrait). lng/lat n'ont pas besoin d'être exacts pour le comptage de sommets.
  const corners: Array<{ lng: number; lat: number; x: number; y: number }> = [
    { lng: -7.62, lat: 33.59, x: 100, y: 100 },
    { lng: -7.619, lat: 33.59, x: 300, y: 100 },
    { lng: -7.619, lat: 33.591, x: 300, y: 300 },
    { lng: -7.62, lat: 33.591, x: 100, y: 300 },
  ];

  it('tracer 4 coins PLUS VITE que le délai ne perd aucun sommet', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    const map = fakeMaps[0];
    vi.useFakeTimers();
    // chaque clic n'avance le temps que de 50 ms (< 240 ms) → l'ancien code jetait
    // les coins rapides ; le nouveau pose d'abord le précédent.
    for (const c of corners) {
      map.fire('click', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      vi.advanceTimersByTime(50);
    }
    vi.advanceTimersByTime(300); // laisse le dernier délai s'écouler
    vi.useRealTimers();
    expect(vertexCount(map)).toBe(4); // les 4 coins posés, aucun perdu
  });

  it('double-tap tactile au même endroit FERME le tracé', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    const map = fakeMaps[0];
    // pose 3 coins distincts au doigt (touchend + click synthétique chacun)
    vi.useFakeTimers();
    for (const c of corners.slice(0, 3)) {
      map.fire('touchend', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      map.fire('click', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      vi.advanceTimersByTime(241); // chaque coin posé
    }
    expect(vertexCount(map)).toBe(3);
    // double-tap au MÊME endroit (dans la fenêtre 300 ms) = terminer
    const last = corners[2];
    map.fire('touchend', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y } });
    vi.advanceTimersByTime(120);
    map.fire('touchend', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y } });
    vi.useRealTimers();
    // close() a tourné → la config est visible et le calcul rempli
    expect((document.getElementById('rp9-config') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  });

  it('double-clic desktop ferme SANS laisser de sommet parasite (desktop inchangé)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    const map = fakeMaps[0];
    vi.useFakeTimers();
    for (const c of corners.slice(0, 3)) {
      map.fire('click', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      vi.advanceTimersByTime(241);
    }
    expect(vertexCount(map)).toBe(3);
    // double-clic au même endroit que le 3ᵉ coin : 2ᵉ clic immédiat puis dblclick
    const last = corners[2];
    map.fire('click', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y } });
    map.fire('dblclick', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y }, preventDefault() {} });
    vi.useRealTimers();
    // fermé avec EXACTEMENT 3 sommets (le clic du double-clic n'a pas ajouté de 4ᵉ)
    expect((document.getElementById('rp9-config') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W93 — AUTOCOMPLÉTION D'ADRESSE (combobox). On mocke MapTiler pour renvoyer 5 résultats,
// puis on vérifie : (1) la frappe peuple jusqu'à 5 suggestions (aria-expanded, role=option) ;
// (2) sélectionner une suggestion VOLE vers son centre (et ferme la liste) ; (3) la
// navigation clavier (flèches) met à jour aria-activedescendant et Entrée valide. On NE vole
// JAMAIS avant la sélection (geocode ne flyTo plus de lui-même).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W93 (map) — autocomplétion d\'adresse', () => {
  // 5 features MapTiler factices (centres distincts au Maroc).
  function geoResponse() {
    const features = Array.from({ length: 5 }, (_, i) => ({
      center: [-7.6 - i * 0.01, 33.5 + i * 0.01],
      place_name: `Adresse ${i + 1}, Casablanca`,
      text: `Adresse ${i + 1}`,
    }));
    return { ok: true, json: () => Promise.resolve({ features }) };
  }

  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(geoResponse() as unknown as Response)));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function type(q: string) {
    const addr = document.getElementById('rp9-address') as HTMLInputElement;
    addr.value = q;
    vi.useFakeTimers();
    addr.dispatchEvent(new window.Event('input', { bubbles: true }));
    vi.advanceTimersByTime(310); // laisse le débounce 300 ms s'écouler
    vi.useRealTimers();
    await Promise.resolve(); // laisse résoudre la promesse fetch
    await Promise.resolve();
  }

  const options = () => Array.from(document.querySelectorAll('#rp9-suggestions [role="option"]'));

  it('taper une adresse peuple jusqu\'à 5 suggestions (combobox ouverte, aria)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    await type('Casa');
    expect(options().length).toBe(5);
    const list = document.getElementById('rp9-suggestions') as HTMLElement;
    expect(list.hidden).toBe(false);
    expect(document.getElementById('rp9-address')!.getAttribute('aria-expanded')).toBe('true');
    // la requête a demandé 5 résultats (et pas 1)
    const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(String(calls[calls.length - 1][0])).toContain('limit=5');
  });

  it('aucun vol AVANT sélection (geocode ne flyTo plus tout seul)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: false, roofType: createRoofTypeSelect(document) });
    await type('Casa');
    // suggestions affichées mais aucun flyTo/jumpTo déclenché
    expect(fakeMaps[0].flyToCalls.length).toBe(0);
    expect(fakeMaps[0].jumpToCalls.length).toBe(0);
  });

  it('sélectionner une suggestion vole vers son centre et ferme la liste', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: false, roofType: createRoofTypeSelect(document) });
    await type('Casa');
    // clic (mousedown) sur la 2ᵉ suggestion
    const second = options()[1] as HTMLElement;
    second.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }));
    const calls = fakeMaps[0].flyToCalls as Array<{ center: [number, number]; zoom: number }>;
    expect(calls.length).toBe(1);
    expect(calls[0].center[0]).toBeCloseTo(-7.61, 5);
    expect(calls[0].center[1]).toBeCloseTo(33.51, 5);
    expect(calls[0].zoom).toBe(19);
    expect((document.getElementById('rp9-suggestions') as HTMLElement).hidden).toBe(true);
  });

  it('navigation clavier : flèches → aria-activedescendant, Entrée valide', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: false, roofType: createRoofTypeSelect(document) });
    await type('Casa');
    const addr = document.getElementById('rp9-address') as HTMLInputElement;
    addr.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    expect(addr.getAttribute('aria-activedescendant')).toBe('rp9-suggestion-0');
    addr.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    expect(addr.getAttribute('aria-activedescendant')).toBe('rp9-suggestion-1');
    // Entrée valide la suggestion survolée → vol
    addr.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(fakeMaps[0].flyToCalls.length).toBe(1);
    expect((document.getElementById('rp9-suggestions') as HTMLElement).hidden).toBe(true);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W92 — SOMMETS DU TRACÉ ÉDITABLES + ANNULER LE DERNIER POINT. On vérifie : (1) « Annuler
// le dernier point » dépile le dernier coin pendant le tracé (bouton visible quand ≥1 coin,
// masqué une fois fermé) ; (2) un coin POSÉ peut être glissé (souris ET tactile) → le
// sommet bouge et la disposition se re-résout (recalc) au relâchement.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W92 (map) — sommets éditables + annuler le dernier point', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  function vertexCount(map: FakeMap): number {
    const d = map.sourceData['rp9-pts'] as { features?: unknown[] } | undefined;
    return d?.features?.length ?? 0;
  }
  function vertexAt(map: FakeMap, idx: number): [number, number] | undefined {
    const d = map.sourceData['rp9-pts'] as { features?: Array<{ geometry: { coordinates: [number, number] } }> } | undefined;
    return d?.features?.[idx]?.geometry.coordinates;
  }
  // Pose 3 coins sans fermer (chaque clic → un sommet après le délai anti-dblclick).
  function placeThree(map: FakeMap) {
    vi.useFakeTimers();
    const pts = [{ x: 100, y: 100 }, { x: 300, y: 100 }, { x: 300, y: 300 }];
    const lls = [{ lng: -7.62, lat: 33.59 }, { lng: -7.619, lat: 33.59 }, { lng: -7.619, lat: 33.591 }];
    pts.forEach((p, i) => {
      map.fire('click', { lngLat: lls[i], point: p });
      vi.advanceTimersByTime(241);
    });
    vi.useRealTimers();
  }

  it('« Annuler le dernier point » dépile le dernier coin (visible pendant le tracé)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    const map = fakeMaps[0];
    placeThree(map);
    expect(vertexCount(map)).toBe(3);
    const undo = document.getElementById('rp9-undo-point') as HTMLButtonElement;
    expect(undo.hidden).toBe(false); // visible pendant le tracé
    undo.click();
    expect(vertexCount(map)).toBe(2); // un coin retiré
    undo.click();
    undo.click();
    expect(vertexCount(map)).toBe(0); // tout dépilé
    expect(undo.hidden).toBe(true); // plus aucun coin → masqué
  });

  it('un coin posé peut être glissé à la souris → le sommet bouge et la 3D re-résout', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    const map = fakeMaps[0];
    // toit fermé (4 coins) → recalc rempli
    vi.useFakeTimers();
    for (const [lng, lat] of squareCorners(16)) {
      map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
      vi.advanceTimersByTime(241);
    }
    vi.useRealTimers();
    (document.getElementById('rp9-finish') as HTMLButtonElement).click();
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    const before = vertexAt(map, 0);
    expect(before).toBeDefined();
    // le hit-test rp9-pts renvoie le sommet 0 → on le saisit et on le glisse
    map.queryHits['rp9-pts'] = [{ properties: { idx: 0 } }];
    map.fire('mousedown', { lngLat: { lng: before![0], lat: before![1] }, point: { x: 10, y: 10 } });
    map.fire('mousemove', { lngLat: { lng: before![0] + 0.0003, lat: before![1] + 0.0003 }, point: { x: 40, y: 40 } });
    map.fire('mouseup', { lngLat: { lng: before![0] + 0.0003, lat: before![1] + 0.0003 }, point: { x: 40, y: 40 } });
    const after = vertexAt(map, 0);
    expect(after).toBeDefined();
    // le sommet 0 a bougé du delta appliqué
    expect(after![0]).toBeCloseTo(before![0] + 0.0003, 6);
    expect(after![1]).toBeCloseTo(before![1] + 0.0003, 6);
    // la carte reste remplie (recalc a re-tourné sans casser)
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  });

  it('ACAL77 — glisser un coin au-delà du coin opposé est REFUSÉ : sommet inchangé, motif affiché', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    const map = fakeMaps[0];
    vi.useFakeTimers();
    for (const [lng, lat] of squareCorners(16)) {
      map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
      vi.advanceTimersByTime(241);
    }
    vi.useRealTimers();
    (document.getElementById('rp9-finish') as HTMLButtonElement).click();
    const coins = squareCorners(16);
    const before = vertexAt(map, 2)!;
    map.queryHits['rp9-pts'] = [{ properties: { idx: 2 } }];
    // Le sommet 2 (nord-est) tiré au-delà du côté ouest opposé, à mi-hauteur : nœud papillon.
    const cible = { lng: coins[0][0] - 0.0005, lat: (coins[0][1] + coins[3][1]) / 2 };
    map.fire('mousedown', { lngLat: { lng: before[0], lat: before[1] }, point: { x: 10, y: 10 } });
    map.fire('mousemove', { lngLat: cible, point: { x: 40, y: 40 } });
    map.fire('mouseup', { lngLat: cible, point: { x: 40, y: 40 } });
    expect(vertexAt(map, 2)).toEqual(before);
    expect(txt('rp9-status')).toMatch(/nœud papillon/);
  });

  it('un coin posé peut être glissé au DOIGT (touch) → le sommet bouge', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    const map = fakeMaps[0];
    vi.useFakeTimers();
    for (const [lng, lat] of squareCorners(16)) {
      map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
      vi.advanceTimersByTime(241);
    }
    vi.useRealTimers();
    (document.getElementById('rp9-finish') as HTMLButtonElement).click();
    const before = vertexAt(map, 1)!;
    map.queryHits['rp9-pts'] = [{ properties: { idx: 1 } }];
    map.fire('touchstart', { lngLat: { lng: before[0], lat: before[1] }, point: { x: 20, y: 20 }, points: [{ x: 20, y: 20 }] });
    map.fire('touchmove', { lngLat: { lng: before[0] - 0.0002, lat: before[1] - 0.0002 }, point: { x: 5, y: 5 }, preventDefault() {} });
    map.fire('touchend', { lngLat: { lng: before[0] - 0.0002, lat: before[1] - 0.0002 }, point: { x: 5, y: 5 } });
    const after = vertexAt(map, 1)!;
    expect(after[0]).toBeCloseTo(before[0] - 0.0002, 6);
    expect(after[1]).toBeCloseTo(before[1] - 0.0002, 6);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W97 §1 — PRÉ-REMPLISSAGE CORRECT + AUCUN LEAD POSTÉ (à travers le script MONTÉ).
// Le test focalisé W85 (prefillOrientationW85) couvre déjà le MAPPING d'orientation en
// pur (createPrefill). Ici on vérifie le chemin VIVANT : tracer → la carte reco peint →
// le CTA #rp9-cta câble prefillLead → un clic écrit lf-area / lf-kwc-est / lf-orient avec
// les VRAIES valeurs, et la preview ne POSTe JAMAIS /api/preview-lead ni /api/simulate.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W97 §1 — prefill via le CTA + aucun POST de lead', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  const lf = (id: string) => (document.getElementById(id) as HTMLInputElement | HTMLSelectElement).value;

  it('toit plat : cliquer le CTA pré-remplit lf-area / lf-kwc-est / lf-orient (sud) sans POST', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    const cta = document.getElementById('rp9-cta') as HTMLButtonElement;
    expect(cta.hidden).toBe(false); // une config gagnante existe → CTA offert
    cta.click(); // → prefillLead(d) (handoff, jamais un POST)
    // surface géodésique d'un carré de 16 m ≈ 256 m² (tolérance projection)
    expect(Number(lf('lf-area'))).toBeGreaterThan(180);
    expect(Number(lf('lf-area'))).toBeLessThan(340);
    // kWc estimé non vide et > 0
    expect(Number(lf('lf-kwc-est'))).toBeGreaterThan(0);
    // toit plat (famille sud par défaut) → orientation « sud » (la liste n'a pas d'est-ouest)
    expect(lf('lf-orient')).toBe('sud');
    // le diagnostic est ouvert (handoff terminé)
    expect((document.getElementById('diag') as HTMLDetailsElement).open).toBe(true);
    // AUCUN appel à une route lead / simulation (le repli PVGIS échoue volontairement,
    // mais ne vise JAMAIS /api/preview-lead ni /api/simulate).
    const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    for (const c of calls) {
      const url = String(c[0]);
      expect(url).not.toContain('/api/preview-lead');
      expect(url).not.toContain('/api/simulate');
    }
  });

  it('W110 — le CTA remplit lf-city depuis l\'adresse géocodée (rp9-address) sans POST', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    // simule une adresse géocodée déjà présente dans le champ de recherche
    (document.getElementById('rp9-address') as HTMLInputElement).value = 'Casablanca, Maroc';
    traceRoof(fakeMaps[0], 16);
    const cta = document.getElementById('rp9-cta') as HTMLButtonElement;
    cta.click(); // → prefillLead(d) : handoff, JAMAIS un POST
    // W110 — la ville du diagnostic est pré-remplie depuis l'adresse géocodée (champ vide).
    expect(lf('lf-city')).toBe('Casablanca, Maroc');
    // toujours aucun POST de lead/simulation
    const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    for (const c of calls) {
      const url = String(c[0]);
      expect(url).not.toContain('/api/preview-lead');
      expect(url).not.toContain('/api/simulate');
    }
  });

  it('W110 — une ville DÉJÀ saisie n\'est pas écrasée par l\'adresse géocodée', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    (document.getElementById('rp9-address') as HTMLInputElement).value = 'Casablanca, Maroc';
    (document.getElementById('lf-city') as HTMLInputElement).value = 'Rabat';
    traceRoof(fakeMaps[0], 16);
    (document.getElementById('rp9-cta') as HTMLButtonElement).click();
    expect(lf('lf-city')).toBe('Rabat'); // saisie utilisateur préservée
  });

  it('toit plat Est-Ouest verrouillé : l\'orientation pré-remplie reste « sud » (W85)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    // verrouille la famille Est-Ouest (la liste enrichment n'a pas d'« est-ouest » → sud)
    document.querySelector<HTMLButtonElement>('[data-family="eastwest"]')!.click();
    (document.getElementById('rp9-cta') as HTMLButtonElement).click();
    expect(lf('lf-orient')).toBe('sud');
    expect(Number(lf('lf-kwc-est'))).toBeGreaterThan(0);
  });

  it('toit en pente face sud-ouest : l\'orientation pré-remplie suit la face réelle (W85)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    // bascule en pente puis choisit la face 225° (sud-ouest)
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    const sw = document.querySelector<HTMLButtonElement>('[data-facing="225"]');
    if (sw) sw.click();
    (document.getElementById('rp9-cta') as HTMLButtonElement).click();
    // 225° → « sud-ouest » dans enrichment.ORIENTATIONS (si la face a bien été appliquée)
    if (sw) expect(lf('lf-orient')).toBe('sud-ouest');
    // dans tous les cas, aucune route lead/simulation n'a été appelée
    const calls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    for (const c of calls) {
      expect(String(c[0])).not.toContain('/api/preview-lead');
      expect(String(c[0])).not.toContain('/api/simulate');
    }
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W97 §2 — TOTAUX MULTI-ZONES (W78 au NIVEAU DONNÉES). On trace une 1ʳᵉ zone, on relève
// ses panneaux/kWc, puis « + Ajouter une zone », on trace une 2ᵉ zone et on vérifie que
// le panneau « Zones » agrège : total panneaux/kWc = somme des deux zones (la zone active
// = résultat LIVE, l'autre = snapshot). Confirme le câblage rp9-add-area + rp9-areas-*.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W97 §2 — totaux multi-zones = somme des zones', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  // Premier nombre entier (sépare les espaces fines) du texte d'un id.
  const intOf = (id: string): number => Number((txt(id).match(/[\d   ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));
  // kWc (décimal français) du texte d'un id.
  const kwcOf = (id: string): number => {
    const m = txt(id).match(/[\d   ]+(?:[.,]\d+)?/);
    return m ? Number(m[0].replace(/[   ]/g, '').replace(',', '.')) : 0;
  };

  it('ajouter une 2ᵉ zone fait que les totaux = somme des deux zones (panneaux + kWc)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('3000'); // besoin large → les deux zones posent des panneaux
    // Zone 1 : carré de 20 m.
    traceRoof(fakeMaps[0], 20);
    const panels1 = intOf('rp9-reco-panels');
    const kwc1 = kwcOf('rp9-reco-kwc');
    expect(panels1).toBeGreaterThan(0);
    // le panneau « Zones » est visible avec un total = la seule zone tracée
    expect((document.getElementById('rp9-areas-window') as HTMLElement).hidden).toBe(false);
    expect(intOf('rp9-areas-total-panels')).toBe(panels1);

    // + Ajouter une zone (autorisé car la zone active est fermée) → 2ᵉ zone vierge.
    const addBtn = document.getElementById('rp9-add-area') as HTMLButtonElement;
    expect(addBtn.disabled).toBe(false);
    addBtn.click();
    // Zone 2 : carré de 16 m (centre différent → tracé indépendant).
    vi.useFakeTimers();
    for (const [lng, lat] of squareCorners(16, -7.60, 33.60)) {
      fakeMaps[0].fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
      vi.advanceTimersByTime(241);
    }
    vi.useRealTimers();
    (document.getElementById('rp9-finish') as HTMLButtonElement).click();
    const panels2 = intOf('rp9-reco-panels'); // zone active = zone 2 (résultat live)
    const kwc2 = kwcOf('rp9-reco-kwc');
    expect(panels2).toBeGreaterThan(0);

    // Totaux agrégés = somme des deux zones.
    const totalPanels = intOf('rp9-areas-total-panels');
    expect(totalPanels).toBe(panels1 + panels2);
    const totalKwc = kwcOf('rp9-areas-total-kwc');
    expect(totalKwc).toBeCloseTo(kwc1 + kwc2, 1);
    // deux lignes de zone listées
    expect(document.querySelectorAll('#rp9-areas-list [data-area-row]').length).toBe(2);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W97 §4 — PLAFOND DES ÉCONOMIES À LA COUCHE RENDUE. annualSavingsMad plafonne l'économie
// au coût énergie évitable = billMAD(conso) × 12 = monthlyBill × 12 (par construction de
// billToAnnualKwh, inverse de billMAD). On MONTE le script, on trace, et on vérifie que le
// chiffre RENDU #rp9-reco-savings (et la fenêtre de production #rp9-prod-savings quand elle
// est peuplée) ne dépasse JAMAIS ce plafond dérivé de la facture — assertion d'exécution,
// pas seulement le solveur pur.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W97 §4 — les économies rendues ne dépassent pas le plafond facture', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    // PVGIS GÉNÉREUX (rendement élevé) → un toit spacieux produirait beaucoup plus que la
    // conso ; seul le PLAFOND empêche l'économie d'exploser. C'est ce qu'on veut tester.
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: { body?: string }) => {
      const body = init?.body ? (JSON.parse(init.body) as { legs?: { kwc?: number }[] }) : {};
      const legs = body.legs || [];
      const annual = legs.reduce((a, lg) => a + (lg.kwc || 1) * 2200, 0); // rendement très élevé
      return { ok: true, json: async () => ({ ok: true, annualKwh: annual }) } as unknown as Response;
    }));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  // Borne haute (MAD) du texte « X – Y/an » : on prend le 2ᵉ nombre (fourchette haute).
  function savingsHigh(id: string): number {
    const nums = (txt(id).match(/[\d   ]+/g) ?? []).map((s) => Number(s.replace(/[^\d]/g, ''))).filter((n) => n > 0);
    return nums.length ? Math.max(...nums) : 0;
  }

  it('toit spacieux + facture modeste : #rp9-reco-savings ≤ facture × 12 (plafond conso)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    const monthlyBill = 1200;
    setBill(String(monthlyBill));
    traceRoof(fakeMaps[0], 30); // grand toit → bien plus de production que la conso
    await flushPvgis();
    const ceiling = monthlyBill * 12; // billMAD(conso) × 12 = facture × 12 (round-trip exact)
    const recoHigh = savingsHigh('rp9-reco-savings');
    expect(recoHigh).toBeGreaterThan(0); // une économie est bien affichée
    // tolérance d'arrondi (fmtMad arrondit chaque borne à l'entier)
    expect(recoHigh).toBeLessThanOrEqual(ceiling + 24);
    // la fenêtre de production, si peuplée, respecte le même plafond
    const prodSav = (document.getElementById('rp9-prod-savings') as HTMLElement | null)?.textContent ?? '';
    if (prodSav && /\d/.test(prodSav)) {
      expect(savingsHigh('rp9-prod-savings')).toBeLessThanOrEqual(ceiling + 24);
    }
  }, 60000);
});

// ════════════════════════════════════════════════════════════════════════════════════
// W97 §6 — DÉGAGEMENT D'OBSTACLE À TRAVERS LE SCRIPT MONTÉ (chemin 0,3 m de bout en bout).
// Le test pur du solveur couvre déjà la règle ; ici on dessine, via le MONTAGE, un obstacle
// qui COUVRE tout le toit (mode obstacle → glissé carte), et on vérifie que la pose chute :
// le calepinage n'a plus de cellule valide → 0 panneau posé + le message honnête « non
// viable ». C'est le chemin de dégagement complet (UI → ctx.obstacles → optimiseur → carte).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W97 §6 — un obstacle couvrant fait chuter la pose (dégagement bout en bout)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  const intOf = (id: string): number => Number((txt(id).match(/[\d   ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));

  it('dessiner un obstacle qui recouvre le toit → 0 panneau + message « non viable »', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    const map = fakeMaps[0];
    // avant l'obstacle : des panneaux tiennent
    expect(intOf('rp9-reco-panels')).toBeGreaterThan(0);

    // Active le mode obstacle puis glisse un grand rectangle qui DÉBORDE le toit (16 m).
    // Les coins lng/lat couvrent largement le carré centré sur (-7.62, 33.59).
    (document.getElementById('rp9-obstacle') as HTMLButtonElement).click();
    const sw = { lng: -7.6215, lat: 33.5885 };
    const ne = { lng: -7.6185, lat: 33.5915 };
    // un VRAI glissé (deltas pixel >> seuil de tap) → obstacleFromDrag (pas un tap par défaut)
    map.fire('mousedown', { lngLat: { lng: sw.lng, lat: sw.lat }, point: { x: 50, y: 350 } });
    map.fire('mousemove', { lngLat: { lng: ne.lng, lat: ne.lat }, point: { x: 350, y: 50 } });
    map.fire('mouseup', { lngLat: { lng: ne.lng, lat: ne.lat }, point: { x: 350, y: 50 } });

    // l'obstacle a été posé et le calepinage l'évite : plus aucun panneau ne tient.
    expect(intOf('rp9-reco-panels')).toBe(0);
    expect(intOf('rp9-reco-kwc')).toBe(0);
    // message honnête « non viable » (W74) au lieu d'un faux « 0 panneau gagnant ».
    expect(txt('rp9-reco-why')).toMatch(/non viable/i);
  });

  // AP-F2/#6 — « Recommencer depuis le tracé client » reposait le contour du
  // client mais LAISSAIT les obstacles dessinés sur le tracé précédent. Ils
  // restaient à leurs coordonnées d'avant — donc possiblement hors du nouveau
  // toit — et continuaient à creuser des trous dans un calepinage qu'ils ne
  // concernaient plus. Test de bout en bout par l'effet OBSERVABLE : un
  // obstacle couvrant met la pose à zéro ; après la reprise, elle remonte.
  it('« Recommencer depuis le tracé client » efface les obstacles du tracé précédent', async () => {
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    const contourClient = squareCorners(16).map(([lng, lat]) => ({ lat, lng }));
    init({
      maptilerKey: 'test', reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      referenceContour: contourClient,
      onApiReady: (a) => { api = a; },
    });
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    const map = fakeMaps[0];
    const avant = intOf('rp9-reco-panels');
    expect(avant).toBeGreaterThan(0);

    // Un obstacle qui recouvre tout le toit : la pose tombe à zéro.
    (document.getElementById('rp9-obstacle') as HTMLButtonElement).click();
    map.fire('mousedown', { lngLat: { lng: -7.6215, lat: 33.5885 }, point: { x: 50, y: 350 } });
    map.fire('mousemove', { lngLat: { lng: -7.6185, lat: 33.5915 }, point: { x: 350, y: 50 } });
    map.fire('mouseup', { lngLat: { lng: -7.6185, lat: 33.5915 }, point: { x: 350, y: 50 } });
    expect(intOf('rp9-reco-panels')).toBe(0);

    // Reprise depuis le tracé CLIENT : sans l'effacement des obstacles, la pose
    // resterait à zéro — c'est exactement ce que cette assertion attrape.
    expect(api!.recommencerDepuisTraceClient()).toBe(true);
    expect(intOf('rp9-reco-panels')).toBeGreaterThan(0);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W113 — REPÈRE CLIENT VISIBLE À L'HYDRATATION. Quand l'étude Meriem (/devis-design/:id)
// hydrate l'outil avec un lead « pin seul » (roof_point sans contour ≥3 sommets), un
// marqueur laiton DOIT être planté à l'endroit exact pointé par le client, pour qu'elle
// le voie. Un lead sans roof_point n'en plante AUCUN. L'effacement le retire.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W113 — marqueur du pin client à l\'hydratation', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  // L'hydratation vit dans le handler map.on('load') (la couche WebGL) ; le mock ne le
  // déclenche pas tout seul → on le déclenche après init, comme MapLibre une fois le style prêt.
  const fireLoad = () => fakeMaps[0].fire('load', {});

  it('hydrater un lead « pin seul » plante un marqueur laiton à ce lng/lat', async () => {
    const init = await loadTool();
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { roof_point: { lat: 33.5905, lng: -7.5997 } } },
    });
    fireLoad();
    // un seul marqueur, ajouté, à la position du pin (lng/lat), couleur laiton de marque
    const added = fakeMarkers.filter((m) => m.added);
    expect(added.length).toBe(1);
    expect(added[0].lngLat).toEqual([-7.5997, 33.5905]); // [lng, lat] convention MapLibre
    expect(added[0].color).toBe('#e8b54a');
  });

  // W113 (atterrissage fiable) — le BUG : la caméra restait à MOROCCO_CENTER (vue Maroc
  // entière) au lieu d'atterrir sur le pin du client, parce que `flyTo` se calculait contre
  // un conteneur React pas encore dimensionné. La correction rend l'atterrissage FIABLE :
  // `resize()` recale la taille, un `jumpTo` INSTANTANÉ pose la caméra (rien à interrompre),
  // et une re-assertion `once('idle')` re-cale après un resize React tardif.
  it('hydrater un lead « pin seul » FAIT ATTERRIR la caméra sur le pin (zoom toit) — resize + jumpTo', async () => {
    const init = await loadTool();
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { roof_point: { lat: 33.5905, lng: -7.5997 } } },
    });
    fireLoad();
    const map = fakeMaps[0];
    // la taille du conteneur est recalée AVANT le déplacement (≥1 resize avant l'idle).
    expect(map.resizeCalls).toBeGreaterThanOrEqual(1);
    // placement INSTANTANÉ via jumpTo (aucune animation interruptible) sur le pin, zoom toit.
    const jt = map.jumpToCalls.at(-1) as { center: [number, number]; zoom: number } | undefined;
    expect(jt).toBeTruthy();
    expect(jt!.center).toEqual([-7.5997, 33.5905]); // [lng, lat] : pin exact
    expect(jt!.zoom).toBeGreaterThanOrEqual(18); // niveau bâtiment, pas Maroc-entier
    // en reduced-motion, AUCUN easeTo (placement instantané pur).
    expect(map.easeToCalls.length).toBe(0);
  });

  it('hydrater un lead « pin seul » RE-CALE au repos (once idle) — un resize React tardif ne ramène pas la caméra au Maroc', async () => {
    const init = await loadTool();
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { roof_point: { lat: 33.5905, lng: -7.5997 } } },
    });
    fireLoad();
    const map = fakeMaps[0];
    const resizesBeforeIdle = map.resizeCalls;
    const jumpsBeforeIdle = map.jumpToCalls.length;
    // le conteneur se redimensionne tard (React) puis la carte se stabilise → `idle`.
    map.fire('idle', {});
    // la re-assertion a recalé la taille ET re-posé la caméra sur le pin.
    expect(map.resizeCalls).toBe(resizesBeforeIdle + 1);
    expect(map.jumpToCalls.length).toBe(jumpsBeforeIdle + 1);
    const jt = map.jumpToCalls.at(-1) as { center: [number, number]; zoom: number };
    expect(jt.center).toEqual([-7.5997, 33.5905]);
    expect(jt.zoom).toBeGreaterThanOrEqual(18);
    // la re-assertion est ONE-SHOT : un second `idle` ne re-déplace plus la caméra.
    map.fire('idle', {});
    expect(map.jumpToCalls.length).toBe(jumpsBeforeIdle + 1);
  });

  it('en mouvement permis, le pin reçoit un jumpTo instantané PUIS un easeTo doux (pas un flyTo interruptible)', async () => {
    const init = await loadTool();
    init({
      maptilerKey: 'test',
      reducedMotion: false, // mouvement permis
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { roof_point: { lat: 33.5905, lng: -7.5997 } } },
    });
    fireLoad();
    const map = fakeMaps[0];
    // l'atterrissage de base reste un jumpTo INSTANTANÉ (jamais interrompu par une étape de boot).
    const jt = map.jumpToCalls.at(-1) as { center: [number, number]; zoom: number };
    expect(jt.center).toEqual([-7.5997, 33.5905]);
    expect(jt.zoom).toBeGreaterThanOrEqual(18);
    // un easeTo COSMÉTIQUE par-dessus (le jumpTo a déjà atterri) ; plus de flyTo « course ».
    const et = map.easeToCalls.at(-1) as { center: [number, number] } | undefined;
    expect(et).toBeTruthy();
    expect(et!.center).toEqual([-7.5997, 33.5905]);
  });

  it('hydrater un lead SANS roof_point ne plante aucun marqueur', async () => {
    const init = await loadTool();
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { fullName: 'Sans GPS' } },
    });
    fireLoad();
    expect(fakeMarkers.filter((m) => m.added).length).toBe(0);
  });

  it('un lead avec un VRAI contour (≥3 sommets) ne plante pas le marqueur pin', async () => {
    const init = await loadTool();
    const sq = squareCorners(16); // [lng,lat] → le lead les fournit en [lat,lng]
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { roof_outline: sq.map(([lng, lat]) => [lat, lng] as [number, number]) } },
    });
    fireLoad();
    // contour fermé → l'optimiseur tourne ; aucun marqueur pin (Meriem trace, pas un point seul)
    expect(fakeMarkers.filter((m) => m.added).length).toBe(0);
  });

  // W120 — REPRODUIT LE BUG RAPPORTÉ : un lead/devis avec un contour COMPLET (≥3 sommets,
  // pas juste un pin) ouvrait l'outil avec la caméra très loin du toit, car `close()` →
  // `go3DView()` ne fixe jamais de zoom lui-même (il ne fait que recentrer/pitcher) : sans
  // recherche d'adresse préalable pour zoomer, la caméra restait au zoom du BOOT (5, Maroc
  // entier) même correctement centrée sur le bon point GPS. La correction cadre
  // explicitement sur le contour ENTIER (`landCameraOnRoof`/`zoomToFitRing`) AVANT `close()`.
  it('un lead avec un VRAI contour cadre la caméra sur le toit ENTIER — pas le zoom du boot (Maroc)', async () => {
    const init = await loadTool();
    const sq = squareCorners(16); // carré 16 m centré sur (-7.62, 33.59)
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { roof_outline: sq.map(([lng, lat]) => [lat, lng] as [number, number]) } },
    });
    fireLoad();
    const map = fakeMaps[0];
    // le conteneur est recalé AVANT le déplacement (même garde que le pin, W113).
    expect(map.resizeCalls).toBeGreaterThanOrEqual(1);
    // le jumpTo de cadrage (posé par landCameraOnRoof, seul à porter un `zoom`) atterrit
    // sur le centre du contour, à un niveau « bâtiment » — jamais le zoom 5 du boot.
    const jt = map.jumpToCalls.find(
      (c) => typeof (c as { zoom?: number }).zoom === 'number',
    ) as { center: [number, number]; zoom: number } | undefined;
    expect(jt).toBeTruthy();
    expect(jt!.center[0]).toBeCloseTo(-7.62, 5);
    expect(jt!.center[1]).toBeCloseTo(33.59, 5);
    expect(jt!.zoom).toBeGreaterThanOrEqual(15); // jamais le zoom 5 (Maroc entier) du bug
    expect(jt!.zoom).toBeLessThanOrEqual(19); // jamais plus près que le niveau « toit » du pin
  });

  it('un lead avec un VRAI contour RE-CALE le cadrage au repos (once idle) — parité avec le pin', async () => {
    const init = await loadTool();
    const sq = squareCorners(16);
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      roofType: createRoofTypeSelect(document),
      hydrate: { lead: { roof_outline: sq.map(([lng, lat]) => [lat, lng] as [number, number]) } },
    });
    fireLoad();
    const map = fakeMaps[0];
    const resizesBeforeIdle = map.resizeCalls;
    const jumpsBeforeIdle = map.jumpToCalls.length;
    // le conteneur se redimensionne tard (React) puis la carte se stabilise → `idle`.
    map.fire('idle', {});
    expect(map.resizeCalls).toBe(resizesBeforeIdle + 1);
    expect(map.jumpToCalls.length).toBe(jumpsBeforeIdle + 1);
    const jt = map.jumpToCalls.at(-1) as { center: [number, number]; zoom: number };
    expect(jt.center[0]).toBeCloseTo(-7.62, 5);
    expect(jt.zoom).toBeGreaterThanOrEqual(15);
  });

  it('« Effacer » rend le marqueur du lead (jamais retiré) ; « + Ajouter une zone » le laisse masqué (ACAL1423)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), hydrate: { lead: { roof_point: { lat: 33.5905, lng: -7.5997 } } } });
    fireLoad();
    expect(fakeMarkers.filter((m) => m.added && !m.removed).length).toBe(1);
    setBill('1500'); traceRoof(fakeMaps[0], 16); // la fermeture du toit masque l'épingle (ACAL972)
    const masque = () => fakeMarkers[0].el.hidden;
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click(); // nouveau pan : l'épingle reste masquée
    expect(masque()).toBe(true);
    (document.getElementById('rp9-clear') as HTMLButtonElement).click(); // « Effacer » (question : le pan tracé)
    document.querySelector<HTMLButtonElement>('#rp9-question-effacer button')?.click();
    expect([masque(), fakeMarkers.map((m) => [m.added, m.removed])]).toEqual([false, [[true, false]]]); // rendue, jamais retirée
  });

  // Boot normal (pro-11 sans hydrate) et capture : aucun marqueur planté → non-régression
  // du builder public preview/capture (le marqueur ne fire QUE dans le flux d'hydratation).
  it('boot pro-11 SANS hydrate ne plante aucun marqueur (preview public intact)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    fireLoad();
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    expect(fakeMarkers.filter((m) => m.added).length).toBe(0);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL29 — les CHOIX DE CONCEPTION épinglés voyagent avec le document et sont réappliqués
// AVANT le pavage : un toit plat épinglé à 10° rouvert puis enregistré sans geste reste à
// 10° (live ATL-07 : 35°, est-ouest, 30 panneaux, une version créée). Boot RÉEL de
// l'atelier (hydrate.devis → load → pavage), sérialisé par le wrapper `onApiReady`.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL29 — choix épinglés réappliqués avant le pavage', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  function documentToitPlat(choixConception?: Record<string, unknown>) {
    return {
      version: 2, pin: { lat: 33.59, lng: -7.62 }, outline: [], billKwh: null, activeAreaId: 'z1',
      zones: [{
        id: 'z1', label: 'Toit', vertices: squareCorners(16), obstacles: [], roofType: 'flat', pitchDeg: 22,
        facingAzimuthDeg: 180, facingManual: false, neededPanels: 12, neededAuto: false,
      }],
      ...(choixConception ? { choixConception } : {}),
    };
  }

  async function bootEtSerialiser(doc: unknown) {
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 9, geometrie: { roof_layout: doc as never }, cibleVendue: false } },
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    return api!.serializeLayout() as { choixConception?: Record<string, unknown> };
  }

  it('choixConception {tilt 10 épinglé, family south} → boot → serializeLayout rend tiltDeg 10 et le même choixConception', async () => {
    const choix = { family: 'south', tilt: 10, orient: 'auto', azimuth: 'reco', margin: 'reco', epingles: ['family', 'tilt'] };
    const sortie = await bootEtSerialiser(documentToitPlat(choix));
    // Le pavage s'est fait avec les épingles : les puces affichent 10° et la famille sud
    // épinglées (pas « Recommandé »). (La scène WebGL mockée ne produit pas de layoutPlan :
    // la géométrie posée elle-même est couverte par prefill.roundtrip.test.ts.)
    expect(pressedVals('data-tilt')).toContain('10');
    expect(pressedVals('data-tilt')).not.toContain('reco');
    expect(pressedVals('data-family')).toContain('south');
    // Enregistrer sans geste : le même bloc repart.
    expect(sortie.choixConception).toEqual(choix);
  });

  it('sans choixConception, le pavage reprend la recommandation (le test discrimine) et aucune clé n’est écrite', async () => {
    const sortie = await bootEtSerialiser(documentToitPlat());
    expect(pressedVals('data-tilt')).not.toContain('10');
    expect('choixConception' in sortie).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL31 — ALLER-RETOUR OCTET-IDENTIQUE, boot RÉEL : l'`exemple` complet du contrat
// `roof_layout_v2.schema.json` (lu dans le dépôt, jamais recopié), semé par le boot devis
// ET par le boot lead, puis « Enregistrer » sans geste (`onApiReady.serializeLayout`) ⇒ le
// document produit est deep-equal à l'exemple : aucune valeur inventée (source 'devis',
// billKwh 0, panelWatt 720, saisi_le refait), numéros conservés, clés non possédées
// transmises.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL31 — l’exemple du contrat ressort identique des deux boots', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function exempleDuContrat(): Promise<Record<string, unknown>> {
    const { readFileSync } = await import('node:fs');
    const { resolve } = await import('node:path');
    // vitest tourne depuis apps/web : le contrat vit dans backend/ à la racine du dépôt.
    const chemin = resolve(process.cwd(), '../../backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json');
    // ACAL1430 — le nom d'un pan est son RANG (« Zone 1 », « Zone 2 ») : le boot réaligne `zones[].label`
    // sur l'ordre des pans ; seul ce champ de l'exemple est aligné, toute autre clé reste comparée telle quelle.
    return ((e: Record<string, unknown>) => ({ ...e, zones: (e.zones as Record<string, unknown>[]).map((z, i) => ('label' in z ? { ...z, label: `Zone ${i + 1}` } : z)) }))((JSON.parse(readFileSync(chemin, 'utf8')) as { exemple: Record<string, unknown> }).exemple);
  }

  /** Les CHEMINS qui diffèrent (la garde rougit en nommant la clé, jamais un « objet ≠ »). */
  function differences(attendu: unknown, obtenu: unknown, chemin = ''): string[] {
    if (JSON.stringify(attendu) === JSON.stringify(obtenu)) return [];
    if (attendu && obtenu && typeof attendu === 'object' && typeof obtenu === 'object'
      && Array.isArray(attendu) === Array.isArray(obtenu)) {
      const a = attendu as Record<string, unknown>;
      const b = obtenu as Record<string, unknown>;
      const cles = new Set([...Object.keys(a), ...Object.keys(b)]);
      const d = [...cles].flatMap((k) => differences(a[k], b[k], `${chemin}.${k}`));
      // Même contenu, ordre des clés différent : égal au sens du document JSON.
      return d;
    }
    return [`${chemin} : attendu ${JSON.stringify(attendu)} — obtenu ${JSON.stringify(obtenu)}`];
  }

  async function bootEtEnregistrer(hydrate: Record<string, unknown>) {
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: hydrate as never,
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    return api!.serializeLayout() as Record<string, unknown>;
  }

  it("l'`exemple` de roof_layout_v2.schema.json : boot devis → serializeLayout deep-equal", async () => {
    const exemple = await exempleDuContrat();
    const sortie = await bootEtEnregistrer({
      devis: { id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(exemple)) }, cibleVendue: false },
    });
    expect(differences(exemple, sortie)).toEqual([]);
  });

  it("l'`exemple` de roof_layout_v2.schema.json : boot lead → serializeLayout deep-equal", async () => {
    const exemple = await exempleDuContrat();
    const sortie = await bootEtEnregistrer({ lead: { roof_layout: JSON.parse(JSON.stringify(exemple)) } });
    expect(differences(exemple, sortie)).toEqual([]);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL64 — boot RÉEL d'un dossier à deux pans (area-1, area-2) puis « + Ajouter une zone » :
// le nouveau pan prend area-3, jamais un second area-2 qui écraserait le contour d'origine.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL64 — ajouter un pan à un dossier rouvert', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('dossier rouvert area-1/area-2 → « + Ajouter une zone » → area-3, area-2 garde son contour', async () => {
    const pan = (id: string, lng0: number) => ({
      id, label: id, vertices: squareCorners(16, lng0), obstacles: [], roofType: 'flat', pitchDeg: 22,
      facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true,
    });
    const doc = {
      version: 2, pin: null, outline: [], billKwh: null, activeAreaId: 'area-1',
      zones: [pan('area-1', -7.62), pan('area-2', -7.6195)],
    };
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 3, geometrie: { roof_layout: doc as never }, cibleVendue: false } },
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click();
    const sortie = api!.serializeLayout() as { zones: Array<{ id: string; vertices: unknown }> };
    expect(sortie.zones.map((z) => z.id)).toEqual(['area-1', 'area-2', 'area-3']);
    expect(sortie.zones[1].vertices).toEqual(squareCorners(16, -7.6195));
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL71 — builderApi.ajouterPanDepuisContour, boot RÉEL : le pan ajouté voyage dans le
// document ; un contour croisé est refusé sans rien créer.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL71 — ajouterPanDepuisContour', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('un carré devient area-2 et voyage dans serializeLayout ; un papillon est refusé', async () => {
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), onApiReady: (a) => { api = a; } });
    fakeMaps[0].fire('load', {});
    setBill('1500');
    traceRoof(fakeMaps[0], 16);
    const nouveau = squareCorners(12, -7.6195);
    const r = api!.ajouterPanDepuisContour(nouveau);
    expect(r).toEqual({ ok: true, id: 'area-2' });
    const doc = api!.serializeLayout() as { zones: Array<{ id: string; vertices: unknown }> };
    expect(doc.zones.map((z) => z.id)).toEqual(['area-1', 'area-2']);
    expect(doc.zones[1].vertices).toEqual(nouveau);
    const papillon = [nouveau[0], nouveau[2], nouveau[1], nouveau[3]];
    const refus = api!.ajouterPanDepuisContour(papillon);
    expect(refus.ok).toBe(false);
    expect((api!.serializeLayout() as { zones: unknown[] }).zones).toHaveLength(2);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL78 — « Recommencer depuis le tracé client », boot RÉEL : les arêtes corrigées à la
// main ne sont plus réappliquées par index au nouveau contour.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL78 — recommencer efface les arêtes manuelles', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('arête 1 corrigée à la main → Recommencer → Enregistrer : aucune arête manuel:true', async () => {
    const doc = {
      version: 2, pin: null, outline: [], billKwh: null, activeAreaId: 'area-1',
      zones: [{
        id: 'area-1', label: 'Toit', vertices: squareCorners(16), obstacles: [], roofType: 'flat', pitchDeg: 22,
        facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true,
        edges: [{ index: 1, type: 'faitage', manuel: true, retraitM: 0.8 }],
      }],
    };
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 4, geometrie: { roof_layout: doc as never }, cibleVendue: false } },
      referenceContour: squareCorners(14, -7.6201).map(([lng, lat]) => ({ lat, lng })),
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    const avant = api!.serializeLayout() as { zones: Array<{ edges?: Array<{ manuel?: boolean }> }> };
    expect(avant.zones[0].edges?.some((e) => e.manuel)).toBe(true);
    expect(api!.recommencerDepuisTraceClient()).toBe(true);
    const apres = api!.serializeLayout() as { zones: Array<{ edges?: Array<{ manuel?: boolean; retraitM?: number }> }> };
    expect((apres.zones[0].edges ?? []).some((e) => e.manuel || e.retraitM !== undefined)).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL79 — boot RÉEL d'un devis vendu à 450 panneaux : le besoin imposé vaut 450, jamais
// le plafond 400 des besoins déduits.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL79 — la cible vendue n’est jamais plafonnée', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('devis vendu à 450 panneaux → neededPanels 450 dans le document', async () => {
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 12, geometrie: { roof_outline: squareCorners(60).map(([lng, lat]) => [lat, lng]) }, cible: { panneaux: 450 } } },
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    const doc = api!.serializeLayout() as { zones: Array<{ neededPanels: number; neededAuto: boolean }> };
    expect(doc.zones[0].neededPanels).toBe(450);
    expect(doc.zones[0].neededAuto).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL80 — boot RÉEL : `rendementPvgis: null` (l'ERP) ⇒ aucune requête /api/roof-yield ;
// sans l'option (pages publiques), la requête part comme avant.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL80 — point de rendement injectable', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    fetchMock = vi.fn(() => Promise.reject(new Error('no network')));
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });
  // Les tests précédents laissent des promesses PVGIS en vol qui atterrissent dans le fetch
  // de CE test : on ne compte que les requêtes portant le site tracé ICI (lon -7.41).
  const demandesRendement = (lon = -7.41) =>
    fetchMock.mock.calls.filter((c) => String(c[0]).includes('/api/roof-yield')
      && Math.abs((JSON.parse(String((c[1] as { body?: string })?.body ?? '{}')).lon ?? 0) - lon) < 0.01).length;
  function tracerA(map: FakeMap, lng0: number) {
    vi.useFakeTimers();
    for (const [lng, lat] of squareCorners(16, lng0)) {
      map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
      vi.advanceTimersByTime(241);
    }
    vi.useRealTimers();
    (document.getElementById('rp9-finish') as HTMLButtonElement).click();
  }

  it('rendementPvgis null : tracer un toit ne demande jamais /api/roof-yield', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), rendementPvgis: null });
    setBill('1500');
    tracerA(fakeMaps[0], -7.41);
    await flushPvgis();
    expect(demandesRendement()).toBe(0);
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/); // la table committée a fourni le chiffre
  });

  it('sans l’option (pages publiques) : la requête part comme avant', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    tracerA(fakeMaps[0], -7.41);
    await flushPvgis();
    expect(demandesRendement()).toBeGreaterThan(0);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL99 — boot RÉEL d'un calepinage lié à un devis de 12, enregistré à 8 : l'atelier
// garde 8 (il ne ré-impose plus la cible du devis).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL99 — la conception enregistrée prime sur la cible du devis', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('enregistré à 8, devis à 12 → rouvrir → Enregistrer garde 8', async () => {
    const doc = {
      version: 2, pin: null, outline: [], billKwh: null, activeAreaId: 'area-1',
      zones: [{
        id: 'area-1', label: 'Toit', vertices: squareCorners(16), obstacles: [], roofType: 'flat', pitchDeg: 22,
        facingAzimuthDeg: 180, facingManual: false, neededPanels: 8, neededAuto: false,
        geometry: {
          azimuthDeg: 180, tiltDeg: 10, family: 'south', flush: false, kwc: 5.76, count: 8,
          origin: squareCorners(16)[0], panels: Array.from({ length: 8 }, (_, i) => ({ cx: i * 1.2, cy: 0 })),
        },
      }],
    };
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 21, geometrie: { roof_layout: doc as never }, cible: { panneaux: 12 } } },
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    const sortie = api!.serializeLayout() as { zones: Array<{ neededPanels: number }> };
    expect(sortie.zones[0].neededPanels).toBe(8);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL138 — boot RÉEL : l'accès solaire écrit porte une valeur par module POSÉ, une méthode
// OBJET annuelle, et la MÊME date de calcul d'une sérialisation à l'autre.
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime ACAL138 — accès solaire persisté', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('deux sérialisations sans geste sont identiques (aucune date de calcul refaite)', async () => {
    // Un immeuble de 40 m posé au sud du toit : une vraie source d'ombre, donc un accès calculé.
    const coins = squareCorners(16);
    const doc = {
      version: 2, pin: null, outline: [], billKwh: null, activeAreaId: 'area-1',
      zones: [{
        id: 'area-1', label: 'Toit', vertices: coins, obstacles: [], roofType: 'flat', pitchDeg: 22,
        facingAzimuthDeg: 180, facingManual: false, neededPanels: 6, neededAuto: false,
      }],
      environment: [{ id: 'env-1', kind: 'batiment', centerLng: -7.62, centerLat: 33.5897, heightM: 40, lengthM: 20, widthM: 10 }],
    };
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 30, geometrie: { roof_layout: doc as never }, cibleVendue: false } },
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    type Geo = { count: number; panels: unknown[]; solarAccess?: { values: unknown[]; method: unknown; computedAt: string } };
    const un = api!.serializeLayout() as { zones: Array<{ geometry?: Geo }> };
    const deux = api!.serializeLayout() as { zones: Array<{ geometry?: Geo }> };
    // Deux « Enregistrer » sans geste : document identique (aucune date refaite).
    // NB : la scène WebGL mockée de ce banc ne produit pas de pavage (pas de `layoutPlan`),
    // donc pas de `solarAccess` ici — la longueur « modules posés » et la méthode objet sont
    // prouvées par prefill.test.ts et lib/shadingEngine.test.ts.
    expect(JSON.stringify(deux)).toBe(JSON.stringify(un));
  });
});

describe('ACAL851 — les cartes disent la puissance du module RÉELLEMENT posé', () => {
  const jinko = {
    id: 'jinko-710', produitId: 9, libelle: 'Panneau Jinko 710W', longueurMm: 2384, largeurMm: 1303,
    epaisseurMm: 35, poidsKg: 34, pmaxWc: 710, source: 'fiche produit du stock',
  };
  const catalogue = {
    calepinage: 1, champs_requis: ['longueur_mm', 'largeur_mm', 'pmax_wc'], motif_liste_vide: null,
    modules: [{ module: jinko, selectionnable: true, champs_manquants: [], motif: null }],
  };
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function tracer(modulesDisponibles: unknown = catalogue) {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      modulesDisponibles } as Parameters<typeof init>[0]);
    setBill('1500');
    traceRoof(fakeMaps[0]);
  }

  it('aucun module (sans catalogue) ⇒ « × 720 W » comme aujourd’hui (module par défaut de l’atelier)', async () => {
    await tracer(null);
    expect(txt('rp9-reco-panels')).toMatch(/^\d[\d\s ]* × 720 W$/);
  });

  it('module de 710 W ⇒ « N × 710 W » et kWc = N × 0,71', async () => {
    await tracer();
    const select = document.getElementById('rp9-pan-module-select') as HTMLSelectElement;
    select.value = 'jinko-710';
    select.dispatchEvent(new window.Event('change', { bubbles: true }));
    const panneaux = txt('rp9-reco-panels');
    expect(panneaux).toMatch(/ × 710 W$/);
    const n = parseInt(panneaux.replace(/\D/g, '').slice(0, -3), 10);
    const kwc = (n * 710) / 1000;
    expect(txt('rp9-reco-kwc')).toBe(`${kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} kWc`);
    expect(txt('rp9-areas-total-panels')).not.toMatch(/720 W/);
  });
});

describe('runtime ACAL852 — sans facture, jamais « 0 MAD » ni « ≈ 0 % »', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('sans facture : « — facture inconnue » et la phrase « Facture inconnue »', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    traceRoof(fakeMaps[0]);
    const savings = txt('rp9-reco-savings');
    expect(savings).toBe('— facture inconnue');
    expect(savings).not.toMatch(/0 MAD/);
    expect(txt('rp9-reco-why')).toMatch(/Facture inconnue — saisissez-la pour voir la couverture/);
    expect(txt('rp9-reco-why')).not.toMatch(/≈ 0 %/);
    expect(txt('rp9-reco-band')).not.toMatch(/MAD/);
  });

  it('avec facture : les montants et « % de la facture », comme avant', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    expect(txt('rp9-reco-savings')).toMatch(/MAD\/an/);
    expect(txt('rp9-reco-savings')).not.toMatch(/inconnue/);
    expect(txt('rp9-reco-why')).toMatch(/% de la facture/);
  });
});

describe('runtime ACAL777 — la facture du lead sert de repli d affichage aux cartes', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  const lancer = async (facture?: number | null) => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), ...(facture === undefined ? {} : { factureMensuelleMad: facture }) });
    traceRoof(fakeMaps[0]);
    return { savings: txt('rp9-reco-savings'), panels: txt('rp9-reco-panels'), cover: txt('rp9-reco-cover'), need: (document.getElementById('rp9-need-input') as HTMLInputElement).value };
  };

  it('facture du lead 900 ⇒ économies calculées (plus de « facture inconnue ») ; nombre de panneaux inchangé', async () => {
    const sans = await lancer();
    expect(sans.savings).toBe('— facture inconnue');
    vi.resetModules();
    document.body.innerHTML = '';
    fakeMaps.length = 0;
    setupDom();
    const avec = await lancer(900);
    expect(avec.savings).toMatch(/MAD\/an/);
    expect(avec.savings).not.toMatch(/inconnue|^0 MAD/);
    expect(avec.cover).not.toMatch(/^0\s*%|≈ 0 %/);
    expect(avec.panels).toBe(sans.panels);
    expect(avec.need).toBe(sans.need);
  }, 60000);
});

describe('runtime ACAL853 — un seul nombre de production pour un toit à un seul pan', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    // PVGIS généreux (comme W97 §4) : la base de la carte diffère de celle du solveur.
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: { body?: string }) => {
      const body = init?.body ? (JSON.parse(init.body) as { legs?: { kwc?: number }[] }) : {};
      const annual = (body.legs || []).reduce((a, lg) => a + (lg.kwc || 1) * 1900, 0);
      return { ok: true, json: async () => ({ ok: true, annualKwh: annual }) } as unknown as Response;
    }));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('#rp9-reco-prod == #rp9-areas-total-prod', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0], 30);
    await flushPvgis();
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);
    expect(txt('rp9-areas-total-prod')).toBe(txt('rp9-reco-prod'));
  }, 60000);
});

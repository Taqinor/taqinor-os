// @vitest-environment jsdom
//
// W2 — géocodage INVERSE du repère (mapDraw.reverseGeocode). Prouve que :
//  - l'URL construite vise l'endpoint reverse MapTiler {lng},{lat}.json avec la clé,
//    language=fr et country=ma ;
//  - le meilleur `place_name` est renvoyé ;
//  - une réponse vide ⇒ null, un échec réseau ⇒ null (jamais de throw).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createMapDraw } from '../src/scripts/roofPro11/mapDraw';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { MapDrawDeps } from '../src/scripts/roofPro11/mapDraw';

// Carte factice : createMapDraw ne lit que getSource() au montage (aucune requête).
function fakeMap(): MapDrawDeps['map'] {
  return {
    getSource: () => ({ setData() {} }),
    flyTo() {},
    jumpTo() {},
  } as unknown as MapDrawDeps['map'];
}

/** DOM minimal lu par createMapDraw (boutons + recherche d'adresse). */
function setupDom() {
  document.body.innerHTML = '';
  for (const id of ['rp9-finish', 'rp9-undo-point']) {
    const b = document.createElement('button');
    b.id = id;
    document.body.appendChild(b);
  }
  const form = document.createElement('form');
  form.id = 'rp9-search';
  document.body.appendChild(form);
  const addr = document.createElement('input');
  addr.id = 'rp9-address';
  document.body.appendChild(addr);
  document.body.appendChild(Object.assign(document.createElement('ul'), { id: 'rp9-suggestions' }));
}

function makeMapDraw(key = 'TESTKEY') {
  const ctx = {
    opts: { maptilerKey: key, reducedMotion: true },
    vertices: [],
    closed: false,
  } as unknown as Ctx;
  return createMapDraw(ctx, { map: fakeMap(), setStatus() {}, updateAreaReadout() {} });
}

describe('W2 — reverseGeocode (repère → adresse)', () => {
  beforeEach(() => setupDom());
  afterEach(() => vi.unstubAllGlobals());

  it('construit l\'URL reverse MapTiler {lng},{lat}.json avec clé + fr + ma, et parse place_name', async () => {
    let calledUrl = '';
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calledUrl = String(url);
        return {
          ok: true,
          json: async () => ({ features: [{ place_name: 'Maârif, Casablanca, Maroc', text: 'Maârif' }] }),
        } as unknown as Response;
      }),
    );
    const md = makeMapDraw('ABC123');
    const place = await md.reverseGeocode(-7.6298, 33.5731);
    expect(place).toBe('Maârif, Casablanca, Maroc');
    // endpoint reverse = /geocoding/{lng},{lat}.json (lng AVANT lat)
    expect(calledUrl).toContain('https://api.maptiler.com/geocoding/');
    expect(calledUrl).toContain(`${encodeURIComponent(-7.6298)},${encodeURIComponent(33.5731)}.json`);
    expect(calledUrl).toContain('key=ABC123');
    expect(calledUrl).toContain('language=fr');
    expect(calledUrl).toContain('country=ma');
  });

  it('retombe sur `text` si place_name absent, et renvoie null sans feature', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, json: async () => ({ features: [{ text: 'Rabat' }] }) }) as unknown as Response),
    );
    expect(await makeMapDraw().reverseGeocode(-6.84, 34.02)).toBe('Rabat');

    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ features: [] }) }) as unknown as Response));
    expect(await makeMapDraw().reverseGeocode(-6.84, 34.02)).toBeNull();
  });

  it('ne LÈVE jamais : un échec réseau / une réponse !ok ⇒ null', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('network'); }));
    expect(await makeMapDraw().reverseGeocode(-7.6, 33.5)).toBeNull();

    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, json: async () => ({}) }) as unknown as Response));
    expect(await makeMapDraw().reverseGeocode(-7.6, 33.5)).toBeNull();
  });

  it('des coordonnées non finies ⇒ null sans requête', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({ features: [] }) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    expect(await makeMapDraw().reverseGeocode(Number.NaN, 33.5)).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

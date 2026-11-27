// D-ACAL-169 (a) — relais PUBLIC /api/panneau-defaut (contrat ERP
// `backend/django_core/apps/stock/contract_samples/panneau_par_defaut_site.json`).
//
// Le relais lit `GET {API_BASE}/api/django/public/stock/panneau-par-defaut/` et rend
// TOUJOURS 200 avec exactement { pmax_wc, source } : ERP en panne, lent (> 2 s),
// illisible ou hors contrat → { pmax_wc: null, source: 'aucun' }, jamais une page
// d'erreur. Seule frontière simulée : `fetch`.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { resetRateLimit } from '../src/lib/rateLimit';

vi.mock('cloudflare:workers', () => ({ env: {} }));

const AUCUN = { pmax_wc: null, source: 'aucun' };

async function appeler(ip = '9.9.9.9') {
  const { GET } = await import('../src/pages/api/panneau-defaut');
  const request = new Request('http://localhost/api/panneau-defaut', {
    method: 'GET',
    headers: { 'cf-connecting-ip': ip },
  });
  const res = (await GET({ request } as unknown as Parameters<typeof GET>[0])) as Response;
  const json = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  return { res, json };
}

function reponseErp(corps: unknown, status = 200): Response {
  return new Response(JSON.stringify(corps), { status, headers: { 'content-type': 'application/json' } });
}

beforeEach(() => resetRateLimit());
afterEach(() => {
  resetRateLimit();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('GET /api/panneau-defaut — relais de la puissance du panneau par défaut', () => {
  it('ERP 200 désigné → 200 { pmax_wc: 715, source: designe }, cache court, bonne cible', async () => {
    const fn = vi.fn().mockResolvedValue(reponseErp({ pmax_wc: 715, source: 'designe' }));
    vi.stubGlobal('fetch', fn);
    const { res, json } = await appeler();
    expect(res.status).toBe(200);
    expect(json).toEqual({ pmax_wc: 715, source: 'designe' });
    expect(res.headers.get('cache-control')).toBe('public, max-age=300, s-maxage=300');
    expect(fn).toHaveBeenCalledTimes(1);
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.taqinor.ma/api/django/public/stock/panneau-par-defaut/');
    expect(init.method).toBe('GET');
    expect(init.body).toBeUndefined();
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it('toute clé hors contrat venue de l’ERP est jetée (jamais un nom, un id ni un prix)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reponseErp({
      pmax_wc: 715, source: 'designe', produit_id: 42, nom: 'Panneau X 715 Wc', prix_vente: 1200,
    })));
    const { json } = await appeler();
    expect(json).toEqual({ pmax_wc: 715, source: 'designe' });
  });

  it('ERP 200 « aucun » → aucun', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reponseErp(AUCUN)));
    const { res, json } = await appeler();
    expect(res.status).toBe(200);
    expect(json).toEqual(AUCUN);
  });

  it('ERP 500 → 200 aucun, jamais une erreur', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reponseErp({ detail: 'boom' }, 500)));
    const { res, json } = await appeler();
    expect(res.status).toBe(200);
    expect(json).toEqual(AUCUN);
    expect(res.headers.get('cache-control')).toBe('no-store');
  });

  it('ERP 429 ou corps hors contrat → aucun', async () => {
    for (const [corps, status] of [
      [{ pmax_wc: 715, source: 'designe' }, 429],
      [{ pmax_wc: '715', source: 'designe' }, 200],
      [{ pmax_wc: -1, source: 'designe' }, 200],
      [[715], 200],
      [null, 200],
    ] as Array<[unknown, number]>) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reponseErp(corps, status)));
      const { res, json } = await appeler();
      expect(res.status).toBe(200);
      expect(json).toEqual(AUCUN);
    }
  });

  it('ERP injoignable → 200 aucun', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const { res, json } = await appeler();
    expect(res.status).toBe(200);
    expect(json).toEqual(AUCUN);
  });

  it('ERP trop lent (> 2 s) → la requête amont est coupée, 200 aucun', async () => {
    const fn = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((_ok, ko) => {
      init.signal?.addEventListener('abort', () => ko(new DOMException('timeout', 'TimeoutError')));
    }));
    vi.stubGlobal('fetch', fn);
    const debut = Date.now();
    const { res, json } = await appeler();
    const duree = Date.now() - debut;
    expect(res.status).toBe(200);
    expect(json).toEqual(AUCUN);
    expect(duree).toBeGreaterThanOrEqual(1900);
    expect(duree).toBeLessThan(4000);
  }, 6000);

  it('débit local dépassé → 200 aucun sans appeler l’ERP', async () => {
    const fn = vi.fn().mockResolvedValue(reponseErp({ pmax_wc: 715, source: 'designe' }));
    vi.stubGlobal('fetch', fn);
    for (let i = 0; i < 60; i += 1) await appeler('7.7.7.7');
    fn.mockClear();
    const { res, json } = await appeler('7.7.7.7');
    expect(res.status).toBe(200);
    expect(json).toEqual(AUCUN);
    expect(fn).not.toHaveBeenCalled();
  });
});

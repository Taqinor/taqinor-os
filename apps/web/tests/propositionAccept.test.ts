// W117 — Proxy same-origin /api/proposition-accept. fetch mocké (aucun réseau).
// Vérifie : validation du token ; relais du corps {nom, option?} au backend ;
// l'option n'est incluse QUE si twoOptions ; le statut + le detail backend sont
// reflétés (400/409/404) ; backend injoignable → 502 propre.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Le proxy importe `cloudflare:workers` (cf.env) — module virtuel hors build.
// On le stube avant d'importer le handler.
vi.mock('cloudflare:workers', () => ({ env: {} }));

import { POST } from '../src/pages/api/proposition-accept';
// W316 — le proxy est désormais rate-limité (bucket dédié, 10/min) : sans
// remise à zéro entre tests, les nombreux appels de ce fichier (partageant
// tous la même IP « unknown ») finiraient par se faire 429 entre eux.
import { resetRateLimit } from '../src/lib/rateLimit';

function makeRequest(body: unknown): Request {
  return new Request('http://localhost/api/proposition-accept', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}

async function call(body: unknown) {
  const res = await POST({ request: makeRequest(body) } as unknown as Parameters<typeof POST>[0]);
  const json = (await (res as Response).json()) as Record<string, unknown>;
  return { status: (res as Response).status, json };
}

function upstream(status: number, payload: unknown) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => payload,
  } as unknown as Response;
}

beforeEach(() => resetRateLimit());
afterEach(() => vi.unstubAllGlobals());

describe('POST /api/proposition-accept — validation', () => {
  it('JSON invalide → 400', async () => {
    const { status } = await call('pas du json');
    expect(status).toBe(400);
  });

  it('token manquant → 400, aucun appel backend', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    const { status } = await call({ nom: 'Reda' });
    expect(status).toBe(400);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('POST /api/proposition-accept — relais au backend', () => {
  it('succès → reflète 200 + reference + accepte_par_nom', async () => {
    const fn = vi.fn().mockResolvedValue(
      upstream(200, { detail: 'Devis accepté', reference: 'DEV-2026-001', statut: 'accepte', accepte_par_nom: 'Reda Kasri' }),
    );
    vi.stubGlobal('fetch', fn);

    const { status, json } = await call({ token: 'tok123', nom: 'Reda Kasri', option: 'avec_batterie', twoOptions: true });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.reference).toBe('DEV-2026-001');
    expect(json.accepte_par_nom).toBe('Reda Kasri');

    // URL backend correcte + token encodé dans le path.
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok123/accept/');
    expect(init.method).toBe('POST');
    // L'option est incluse car twoOptions = true.
    expect(JSON.parse(init.body as string)).toEqual({ nom: 'Reda Kasri', option: 'avec_batterie' });
  });

  it('une seule option → option omise du corps relayé', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'Devis accepté', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call({ token: 'tok123', nom: 'Reda', option: 'avec_batterie', twoOptions: false });
    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ nom: 'Reda' });
  });

  // WJ11 — le proxy relaie les champs e-signature OPTIONNELS (rétro-compatible).
  it('WJ11 — relaie signature/consentement/horodatage quand fournis', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'Devis accepté', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call({
      token: 'tok123',
      nom: 'Reda',
      option: 'avec_batterie',
      twoOptions: true,
      signature_data_url: 'data:image/png;base64,AAAA',
      consent_esign: true,
      signed_at_client: '2026-06-24T10:00:00Z',
    });
    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      nom: 'Reda',
      option: 'avec_batterie',
      signature_data_url: 'data:image/png;base64,AAAA',
      consent_esign: true,
      signed_at_client: '2026-06-24T10:00:00Z',
    });
  });

  it('WJ11 — sans champs e-signature, le corps reste le contrat de base (rétro-compat)', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'OK', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call({ token: 'tok', nom: 'Reda', twoOptions: false });
    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    // Aucun champ optionnel ajouté → backend non mis à jour fonctionne comme avant.
    expect(JSON.parse(init.body as string)).toEqual({ nom: 'Reda' });
  });

  it('WJ11 — rejette un data URL non-image ou surdimensionné (jamais relayé)', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'OK', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call({
      token: 'tok',
      nom: 'Reda',
      twoOptions: false,
      signature_data_url: 'javascript:alert(1)',
      consent_esign: true,
    });
    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    const relayed = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(relayed.signature_data_url).toBeUndefined();
    expect(relayed.consent_esign).toBe(true);
  });

  it('400 backend → reflète le statut + detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(400, { detail: 'Le nom est requis.' })));
    const { status, json } = await call({ token: 'tok', nom: '', twoOptions: false });
    expect(status).toBe(400);
    expect(json.ok).toBe(false);
    expect(json.detail).toBe('Le nom est requis.');
  });

  it('409 déjà accepté → reflète le statut + detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(409, { detail: 'Devis déjà accepté.' })));
    const { status, json } = await call({ token: 'tok', nom: 'Reda', twoOptions: false });
    expect(status).toBe(409);
    expect(json.detail).toBe('Devis déjà accepté.');
  });

  it('404 token invalide → reflète le statut', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(404, { detail: 'Introuvable.' })));
    const { status, json } = await call({ token: 'bad', nom: 'Reda', twoOptions: false });
    expect(status).toBe(404);
    expect(json.detail).toBe('Introuvable.');
  });

  it('backend injoignable → 502 propre', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const { status, json } = await call({ token: 'tok', nom: 'Reda', twoOptions: false });
    expect(status).toBe(502);
    expect(json.ok).toBe(false);
    expect(json.detail).toMatch(/indisponible/i);
  });
});

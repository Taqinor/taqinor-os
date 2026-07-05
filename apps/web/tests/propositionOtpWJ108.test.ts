// WJ108 — proxy same-origin /api/proposition-otp (demande d'envoi d'un code
// OTP e-signature). fetch mocké (aucun réseau). Vérifie : validation du
// token ; relais vers le backend otp/ ; reflet du statut/detail ; panne
// réseau → 502 propre. Le backend est déjà construit (ESIGN_OTP_ENABLED
// toggle) — ce proxy est un simple relais same-origin, symétrique de
// proposition-accept.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('cloudflare:workers', () => ({ env: {} }));

import { POST } from '../src/pages/api/proposition-otp';
import { resetRateLimit } from '../src/lib/rateLimit';

function makeRequest(body: unknown): Request {
  return new Request('http://localhost/api/proposition-otp', {
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

describe('POST /api/proposition-otp — validation', () => {
  it('JSON invalide → 400', async () => {
    const { status } = await call('pas du json');
    expect(status).toBe(400);
  });

  it('token manquant → 400, aucun appel backend', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    const { status } = await call({});
    expect(status).toBe(400);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('POST /api/proposition-otp — relais au backend', () => {
  it('succès (toggle OFF, no-op backend) → 200 ok:true', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'Code envoyé.' }));
    vi.stubGlobal('fetch', fn);

    const { status, json } = await call({ token: 'tok123' });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);

    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok123/otp/');
    expect(init.method).toBe('POST');
  });

  it('400 backend → reflète le statut + detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(400, { detail: 'Aucun contact disponible.' })));
    const { status, json } = await call({ token: 'tok' });
    expect(status).toBe(400);
    expect(json.ok).toBe(false);
    expect(json.detail).toBe('Aucun contact disponible.');
  });

  it('backend injoignable → 502 propre, sans PII', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const { status, json } = await call({ token: 'tok' });
    expect(status).toBe(502);
    expect(json.ok).toBe(false);
  });
});

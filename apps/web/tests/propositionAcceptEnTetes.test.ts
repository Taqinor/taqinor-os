// QJW25 — /api/proposition-accept transmet enfin l'IP du signataire à l'ERP.
//
// Avant ce correctif, le fetch sortant du proxy ne portait, pour tout en-tête,
// que content-type/accept (voir `proposition-accept.ts:109-113` avant QJW25) :
// ni CF-Connecting-IP ni X-Forwarded-For. L'ERP enregistrait donc, comme
// preuve légale de signature (loi 53-05), l'adresse du proxy Worker et non
// celle du signataire — le champ de preuve du registre immuable était vide de
// sens. `visite.ts`, `questionnaire/[token].astro` et
// `proposition/[...token].astro` transmettent déjà ces deux en-têtes ;
// `proposition-accept.ts` était le seul dissident, précisément le relais qui
// porte l'acte juridique.
//
// Moitié ERP jumelle : QJR416 (docs/PLAN2.md) — unifie la lecture d'IP côté
// serveur et lui fait prendre le dernier saut de confiance.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Le proxy importe `cloudflare:workers` (cf.env) — module virtuel hors build.
// On le stube avant d'importer le handler (même patron que propositionAccept.test.ts).
vi.mock('cloudflare:workers', () => ({ env: {} }));

import { POST } from '../src/pages/api/proposition-accept';
import { resetRateLimit } from '../src/lib/rateLimit';

function makeRequest(body: unknown, extraHeaders: Record<string, string> = {}): Request {
  return new Request('http://localhost/api/proposition-accept', {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...extraHeaders },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}

async function call(body: unknown, extraHeaders: Record<string, string> = {}) {
  const res = await POST({ request: makeRequest(body, extraHeaders) } as unknown as Parameters<typeof POST>[0]);
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

describe("QJW25 — le fetch sortant porte l'IP du signataire quand elle est déterminable", () => {
  it('CF-Connecting-IP présent sur la requête entrante → les DEUX en-têtes sortants portent cette IP', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'Devis accepté', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call(
      { token: 'tok123', nom: 'Reda', twoOptions: false },
      { 'cf-connecting-ip': '41.248.10.5' },
    );

    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    // Avant QJW25 : ces deux clés étaient absentes (aucun des deux en-têtes
    // n'existait) — c'est le cas rouge que ce test aurait dû détecter.
    expect(headers['X-Forwarded-For']).toBe('41.248.10.5');
    expect(headers['CF-Connecting-IP']).toBe('41.248.10.5');
  });

  it('seul X-Forwarded-For entrant (pas de CF-Connecting-IP) → les deux en-têtes sortants reprennent quand même cette IP', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'OK', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call(
      { token: 'tok123', nom: 'Reda', twoOptions: false },
      { 'x-forwarded-for': '105.157.20.9, 10.0.0.1' },
    );

    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers['X-Forwarded-For']).toBe('105.157.20.9');
    expect(headers['CF-Connecting-IP']).toBe('105.157.20.9');
  });
});

describe("QJW25 — IP non déterminable : aucun des deux en-têtes n'est envoyé (jamais une valeur vide ni inventée)", () => {
  it('aucun en-tête d\'IP entrant → ni X-Forwarded-For ni CF-Connecting-IP sortants (pas même une chaîne vide, pas "unknown")', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'OK', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    // Comme `propositionAccept.test.ts` : requête sans cf-connecting-ip ni
    // x-forwarded-for → `clientIpFromRequest` retombe sur le littéral
    // 'unknown' (utile comme clé de rate-limit, jamais comme valeur d'IP
    // légale) : ce littéral ne doit JAMAIS être envoyé comme si c'était une
    // vraie IP.
    await call({ token: 'tok123', nom: 'Reda', twoOptions: false });

    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(Object.prototype.hasOwnProperty.call(headers, 'X-Forwarded-For')).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(headers, 'CF-Connecting-IP')).toBe(false);
    expect(headers['X-Forwarded-For']).not.toBe('unknown');
    expect(headers['CF-Connecting-IP']).not.toBe('unknown');
    expect(headers['X-Forwarded-For']).not.toBe('');
    expect(headers['CF-Connecting-IP']).not.toBe('');
  });
});

describe('QJW25 — le corps transmis et le reste des en-têtes restent inchangés à l\'octet', () => {
  it('content-type/accept identiques, méthode POST, corps JSON identique à hier (avec IP déterminable)', async () => {
    const fn = vi.fn().mockResolvedValue(
      upstream(200, { detail: 'Devis accepté', reference: 'DEV-2026-001', statut: 'accepte', accepte_par_nom: 'Reda Kasri' }),
    );
    vi.stubGlobal('fetch', fn);

    const { status, json } = await call(
      { token: 'tok123', nom: 'Reda Kasri', option: 'avec_batterie', twoOptions: true },
      { 'cf-connecting-ip': '41.248.10.5' },
    );

    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.reference).toBe('DEV-2026-001');

    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok123/accept/');
    expect(init.method).toBe('POST');
    const headers = init.headers as Record<string, string>;
    expect(headers['content-type']).toBe('application/json');
    expect(headers['accept']).toBe('application/json');
    // Le corps relayé reste EXACTEMENT le contrat WJ11/W117 — aucun champ
    // d'IP n'y est ajouté (l'IP part en en-têtes, jamais dans le corps).
    expect(JSON.parse(init.body as string)).toEqual({ nom: 'Reda Kasri', option: 'avec_batterie' });
  });

  it('content-type/accept identiques quand l\'IP est indéterminable — seuls les deux en-têtes d\'IP varient', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'OK', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call({ token: 'tok', nom: 'Reda', twoOptions: false });

    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers['content-type']).toBe('application/json');
    expect(headers['accept']).toBe('application/json');
    expect(JSON.parse(init.body as string)).toEqual({ nom: 'Reda' });
  });
});

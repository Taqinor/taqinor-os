// ADEV51 (C-ADEV-018) — la signature engage l'empreinte du contenu VU.
//
// La page lit `empreinte_contenu` dans `/data/` (contrat `proposal_data.json`),
// la renvoie à `/api/proposition-accept`, que le proxy RELAIE au serveur ; un
// 409 `empreinte_perimee` (contrat `proposal_accept.json`) n'est JAMAIS un
// succès : la page affiche le message et recharge la proposition.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

vi.mock('cloudflare:workers', () => ({ env: {} }));

import { POST } from '../src/pages/api/proposition-accept';
import { resetRateLimit } from '../src/lib/rateLimit';
import {
  buildAcceptBodyRich,
  estEmpreintePerimee,
  normalizeAcceptResponse,
} from '../src/lib/proposition';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const DATA = JSON.parse(read('../src/contract_samples/proposal_data.json')) as Record<string, Record<string, unknown>>;
const ACCEPT = JSON.parse(read('../src/contract_samples/proposal_accept.json')) as Record<string, Record<string, unknown>>;
const PAGE = read('../src/pages/proposition/[...token].astro');
const EMPREINTE = String(DATA.exemple.empreinte_contenu);
const REFUS = (ACCEPT.reponses_409 as Record<string, unknown>).empreinte_perimee as { detail: string; code: string };

function upstream(status: number, payload: unknown) {
  return { status, ok: status >= 200 && status < 300, json: async () => payload } as unknown as Response;
}

async function call(body: unknown) {
  const req = new Request('http://localhost/api/proposition-accept', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const res = (await POST({ request: req } as unknown as Parameters<typeof POST>[0])) as Response;
  return { status: res.status, json: (await res.json()) as Record<string, unknown> };
}

beforeEach(() => resetRateLimit());
afterEach(() => vi.unstubAllGlobals());

describe('ADEV51 — empreinte du contenu lu, de la page au serveur', () => {
  it('le contrat sert une empreinte et le corps de signature la porte telle quelle', () => {
    expect(EMPREINTE).toMatch(/^[0-9a-f]{64}$/);
    const corps = buildAcceptBodyRich({ nom: 'Karim', option: null }, false, {
      consent_esign: true,
      empreinte_contenu: EMPREINTE,
    });
    expect(corps.empreinte_contenu).toBe(EMPREINTE);
    expect(buildAcceptBodyRich({ nom: 'Karim', option: null }, false, {})).not.toHaveProperty('empreinte_contenu');
  });

  it('le proxy relaie `empreinte_contenu` au serveur', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'ok', accepte_par_nom: 'Karim' }));
    vi.stubGlobal('fetch', fn);
    await call({ token: 'tok', nom: 'Karim', twoOptions: false, consent_esign: true, empreinte_contenu: EMPREINTE });
    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body)).empreinte_contenu).toBe(EMPREINTE);
  });

  it('le 409 `empreinte_perimee` est relayé avec son code, jamais comme un succès', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(409, REFUS)));
    const { status, json } = await call({ token: 'tok', nom: 'Karim', twoOptions: false, empreinte_contenu: EMPREINTE });
    expect(status).toBe(409);
    expect(json.ok).toBe(false);
    expect(json.code).toBe('empreinte_perimee');
    expect(json.detail).toBe(REFUS.detail);
    expect(estEmpreintePerimee(409, json)).toBe(true);
    expect(estEmpreintePerimee(409, normalizeAcceptResponse(409, { detail: 'x', code: 'statut' }))).toBe(false);
  });

  it('la page envoie l’empreinte lue et recharge sur `empreinte_perimee` AVANT la branche 409 « déjà accepté »', () => {
    expect(PAGE).toContain('empreinte: data?.empreinte_contenu');
    expect(PAGE).toContain("empreinte_contenu: cfg.empreinte ?? ''");
    const iRecharge = PAGE.indexOf('if (estEmpreintePerimee(res.status, data))');
    const iDejaAccepte = PAGE.indexOf('if (res.status === 409)');
    expect(iRecharge).toBeGreaterThan(0);
    expect(iRecharge).toBeLessThan(iDejaAccepte);
    expect(PAGE.slice(iRecharge, iDejaAccepte)).toContain('window.location.reload()');
  });
});

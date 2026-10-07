// CIW305 — Signature en ligne d'un devis C&I : raison sociale, nom, qualité du signataire et ICE ;
// plus « mes parents, mon foyer ». Contrat partagé `acceptation_entreprise.json`.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

vi.mock('cloudflare:workers', () => ({ env: {} }));

import { POST } from '../src/pages/api/proposition-accept';
import { resetRateLimit } from '../src/lib/rateLimit';
import {
  validateSign,
  buildAcceptBody,
  buildAcceptBodyRich,
  normalizeAcceptResponse,
  signatureEntrepriseRequise,
  type SignFormState,
} from '../src/lib/proposition';

const ENT = { raison_sociale: 'Hôtel Exemple SARL', signataire_qualite: 'Directeur général', ice: '000000000000000' };

describe('CIW305 — validateSign C&I', () => {
  it('sans ICE → invalide sur l\'ICE (champ nommé)', () => {
    const f: SignFormState = { nom: 'Karim Exemple', option: null, entreprise: { ...ENT, ice: '  ' } };
    const v = validateSign(f, false, true);
    expect(v.valid).toBe(false);
    expect(v.champ).toBe('entreprise.ice');
    expect(v.error).toMatch(/ICE/);
  });

  it('sans raison sociale / sans qualité → invalide sur le bon champ', () => {
    expect(validateSign({ nom: 'K', option: null, entreprise: { ...ENT, raison_sociale: '' } }, false, true).champ).toBe(
      'entreprise.raison_sociale',
    );
    expect(validateSign({ nom: 'K', option: null, entreprise: { ...ENT, signataire_qualite: '' } }, false, true).champ).toBe(
      'entreprise.signataire_qualite',
    );
    // aucun bloc entreprise du tout → la raison sociale d'abord
    expect(validateSign({ nom: 'K', option: null }, false, true).champ).toBe('entreprise.raison_sociale');
  });

  it('nom vide → champ « nom » ; quatre champs remplis → valide', () => {
    expect(validateSign({ nom: ' ', option: null, entreprise: ENT }, false, true).champ).toBe('nom');
    expect(validateSign({ nom: 'Karim Exemple', option: null, entreprise: ENT }, false, true)).toEqual({ valid: true, error: null });
  });

  it('l\'option reste exigée à deux options, après l\'identité de l\'entreprise', () => {
    const v = validateSign({ nom: 'K', option: null, entreprise: ENT }, true, true);
    expect(v.valid).toBe(false);
    expect(v.champ).toBe('option');
  });

  it('résidentiel inchangé : aucune exigence entreprise', () => {
    expect(validateSign({ nom: 'Hassan', option: null }, false)).toEqual({ valid: true, error: null });
    expect(validateSign({ nom: 'Hassan', option: null }, false, false).valid).toBe(true);
  });

  it('seuls commercial / industriel exigent l\'entreprise', () => {
    expect(signatureEntrepriseRequise('commercial')).toBe(true);
    expect(signatureEntrepriseRequise('industriel')).toBe(true);
    for (const m of ['residentiel', 'agricole', '', null, undefined]) {
      expect(signatureEntrepriseRequise(m as string | null | undefined)).toBe(false);
    }
  });
});

describe('CIW305 — corps construit avec `entreprise`', () => {
  it('buildAcceptBody / buildAcceptBodyRich portent entreprise (trimée)', () => {
    const f: SignFormState = {
      nom: ' Karim Exemple ',
      option: null,
      entreprise: { raison_sociale: ' Hôtel Exemple SARL ', signataire_qualite: ' DG ', ice: ' 000000000000000 ' },
    };
    expect(buildAcceptBody(f, false).entreprise).toEqual({
      raison_sociale: 'Hôtel Exemple SARL',
      signataire_qualite: 'DG',
      ice: '000000000000000',
    });
    const rich = buildAcceptBodyRich(f, false, { consent_esign: true });
    expect(rich.entreprise?.ice).toBe('000000000000000');
    expect(rich.nom).toBe('Karim Exemple');
  });

  it('sans saisie entreprise → aucune clé `entreprise` (résidentiel : corps inchangé)', () => {
    const body = buildAcceptBodyRich({ nom: 'Hassan', option: null }, false, {});
    expect('entreprise' in body).toBe(false);
  });
});

describe('CIW305 — normalizeAcceptResponse relaie le champ nommé par le serveur', () => {
  it('400 {detail, champ} → champ conservé', () => {
    const r = normalizeAcceptResponse(400, { detail: "L'ICE de l'entreprise est requis pour accepter ce devis.", champ: 'entreprise.ice' });
    expect(r.ok).toBe(false);
    expect(r.champ).toBe('entreprise.ice');
    expect(r.detail).toContain('ICE');
  });
  it('sans champ → pas de clé champ', () => {
    expect('champ' in normalizeAcceptResponse(400, { detail: 'x' })).toBe(false);
  });
});

describe('CIW305 — proxy /api/proposition-accept : `entreprise` relayé, champ d\'erreur renvoyé', () => {
  function makeRequest(body: unknown): Request {
    return new Request('http://localhost/api/proposition-accept', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
  }
  async function call(body: unknown) {
    const res = await POST({ request: makeRequest(body) } as unknown as Parameters<typeof POST>[0]);
    return { status: (res as Response).status, json: (await (res as Response).json()) as Record<string, unknown> };
  }
  beforeEach(() => resetRateLimit());
  afterEach(() => vi.unstubAllGlobals());

  it('le corps relayé au backend porte `entreprise`', async () => {
    const fetchMock = vi.fn(async () => ({ status: 200, ok: true, json: async () => ({ detail: 'ok', reference: 'DEV-1' }) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { status } = await call({ token: 'tok', nom: 'Karim Exemple', entreprise: ENT });
    expect(status).toBe(200);
    const sent = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, { body: string }])[1].body);
    expect(sent.entreprise).toEqual(ENT);
    expect(sent.nom).toBe('Karim Exemple');
  });

  it('un bloc entreprise mal formé n\'est pas relayé tel quel (chaînes bornées)', async () => {
    const fetchMock = vi.fn(async () => ({ status: 200, ok: true, json: async () => ({ detail: 'ok' }) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    await call({ token: 'tok', nom: 'K', entreprise: { raison_sociale: 'x'.repeat(500), ice: 42 } });
    const sent = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, { body: string }])[1].body);
    expect(sent.entreprise.raison_sociale).toHaveLength(200);
    expect(sent.entreprise.ice).toBe('');
  });

  it('400 serveur nommant le champ → renvoyé au navigateur (affichage sous le bon champ)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ status: 400, ok: false, json: async () => ({ detail: "L'ICE de l'entreprise est requis pour accepter ce devis.", champ: 'entreprise.ice' }) }) as unknown as Response),
    );
    const { status, json } = await call({ token: 'tok', nom: 'K', entreprise: { ...ENT, ice: '' } });
    expect(status).toBe(400);
    expect(json.champ).toBe('entreprise.ice');
  });

  it('résidentiel : aucun `entreprise` relayé quand le navigateur n\'en envoie pas', async () => {
    const fetchMock = vi.fn(async () => ({ status: 200, ok: true, json: async () => ({ detail: 'ok' }) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    await call({ token: 'tok', nom: 'Hassan' });
    const sent = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, { body: string }])[1].body);
    expect('entreprise' in sent).toBe(false);
  });
});

describe('CIW305 — la page C&I ne propose plus « mes parents, mon foyer »', () => {
  const page = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
  it('le bloc « pour quelqu\'un d\'autre » n\'est rendu que hors C&I', () => {
    const i = page.indexOf('id="sign-on-behalf-of"');
    expect(i).toBeGreaterThan(0);
    const avant = page.slice(Math.max(0, i - 1800), i);
    expect(avant).toContain('{!entrepriseRequise && (');
  });
  it('quatre champs entreprise rendus quand le devis est C&I, avec l\'erreur sous chaque champ', () => {
    for (const id of ['sign-raison-sociale', 'sign-qualite', 'sign-ice']) expect(page).toContain(`id="${id}"`);
    for (const id of ['entreprise-raison_sociale', 'entreprise-signataire_qualite', 'entreprise-ice']) {
      expect(page).toContain(`id="sign-err-${id}"`);
    }
    expect(page).toContain('validateSign(state, cfg.twoOptions, !!cfg.entrepriseRequise)');
  });
});

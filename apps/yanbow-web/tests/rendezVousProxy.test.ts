/**
 * YBW54 — proxy même origine `POST /api/rendez-vous` + envoi signé non bloquant.
 *
 * La signature est vérifiée par un vérificateur INDÉPENDANT (node:crypto), pas
 * par le code sous test ; le `fetch` vers l'ERP est simulé (aucun réseau).
 */
import { createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CLES_CHAMPS, POT_DE_MIEL } from '../src/lib/rdv/champs';
import { reinitialiserEtat, traiterDemande, type Dependances, LIMITE_PAR_MINUTE, SEUIL_ALERTE } from '../src/lib/rdv/forward';
import { signer } from '../src/lib/rdv/sign';
import { PREFIXE, reinitialiserAvertissement } from '../worker/reprise.mjs';

const CONTRAT = JSON.parse(readFileSync(fileURLToPath(new URL('../src/contract_samples/demande_rdv_site.json', import.meta.url)), 'utf-8'));

const ORIGINE = 'https://site.exemple.test';
const URL_ERP = 'https://erp.exemple.test/api/django/crm/webhooks/demande-rdv/';
const SECRET = 'c'.repeat(64);
const T0 = Date.UTC(2026, 9, 8, 9, 0, 0);
const IDEM = '11111111-2222-4333-8444-555555555555';

/** Vérificateur indépendant de la sémantique ERP (`verify_signature_v2`). */
function signatureValide(entete: string, corps: string, maintenantSec: number): boolean {
  const m = /^t=(\d+),v1=([0-9a-f]{64})$/.exec(entete);
  if (!m) return false;
  if (Math.abs(maintenantSec - Number(m[1])) > 300) return false;
  return createHmac('sha256', SECRET).update(`${m[1]}.${corps}`).digest('hex') === m[2];
}

function demande(corps: Record<string, unknown>, entetes: Record<string, string> = { 'sec-fetch-site': 'same-origin' }): Request {
  return new Request(`${ORIGINE}/api/rendez-vous`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'user-agent': 'NavigateurTest/1.0', 'x-forwarded-for': '203.0.113.9', ...entetes },
    body: JSON.stringify(corps),
  });
}

const VALIDE = {
  idempotency_key: IDEM,
  nom: '  Jeanne   Test ',
  societe: 'Atelier Test',
  email: ' Jeanne.Test@Example.COM ',
  telephone: '+33 6 00 00 00 00',
  produit: 'solarbow',
  message: 'Bonjour,\r\n\r\n\r\nune démo ?',
  langue: 'fr',
  consentement: true,
  consentement_le: '1999-01-01T00:00:00Z',
  page: '/rendez-vous/?email=fuite@example.com#x',
  utm_source: 'test',
  [POT_DE_MIEL]: '',
  company_id: 7,
  ip: '203.0.113.9',
};

interface Capture {
  url: string;
  entetes: Record<string, string>;
  corps: string;
  t: number;
}

function banc(options: { reponses?: (number | 'reseau')[]; env?: Record<string, unknown>; dureeRepriseJours?: number | null } = {}) {
  let horloge = T0;
  const appels: Capture[] = [];
  const reponses = [...(options.reponses ?? [201])];
  const journal = { info: vi.fn(), warn: vi.fn(), error: vi.fn() };
  const enAttente: Promise<unknown>[] = [];
  const fetchSimule = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const entetes = Object.fromEntries(new Headers(init?.headers).entries());
    appels.push({ url: String(url), entetes, corps: String(init?.body), t: horloge });
    const r = reponses.length > 1 ? reponses.shift()! : reponses[0];
    if (r === 'reseau') throw new TypeError('fetch failed');
    return new Response(JSON.stringify({ id: 1, statut: 'recu' }), { status: r });
  });
  const deps: Dependances = {
    env: options.env ?? { YANBOW_RDV_URL: URL_ERP, YANBOW_RDV_CLE_ID: 'cle-test', YANBOW_RDV_SECRET: SECRET },
    waitUntil: (p) => {
      enAttente.push(p);
    },
    fetch: fetchSimule as unknown as typeof fetch,
    maintenant: () => horloge,
    journal,
    nouvelleCle: () => '99999999-9999-4999-8999-999999999999',
    dureeRepriseJours: options.dureeRepriseJours ?? null,
  };
  return {
    deps,
    appels,
    journal,
    fetchSimule,
    avancer: (ms: number) => {
      horloge += ms;
    },
    terminer: () => Promise.all(enAttente.splice(0)),
    journaux: () => [...journal.info.mock.calls, ...journal.warn.mock.calls, ...journal.error.mock.calls].map((c) => String(c[0])).join('\n'),
  };
}

beforeEach(() => {
  reinitialiserEtat();
  reinitialiserAvertissement();
});

describe('YBW54 — signature (sign.ts)', () => {
  it('la sortie de sign.ts = le vecteur doré du contrat', async () => {
    const v = CONTRAT.vecteur_signature;
    expect(await signer(v.secret, v.corps_brut, v.t)).toBe(v.x_signature);
  });
});

describe('YBW54 — garde d’origine, limite, pot de miel, validation', () => {
  it('cross-site → 403, rien envoyé', async () => {
    const b = banc();
    const r = await traiterDemande(demande(VALIDE, { 'sec-fetch-site': 'cross-site' }), b.deps);
    expect(r.status).toBe(403);
    expect(b.fetchSimule).not.toHaveBeenCalled();
  });

  it('Sec-Fetch-Site absent → repli sur Origin', async () => {
    const b = banc();
    expect((await traiterDemande(demande(VALIDE, { origin: 'https://autre.exemple.test' }), b.deps)).status).toBe(403);
    expect((await traiterDemande(demande(VALIDE, {}), b.deps)).status).toBe(403);
    expect((await traiterDemande(demande(VALIDE, { origin: ORIGINE }), b.deps)).status).toBe(200);
  });

  it('limite par isolat → 429 + Retry-After', async () => {
    const b = banc();
    for (let i = 0; i < LIMITE_PAR_MINUTE; i++) {
      expect((await traiterDemande(demande({}), b.deps)).status).toBe(400);
    }
    const r = await traiterDemande(demande(VALIDE), b.deps);
    expect(r.status).toBe(429);
    expect(Number(r.headers.get('retry-after'))).toBeGreaterThan(0);
  });

  it('pot de miel rempli → faux succès, jamais transmis', async () => {
    const b = banc();
    const r = await traiterDemande(demande({ ...VALIDE, [POT_DE_MIEL]: 'https://spam.test' }), b.deps);
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ ok: true });
    await b.terminer();
    expect(b.fetchSimule).not.toHaveBeenCalled();
  });

  it('erreurs PAR CHAMP, dans la langue, consentement requis', async () => {
    const b = banc();
    const r = await traiterDemande(
      demande({ ...VALIDE, langue: 'en', nom: '', email: 'jeanne@', produit: 'autre', consentement: false, message: 'x'.repeat(2001) }),
      b.deps,
    );
    expect(r.status).toBe(400);
    const { erreurs } = (await r.json()) as { erreurs: Record<string, string> };
    expect(Object.keys(erreurs).sort()).toEqual(['consentement', 'email', 'message', 'nom', 'produit']);
    expect(erreurs.nom).toBe('This field is required.');
    expect(erreurs.consentement).toMatch(/Tick the box/);
    expect(JSON.stringify(erreurs)).not.toContain('jeanne@');
    const fr = await traiterDemande(demande({ ...VALIDE, consentement: 'oui' }), b.deps);
    expect(((await fr.json()) as { erreurs: Record<string, string> }).erreurs.consentement).toMatch(/Cochez la case/);
    expect(b.fetchSimule).not.toHaveBeenCalled();
  });

  it('envoi non configuré → 503, rien envoyé', async () => {
    const b = banc({ env: { YANBOW_RDV_URL: URL_ERP } });
    const r = await traiterDemande(demande(VALIDE), b.deps);
    expect(r.status).toBe(503);
    expect(b.fetchSimule).not.toHaveBeenCalled();
  });

  it("n'utilise jamais les variables du site TAQINOR", async () => {
    const b = banc({ env: { LEAD_WEBHOOK_URL: URL_ERP, LEAD_WEBHOOK_SECRET: SECRET } });
    expect((await traiterDemande(demande(VALIDE), b.deps)).status).toBe(503);
  });
});

describe('YBW54 — envoi signé en arrière-plan', () => {
  it('SEULES les clés du registre, signées, sans IP ni agent, idempotency_key en miroir', async () => {
    const b = banc();
    const r = await traiterDemande(demande(VALIDE), b.deps);
    expect(r.status).toBe(200);
    expect(b.fetchSimule).not.toHaveBeenCalled(); // pas encore : arrière-plan
    await b.terminer();
    expect(b.appels).toHaveLength(1);
    const [a] = b.appels;
    expect(a.url).toBe(URL_ERP);
    const corps = JSON.parse(a.corps);
    for (const k of Object.keys(corps)) expect(CLES_CHAMPS).toContain(k);
    expect(Object.keys(corps)).not.toContain('company_id');
    expect(Object.keys(corps)).not.toContain(POT_DE_MIEL);
    expect(corps).toMatchObject({
      idempotency_key: IDEM,
      nom: 'Jeanne Test',
      email: 'jeanne.test@example.com',
      message: 'Bonjour,\n\nune démo ?',
      page: '/rendez-vous/',
      consentement: true,
      consentement_le: '2026-10-08T09:00:00Z',
    });
    expect(a.entetes['x-site-cle']).toBe('cle-test');
    expect(a.entetes['idempotency-key']).toBe(IDEM);
    expect(signatureValide(a.entetes['x-signature'], a.corps, Math.floor(T0 / 1000))).toBe(true);
    for (const h of Object.keys(a.entetes)) expect(h).not.toMatch(/forwarded|user-agent|cf-connecting-ip|x-real-ip/);
    expect(a.corps).not.toContain('203.0.113.9');
    expect(a.corps).not.toContain('NavigateurTest');
  });

  it('nouvel essai re-signé sur 5xx, jamais sur 4xx ni sur panne réseau', async () => {
    const b = banc({ reponses: [503, 201] });
    await traiterDemande(demande(VALIDE), b.deps);
    await b.terminer();
    expect(b.appels).toHaveLength(2);
    expect(b.appels[0].corps).toBe(b.appels[1].corps);

    const b400 = banc({ reponses: [400] });
    await traiterDemande(demande(VALIDE), b400.deps);
    await b400.terminer();
    expect(b400.appels).toHaveLength(1);

    const bRes = banc({ reponses: ['reseau'] });
    await traiterDemande(demande(VALIDE), bRes.deps);
    await bRes.terminer();
    expect(bRes.appels).toHaveLength(1);
  });

  it('liaison KV absente : un avertissement UNE fois, jamais d’exception', async () => {
    const b = banc({ reponses: [500] });
    await traiterDemande(demande(VALIDE), b.deps);
    await traiterDemande(demande({ ...VALIDE, idempotency_key: '22222222-2222-4222-8222-222222222222' }), b.deps);
    await expect(b.terminer()).resolves.toBeDefined();
    expect(b.journal.warn.mock.calls.filter((c) => String(c[0]).includes('aucun espace de reprise'))).toHaveLength(1);
  });

  it(`ALERT au-delà de ${SEUIL_ALERTE} échecs consécutifs, aucune donnée personnelle dans les journaux`, async () => {
    const b = banc({ reponses: [500] });
    for (let i = 0; i < SEUIL_ALERTE; i++) {
      await traiterDemande(demande({ ...VALIDE, idempotency_key: `3333333${i}-3333-4333-8333-333333333333` }), b.deps);
      await b.terminer();
    }
    expect(b.journal.error.mock.calls.some((c) => String(c[0]).includes('[ALERT]'))).toBe(true);
    const tout = b.journaux();
    for (const pii of ['Jeanne', 'jeanne', 'Atelier', '+33', 'démo']) expect(tout).not.toContain(pii);
  });

  it('reprise KV : 31 min plus tard, RE-SIGNÉE avec un t frais, même idempotency_key', async () => {
    const stock = new Map<string, string>();
    const kv = {
      get: vi.fn(async (k: string) => stock.get(k) ?? null),
      put: vi.fn(async (k: string, v: string, _options?: { expirationTtl?: number }) => {
        stock.set(k, v);
      }),
      delete: vi.fn(async (k: string) => {
        stock.delete(k);
      }),
      list: vi.fn(async ({ prefix }: { prefix?: string } = {}) => ({ keys: [...stock.keys()].filter((k) => k.startsWith(prefix ?? '')).map((name) => ({ name })) })),
    };
    const b = banc({
      reponses: [500, 500, 201],
      env: { YANBOW_RDV_URL: URL_ERP, YANBOW_RDV_CLE_ID: 'cle-test', YANBOW_RDV_SECRET: SECRET, RDV_REPRISE: kv },
      dureeRepriseJours: 7,
    });
    await traiterDemande(demande(VALIDE), b.deps);
    await b.terminer();
    expect([...stock.keys()]).toEqual([PREFIXE + IDEM]);
    expect(kv.put.mock.calls[0][2]).toEqual({ expirationTtl: 7 * 86400 });
    expect(b.appels).toHaveLength(2);

    b.avancer(31 * 60 * 1000);
    await traiterDemande(demande({ ...VALIDE, idempotency_key: '44444444-4444-4444-8444-444444444444' }), b.deps);
    await b.terminer();
    const rejeu = b.appels.at(-1)!;
    expect(JSON.parse(rejeu.corps).idempotency_key).toBe(IDEM);
    expect(rejeu.entetes['idempotency-key']).toBe(IDEM);
    const maintenant = Math.floor((T0 + 31 * 60 * 1000) / 1000);
    expect(rejeu.entetes['x-signature']).toMatch(new RegExp(`^t=${maintenant},`));
    expect(signatureValide(rejeu.entetes['x-signature'], rejeu.corps, maintenant)).toBe(true);
    // La signature d'origine, rejouée telle quelle, serait périmée.
    expect(signatureValide(b.appels[0].entetes['x-signature'], b.appels[0].corps, maintenant)).toBe(false);
    expect(stock.size).toBe(0);
  });
});

// W117 — Proxy same-origin /api/proposition-accept. fetch mocké (aucun réseau).
// Vérifie : validation du token ; relais du corps {nom, option?} au backend ;
// l'option n'est incluse QUE si twoOptions ; le statut + le detail backend sont
// reflétés (400/409/404) ; backend injoignable → 502 propre.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Le proxy importe `cloudflare:workers` (cf.env) — module virtuel hors build.
// On le stube avant d'importer le handler.
vi.mock('cloudflare:workers', () => ({ env: {} }));

import { POST } from '../src/pages/api/proposition-accept';
import { lireRecuAcceptation } from '../src/lib/proposition';
// W316 — le proxy est désormais rate-limité (bucket dédié, 10/min) : sans
// remise à zéro entre tests, les nombreux appels de ce fichier (partageant
// tous la même IP « unknown ») finiraient par se faire 429 entre eux.
import { resetRateLimit } from '../src/lib/rateLimit';
// ADEV53 — succès post-signature : `paiement` du contrat partagé `proposal_accept.json`.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { POST as POST_VIREMENT } from '../src/pages/api/proposition-virement';
import {
  lirePaiementAcceptation,
  paiementVue,
  virementEndpoint,
  virementMessage,
  VIREMENT_MSG,
} from '../src/lib/paiementAcceptation';

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

  // WJ108 — code OTP optionnel (backend validate_esign_otp, toggle ESIGN_OTP_ENABLED).
  it('WJ108 — relaie otp_code quand fourni', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'OK', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call({ token: 'tok', nom: 'Reda', twoOptions: false, otp_code: '123456' });
    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ nom: 'Reda', otp_code: '123456' });
  });

  it('WJ108 — otp_code absent/vide n\'est jamais relayé (comportement inchangé, toggle OFF)', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'OK', accepte_par_nom: 'Reda' }));
    vi.stubGlobal('fetch', fn);

    await call({ token: 'tok', nom: 'Reda', twoOptions: false, otp_code: '' });
    const [, init] = fn.mock.calls[0] as [string, RequestInit];
    const relayed = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(relayed.otp_code).toBeUndefined();
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

// ── ADEV53 (C-ADEV-023) — l'écran de paiement naît de l'échantillon du contrat ──────────────
const lire = (rel: string): string => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const CONTRAT = JSON.parse(lire('../src/contract_samples/proposal_accept.json')) as {
  reponse_200: Record<string, unknown> & { paiement: Record<string, unknown> };
};
const PAGE = lire('../src/pages/proposition/[...token].astro');

async function callVirement(body: unknown) {
  const req = new Request('http://localhost/api/proposition-virement', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const res = (await POST_VIREMENT({ request: req } as unknown as Parameters<typeof POST_VIREMENT>[0])) as Response;
  return { status: res.status, json: (await res.json()) as Record<string, unknown> };
}

describe('ADEV53 — succès post-signature : acompte, RIB, déclaration de virement', () => {
  it('le contrat ne sert plus de lien carte (aucune route pay-card)', () => {
    expect(CONTRAT.reponse_200.paiement).not.toHaveProperty('card_payment_url');
    expect(String(CONTRAT.reponse_200.paiement.declare_url)).toMatch(/\/virement\/$/);
  });

  it('le proxy relaie `paiement` de la réponse 200 du contrat, jamais sur un refus', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(200, CONTRAT.reponse_200)));
    const ok = await call({ token: 'tok', nom: 'Karim Exemple', twoOptions: false });
    expect(ok.status).toBe(200);
    expect(ok.json.paiement).toEqual(lirePaiementAcceptation(CONTRAT.reponse_200));
    expect(Object.keys(ok.json.paiement as object).sort()).toEqual(Object.keys(CONTRAT.reponse_200.paiement).sort());

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(409, { detail: 'Refus.', code: 'statut', paiement: {} })));
    const refus = await call({ token: 'tok', nom: 'Karim Exemple', twoOptions: false });
    expect(refus.json).not.toHaveProperty('paiement');
  });

  it('la réponse du contrat produit l’écran : acompte servi, RIB absent quand vide, action de déclaration', () => {
    const vue = paiementVue(lirePaiementAcceptation(CONTRAT.reponse_200));
    expect(vue).toEqual({
      acompte: '12 000,00 MAD',
      pourcentage: '30',
      rib: null,
      message: null,
      peutDeclarer: true,
    });
    // Un RIB servi par le profil société est affiché tel quel (valeur de test, pas un vrai compte).
    const avecRib = { ...CONTRAT.reponse_200, paiement: { ...CONTRAT.reponse_200.paiement, rib: 'RIB-DE-TEST' } };
    expect(paiementVue(lirePaiementAcceptation(avecRib))?.rib).toBe('RIB-DE-TEST');
    // Rien de servi ⇒ aucun écran (jamais un montant de repli).
    const vide = { paiement: { acompte_ttc: null, pourcentage: null, rib: '', message: '', declare_url: '' } };
    expect(paiementVue(lirePaiementAcceptation(vide))).toBeNull();
  });

  it('la page branche le bloc de paiement sur la réponse d’acceptation', () => {
    expect(PAGE).toContain('id="sign-paiement"');
    expect(PAGE).toContain('id="sign-paiement-acompte"');
    expect(PAGE).toContain('id="sign-paiement-rib"');
    expect(PAGE).toContain('id="sign-virement-btn"');
    expect(PAGE).toContain('afficherPaiement(data);');
    expect(PAGE).toContain("fetch('/api/proposition-virement'");
    expect(PAGE).not.toMatch(/card_payment_url|pay-card/);
  });

  it('le proxy de virement poste au /virement/ du jeton et reflète 200 puis 403 otp_required', async () => {
    const fn = vi.fn().mockResolvedValue(upstream(200, { detail: 'Merci ! Votre déclaration a été transmise.' }));
    vi.stubGlobal('fetch', fn);
    const ok = await callVirement({ token: 'tok 1' });
    expect(ok.status).toBe(200);
    expect(ok.json.ok).toBe(true);
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(virementEndpoint('https://api.taqinor.ma', 'tok 1'));
    expect(url).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok%201/virement/');
    expect(init.method).toBe('POST');
    expect(virementMessage(ok.json as never)).toBe(VIREMENT_MSG.succes);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(403, { detail: 'otp_required' })));
    const refus = await callVirement({ token: 'tok' });
    expect(refus.status).toBe(403);
    expect(refus.json.detail).toBe('otp_required');
    expect(virementMessage(refus.json as never)).toBe(VIREMENT_MSG.otp);
  });

  it('le proxy de virement exige un jeton (aucun appel amont sinon)', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    const { status } = await callVirement({});
    expect(status).toBe(400);
    expect(fn).not.toHaveBeenCalled();
  });
});

// ── ADEV104 (C-L3-LIEN-10) — le reçu nomme deux empreintes : le défi lu ≠ le sceau stocké ──────
describe('ADEV104 — reçu de signature à deux empreintes', () => {
  const RECU = CONTRAT.reponse_200.recu as Record<string, string>;

  it('lit le reçu du contrat : défi lu, sceau stocké, PDF ; l’alias n’est qu’un repli', () => {
    expect(lireRecuAcceptation(RECU)).toEqual({
      signe_le: RECU.signe_le,
      empreinte_lue: RECU.empreinte_lue,
      empreinte_scellee: RECU.empreinte_scellee,
      empreinte_pdf: RECU.empreinte_pdf,
    });
    expect(RECU.empreinte_lue).not.toBe(RECU.empreinte_scellee);
    // Serveur d'avant ADEV104 : seule la clé `empreinte_contenu` (= le sceau) est servie.
    const ancien = lireRecuAcceptation({ signe_le: RECU.signe_le, empreinte_contenu: 'c'.repeat(64), empreinte_pdf: '' });
    expect(ancien).toMatchObject({ empreinte_lue: '', empreinte_scellee: 'c'.repeat(64) });
    expect(lireRecuAcceptation(null)).toBeUndefined();
  });

  it('le proxy relaie le reçu de la réponse 200 du contrat, jamais sur un refus', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(200, CONTRAT.reponse_200)));
    const ok = await call({ token: 'tok', nom: 'Karim Exemple', twoOptions: false });
    expect(ok.json.recu).toEqual(lireRecuAcceptation(RECU));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstream(409, { detail: 'Refus.', code: 'statut', recu: RECU })));
    const refus = await call({ token: 'tok', nom: 'Karim Exemple', twoOptions: false });
    expect(refus.json).not.toHaveProperty('recu');
  });
});

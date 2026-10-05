// AGW308 — options du kit à cocher sur /proposition : le client ajoute une option NOMMÉE à son
// devis avant de signer, avec confirmation (endpoint XSAL5 existant).
//
//  1. constructeur d'URL du proxy → `…/ventes/proposal/<token>/activer-option/` ;
//  2. fonction pure qui décide l'affichage : option servie + lien non interne + devis non figé ;
//  3. proxy same-origin : corps `{ligne_id}` transmis, statut renvoyé (200 / 403 / 404 / 409) ;
//  4. la page : confirmation (+ X TTC, « ne peut pas être retirée en ligne »), bouton inactif en
//     aperçu interne, rechargement des totaux servis (aucun total recalculé).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resetRateLimit } from '../src/lib/rateLimit';
import {
  buildOptionBody,
  confirmationOption,
  etatActivationOption,
  normalizeOptionResponse,
  OPTION_MSG,
  optionEndpoint,
  optionMessage,
} from '../src/lib/proposition';

vi.mock('cloudflare:workers', () => ({ env: {} }));

const lire = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('AGW308 — constructeur d’URL', () => {
  it('pointe la route XSAL5 montée sous ventes/ (défaut api.taqinor.ma)', () => {
    expect(optionEndpoint('', 'abc123')).toBe('https://api.taqinor.ma/api/django/ventes/proposal/abc123/activer-option/');
    expect(optionEndpoint('https://staging.example/', 'tok')).toBe('https://staging.example/api/django/ventes/proposal/tok/activer-option/');
  });
  it('encode le token (segment de chemin)', () => {
    expect(optionEndpoint('https://x.ma', 'a/b c')).toBe('https://x.ma/api/django/ventes/proposal/a%2Fb%20c/activer-option/');
  });
  it('le chemin existe côté backend (urls.py › activer-option)', () => {
    const urls = lire('../../../backend/django_core/apps/ventes/urls.py');
    expect(urls).toContain("path('proposal/<str:token>/activer-option/', proposal_activate_option");
  });
});

describe('AGW308 — la fonction pure qui décide l’affichage', () => {
  const vivante = { apercuInterne: false, offreVivante: true };
  it('option servie + lien non interne + devis non figé → actif', () => {
    expect(etatActivationOption({ ligneId: 90311, ...vivante })).toBe('actif');
  });
  it('aperçu interne → bouton INACTIF (R4), jamais masqué', () => {
    expect(etatActivationOption({ ligneId: 90311, apercuInterne: true, offreVivante: true })).toBe('apercu');
  });
  it('devis figé (signé, refusé, expiré, remplacé) → pas de bouton', () => {
    expect(etatActivationOption({ ligneId: 90311, apercuInterne: false, offreVivante: false })).toBe('masque');
    expect(etatActivationOption({ ligneId: 90311, apercuInterne: true, offreVivante: false })).toBe('masque');
  });
  it('option non servie (identifiant absent, nul, non entier) → pas de bouton', () => {
    for (const id of [null, undefined, 0, -3, 1.5, Number.NaN]) {
      expect(etatActivationOption({ ligneId: id as number | null | undefined, ...vivante }), String(id)).toBe('masque');
    }
  });
});

describe('AGW308 — corps et réponses', () => {
  it('buildOptionBody : entier > 0 seulement', () => {
    expect(buildOptionBody(90311)).toEqual({ ligne_id: 90311 });
    expect(buildOptionBody('42')).toEqual({ ligne_id: 42 });
    for (const bad of [0, -1, 1.5, 'abc', '', null, undefined, {}, [1]]) expect(buildOptionBody(bad), String(bad)).toBeNull();
  });
  it('normalizeOptionResponse : succès → ligneId + désignation ; échec → rien', () => {
    expect(normalizeOptionResponse(200, { detail: 'Option activée.', ligne_id: 7, designation: 'Afficheur' })).toEqual({
      ok: true, status: 200, detail: 'Option activée.', ligneId: 7, designation: 'Afficheur',
    });
    expect(normalizeOptionResponse(409, { detail: 'Devis figé.' })).toEqual({ ok: false, status: 409, detail: 'Devis figé.' });
    expect(normalizeOptionResponse(502, null)).toEqual({ ok: false, status: 502, detail: '' });
  });
  it('un 409 et un 404 donnent un message AMICAL en trois langues, jamais le détail technique', () => {
    expect(optionMessage(409, { detail: 'Traceback…' })).toEqual(OPTION_MSG.fige);
    expect(optionMessage(404)).toEqual(OPTION_MSG.introuvable);
    expect(optionMessage(403, { detail: 'otp_required' })).toEqual(OPTION_MSG.otp);
    expect(optionMessage(500)).toEqual(OPTION_MSG.generique);
    expect(optionMessage(200)).toEqual(OPTION_MSG.succes);
    for (const m of [OPTION_MSG.fige, OPTION_MSG.introuvable, OPTION_MSG.generique]) {
      expect(m.fr.length).toBeGreaterThan(10);
      expect(m.en.length).toBeGreaterThan(10);
      expect(m.ar.length).toBeGreaterThan(10);
      expect(m.fr).toContain('conseiller');
    }
  });
  it('la confirmation dit le supplément TTC et que l’option ne se retire pas en ligne', () => {
    const c = confirmationOption('Afficheur du variateur', '950 MAD');
    expect(c.fr).toContain('sera ajoutée à votre devis : + 950 MAD TTC');
    expect(c.fr).toContain('ne peut pas être retirée en ligne, contactez votre conseiller');
    expect(c.en).toContain('cannot be removed online');
    expect(c.ar).toContain('950 MAD');
    // sans supplément servi : jamais un montant inventé
    expect(confirmationOption('X', null).fr).not.toContain('TTC');
  });
});

function makeRequest(body: unknown, headers: Record<string, string> = {}): Request {
  return new Request('http://localhost/api/proposition-option', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'cf-connecting-ip': '9.9.9.9', ...headers },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}
async function call(body: unknown, headers?: Record<string, string>) {
  const { POST } = await import('../src/pages/api/proposition-option');
  const res = (await POST({ request: makeRequest(body, headers) } as unknown as Parameters<typeof POST>[0])) as Response;
  return { status: res.status, json: (await res.json().catch(() => null)) as Record<string, unknown> | null };
}

beforeEach(() => resetRateLimit());
afterEach(() => {
  resetRateLimit();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('POST /api/proposition-option — le proxy', () => {
  it('relaie { ligne_id } SEUL vers la route backend et renvoie le statut + l’objet normalisé', async () => {
    const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Option activée.', ligne_id: 90311, designation: 'Afficheur' }), { status: 200 }));
    vi.stubGlobal('fetch', fn);
    const { status, json } = await call({ token: 'tok-abc', ligne_id: 90311, extra: 'ignoré' });
    expect(status).toBe(200);
    expect(json).toMatchObject({ ok: true, status: 200, ligneId: 90311 });
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok-abc/activer-option/');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ ligne_id: 90311 });
  });

  it('reflète les statuts amont : 409 (devis figé), 404 (lien), 403 otp_required', async () => {
    for (const [amont, detail] of [[409, 'figé'], [404, 'Introuvable.'], [403, 'otp_required']] as const) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: amont })));
      const { status, json } = await call({ token: 't', ligne_id: 5 });
      expect(status).toBe(amont);
      expect(json!.ok).toBe(false);
      if (amont === 403) expect(json!.detail).toBe('otp_required');
    }
  });

  it('refuse un appel cross-site (403), un corps illisible, un token ou une option invalide — sans appel amont', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    expect((await call({ token: 't', ligne_id: 1 }, { 'sec-fetch-site': 'cross-site' })).status).toBe(403);
    expect((await call('pas du json')).status).toBe(400);
    expect((await call({ ligne_id: 1 })).status).toBe(400);
    expect((await call({ token: 't', ligne_id: 'x' })).status).toBe(400);
    expect((await call({ token: 't', ligne_id: -4 })).status).toBe(400);
    expect(fn).not.toHaveBeenCalled();
  });

  it('backend injoignable → 502 propre', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    const { status, json } = await call({ token: 't', ligne_id: 5 });
    expect(status).toBe(502);
    expect(json!.ok).toBe(false);
  });
});

describe('AGW308 — la page', () => {
  const page = lire('../src/pages/proposition/[...token].astro');
  const bloc = page.slice(page.indexOf('data-agri-options-kit'), page.indexOf('data-agri-non-inclus'));

  it('chaque option servie porte « Ajouter au devis », gaté par la fonction pure', () => {
    expect(bloc).toContain('etatActivationOption({ ligneId: o.ligneId, apercuInterne, offreVivante: offerState');
    expect(bloc).toContain("{etat !== 'masque' && (");
    expect(bloc).toContain('data-option-ajouter');
    expect(bloc).toContain("disabled={etat === 'apercu'}");
    expect(bloc).toContain('data-confirm-fr={conf.fr}');
  });

  it('une confirmation avant l’appel, annulable', () => {
    expect(bloc).toContain('id="agri-option-confirm"');
    expect(bloc).toContain('id="agri-option-confirm-ok"');
    expect(bloc).toContain('id="agri-option-confirm-annuler"');
  });

  it('le client appelle le proxy same-origin puis recharge — aucun total recalculé', () => {
    expect(page).toContain('fetch(OPTION_PROXY_PATH');
    expect(page).toContain('window.location.reload()');
    const script = page.slice(page.indexOf('AGW308 — OPTIONS DU KIT À COCHER'));
    expect(script).not.toMatch(/total_ttc\s*[+*]|\.reduce\(/);
    expect(script).not.toContain('/api/django/');
  });

  it('la page garde EXACTEMENT trois blocs <script> (garde perceivedPerfWJ34)', () => {
    expect(page.match(/^<script/gm)).toHaveLength(3);
  });

  it('aucune route de retrait n’est appelée (le backend n’en a pas)', () => {
    expect(page).not.toMatch(/retirer-option|desactiver-option|supprimer-option/);
  });
});

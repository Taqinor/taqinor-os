// PREVIEW-V3-FIX (16/09/2026, audit C5) — LE MOT « otp_required » NE S'AFFICHE
// PLUS EN FACE DU CLIENT.
//
// `ShareLink.otp_lecture` est un réglage PAR LIEN, actif en production : quand
// le commercial le pose, le GET SSR de la proposition (`proposal_data`) répond
// 403 `{"detail": "otp_required"}` et la page rendait ce littéral machine comme
// message d'erreur — le PREMIER écran du client. Le correctif de v3 ne couvrait
// que `/accept/`, c'est-à-dire un cas qui suppose le GET déjà passé.
//
// Trois gardes de SOURCE (un montage DOM complet d'un .astro n'est pas
// praticable ici — même convention que les autres modules de cette page) :
// la détection côté frontmatter, l'écran de saisie, et le champ que le proxy
// envoie au backend.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// ASEC53 — les proxys importent `cloudflare:workers` (cf.env) : module virtuel hors build.
vi.mock('cloudflare:workers', () => ({ env: {} }));

import { mapAcceptResponseToUiState, OTP_LECTURE_DETAIL } from '../src/lib/proposition';
import { lireReponseAccesPdf } from '../src/lib/propositionPdfSigne';
import { resetRateLimit } from '../src/lib/rateLimit';
import { COOKIE_PREUVE, EN_TETE_PREUVE, cookieDePreuve, entetePreuve } from '../src/pages/api/_apiBase';
import { POST as postOtp } from '../src/pages/api/proposition-otp';
import { POST as postAccept } from '../src/pages/api/proposition-accept';
import { POST as postOption } from '../src/pages/api/proposition-option';
import { POST as postContact } from '../src/pages/api/proposition-contact';
import { POST as postEngagement } from '../src/pages/api/proposition-engagement';
import { POST as postDecliner } from '../src/pages/api/proposition-decliner';
import { POST as postVirement } from '../src/pages/api/proposition-virement';
import { POST as postVu } from '../src/pages/api/proposition-vu';
import { GET as getTaille } from '../src/pages/api/proposition-taille';
import { GET as getPdf } from '../src/pages/api/proposition-pdf/[token]';
import { GET as getToiture } from '../src/pages/api/proposition-toiture/[token]';
import { relaisAfficheToiture, relaisPdfProposition } from '../src/pages/api/_apiBase';
import { lirePageProposition } from './astroBlocsHelper';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const PROPOSITION = lirePageProposition();
const PROXY = read('../src/pages/api/proposition-otp.ts');
// Formulaire et logique client PARTAGÉS avec /suivi (garde ACAL345).
const OTP_FORM = read('../src/components/OtpLectureForm.astro');
const OTP_LIB = read('../src/lib/otpLecture.ts');

describe('audit C5 — l’OTP de LECTURE a enfin son écran', () => {
  it('le 403 de la lecture est reconnu, pas recopié', () => {
    expect(OTP_LECTURE_DETAIL).toBe('otp_required');
    expect(PROPOSITION).toContain(
      "otpLectureRequis = res.status === 403 && detail.trim() === OTP_LECTURE_DETAIL;",
    );
    // Le littéral machine n’est jamais ce que le client lit.
    expect(PROPOSITION).toContain('Cette proposition est protégée par un code à usage unique.');
  });

  it('un écran de saisie remplace le message d’erreur générique', () => {
    const ecran = PROPOSITION.indexOf('{!ok && otpLectureRequis ? (');
    const erreur = PROPOSITION.indexOf('État « lien expiré / introuvable »');
    expect(ecran).toBeGreaterThan(0);
    expect(erreur).toBeGreaterThan(ecran);
    expect(PROPOSITION).toContain('id="otp-lecture"');
    expect(PROPOSITION).toContain('<OtpLectureForm valider="Ouvrir ma proposition" />');
    for (const hook of ['id="otp-lecture-form"',
      'id="otp-lecture-demander"', 'id="otp-lecture-code"',
      'id="otp-lecture-valider"', 'id="otp-lecture-message"']) {
      expect(OTP_FORM, `hook manquant : ${hook}`).toContain(hook);
    }
    // Le code est saisi puis la MÊME url est rechargée : le serveur a
    // déverrouillé la lecture de ce lien, rien ne voyage dans l'URL.
    expect(PROPOSITION).toContain("brancherOtpLecture('votre proposition');");
    expect(OTP_LIB).toContain('window.location.reload();');
    expect(OTP_LIB).toContain("mode: 'lecture'");
  });

  it('le proxy envoie `otp_code`, le champ que le backend lit VRAIMENT', () => {
    // `proposal_verify_otp_lecture` lit `_texte_du_corps(request, 'otp_code')` :
    // un corps `{code: …}` était lu comme un code VIDE, et la vérification
    // n'aurait jamais pu aboutir.
    expect(PROXY).toContain("{ otp_code: code }");
    expect(PROXY).not.toMatch(/JSON\.stringify\(mode === 'lecture' && code \? \{ code \}/);
  });

  it('la fonction pure d’acceptation garde son verdict (aucune régression)', () => {
    expect(mapAcceptResponseToUiState(403, 'otp_required')).toEqual({ kind: 'otp-lecture' });
    expect(mapAcceptResponseToUiState(200)).toEqual({ kind: 'ok' });
  });
});

describe('ADEV97 — l’exemplaire SIGNÉ se télécharge avec le code de lecture', () => {
  it('« aucun code requis » (`code_requis: false`) ouvre le PDF ; sinon un code est demandé', () => {
    expect(lireReponseAccesPdf(200, { ok: true, detail: 'Aucun code requis pour ce lien.', code_requis: false })).toEqual({
      ok: true,
      codeRequis: false,
      detail: 'Aucun code requis pour ce lien.',
    });
    expect(lireReponseAccesPdf(200, { ok: true, detail: 'Code envoyé.' }).codeRequis).toBe(true);
    expect(lireReponseAccesPdf(400, { ok: false, detail: 'Code incorrect.' }).ok).toBe(false);
  });

  it('le proxy relaie `code_requis: false` ; la page installe la garde sur le flux `/pdf/`', () => {
    expect(PROXY).toContain('payload.code_requis === false ? { code_requis: false } : {}');
    expect(PROPOSITION).toContain('installerGardePdfSigne({');
    expect(PROPOSITION).toContain('id="pdf-otp-block"');
    expect(PROPOSITION).toContain('estAccepte: () => cfg.accepted || propositionAcceptee');
  });
});

// CPRW27 (28/10/2026) — le texte FR du serveur n'est montré qu'en français.
describe('CPRW27 — propositionPdfSigne : `detail` serveur seulement en FR', () => {
  it('le gestionnaire ne montre r.detail que si la langue courante est fr', () => {
    const src = read('../src/lib/propositionPdfSigne.ts');
    expect(src).toContain("(g.langue() === 'fr' && r.detail) || MSG.erreur[g.langue()]");
    expect(src).not.toMatch(/: r\.detail \|\| MSG\.erreur/);
  });
});

// ── ASEC53 (C-ASEC-025, D-ASEC-3) — la preuve de lecture vaut pour CE navigateur ──
//
// Moitié web du contrat ASEC1, CHARGÉ depuis le fichier partagé du backend (jamais un mock écrit
// à la main) : le proxy OTP pose le cookie httpOnly `tq_prop_preuve` et ne renvoie jamais la
// preuve au JavaScript de la page ; le SSR et chaque proxy vers l'ERP la relaient en en-tête.
// Test-du-test : retirer `...entetePreuve(request)` de `proposition-accept.ts` ⇒ « accept » rougit.
const CONTRAT = JSON.parse(
  read('../../../backend/django_core/apps/ventes/contract_samples/proposition_otp_preuve.json'),
) as {
  regles: { cookie: string; en_tete: string };
  exemple: { detail: string; verifie: boolean; preuve: string; expire_dans: number };
  exemple_refus_sans_preuve: { detail: string };
};
const PREUVE = CONTRAT.exemple.preuve;

type Handler = (ctx: { request: Request }) => Response | Promise<Response>;
const appeler = (h: unknown, request: Request) => (h as Handler)({ request });

function requete(chemin: string, corps: unknown, cookie = `${COOKIE_PREUVE}=${PREUVE}`): Request {
  return new Request(`http://localhost${chemin}`, {
    method: corps === undefined ? 'GET' : 'POST',
    headers: { 'content-type': 'application/json', ...(cookie ? { cookie } : {}) },
    ...(corps === undefined ? {} : { body: JSON.stringify(corps) }),
  });
}

function amont(status: number, payload: unknown) {
  return { status, ok: status >= 200 && status < 300, json: async () => payload } as unknown as Response;
}

function entetesAmont(fn: ReturnType<typeof vi.fn>): Record<string, string> {
  expect(fn).toHaveBeenCalledTimes(1);
  const [, init] = fn.mock.calls[0] as [string, RequestInit];
  return (init.headers ?? {}) as Record<string, string>;
}

describe('ASEC53 — le contrat ASEC1 et le socle', () => {
  beforeEach(() => resetRateLimit());
  afterEach(() => vi.unstubAllGlobals());

  it('nom du cookie et en-tête = ceux du contrat', () => {
    expect(CONTRAT.regles.cookie).toContain(`${COOKIE_PREUVE}=<preuve>`);
    expect(CONTRAT.regles.en_tete).toContain(`${EN_TETE_PREUVE}: <preuve>`);
  });

  it('Set-Cookie httpOnly/Secure/Lax, Max-Age = expire_dans ; rien sans `verifie`', () => {
    expect(cookieDePreuve(CONTRAT.exemple)).toBe(
      `${COOKIE_PREUVE}=${PREUVE}; Max-Age=${CONTRAT.exemple.expire_dans}; Path=/; HttpOnly; Secure; SameSite=Lax`,
    );
    expect(cookieDePreuve({ detail: 'Code vérifié.' })).toBeNull();
    expect(cookieDePreuve({ ...CONTRAT.exemple, verifie: false })).toBeNull();
    expect(cookieDePreuve({ ...CONTRAT.exemple, preuve: 'a;b=c' })).toBeNull();
  });

  it('un cookie mal formé ou absent n’est jamais relayé', () => {
    expect(entetePreuve(`${COOKIE_PREUVE}=${PREUVE}; tq_equipe=1`)).toEqual({ [EN_TETE_PREUVE]: PREUVE });
    expect(entetePreuve('tq_equipe=1')).toEqual({});
    expect(entetePreuve(`${COOKIE_PREUVE}=a%0d%0aX-Injecte: 1`)).toEqual({});
    expect(entetePreuve(null)).toEqual({});
  });

  it('le proxy OTP pose le cookie à la vérification, et la preuve n’est PAS dans le corps', async () => {
    const fn = vi.fn().mockResolvedValue(amont(200, CONTRAT.exemple));
    vi.stubGlobal('fetch', fn);
    const res = await appeler(postOtp, requete('/api/proposition-otp', { token: 'tok', mode: 'lecture', code: '123456' }, ''));
    expect(res.status).toBe(200);
    expect(res.headers.get('set-cookie')).toBe(cookieDePreuve(CONTRAT.exemple));
    const texte = await res.text();
    expect(texte).not.toContain(PREUVE);
    expect(JSON.parse(texte)).toEqual({ ok: true, detail: CONTRAT.exemple.detail });
  });

  it('aucun cookie posé sur un code refusé, une demande, ou le mode e-signature', async () => {
    for (const [corps, reponse] of [
      [{ token: 'tok', mode: 'lecture', code: '000000' }, amont(400, { detail: 'Code incorrect.' })],
      [{ token: 'tok', mode: 'lecture' }, amont(200, CONTRAT.exemple)],
      [{ token: 'tok' }, amont(200, CONTRAT.exemple)],
    ] as const) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reponse));
      const res = await appeler(postOtp, requete('/api/proposition-otp', corps, ''));
      expect(res.headers.get('set-cookie')).toBeNull();
    }
  });
});

describe('ASEC53 — chaque relais vers l’ERP porte la preuve de CE navigateur', () => {
  beforeEach(() => resetRateLimit());
  afterEach(() => vi.unstubAllGlobals());

  const relais: Array<[string, unknown, Request]> = [
    ['accept', postAccept, requete('/api/proposition-accept', { token: 'tok', nom: 'Reda', twoOptions: false })],
    ['option', postOption, requete('/api/proposition-option', { token: 'tok', ligne_id: 3 })],
    ['contact', postContact, requete('/api/proposition-contact', { token: 'tok', channel: 'rappel' })],
    ['engagement', postEngagement, requete('/api/proposition-engagement', { token: 'tok', section: 'prix', seconds: 5 })],
    ['decliner', postDecliner, requete('/api/proposition-decliner', { token: 'tok', motif: 'prix' })],
    ['virement', postVirement, requete('/api/proposition-virement', { token: 'tok' })],
    ['vu', postVu, requete('/api/proposition-vu', { token: 'tok' })],
    ['taille', getTaille, requete('/api/proposition-taille?token=tok&cle=eco&variante=sans', undefined)],
    ['otp (demander)', postOtp, requete('/api/proposition-otp', { token: 'tok', mode: 'lecture' })],
  ];

  for (const [nom, handler, req] of relais) {
    it(`${nom} relaie X-Proposition-Preuve depuis le cookie httpOnly`, async () => {
      const fn = vi.fn().mockResolvedValue(amont(200, { detail: 'ok' }));
      vi.stubGlobal('fetch', fn);
      await appeler(handler, req.clone());
      expect(entetesAmont(fn)[EN_TETE_PREUVE]).toBe(PREUVE);
    });
  }

  it('sans cookie (second navigateur) : aucun en-tête, et le 403 `otp_required` reste lisible', async () => {
    const fn = vi.fn().mockResolvedValue(amont(403, CONTRAT.exemple_refus_sans_preuve));
    vi.stubGlobal('fetch', fn);
    const res = await appeler(postOption, requete('/api/proposition-option', { token: 'tok', ligne_id: 3 }, ''));
    expect(entetesAmont(fn)[EN_TETE_PREUVE]).toBeUndefined();
    expect(res.status).toBe(403);
    expect(((await res.json()) as { detail: string }).detail).toBe(OTP_LECTURE_DETAIL);
  });

  it('le SSR de /proposition et de /suivi relaie la preuve (même patron que tq_appareil)', () => {
    expect(PROPOSITION).toContain('...entetePreuve(Astro.request),');
    expect(read('../src/pages/suivi/[token].astro')).toContain("...entetePreuve(Astro.request) }");
  });

  it('la télémétrie WJ55 (webhook externe) ne reçoit JAMAIS la preuve', () => {
    expect(read('../src/pages/api/proposition-track.ts')).not.toContain('entetePreuve');
  });
});

// ── ASEC53 / D-ASEC-53-RELAIS (29/10/2026) — PDF, exemplaire signé et affiche de toiture ──
//
// L'ERP ne voit pas le cookie du site : la page pointe ces trois flux sur des relais
// same-origin qui transmettent la preuve et renvoient le binaire tel quel. L'exemplaire signé
// est le même `/pdf/` côté ERP (QJR670) : le relais PDF le couvre.
describe('ASEC53 — relais binaires same-origin (PDF / exemplaire signé / toiture)', () => {
  beforeEach(() => resetRateLimit());
  afterEach(() => vi.unstubAllGlobals());

  type GetParams = (ctx: { request: Request; params: Record<string, string> }) => Promise<Response>;
  const get = (h: unknown, chemin: string, token: string, cookie = `${COOKIE_PREUVE}=${PREUVE}`) =>
    (h as GetParams)({ request: requete(chemin, undefined, cookie), params: { token } });
  const OCTETS = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x00, 0xff, 0x0a]); // %PDF- + binaire
  const binaire = (status: number, entetes: Record<string, string>) =>
    vi.fn().mockResolvedValue(new Response(OCTETS, { status, headers: entetes }));

  it('PDF : preuve relayée, octets / content-type / content-disposition inchangés, cache privé', async () => {
    const fn = binaire(200, { 'content-type': 'application/pdf', 'content-disposition': 'inline; filename="Devis_DV-1.pdf"' });
    vi.stubGlobal('fetch', fn);
    const res = await get(getPdf, '/api/proposition-pdf/tok?variante=avec', 'tok');
    const [url] = fn.mock.calls[0] as [string];
    expect(url).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok/pdf/?variante=avec');
    expect(entetesAmont(fn)[EN_TETE_PREUVE]).toBe(PREUVE);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('application/pdf');
    expect(res.headers.get('content-disposition')).toBe('inline; filename="Devis_DV-1.pdf"');
    expect(res.headers.get('cache-control')).toBe('private, no-store');
    expect(new Uint8Array(await res.arrayBuffer())).toEqual(OCTETS);
    expect([...res.headers.values()].join(' ')).not.toContain(PREUVE);
  });

  it('PDF : variante hors liste blanche jamais relayée', async () => {
    const fn = binaire(200, { 'content-type': 'application/pdf' });
    vi.stubGlobal('fetch', fn);
    await get(getPdf, '/api/proposition-pdf/tok?variante=x%26y', 'tok');
    expect((fn.mock.calls[0] as [string])[0]).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok/pdf/');
  });

  it('toiture : preuve relayée, image inchangée, cache privé amont conservé', async () => {
    const fn = binaire(200, { 'content-type': 'image/png', 'cache-control': 'private, max-age=300' });
    vi.stubGlobal('fetch', fn);
    const res = await get(getToiture, '/api/proposition-toiture/tok', 'tok');
    expect((fn.mock.calls[0] as [string])[0]).toBe('https://api.taqinor.ma/api/django/ventes/proposal/tok/roof-image/');
    expect(entetesAmont(fn)[EN_TETE_PREUVE]).toBe(PREUVE);
    // Rejeu en direct 29/10 : un `image/*` seul vaut 406 côté DRF (rendus JSON) — `*/*` en repli.
    expect(entetesAmont(fn).accept).toContain('*/*');
    expect(res.headers.get('content-type')).toBe('image/png');
    expect(res.headers.get('cache-control')).toBe('private, max-age=300');
    expect(new Uint8Array(await res.arrayBuffer())).toEqual(OCTETS);
  });

  it('sans cookie (second navigateur) : aucun en-tête, le 403 de l’ERP est relayé tel quel', async () => {
    for (const [h, chemin] of [[getPdf, '/api/proposition-pdf/tok'], [getToiture, '/api/proposition-toiture/tok']] as const) {
      const fn = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(CONTRAT.exemple_refus_sans_preuve), { status: 403, headers: { 'content-type': 'application/json' } }),
      );
      vi.stubGlobal('fetch', fn);
      const res = await get(h, chemin, 'tok', '');
      expect(entetesAmont(fn)[EN_TETE_PREUVE]).toBeUndefined();
      expect(res.status).toBe(403);
      expect(await res.json()).toEqual(CONTRAT.exemple_refus_sans_preuve);
    }
  });

  it('ERP injoignable → 502 JSON, jamais un faux succès', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    expect((await get(getPdf, '/api/proposition-pdf/tok', 'tok')).status).toBe(502);
    expect((await get(getToiture, '/api/proposition-toiture/tok', 'tok')).status).toBe(502);
  });

  it('la page pointe PDF, exemplaire signé et affiche sur les relais (jamais sur api.taqinor.ma)', () => {
    expect(relaisPdfProposition('a b')).toBe('/api/proposition-pdf/a%20b');
    expect(relaisAfficheToiture('a b')).toBe('/api/proposition-toiture/a%20b');
    expect(PROPOSITION).toContain("const pdfUrl = ok ? relaisPdfProposition(token) : '';");
    expect(PROPOSITION).toContain('? relaisAfficheToiture(token) : null;');
    // Le garde ADEV97 compare un href ABSOLU au relais RELATIF résolu sur la page.
    expect(read('../src/lib/propositionPdfSigne.ts')).toContain('new URL(g.pdfUrl, window.location.href).href');
  });
});

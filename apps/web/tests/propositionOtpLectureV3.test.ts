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
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { mapAcceptResponseToUiState, OTP_LECTURE_DETAIL } from '../src/lib/proposition';
import { lireReponseAccesPdf } from '../src/lib/propositionPdfSigne';
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

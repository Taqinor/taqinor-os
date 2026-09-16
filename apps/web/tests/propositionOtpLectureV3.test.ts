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

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[...token].astro');
const PROXY = read('../src/pages/api/proposition-otp.ts');

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
    for (const hook of ['id="otp-lecture"', 'id="otp-lecture-form"',
      'id="otp-lecture-demander"', 'id="otp-lecture-code"',
      'id="otp-lecture-valider"', 'id="otp-lecture-message"']) {
      expect(PROPOSITION, `hook manquant : ${hook}`).toContain(hook);
    }
    // Le code est saisi puis la MÊME url est rechargée : le serveur a
    // déverrouillé la lecture de ce lien, rien ne voyage dans l'URL.
    expect(PROPOSITION).toContain('window.location.reload();');
    expect(PROPOSITION).toContain("mode: 'lecture'");
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

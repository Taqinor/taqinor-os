/**
 * POST /api/proposition-otp — proxy SAME-ORIGIN des codes OTP de la page de
 * proposition : e-signature (WJ108) et, depuis PREVIEW-V3, LECTURE.
 *
 * Le navigateur du client n'appelle JAMAIS le backend en cross-origin : il
 * poste ici { token } et ce handler relaie côté serveur vers
 * `{API_BASE}/api/django/ventes/proposal/<token>/otp/` (endpoint public/token,
 * sans login — `apps/ventes/public_urls.py public-proposal-otp`) — SYMÉTRIQUE
 * de /api/proposition-accept (même résolution d'API_BASE).
 *
 * Le backend est déjà construit (`apps/ventes/services.py request_esign_otp`,
 * toggle `ESIGN_OTP_ENABLED`) : quand le toggle est OFF (par défaut), l'appel
 * répond succès immédiatement sans rien envoyer (no-op, comportement
 * inchangé). Quand ON, un code à 6 chiffres est envoyé au contact du devis
 * (WhatsApp ou e-mail) et stocké 10 min côté serveur.
 *
 * WJ108 — ce proxy n'est appelé par le client QUE lorsque la page a déjà
 * détecté un besoin d'OTP (réponse d'acceptation reconnue par
 * `isOtpRequiredDetail`, lib/proposition.ts) — jamais de manière proactive :
 * tant que le toggle backend reste OFF, ce chemin entier reste inerte et
 * invisible pour le visiteur.
 *
 * W316 — bucket de rate-limit DÉDIÉ (distinct d'accept/track/contact/roof-*) :
 * généreux mais borné (un client qui redemande un code plusieurs fois ne doit
 * jamais être bloqué, un bot qui martèle l'endpoint doit l'être).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { otpLectureEndpoint, otpRequestEndpoint } from '../../lib/proposition';
import { appelAmontJson, preludeJeton } from '../../lib/apiPreludeJeton';
import { jsonResponse as json } from '../../lib/apiJson';
import { cookieDePreuve, entetesJsonPreuve, resolveApiBase } from './_apiBase';

export const POST: APIRoute = async ({ request }) => {
  // W317 — Origin/Sec-Fetch-Site : refuse un POST cross-site forgé avant tout
  // traitement (même garde-fou que les autres proxies same-origin).
  const pre = await preludeJeton(request, { scope: 'proposition-otp', limit: 10, jetonManquant: 'Lien de proposition manquant.' });
  if ('response' in pre) return pre.response;
  const { body, token } = pre;

  // PREVIEW-V3 (16/09/2026) — DEUXIÈME MODE : l'OTP de LECTURE.
  //
  // `ShareLink.otp_lecture` est un réglage PAR LIEN, actif en production :
  // quand le commercial le pose, /accept/ répond 403 `otp_required` et la page
  // n'avait AUCUN moyen de satisfaire ce gate — elle affichait le littéral
  // machine au client. Ce proxy relaie donc aussi les deux endpoints de ce
  // mécanisme : `demander` (sans code) puis `verifier` (avec code), qui
  // déverrouille la lecture pour une heure — ASEC53 : pour CE navigateur seul
  // (preuve en cookie httpOnly), jamais pour le lien entier.
  //
  // `mode` ABSENT ⇒ 'esign' ⇒ comportement d'hier, octet pour octet.
  const mode = body.mode === 'lecture' ? 'lecture' : 'esign';
  const code = typeof body.code === 'string' ? body.code.trim() : '';

  const url = mode === 'lecture'
    ? otpLectureEndpoint(resolveApiBase(), token, code ? 'verifier' : 'demander')
    : otpRequestEndpoint(resolveApiBase(), token);

  const amont = await appelAmontJson(url, {
    method: 'POST',
    // ASEC53 — en mode lecture, la preuve de CE navigateur (cookie httpOnly) : un navigateur
    // déjà vérifié reçoit « aucun code requis » (ADEV97) au lieu d'un second code.
    headers: entetesJsonPreuve(mode === 'lecture' ? request : null),
    // PREVIEW-V3-FIX (16/09/2026, audit C5) — LE CHAMP S'APPELLE `otp_code`.
    // `proposal_verify_otp_lecture` lit son corps avec
    // `_texte_du_corps(request, 'otp_code')` : un corps `{code: "123456"}`
    // était donc lu comme un code VIDE, et l'endpoint répondait « le code a
    // expiré ou n'a pas été demandé » quel que soit le code saisi — le
    // chemin de vérification n'aurait jamais pu aboutir.
    body: JSON.stringify(mode === 'lecture' && code ? { otp_code: code } : {}),
  });
  if (!amont) {
    // Backend injoignable : erreur réseau propre, sans détail PII.
    return json({ ok: false, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
  }
  const { status: upstreamStatus, payload: upstreamPayload } = amont;

  const payload = (upstreamPayload ?? {}) as Record<string, unknown>;
  const detail = typeof payload.detail === 'string' ? payload.detail : '';
  const ok = upstreamStatus >= 200 && upstreamStatus < 300;
  // ASEC53 (contrat ASEC1) — vérification de LECTURE réussie : la preuve opaque rendue par l'ERP
  // devient le cookie httpOnly `tq_prop_preuve` de CE navigateur. Elle ne figure JAMAIS dans le
  // corps renvoyé ci-dessous (construit champ par champ), ni dans une URL, ni dans un journal.
  const setCookie = ok && mode === 'lecture' && code ? cookieDePreuve(payload) : null;
  // ADEV97 — `code_requis: false` (aucun code de lecture sur ce lien) relayé tel quel : au clic
  // « Télécharger », la page sait si l'exemplaire signé exige un code avant de l'ouvrir.
  return json(
    {
      ok,
      detail: detail || (ok ? 'Code envoyé.' : 'Une erreur est survenue. Veuillez réessayer.'),
      ...(payload.code_requis === false ? { code_requis: false } : {}),
    },
    upstreamStatus >= 200 && upstreamStatus < 600 ? upstreamStatus : 502,
    setCookie ? { 'set-cookie': setCookie } : {},
  );
};

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
import * as cf from 'cloudflare:workers';
import { otpLectureEndpoint, otpRequestEndpoint } from '../../lib/proposition';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  });
}

function resolveApiBase(): string {
  const env = (cf.env ?? {}) as { PUBLIC_API_BASE?: string };
  const runtime = env.PUBLIC_API_BASE?.trim();
  const build = (import.meta.env.PUBLIC_API_BASE as string | undefined)?.trim();
  return runtime || build || 'https://api.taqinor.ma';
}

export const POST: APIRoute = async ({ request }) => {
  // W317 — Origin/Sec-Fetch-Site : refuse un POST cross-site forgé avant tout
  // traitement (même garde-fou que les autres proxies same-origin).
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const rl = rateLimit(`proposition-otp:${clientIpFromRequest(request)}`, { limit: 10, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false, detail: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, detail: 'Requête invalide.' }, 400);
  }

  const token = typeof body.token === 'string' ? body.token.trim() : '';
  if (!token) return json({ ok: false, detail: 'Lien de proposition manquant.' }, 400);

  // PREVIEW-V3 (16/09/2026) — DEUXIÈME MODE : l'OTP de LECTURE.
  //
  // `ShareLink.otp_lecture` est un réglage PAR LIEN, actif en production :
  // quand le commercial le pose, /accept/ répond 403 `otp_required` et la page
  // n'avait AUCUN moyen de satisfaire ce gate — elle affichait le littéral
  // machine au client. Ce proxy relaie donc aussi les deux endpoints de ce
  // mécanisme : `demander` (sans code) puis `verifier` (avec code), qui
  // déverrouille le lien côté serveur pour une heure.
  //
  // `mode` ABSENT ⇒ 'esign' ⇒ comportement d'hier, octet pour octet.
  const mode = body.mode === 'lecture' ? 'lecture' : 'esign';
  const code = typeof body.code === 'string' ? body.code.trim() : '';

  const url = mode === 'lecture'
    ? otpLectureEndpoint(resolveApiBase(), token, code ? 'verifier' : 'demander')
    : otpRequestEndpoint(resolveApiBase(), token);

  let upstreamStatus = 502;
  let upstreamPayload: unknown = null;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      // PREVIEW-V3-FIX (16/09/2026, audit C5) — LE CHAMP S'APPELLE `otp_code`.
      // `proposal_verify_otp_lecture` lit son corps avec
      // `_texte_du_corps(request, 'otp_code')` : un corps `{code: "123456"}`
      // était donc lu comme un code VIDE, et l'endpoint répondait « le code a
      // expiré ou n'a pas été demandé » quel que soit le code saisi — le
      // chemin de vérification n'aurait jamais pu aboutir.
      body: JSON.stringify(mode === 'lecture' && code ? { otp_code: code } : {}),
    });
    upstreamStatus = res.status;
    try {
      upstreamPayload = await res.json();
    } catch {
      upstreamPayload = null;
    }
  } catch {
    // Backend injoignable : erreur réseau propre, sans détail PII.
    return json({ ok: false, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
  }

  const payload = (upstreamPayload ?? {}) as Record<string, unknown>;
  const detail = typeof payload.detail === 'string' ? payload.detail : '';
  const ok = upstreamStatus >= 200 && upstreamStatus < 300;
  return json(
    { ok, detail: detail || (ok ? 'Code envoyé.' : 'Une erreur est survenue. Veuillez réessayer.') },
    upstreamStatus >= 200 && upstreamStatus < 600 ? upstreamStatus : 502,
  );
};

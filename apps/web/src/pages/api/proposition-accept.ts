/**
 * POST /api/proposition-accept — proxy SAME-ORIGIN de la signature en ligne (W117).
 *
 * Le navigateur du client n'appelle JAMAIS le backend en cross-origin : il poste
 * ici { token, nom, option? } et ce handler relaie côté serveur vers
 * `{API_BASE}/api/django/ventes/proposal/<token>/accept/` (endpoint public/token,
 * sans login), puis renvoie le statut + le JSON tels quels au navigateur.
 *
 * API_BASE = PUBLIC_API_BASE (runtime cf.env OU build import.meta.env) sinon
 * https://api.taqinor.ma. Le backend est idempotent (un second envoi sur un devis
 * déjà accepté → 409) : on se contente de refléter sa réponse, ce qui rend le
 * double-clic sûr. Aucune donnée de lead, aucun prix d'achat n'est manipulé ici.
 *
 * W316 — bucket de rate-limit DÉDIÉ (distinct de proposition-contact/track) :
 * c'est le chemin d'e-signature, le plus sensible des cinq endpoints protégés
 * ici. Généreux malgré tout (un double-clic, ou un couple qui corrige son nom
 * juste avant de signer, ne doivent jamais être bloqués).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import {
  acceptEndpoint,
  buildAcceptBodyRich,
  normalizeAcceptResponse,
  type OptionKey,
  type SignFormState,
} from '../../lib/proposition';
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
  const rl = rateLimit(`proposition-accept:${clientIpFromRequest(request)}`, { limit: 10, windowMs: 60_000 });
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

  const optRaw = body.option;
  const option: OptionKey | null =
    optRaw === 'sans_batterie' || optRaw === 'avec_batterie' ? optRaw : null;
  const form: SignFormState = {
    nom: typeof body.nom === 'string' ? body.nom : '',
    option,
  };

  // `twoOptions` est transmis par le client (il connaît l'état rendu de la page).
  // Quand il est vrai, l'option est incluse dans le corps relayé au backend.
  const twoOptions = body.twoOptions === true || body.twoOptions === 'true';

  // WJ11 — champs e-signature OPTIONNELS, relayés tels quels et IGNORABLES par
  // un backend non mis à jour (le contrat de base nom/option reste intact). On
  // borne la taille du data URL pour éviter d'inonder l'upstream.
  const signatureRaw = typeof body.signature_data_url === 'string' ? body.signature_data_url : '';
  const signature_data_url =
    signatureRaw.startsWith('data:image/') && signatureRaw.length <= 300_000 ? signatureRaw : '';
  const consent_esign = body.consent_esign === true || body.consent_esign === 'true';
  const signed_at_client = typeof body.signed_at_client === 'string' ? body.signed_at_client : '';

  const upstreamBody = buildAcceptBodyRich(form, twoOptions, {
    signature_data_url,
    consent_esign,
    signed_at_client,
  });

  const url = acceptEndpoint(resolveApiBase(), token);

  let upstreamStatus = 502;
  let upstreamPayload: unknown = null;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify(upstreamBody),
    });
    upstreamStatus = res.status;
    try {
      upstreamPayload = await res.json();
    } catch {
      upstreamPayload = null;
    }
  } catch {
    // Backend injoignable : on renvoie une erreur réseau propre, sans détail PII.
    return json({ ok: false, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
  }

  const result = normalizeAcceptResponse(upstreamStatus, upstreamPayload);
  // On relaie le statut backend (200 / 400 / 409 / 404) et l'objet normalisé,
  // ce qui permet au client d'afficher le message `detail` exact inline.
  return json(result, upstreamStatus >= 200 && upstreamStatus < 600 ? upstreamStatus : 502);
};

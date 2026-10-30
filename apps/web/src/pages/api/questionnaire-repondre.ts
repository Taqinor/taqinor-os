/**
 * POST /api/questionnaire-repondre — proxy SAME-ORIGIN des réponses du
 * questionnaire client (lane Q, recalage orchestrateur 25/08).
 *
 * La page /questionnaire/[token] enregistre SECTION PAR SECTION (le client
 * reprend où il s'est arrêté). Le navigateur poste { token, section,
 * reponses, photo? } ICI, et le proxy relaie côté serveur vers
 * `{API_BASE}/api/django/crm/public/questionnaire/<token>/` — MÊME patron que
 * /api/proposition-contact : le backend n'est jamais exposé au navigateur,
 * aucun CORS n'est ouvert, l'IP cliente reste côté Cloudflare.
 *
 * Contrairement au proxy contact (« mieux si possible »), la RÉUSSITE compte
 * ici : la page marque la section « répondue » seulement sur { ok:true } — on
 * relaie donc fidèlement le { ok, enregistrees } du backend en 200, et tout
 * échec (token invalide/expiré → 404 générique amont, 5xx, réseau) redescend
 * en { ok:false, detail } SOBRE — jamais un détail technique, jamais un faux
 * succès.
 *
 * Bucket de rate-limit DÉDIÉ (les sections photo portent du base64 ~Mo) :
 * 30 requêtes/min/IP — au-dessus du parcours réel (9 sections + reprises),
 * en dessous d'un abus.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { questionnaireEndpoint } from '../../lib/questionnaire';
import { preludeJeton } from '../../lib/apiPreludeJeton';
import { jsonResponse as json } from '../../lib/apiJson';
import { resolveApiBase } from './_apiBase';

const DETAIL_EXPIRE = 'Ce lien a expiré — demandez-en un nouveau à votre conseiller.';
const DETAIL_ECHEC = 'Cette réponse n’a pas pu être enregistrée. Réessayez dans un instant.';

export const POST: APIRoute = async ({ request }) => {
  const pre = await preludeJeton(request, { scope: 'questionnaire-repondre', limit: 30, jetonManquant: 'Lien de questionnaire manquant.' });
  if ('response' in pre) return pre.response;
  const { body, token } = pre;

  // Le corps amont est celui du contrat (section/reponses/photo) — le token
  // voyage dans l'URL amont, jamais dupliqué dans le corps relayé.
  const { token: _t, ...upstreamBody } = body;

  try {
    const res = await fetch(questionnaireEndpoint(resolveApiBase(), token), {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify(upstreamBody),
    });
    let upstream: unknown = null;
    try {
      upstream = await res.json();
    } catch {
      upstream = null;
    }
    if (res.ok && upstream && typeof upstream === 'object') {
      // Relais fidèle du { ok, enregistrees } backend — la page s'appuie dessus.
      return json(upstream, 200);
    }
    // CQSTW5 — 404 amont = lien introuvable ou expiré : marqueur distinct, la page
    // dit « demandez-en un nouveau » au lieu d'un « réessayez » qui ne servirait à rien.
    if (res.status === 404) return json({ ok: false, code: 'expire', detail: DETAIL_EXPIRE }, 200);
    return json({ ok: false, code: 'echec', detail: DETAIL_ECHEC }, 200);
  } catch {
    return json({ ok: false, code: 'reseau', detail: 'Connexion impossible. Vérifiez votre réseau et réessayez.' }, 200);
  }
};

/**
 * Google Ads / Google tag (gtag.js) — lecture PURE de la configuration
 * d'environnement, partagée par `components/GoogleTag.astro` et ses tests.
 *
 * Deux variables PUBLIC_ (inlinées au build par Vite ; posées par Reda dans le
 * tableau de bord Cloudflare Workers Builds, JAMAIS écrites dans le code) :
 *  - PUBLIC_GOOGLE_TAG_ID : un ou plusieurs ID séparés par des virgules
 *    (`AW-…` Google Ads et/ou `G-…` GA4). Vide/absente ⇒ aucun tag chargé.
 *  - PUBLIC_GOOGLE_ADS_LEAD_SEND_TO : l'action de conversion « Lead »
 *    (`AW-XXXXXXXXX/libellé`). Absente ⇒ seul l'événement GA4
 *    `generate_lead` part.
 *
 * Ces ID ne sont pas des secrets (visibles dans toute page qui les embarque).
 */

/** Forme d'un ID de Google tag accepté : AW-…, G-…, GT-… (lettres/chiffres). */
const TAG_ID_RE = /^(AW|G|GT|DC)-[A-Za-z0-9]+$/;

/** Forme d'un `send_to` de conversion Google Ads : `AW-123/libellé`. */
const SEND_TO_RE = /^AW-[0-9]+\/[A-Za-z0-9_-]+$/;

/**
 * Liste des ID de Google tag valides, dédoublonnés, dans l'ordre fourni.
 * Tout fragment malformé est écarté (jamais injecté dans la page).
 */
export function parseGoogleTagIds(raw: string | undefined | null): string[] {
  if (!raw) return [];
  const out: string[] = [];
  for (const part of String(raw).split(',')) {
    const id = part.trim();
    if (id && TAG_ID_RE.test(id) && !out.includes(id)) out.push(id);
  }
  return out;
}

/** `send_to` de conversion valide, sinon chaîne vide (conversion Ads désactivée). */
export function parseLeadSendTo(raw: string | undefined | null): string {
  const v = (raw ?? '').trim();
  return SEND_TO_RE.test(v) ? v : '';
}

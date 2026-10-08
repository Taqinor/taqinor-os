/**
 * Signature des demandes de rendez-vous relayées vers l'ERP (YBW54).
 *
 * Format du contrat (YBW50, `X-Signature`) : `t=<epoch secondes>,v1=<hex>` où
 * `<hex>` = HMAC-SHA256(secret, `"<t>." + corps brut`) — la sémantique de
 * `apps.publicapi.delivery.sign_payload` côté ERP. Web Crypto seulement
 * (Worker Cloudflare et Node 22 l'exposent tous deux) ; aucun secret journalisé.
 * Le vecteur doré du contrat est vérifié par `tests/rendezVousProxy.test.ts`.
 */

const encodeur = new TextEncoder();

function hex(octets: ArrayBuffer): string {
  return [...new Uint8Array(octets)].map((o) => o.toString(16).padStart(2, '0')).join('');
}

/** HMAC-SHA256 en hexadécimal. */
export async function hmacSha256Hex(secret: string, message: string): Promise<string> {
  const cle = await crypto.subtle.importKey('raw', encodeur.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', cle, encodeur.encode(message)));
}

/** Valeur de l'en-tête `X-Signature` pour `corps` (chaîne JSON EXACTE envoyée) à l'instant `t`. */
export async function signer(secret: string, corps: string, t: number): Promise<string> {
  const ts = Math.floor(t);
  return `t=${ts},v1=${await hmacSha256Hex(secret, `${ts}.${corps}`)}`;
}

/**
 * Socle commun des routes `src/pages/api/roof-*` (ENF19 : une seule copie). Volontairement
 * découplé de lib/lead (aucune plomberie de lead/CRM) : réponse de rejet cross-site propre à ces
 * routes (`error`, pas `detail`/`errors.origin`) et lecture tolérante d'un nombre (virgule FR).
 */
import { jsonResponse } from './apiJson';

export function crossSiteRejection(): Response {
  return jsonResponse({ ok: false, error: 'Requête refusée.' }, 403);
}

export function num(v: unknown): number {
  return typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(',', '.'));
}

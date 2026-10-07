import type { APIRoute } from 'astro';
import { traiterRapport } from '../../lib/clientError';

/**
 * Rapport d'erreurs du navigateur (YBW20) — `POST /api/client-error`.
 * Journal du Worker seulement, aucune donnée personnelle : voir src/lib/clientError.ts.
 */
export const prerender = false;

export const ALL: APIRoute = ({ request }) => traiterRapport(request);

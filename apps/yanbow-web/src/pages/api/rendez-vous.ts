import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { dependancesWorker, traiterDemande, type EnvRdv } from '../../lib/rdv/forward';

/**
 * Demande de rendez-vous (YBW54) — `POST /api/rendez-vous`, même origine.
 * Toute la logique (garde d'origine, limite, pot de miel, validation du
 * registre, envoi signé en arrière-plan) vit dans `src/lib/rdv/forward.ts` ;
 * cette route ne branche que l'exécution Cloudflare (`env`, `waitUntil`).
 */
export const prerender = false;

export const ALL: APIRoute = ({ request }) => {
  const waitUntil = typeof cf.waitUntil === 'function' ? (p: Promise<unknown>) => cf.waitUntil(p) : undefined;
  return traiterDemande(request, dependancesWorker((cf.env ?? {}) as EnvRdv, waitUntil));
};
